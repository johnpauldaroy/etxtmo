from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import Campaign, MessageLog, MessageQueue, QueueStatus, User
from app.schemas import QueueItemOut
from app.services.audit import record_audit_event

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
    db.flush()
    record_audit_event(
        db,
        action="queue_retry_requested",
        entity_type="message_queue",
        entity_id=str(item.id),
        user_id=current_user.id,
        branch_id=item.branch_id,
    )
    db.commit()
    return {"status": "pending"}
