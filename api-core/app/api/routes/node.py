from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import (
    CampaignRecipient,
    IncomingMessage,
    MessageQueue,
    Modem,
    ModemStatus,
    NodeHeartbeat,
    NodeSyncEvent,
    QueueStatus,
    User,
)
from app.schemas import (
    HeartbeatRequest,
    IncomingMessageCreate,
    ModemOut,
    ModemRegister,
    NodeEventRequest,
    QueueItemOut,
    QueuePullRequest,
    QueueResultRequest,
)
from app.services.audit import record_audit_event
from app.services.queue import apply_queue_results, effective_modem_status, pull_pending_queue_items

router = APIRouter(prefix="/node", tags=["node"])


@router.post("/register-modem", response_model=ModemOut)
def register_modem(
    payload: ModemRegister,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ModemOut:
    assert_branch_access(db, current_user, payload.branch_id)
    existing = None
    if payload.imei:
        existing = db.execute(select(Modem).where(Modem.imei == payload.imei)).scalar_one_or_none()
    if existing is None:
        # No IMEI configured (common -- it's optional): fall back to
        # (branch_id, node_name) so restarting branch-agent reconciles into
        # the same row instead of registering a new modem every time. Use
        # the most recently updated match rather than scalar_one_or_none(),
        # since duplicate rows can already exist from before this fallback
        # existed -- picking one deterministically beats crashing the whole
        # registration on MultipleResultsFound.
        existing = db.execute(
            select(Modem)
            .where(
                Modem.branch_id == payload.branch_id,
                Modem.node_name == payload.node_name,
                Modem.imei.is_(None),
            )
            .order_by(Modem.updated_at.desc())
            .limit(1),
        ).scalar_one_or_none()
    if existing is None:
        modem = Modem(**payload.model_dump(), status=ModemStatus.online, last_seen_at=datetime.now(timezone.utc))
        db.add(modem)
    else:
        modem = existing
        if modem.branch_id != payload.branch_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This modem IMEI is already registered to another branch",
            )
        modem.node_name = payload.node_name
        modem.name = payload.name
        modem.port = payload.port
        modem.status = ModemStatus.online
        modem.last_seen_at = datetime.now(timezone.utc)

    db.flush()
    record_audit_event(
        db,
        action="modem_registered",
        entity_type="modem",
        entity_id=str(modem.id),
        user_id=current_user.id,
        branch_id=payload.branch_id,
    )
    db.commit()
    db.refresh(modem)
    return ModemOut.model_validate(modem)


@router.post("/heartbeat")
def heartbeat(
    payload: HeartbeatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    assert_branch_access(db, current_user, payload.branch_id)
    beat = NodeHeartbeat(
        branch_id=payload.branch_id,
        node_name=payload.node_name,
        status=payload.status,
        payload=payload.payload,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(beat)
    modem_rows = db.execute(
        select(Modem).where(Modem.branch_id == payload.branch_id, Modem.node_name == payload.node_name),
    ).scalars()
    for modem in modem_rows:
        modem.status = ModemStatus.online if payload.status.lower() == "online" else ModemStatus.error
        modem.last_seen_at = beat.last_seen_at
    db.commit()
    return {"status": "ok"}


@router.post("/pull-jobs", response_model=list[QueueItemOut])
def pull_jobs(
    payload: QueuePullRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QueueItemOut]:
    assert_branch_access(db, current_user, payload.branch_id)
    if payload.modem_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A registered modem is required")
    modem = db.get(Modem, payload.modem_id)
    if modem is None or modem.branch_id != payload.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Modem does not belong to this branch")
    # Defense in depth for older agents: an unhealthy execution modem must
    # never claim local or failover work. A healthy backup agent will claim
    # eligible pending messages through pull_pending_queue_items instead.
    if effective_modem_status(modem) != ModemStatus.online:
        return []
    rows = pull_pending_queue_items(
        db,
        execution_branch_id=payload.branch_id,
        modem_id=payload.modem_id,
        limit=payload.limit,
    )
    response: list[QueueItemOut] = []
    for row in rows:
        recipient = db.execute(
            select(CampaignRecipient).where(CampaignRecipient.id == row.campaign_recipient_id),
        ).scalar_one_or_none()
        response.append(
            QueueItemOut(
                id=row.id,
                branch_id=row.branch_id,
                campaign_id=row.campaign_id,
                campaign_recipient_id=row.campaign_recipient_id,
                status=row.status,
                attempts=row.attempts,
                max_attempts=row.max_attempts,
                next_attempt_at=row.next_attempt_at,
                external_message_id=row.external_message_id,
                error_message=row.error_message,
                modem_id=row.modem_id,
                execution_branch_id=row.execution_branch_id,
                failover_route_id=row.failover_route_id,
                phone_number=recipient.phone_number if recipient else None,
                message_body=recipient.message_body if recipient else None,
            ),
        )
    db.commit()
    return response


@router.post("/queue-results")
def queue_results(
    payload: QueueResultRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    assert_branch_access(db, current_user, payload.branch_id)
    modem = db.get(Modem, payload.modem_id)
    if modem is None or modem.branch_id != payload.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Modem does not belong to this branch")
    mapped = [item.model_dump() for item in payload.items]
    result = apply_queue_results(
        db,
        execution_branch_id=payload.branch_id,
        modem_id=payload.modem_id,
        items=mapped,
    )
    db.add(
        NodeSyncEvent(
            branch_id=payload.branch_id,
            node_name=payload.node_name,
            event_type="queue_results",
            payload={"count": len(mapped), **result},
        ),
    )
    db.commit()
    return result


@router.post("/incoming")
def upload_incoming(
    payload: IncomingMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    assert_branch_access(db, current_user, payload.branch_id)
    msg = IncomingMessage(**payload.model_dump(), processed=False)
    db.add(msg)
    db.flush()
    record_audit_event(
        db,
        action="incoming_uploaded_from_node",
        entity_type="incoming_message",
        entity_id=str(msg.id),
        user_id=current_user.id,
        branch_id=payload.branch_id,
    )
    db.commit()
    return {"status": "accepted"}


@router.post("/event")
def upload_event(
    payload: NodeEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    assert_branch_access(db, current_user, payload.branch_id)
    db.add(
        NodeSyncEvent(
            branch_id=payload.branch_id,
            node_name=payload.node_name,
            event_type=payload.event_type,
            payload=payload.payload,
        ),
    )
    db.commit()
    return {"status": "ok"}


@router.post("/mark-modem-offline")
def mark_modem_offline(
    modem_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    modem = db.get(Modem, modem_id)
    if modem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modem not found")
    assert_branch_access(db, current_user, modem.branch_id)
    modem.status = ModemStatus.offline
    modem.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "offline"}


@router.get("/dead-letter")
def dead_letter(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, str]]]:
    assert_branch_access(db, current_user, branch_id)
    failed_rows = db.execute(
        select(MessageQueue).where(MessageQueue.branch_id == branch_id, MessageQueue.status == QueueStatus.failed).limit(500),
    ).scalars()
    return {
        "items": [
            {
                "id": str(row.id),
                "campaign_id": str(row.campaign_id),
                "recipient_id": str(row.campaign_recipient_id),
                "error_message": row.error_message or "",
            }
            for row in failed_rows
        ],
    }
