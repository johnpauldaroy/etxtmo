from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.security import get_password_hash
from app.models import Branch, Role, User, UserBranch


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded_access(db_session: Session) -> dict[str, object]:
    superuser = User(
        id=uuid.uuid4(),
        email="root@example.com",
        username="root",
        full_name="Root User",
        password_hash=get_password_hash("password"),
        is_superuser=True,
    )
    user = User(
        id=uuid.uuid4(),
        email="branch@example.com",
        username="branch",
        full_name="Branch User",
        password_hash=get_password_hash("password"),
        is_superuser=False,
    )
    branch_a = Branch(id=uuid.uuid4(), code="A", name="Branch A", timezone="Asia/Manila")
    branch_b = Branch(id=uuid.uuid4(), code="B", name="Branch B", timezone="Asia/Manila")
    role = Role(name="BRANCH_ADMIN", description="Branch admin")
    db_session.add_all([superuser, user, branch_a, branch_b, role])
    db_session.flush()
    db_session.add(UserBranch(user_id=user.id, branch_id=branch_a.id, role_id=role.id))
    db_session.commit()
    return {
        "superuser": superuser,
        "user": user,
        "branch_a": branch_a,
        "branch_b": branch_b,
        "role": role,
    }

