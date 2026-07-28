from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models import Campaign, CampaignStatus, Contact, MessageQueue
from app.services.queue import expand_recipients_for_campaign, queue_campaign


def test_queue_idempotency(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    campaign = Campaign(
        id=uuid.uuid4(),
        branch_id=branch.id,
        name="Idempotency",
        status=CampaignStatus.approved,
        timezone="Asia/Manila",
        created_by=user.id,
    )
    contact = Contact(branch_id=branch.id, phone_number="+639111111111", consented=True)
    db_session.add_all([campaign, contact])
    db_session.commit()

    expand_recipients_for_campaign(db_session, campaign, group_id=None, raw_message="Hello")
    queued_first = queue_campaign(db_session, campaign)
    queued_second = queue_campaign(db_session, campaign)
    db_session.commit()

    total_queue = db_session.execute(select(func.count(MessageQueue.id))).scalar_one()
    assert queued_first == 1
    assert queued_second == 0
    assert total_queue == 1
