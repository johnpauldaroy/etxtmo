from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import Template, User
from app.schemas import TemplateCreate, TemplateOut, TemplateUpdate
from app.services.audit import record_audit_event

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
def list_templates(
    branch_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TemplateOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(Template).where(Template.branch_id == branch_id, Template.deleted_at.is_(None)).order_by(Template.created_at.desc()),
    ).scalars()
    return [TemplateOut.model_validate(row) for row in rows]


@router.post("", response_model=TemplateOut)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateOut:
    assert_branch_access(db, current_user, payload.branch_id)
    existing = db.execute(
        select(Template.id).where(Template.branch_id == payload.branch_id, Template.name == payload.name),
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name already exists")
    tpl = Template(**payload.model_dump())
    db.add(tpl)
    db.flush()
    record_audit_event(
        db,
        action="template_created",
        entity_type="template",
        entity_id=str(tpl.id),
        user_id=current_user.id,
        branch_id=tpl.branch_id,
    )
    db.commit()
    db.refresh(tpl)
    return TemplateOut.model_validate(tpl)


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateOut:
    tpl = db.get(Template, template_id)
    if tpl is None or tpl.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    assert_branch_access(db, current_user, tpl.branch_id)

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        name = (updates["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name is required")
        duplicate = db.execute(
            select(Template.id).where(
                Template.branch_id == tpl.branch_id,
                Template.name == name,
                Template.id != tpl.id,
                Template.deleted_at.is_(None),
            ),
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name already exists")
        updates["name"] = name
    if "body" in updates:
        body = (updates["body"] or "").strip()
        if not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message body is required")
        updates["body"] = body

    for field, value in updates.items():
        setattr(tpl, field, value)
    db.flush()
    record_audit_event(
        db,
        action="template_updated",
        entity_type="template",
        entity_id=str(tpl.id),
        user_id=current_user.id,
        branch_id=tpl.branch_id,
        payload={"updated_fields": sorted(updates)},
    )
    db.commit()
    db.refresh(tpl)
    return TemplateOut.model_validate(tpl)


@router.delete("/{template_id}")
def delete_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    tpl = db.get(Template, template_id)
    if tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    assert_branch_access(db, current_user, tpl.branch_id)
    tpl.deleted_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db,
        action="template_soft_deleted",
        entity_type="template",
        entity_id=str(tpl.id),
        user_id=current_user.id,
        branch_id=tpl.branch_id,
    )
    db.commit()
    return {"status": "deleted"}
