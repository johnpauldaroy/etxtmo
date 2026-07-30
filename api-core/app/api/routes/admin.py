from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_branch_access, get_current_user
from app.core.security import generate_api_key, get_password_hash
from app.models import ApiKey, Branch, Role, User, UserBranch
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    BranchCreate,
    BranchOut,
    RoleCreate,
    RoleOut,
    UserBranchAssign,
    UserOut,
    UserUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/branches", response_model=list[BranchOut])
def list_branches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BranchOut]:
    if current_user.is_superuser:
        branches = db.execute(select(Branch).order_by(Branch.name.asc())).scalars().all()
    else:
        branches = db.execute(
            select(Branch)
            .join(UserBranch, UserBranch.branch_id == Branch.id)
            .where(UserBranch.user_id == current_user.id),
        ).scalars()
    return [BranchOut.model_validate(branch) for branch in branches]


@router.post("/branches", response_model=BranchOut)
def create_branch(
    payload: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchOut:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")
    existing = db.execute(select(Branch.id).where(Branch.code == payload.code)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Branch code already exists")

    branch = Branch(code=payload.code, name=payload.name, timezone=payload.timezone)
    db.add(branch)
    db.flush()
    record_audit_event(
        db,
        action="branch_created",
        entity_type="branch",
        entity_id=str(branch.id),
        user_id=current_user.id,
        branch_id=branch.id,
        payload={"code": branch.code, "name": branch.name},
    )
    db.commit()
    db.refresh(branch)
    return BranchOut.model_validate(branch)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserOut]:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return [UserOut.model_validate(user) for user in users]


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    username = payload.username.strip()
    full_name = payload.full_name.strip()
    if not username or not full_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username and full name are required")

    duplicate = db.execute(
        select(User.id).where(
            User.id != user_id,
            (User.email == payload.email) | (User.username == username),
        ),
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username is already in use")

    removing_active_superuser = (
        user.is_superuser
        and user.is_active
        and (not payload.is_superuser or not payload.is_active)
    )
    if removing_active_superuser:
        active_superusers = db.execute(
            select(func.count(User.id)).where(User.is_superuser.is_(True), User.is_active.is_(True)),
        ).scalar_one()
        if active_superusers <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active superuser cannot be deactivated or changed to a standard user",
            )

    if not payload.is_superuser:
        has_branch = db.execute(
            select(UserBranch.id).where(UserBranch.user_id == user_id).limit(1),
        ).scalar_one_or_none()
        if has_branch is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assign at least one branch before changing this account to a standard user",
            )

    changed_fields: list[str] = []
    updates = {
        "email": str(payload.email),
        "username": username,
        "full_name": full_name,
        "is_active": payload.is_active,
        "is_superuser": payload.is_superuser,
    }
    for field, value in updates.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            changed_fields.append(field)
    if payload.password:
        user.password_hash = get_password_hash(payload.password)
        changed_fields.append("password")

    record_audit_event(
        db,
        action="user_updated",
        entity_type="user",
        entity_id=str(user.id),
        user_id=current_user.id,
        payload={"changed_fields": changed_fields},
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[RoleOut]:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")
    roles = db.execute(select(Role).order_by(Role.id.asc())).scalars().all()
    return [RoleOut.model_validate(role) for role in roles]


@router.post("/roles", response_model=RoleOut)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoleOut:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")
    existing = db.execute(select(Role.id).where(Role.name == payload.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")
    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    db.flush()
    record_audit_event(
        db,
        action="role_created",
        entity_type="role",
        entity_id=str(role.id),
        user_id=current_user.id,
        payload={"name": role.name},
    )
    db.commit()
    db.refresh(role)
    return RoleOut.model_validate(role)


@router.post("/user-branches")
def assign_user_branch(
    payload: UserBranchAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")

    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if db.get(Branch, payload.branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    link = db.execute(
        select(UserBranch).where(UserBranch.user_id == payload.user_id, UserBranch.branch_id == payload.branch_id),
    ).scalar_one_or_none()
    if link is None:
        link = UserBranch(user_id=payload.user_id, branch_id=payload.branch_id, role_id=payload.role_id)
        db.add(link)
    else:
        link.role_id = payload.role_id
    db.flush()
    record_audit_event(
        db,
        action="user_branch_assigned",
        entity_type="user_branch",
        entity_id=str(link.id),
        user_id=current_user.id,
        branch_id=payload.branch_id,
        payload={"user_id": str(payload.user_id), "role_id": payload.role_id},
    )
    db.commit()
    return {"status": "ok"}


@router.get("/branches/{branch_id}")
def get_branch_users(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, str | int | None]]]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(User, UserBranch.role_id)
        .join(UserBranch, UserBranch.user_id == User.id)
        .where(UserBranch.branch_id == branch_id),
    ).all()
    result = [
        {
            "user_id": str(row[0].id),
            "username": row[0].username,
            "email": row[0].email,
            "role_id": row[1],
        }
        for row in rows
    ]
    return {"users": result}


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ApiKeyOut]:
    assert_branch_access(db, current_user, branch_id)
    rows = db.execute(
        select(ApiKey).where(ApiKey.branch_id == branch_id).order_by(ApiKey.created_at.desc()),
    ).scalars()
    return [ApiKeyOut.model_validate(row) for row in rows]


@router.post("/api-keys", response_model=ApiKeyCreated)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyCreated:
    assert_branch_access(db, current_user, payload.branch_id)
    full_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        branch_id=payload.branch_id,
        label=payload.label,
        key_prefix=prefix,
        key_hash=key_hash,
        created_by=current_user.id,
    )
    db.add(api_key)
    db.flush()
    record_audit_event(
        db,
        action="api_key_created",
        entity_type="api_key",
        entity_id=str(api_key.id),
        user_id=current_user.id,
        branch_id=api_key.branch_id,
        payload={"label": api_key.label},
    )
    db.commit()
    db.refresh(api_key)
    return ApiKeyCreated(api_key=full_key, **ApiKeyOut.model_validate(api_key).model_dump())


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    api_key = db.get(ApiKey, key_id)
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    assert_branch_access(db, current_user, api_key.branch_id)
    api_key.is_active = False
    db.flush()
    record_audit_event(
        db,
        action="api_key_revoked",
        entity_type="api_key",
        entity_id=str(api_key.id),
        user_id=current_user.id,
        branch_id=api_key.branch_id,
    )
    db.commit()
    return {"status": "revoked"}
