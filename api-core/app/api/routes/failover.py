from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_superuser, get_current_user
from app.models import (
    Branch,
    CampaignRecipient,
    FailoverPolicy,
    FailoverRoute,
    MessageQueue,
    QueueStatus,
    RecipientStatus,
    User,
)
from app.schemas import (
    FailoverPolicyOut,
    FailoverPolicyUpsert,
    FailoverRouteCreate,
    FailoverRouteOut,
    FailoverStatusOut,
)
from app.services.audit import record_audit_event
from app.services.queue import healthy_modem_count
from app.services.queue import now_utc

router = APIRouter(prefix="/failover", tags=["failover"])


def _default_policy(branch_id: uuid.UUID) -> FailoverPolicyOut:
    return FailoverPolicyOut(
        id=None,
        branch_id=branch_id,
        enabled=False,
        offline_after_seconds=90,
        failover_delay_seconds=60,
        claim_timeout_seconds=120,
    )


def _route_out(db: Session, route: FailoverRoute) -> FailoverRouteOut:
    branch = db.get(Branch, route.backup_branch_id)
    return FailoverRouteOut(
        id=route.id,
        source_branch_id=route.source_branch_id,
        backup_branch_id=route.backup_branch_id,
        priority=route.priority,
        enabled=route.enabled,
        backup_branch_code=branch.code if branch else None,
        backup_branch_name=branch.name if branch else None,
    )


@router.get("/{branch_id}", response_model=FailoverStatusOut)
def get_failover_status(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FailoverStatusOut:
    assert_branch_access(db, current_user, branch_id)
    policy = db.execute(
        select(FailoverPolicy).where(FailoverPolicy.branch_id == branch_id),
    ).scalar_one_or_none()
    policy_out = FailoverPolicyOut.model_validate(policy) if policy else _default_policy(branch_id)
    routes = db.execute(
        select(FailoverRoute)
        .where(FailoverRoute.source_branch_id == branch_id)
        .order_by(FailoverRoute.priority.asc(), FailoverRoute.created_at.asc()),
    ).scalars().all()
    healthy_count = healthy_modem_count(db, branch_id, policy_out.offline_after_seconds)
    pending = db.execute(
        select(func.count(MessageQueue.id)).where(
            MessageQueue.branch_id == branch_id,
            MessageQueue.status.in_([QueueStatus.pending, QueueStatus.sending]),
        ),
    ).scalar_one()
    failover_messages = db.execute(
        select(func.count(MessageQueue.id)).where(
            MessageQueue.branch_id == branch_id,
            MessageQueue.execution_branch_id.is_not(None),
            MessageQueue.execution_branch_id != branch_id,
            MessageQueue.status == QueueStatus.sending,
        ),
    ).scalar_one()
    backup_ready = any(
        route.enabled
        and healthy_modem_count(db, route.backup_branch_id, policy_out.offline_after_seconds) > 0
        for route in routes
    )
    return FailoverStatusOut(
        policy=policy_out,
        routes=[_route_out(db, route) for route in routes],
        local_modems_healthy=healthy_count > 0,
        healthy_local_modems=healthy_count,
        failover_active=bool(policy_out.enabled and healthy_count == 0 and backup_ready),
        pending_messages=pending,
        failover_messages=failover_messages,
    )


@router.put("/policy/{branch_id}", response_model=FailoverPolicyOut)
def upsert_failover_policy(
    branch_id: uuid.UUID,
    payload: FailoverPolicyUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> FailoverPolicyOut:
    if branch_id != payload.branch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Branch mismatch")
    if db.get(Branch, branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    policy = db.execute(
        select(FailoverPolicy).where(FailoverPolicy.branch_id == branch_id),
    ).scalar_one_or_none()
    if policy is None:
        policy = FailoverPolicy(**payload.model_dump())
        db.add(policy)
    else:
        for key, value in payload.model_dump(exclude={"branch_id"}).items():
            setattr(policy, key, value)
    db.flush()
    record_audit_event(
        db,
        action="failover_policy_updated",
        entity_type="failover_policy",
        entity_id=str(policy.id),
        user_id=current_user.id,
        branch_id=branch_id,
        payload=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(policy)
    return FailoverPolicyOut.model_validate(policy)


@router.post("/routes", response_model=FailoverRouteOut)
def create_failover_route(
    payload: FailoverRouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> FailoverRouteOut:
    if payload.source_branch_id == payload.backup_branch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Backup branch must be different")
    if db.get(Branch, payload.source_branch_id) is None or db.get(Branch, payload.backup_branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    route = db.execute(
        select(FailoverRoute).where(
            FailoverRoute.source_branch_id == payload.source_branch_id,
            FailoverRoute.backup_branch_id == payload.backup_branch_id,
        ),
    ).scalar_one_or_none()
    if route is None:
        route = FailoverRoute(**payload.model_dump())
        db.add(route)
    else:
        route.priority = payload.priority
        route.enabled = payload.enabled
    db.flush()
    record_audit_event(
        db,
        action="failover_route_saved",
        entity_type="failover_route",
        entity_id=str(route.id),
        user_id=current_user.id,
        branch_id=payload.source_branch_id,
        payload=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(route)
    return _route_out(db, route)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_failover_route(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> None:
    route = db.get(FailoverRoute, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failover route not found")
    source_branch_id = route.source_branch_id
    db.delete(route)
    record_audit_event(
        db,
        action="failover_route_deleted",
        entity_type="failover_route",
        entity_id=str(route_id),
        user_id=current_user.id,
        branch_id=source_branch_id,
    )
    db.commit()


@router.post("/{branch_id}/recover-stale")
def recover_stale_deliveries(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> dict[str, int]:
    policy = db.execute(
        select(FailoverPolicy).where(FailoverPolicy.branch_id == branch_id),
    ).scalar_one_or_none()
    timeout_seconds = policy.claim_timeout_seconds if policy else 120
    from datetime import timedelta

    cutoff = now_utc() - timedelta(seconds=timeout_seconds)
    rows = db.execute(
        select(MessageQueue).where(
            MessageQueue.branch_id == branch_id,
            MessageQueue.status == QueueStatus.sending,
            MessageQueue.locked_at.is_not(None),
            MessageQueue.locked_at < cutoff,
        ),
    ).scalars().all()
    for row in rows:
        row.status = QueueStatus.failed
        row.error_message = "Delivery status unknown after modem claim timed out; review before retrying"
        recipient = db.get(CampaignRecipient, row.campaign_recipient_id)
        if recipient:
            recipient.status = RecipientStatus.failed
    record_audit_event(
        db,
        action="stale_queue_marked_for_review",
        entity_type="message_queue",
        user_id=current_user.id,
        branch_id=branch_id,
        payload={"count": len(rows), "timeout_seconds": timeout_seconds},
    )
    db.commit()
    return {"recovered": len(rows)}
