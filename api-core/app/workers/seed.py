from __future__ import annotations

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.models import Role


DEFAULT_ROLES = [
    ("SUPER_ADMIN", "Global administrator"),
    ("HQ_ADMIN", "HQ-level branch visibility"),
    ("BRANCH_ADMIN", "Branch management and campaign control"),
    ("OPERATOR", "Branch sending operations"),
    ("VIEWER", "Read-only branch access"),
]


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for role_name, role_desc in DEFAULT_ROLES:
            exists = db.execute(select(Role.id).where(Role.name == role_name)).scalar_one_or_none()
            if exists is None:
                db.add(Role(name=role_name, description=role_desc))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
    print("Seed complete")

