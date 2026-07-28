from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, verify_api_key
from app.models import ApiKey, Role, User, UserBranch

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_api_key_context(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")

    prefix = x_api_key[:12]
    candidates = db.execute(
        select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True)),
    ).scalars().all()

    for candidate in candidates:
        if verify_api_key(x_api_key, candidate.key_hash):
            candidate.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return candidate

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive API key")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


def get_optional_current_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(optional_oauth2_scheme),
) -> User | None:
    if not token:
        return None
    payload = decode_token(token)
    if payload is None or "sub" not in payload:
        return None
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required")
    return current_user


def get_accessible_branch_ids(db: Session, user: User) -> set[uuid.UUID]:
    if user.is_superuser:
        branch_ids = db.execute(select(UserBranch.branch_id)).scalars().all()
        return set(branch_ids)
    branch_ids = db.execute(select(UserBranch.branch_id).where(UserBranch.user_id == user.id)).scalars().all()
    return set(branch_ids)


def user_has_branch_access(db: Session, user: User, branch_id: uuid.UUID) -> bool:
    if user.is_superuser:
        return True
    stmt = select(UserBranch.id).where(UserBranch.user_id == user.id, UserBranch.branch_id == branch_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def assert_branch_access(db: Session, user: User, branch_id: uuid.UUID) -> None:
    if not user_has_branch_access(db, user, branch_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch access denied")


def user_has_role(db: Session, user_id: uuid.UUID, branch_id: uuid.UUID, role_name: str) -> bool:
    stmt = (
        select(Role.name)
        .join(UserBranch, UserBranch.role_id == Role.id)
        .where(UserBranch.user_id == user_id, UserBranch.branch_id == branch_id)
    )
    user_roles = {role for role in db.execute(stmt).scalars().all()}
    return role_name in user_roles
