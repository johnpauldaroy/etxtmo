from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_optional_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import Branch, User, UserBranch
from app.schemas import LoginRequest, PasswordReset, Token, UserCreate, UserOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    user = db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.username)),
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    token = create_access_token(user.id)
    return Token(access_token=token)


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> UserOut:
    existing_count = db.execute(select(func.count(User.id))).scalar_one()
    if existing_count > 0 and (current_user is None or not current_user.is_superuser):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superusers can create users")

    exists = db.execute(
        select(User.id).where((User.email == payload.email) | (User.username == payload.username)),
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    branch = db.get(Branch, payload.branch_id) if payload.branch_id else None
    if payload.branch_id and branch is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected branch does not exist")
    if existing_count > 0 and not payload.is_superuser and branch is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A branch is required for standard users")

    user = User(
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_superuser=payload.is_superuser if existing_count > 0 else True,
    )
    db.add(user)
    db.flush()
    if branch:
        assignment = UserBranch(user_id=user.id, branch_id=branch.id, role_id=None)
        db.add(assignment)
        db.flush()
        record_audit_event(
            db,
            action="user_branch_assigned",
            entity_type="user_branch",
            entity_id=str(assignment.id),
            user_id=current_user.id if current_user else None,
            branch_id=branch.id,
            payload={"user_id": str(user.id), "role_id": None},
        )
    record_audit_event(
        db,
        action="user_created",
        entity_type="user",
        entity_id=str(user.id),
        user_id=current_user.id if current_user else None,
        payload={"email": user.email, "username": user.username},
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


@router.put("/users/{user_id}/password", response_model=UserOut)
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot reset another user's password")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = get_password_hash(payload.password)
    db.flush()
    record_audit_event(
        db,
        action="password_reset",
        entity_type="user",
        entity_id=str(user.id),
        user_id=current_user.id,
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
