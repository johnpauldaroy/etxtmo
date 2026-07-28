from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import ScheduleRule, Template, User
from app.schemas import RuleCreate, RuleOut, RuleUpdate
from app.services.audit import record_audit_event
from app.services.scheduler import evaluate_rules_once

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
def list_rules(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RuleOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(select(ScheduleRule).where(ScheduleRule.branch_id == branch_id)).scalars()
    return [RuleOut.model_validate(row) for row in rows]


@router.post("", response_model=RuleOut)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuleOut:
    assert_branch_access(db, current_user, payload.branch_id)
    if payload.template_id:
        template = db.get(Template, payload.template_id)
        if template is None or template.deleted_at is not None or template.branch_id != payload.branch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected template is not available for this branch")
    elif not (payload.message_body or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select a template or enter a message")
    rule = ScheduleRule(**payload.model_dump(), created_by=current_user.id)
    db.add(rule)
    db.flush()
    record_audit_event(
        db,
        action="schedule_rule_created",
        entity_type="schedule_rule",
        entity_id=str(rule.id),
        user_id=current_user.id,
        branch_id=rule.branch_id,
    )
    db.commit()
    db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: uuid.UUID,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuleOut:
    rule = db.get(ScheduleRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    assert_branch_access(db, current_user, rule.branch_id)

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        name = (updates["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rule name is required")
        updates["name"] = name

    template_id = updates.get("template_id", rule.template_id)
    message_body = updates.get("message_body", rule.message_body)
    if template_id:
        template = db.get(Template, template_id)
        if template is None or template.deleted_at is not None or template.branch_id != rule.branch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected template is not available for this branch")
    elif not (message_body or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select a template or enter a message")

    for field, value in updates.items():
        setattr(rule, field, value)
    db.flush()
    record_audit_event(
        db,
        action="schedule_rule_updated",
        entity_type="schedule_rule",
        entity_id=str(rule.id),
        user_id=current_user.id,
        branch_id=rule.branch_id,
    )
    db.commit()
    db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.delete("/{rule_id}")
def disable_rule(
    rule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    rule = db.get(ScheduleRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    assert_branch_access(db, current_user, rule.branch_id)
    rule.is_active = False
    db.flush()
    record_audit_event(
        db,
        action="schedule_rule_disabled",
        entity_type="schedule_rule",
        entity_id=str(rule.id),
        user_id=current_user.id,
        branch_id=rule.branch_id,
    )
    db.commit()
    return {"status": "disabled"}


@router.post("/{rule_id}/enable")
def enable_rule(
    rule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    rule = db.get(ScheduleRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    assert_branch_access(db, current_user, rule.branch_id)
    rule.is_active = True
    db.flush()
    record_audit_event(
        db,
        action="schedule_rule_enabled",
        entity_type="schedule_rule",
        entity_id=str(rule.id),
        user_id=current_user.id,
        branch_id=rule.branch_id,
    )
    db.commit()
    return {"status": "active"}


@router.post("/evaluate")
def evaluate_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")
    generated = evaluate_rules_once(db, datetime.now(timezone.utc))
    db.commit()
    return {"generated_campaigns": generated}
