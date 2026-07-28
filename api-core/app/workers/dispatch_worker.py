from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Campaign, CampaignStatus
from app.services.queue import queue_campaign


def run_dispatch_cycle() -> int:
    db = SessionLocal()
    try:
        campaigns = db.execute(
            select(Campaign).where(
                Campaign.status == CampaignStatus.approved,
                Campaign.scheduled_at.is_not(None),
                Campaign.scheduled_at <= datetime.now(timezone.utc),
            ),
        ).scalars()
        moved = 0
        for campaign in campaigns:
            queued = queue_campaign(db, campaign)
            campaign.status = CampaignStatus.queued if queued > 0 else CampaignStatus.failed
            moved += 1
        db.commit()
        return moved
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    count = run_dispatch_cycle()
    print(f"Dispatched {count} campaigns")

