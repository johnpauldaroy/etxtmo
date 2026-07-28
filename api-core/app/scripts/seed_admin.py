"""Create the first superuser from SEED_ADMIN_* env vars, if the users table is empty.

Safe to run on every deploy: no-ops if a user already exists or the seed
env vars are not set.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import User


def main() -> None:
    settings = get_settings()
    if not (settings.seed_admin_email and settings.seed_admin_username and settings.seed_admin_password):
        print("seed_admin: SEED_ADMIN_EMAIL/USERNAME/PASSWORD not fully set, skipping")
        return

    db = SessionLocal()
    try:
        existing_count = db.execute(select(func.count(User.id))).scalar_one()
        if existing_count > 0:
            print("seed_admin: users table is not empty, skipping")
            return

        user = User(
            email=settings.seed_admin_email,
            username=settings.seed_admin_username,
            full_name=settings.seed_admin_full_name,
            password_hash=get_password_hash(settings.seed_admin_password),
            is_superuser=True,
        )
        db.add(user)
        db.commit()
        print(f"seed_admin: created superuser '{settings.seed_admin_username}'")
    finally:
        db.close()


if __name__ == "__main__":
    main()
