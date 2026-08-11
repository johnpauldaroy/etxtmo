from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_superuser, get_current_user
from app.models import (
    Branch,
    Campaign,
    CampaignRecipient,
    CampaignStatus,
    MessageLog,
    MessageQueue,
    QueueStatus,
    RecipientStatus,
    User,
)
from app.schemas import QueueItemOut, QueueReassignBranchRequest
from app.services.audit import record_audit_event
from app.services.queue import recalculate_campaign_status, stale_lock_cutoff

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("", response_model=list[QueueItemOut])
def list_queue(
    branch_id: uuid.UUID = Query(...),
    status_filter: QueueStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QueueItemOut]:
    assert_branch_access(db, current_user, branch_id)
    sent_at = (
        select(func.max(MessageLog.created_at))
        .where(
            MessageLog.queue_id == MessageQueue.id,
            MessageLog.event_type == "queue_result",
            MessageLog.event_status == QueueStatus.sent.value,
        )
        .correlate(MessageQueue)
        .scalar_subquery()
    )
    stmt = (
        select(MessageQueue, Campaign.name, sent_at.label("sent_at"))
        .join(Campaign, Campaign.id == MessageQueue.campaign_id)
        .where(MessageQueue.branch_id == branch_id)
        .order_by(MessageQueue.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(MessageQueue.status == status_filter)
    rows = db.execute(stmt.limit(500)).all()
    return [
        QueueItemOut.model_validate(item).model_copy(
            update={"campaign_name": campaign_name, "sent_at": item_sent_at},
        )
        for item, campaign_name, item_sent_at in rows
    ]


@router.post("/{queue_id}/retry")
def retry_failed_message(
    queue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    item = db.get(MessageQueue, queue_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    assert_branch_access(db, current_user, item.branch_id)
    if item.status != QueueStatus.failed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed messages can be retried")
    item.status = QueueStatus.pending
    item.next_attempt_at = datetime.now(timezone.utc)
    item.error_message = None
    item.modem_id = None
    item.execution_branch_id = None
    item.failover_route_id = None
    item.locked_at = None
    recipient = db.get(CampaignRecipient, item.campaign_recipient_id)
    if recipient is not None:
        recipient.status = RecipientStatus.pending
    db.flush()
    record_audit_event(
        db,
        action="queue_retry_requested",
        entity_type="message_queue",
        entity_id=str(item.id),
        user_id=current_user.id,
        branch_id=item.branch_id,
    )
    recalculate_campaign_status(db, item.campaign_id)
    db.commit()
    return {"status": "pending"}


@router.post("/campaigns/{campaign_id}/reassign-branch")
def reassign_campaign_branch(
    campaign_id: uuid.UUID,
    payload: QueueReassignBranchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> dict[str, int]:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    target_branch = db.get(Branch, payload.target_branch_id)
    if target_branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target branch not found")
    if payload.target_branch_id == campaign.branch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign already routes through this branch")

    items = db.execute(
        select(MessageQueue).where(
            MessageQueue.campaign_id == campaign_id,
            MessageQueue.status.in_([QueueStatus.pending, QueueStatus.failed]),
        ),
    ).scalars().all()

    now = datetime.now(timezone.utc)
    for item in items:
        item.status = QueueStatus.pending
        item.next_attempt_at = now
        item.error_message = None
        item.modem_id = None
        item.execution_branch_id = None
        item.failover_route_id = None
        item.locked_at = None
        item.forced_execution_branch_id = payload.target_branch_id
        recipient = db.get(CampaignRecipient, item.campaign_recipient_id)
        if recipient is not None:
            recipient.status = RecipientStatus.pending

    if items:
        db.flush()
        record_audit_event(
            db,
            action="queue_campaign_reassigned",
            entity_type="campaign",
            entity_id=str(campaign_id),
            user_id=current_user.id,
            branch_id=campaign.branch_id,
            payload={"reassigned": len(items), "target_branch_id": str(payload.target_branch_id)},
        )
        recalculate_campaign_status(db, campaign_id)
        db.commit()
    return {"reassigned": len(items)}


@router.post("/campaigns/{campaign_id}/cancel")
def cancel_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | str]:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    assert_branch_access(db, current_user, campaign.branch_id)

    # Queue claims use row locks too. Locked rows are already being handed to a
    # modem, so skip them instead of claiming that they were cancelled.
    #
    # Stale claims are the exception: only an agent reporting back moves a row
    # out of `sending`, so one whose agent died stays there indefinitely and is
    # not cancellable by any other path. Past the timeout it is no longer
    # plausibly in flight, so an operator may stop it.
    cutoff = stale_lock_cutoff(get_settings().queue_stale_lock_seconds)
    stoppable = or_(
        MessageQueue.status == QueueStatus.pending,
        and_(
            MessageQueue.status == QueueStatus.sending,
            MessageQueue.locked_at.is_not(None),
            MessageQueue.locked_at < cutoff,
        ),
    )
    items = db.execute(
        select(MessageQueue)
        .where(MessageQueue.campaign_id == campaign_id, stoppable)
        .with_for_update(skip_locked=True),
    ).scalars().all()

    for item in items:
        item.status = QueueStatus.cancelled
        item.error_message = "Cancelled by user"
        item.locked_at = None
        item.modem_id = None
        item.execution_branch_id = None
        item.failover_route_id = None
        item.forced_execution_branch_id = None
        recipient = db.get(CampaignRecipient, item.campaign_recipient_id)
        if recipient is not None:
            recipient.status = RecipientStatus.cancelled
        db.add(
            MessageLog(
                branch_id=item.branch_id,
                campaign_id=item.campaign_id,
                queue_id=item.id,
                recipient_phone=recipient.phone_number if recipient else "",
                event_type="queue_cancelled",
                event_status=QueueStatus.cancelled.value,
                details_json={"reason": "Cancelled by user"},
            ),
        )

    # Counted after the cancellations above are in the session so the rows just
    # stopped are not also reported as in flight. Only genuinely live claims --
    # those still inside the timeout -- are beyond recall.
    db.flush()
    in_flight = db.execute(
        select(func.count(MessageQueue.id)).where(
            MessageQueue.campaign_id == campaign_id,
            MessageQueue.status == QueueStatus.sending,
        ),
    ).scalar_one()
    if items:
        campaign.status = CampaignStatus.cancelled

    record_audit_event(
        db,
        action="queue_campaign_cancelled",
        entity_type="campaign",
        entity_id=str(campaign_id),
        user_id=current_user.id,
        branch_id=campaign.branch_id,
        payload={"cancelled": len(items), "in_flight": in_flight},
    )
    db.commit()
    return {"status": campaign.status.value, "cancelled": len(items), "in_flight": in_flight}


@router.post("/campaigns/{campaign_id}/retry-failed")
def retry_failed_for_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    assert_branch_access(db, current_user, campaign.branch_id)

    items = db.execute(
        select(MessageQueue).where(
            MessageQueue.campaign_id == campaign_id,
            MessageQueue.status == QueueStatus.failed,
        ),
    ).scalars().all()

    now = datetime.now(timezone.utc)
    for item in items:
        item.status = QueueStatus.pending
        item.next_attempt_at = now
        item.error_message = None
        item.modem_id = None
        item.execution_branch_id = None
        item.failover_route_id = None
        item.locked_at = None
        recipient = db.get(CampaignRecipient, item.campaign_recipient_id)
        if recipient is not None:
            recipient.status = RecipientStatus.pending

    if items:
        db.flush()
        record_audit_event(
            db,
            action="queue_bulk_retry_requested",
            entity_type="campaign",
            entity_id=str(campaign_id),
            user_id=current_user.id,
            branch_id=campaign.branch_id,
            payload={"retried": len(items)},
        )
        recalculate_campaign_status(db, campaign_id)
        db.commit()
    return {"retried": len(items)}
