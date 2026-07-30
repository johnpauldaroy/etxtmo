from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.admin import update_user
from app.api.routes.auth import create_user
from app.core.deps import user_has_branch_access
from app.core.security import verify_password
from app.models import UserBranch
from app.schemas import UserCreate, UserUpdate


def test_branch_access_scope(seeded_access, db_session):
    user = seeded_access["user"]
    superuser = seeded_access["superuser"]
    branch_a = seeded_access["branch_a"]
    branch_b = seeded_access["branch_b"]

    assert user_has_branch_access(db_session, user, branch_a.id) is True
    assert user_has_branch_access(db_session, user, branch_b.id) is False
    assert user_has_branch_access(db_session, superuser, branch_a.id) is True
    assert user_has_branch_access(db_session, superuser, branch_b.id) is True


def test_standard_user_creation_assigns_selected_branch(seeded_access, db_session):
    superuser = seeded_access["superuser"]
    branch = seeded_access["branch_b"]

    created = create_user(
        UserCreate(
            email="new.user@example.com",
            username="new.user",
            full_name="New User",
            password="temporary-password",
            is_superuser=False,
            branch_id=branch.id,
        ),
        db_session,
        superuser,
    )

    assignment = db_session.execute(
        select(UserBranch).where(UserBranch.user_id == created.id, UserBranch.branch_id == branch.id),
    ).scalar_one()
    assert assignment.role_id is None


def test_standard_user_creation_requires_branch(seeded_access, db_session):
    with pytest.raises(HTTPException) as exc_info:
        create_user(
            UserCreate(
                email="unassigned@example.com",
                username="unassigned",
                full_name="Unassigned User",
                password="temporary-password",
                is_superuser=False,
            ),
            db_session,
            seeded_access["superuser"],
        )

    assert exc_info.value.status_code == 400


def test_superuser_can_edit_account_details_and_password(seeded_access, db_session):
    user = seeded_access["user"]

    updated = update_user(
        user.id,
        UserUpdate(
            email="updated.branch@example.com",
            username="updated-branch",
            full_name="Updated Branch User",
            is_active=False,
            is_superuser=False,
            password="new-password",
        ),
        db_session,
        seeded_access["superuser"],
    )

    assert updated.email == "updated.branch@example.com"
    assert updated.username == "updated-branch"
    assert updated.full_name == "Updated Branch User"
    assert updated.is_active is False
    assert verify_password("new-password", user.password_hash)


def test_last_active_superuser_cannot_be_deactivated_or_demoted(seeded_access, db_session):
    superuser = seeded_access["superuser"]

    with pytest.raises(HTTPException) as exc_info:
        update_user(
            superuser.id,
            UserUpdate(
                email=superuser.email,
                username=superuser.username,
                full_name=superuser.full_name,
                is_active=False,
                is_superuser=True,
            ),
            db_session,
            superuser,
        )

    assert exc_info.value.status_code == 400
    assert "last active superuser" in exc_info.value.detail.lower()


def test_standard_user_cannot_edit_accounts(seeded_access, db_session):
    user = seeded_access["user"]
    superuser = seeded_access["superuser"]

    with pytest.raises(HTTPException) as exc_info:
        update_user(
            superuser.id,
            UserUpdate(
                email=superuser.email,
                username=superuser.username,
                full_name=superuser.full_name,
                is_active=True,
                is_superuser=True,
            ),
            db_session,
            user,
        )

    assert exc_info.value.status_code == 403
