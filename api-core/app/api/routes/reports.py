from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import Campaign, MessageQueue, QueueStatus, User, UserBranch
from app.schemas import ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/delivery-trend")
def delivery_trend(
    branch_id: uuid.UUID = Query(...),
    days: int = Query(default=7, ge=2, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str | int]]:
    assert_branch_access(db, current_user, branch_id)
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    date_bucket = func.date(MessageQueue.updated_at)
    rows = db.execute(
        select(date_bucket, MessageQueue.status, func.count(MessageQueue.id))
        .where(
            MessageQueue.branch_id == branch_id,
            MessageQueue.status.in_([QueueStatus.sent, QueueStatus.failed]),
            MessageQueue.updated_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        .group_by(date_bucket, MessageQueue.status),
    ).all()

    buckets = {
        (start_date + timedelta(days=offset)).isoformat(): {"sent": 0, "failed": 0}
        for offset in range(days)
    }
    for day, queue_status, count in rows:
        day_key = str(day)
        if day_key in buckets:
            buckets[day_key][queue_status.value] = count

    return [
        {"date": day, "sent": totals["sent"], "failed": totals["failed"]}
        for day, totals in buckets.items()
    ]


@router.get("/summary", response_model=ReportSummary)
def summary(
    branch_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportSummary:
    if branch_id:
        assert_branch_access(db, current_user, branch_id)
    elif not current_user.is_superuser:
        branch_id = db.execute(
            select(UserBranch.branch_id).where(UserBranch.user_id == current_user.id).limit(1),
        ).scalar_one_or_none()
        if not branch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No branch assigned to user")

    campaign_stmt = select(func.count(Campaign.id))
    sent_stmt = select(func.count(MessageQueue.id)).where(MessageQueue.status == QueueStatus.sent)
    failed_stmt = select(func.count(MessageQueue.id)).where(MessageQueue.status == QueueStatus.failed)
    pending_stmt = select(func.count(MessageQueue.id)).where(MessageQueue.status.in_([QueueStatus.pending, QueueStatus.sending]))

    if branch_id:
        campaign_stmt = campaign_stmt.where(Campaign.branch_id == branch_id)
        sent_stmt = sent_stmt.where(MessageQueue.branch_id == branch_id)
        failed_stmt = failed_stmt.where(MessageQueue.branch_id == branch_id)
        pending_stmt = pending_stmt.where(MessageQueue.branch_id == branch_id)

    return ReportSummary(
        branch_id=branch_id,
        campaigns_total=db.execute(campaign_stmt).scalar_one(),
        messages_sent=db.execute(sent_stmt).scalar_one(),
        messages_failed=db.execute(failed_stmt).scalar_one(),
        pending_queue=db.execute(pending_stmt).scalar_one(),
    )
