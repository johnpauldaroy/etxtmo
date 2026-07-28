from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.models import AuditLog, User
from app.schemas import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    branch_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditLogOut]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1000)
    if branch_id:
        assert_branch_access(db, current_user, branch_id)
        stmt = stmt.where(AuditLog.branch_id == branch_id)
    elif not current_user.is_superuser:
        stmt = stmt.where(AuditLog.user_id == current_user.id)
    rows = db.execute(stmt).scalars().all()
    return [AuditLogOut.model_validate(row) for row in rows]

