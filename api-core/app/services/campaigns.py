from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Campaign, CampaignStatus


def move_to_submission_state(db: Session, campaign: Campaign) -> CampaignStatus:
    campaign.status = CampaignStatus.approved
    db.flush()
    return campaign.status
