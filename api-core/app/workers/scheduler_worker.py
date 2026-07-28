from __future__ import annotations

from app.core.database import SessionLocal
from app.services.scheduler import dispatch_due_scheduled_campaigns, evaluate_rules_once


def run() -> int:
    db = SessionLocal()
    try:
        generated = evaluate_rules_once(db)
        dispatched = dispatch_due_scheduled_campaigns(db)
        db.commit()
        return generated + dispatched
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Generated campaigns: {run()}")

