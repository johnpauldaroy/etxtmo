from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models import Campaign, CampaignStatus, Contact, MessageQueue, QueueStatus, Template
from app.api.routes.campaigns import list_campaign_recipients
from app.api.routes.queue import list_queue
from app.services.campaigns import move_to_submission_state
from app.services.queue import apply_queue_results, expand_recipients_for_campaign, pull_pending_queue_items, queue_campaign


def test_campaign_lifecycle_to_sent(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]

    contact = Contact(
        branch_id=branch.id,
        phone_number="+639221111111",
        first_name="Juan",
        last_name="Dela Cruz",
        consented=True,
    )
    template = Template(branch_id=branch.id, name="Notice", body="Hello members", is_official=True)
    campaign = Campaign(
        id=uuid.uuid4(),
        branch_id=branch.id,
        name="Lifecycle",
        status=CampaignStatus.draft,
        timezone="Asia/Manila",
        created_by=user.id,
    )
    db_session.add_all([contact, template, campaign])
    db_session.flush()
    campaign.template_id = template.id

    recipients = expand_recipients_for_campaign(db_session, campaign, group_id=None)
    next_state = move_to_submission_state(db_session, campaign)
    queued = queue_campaign(db_session, campaign)
    db_session.commit()

    assert recipients == 1
    assert next_state == CampaignStatus.approved
    assert queued == 1

    jobs = pull_pending_queue_items(db_session, branch_id=branch.id, modem_id=None, limit=10)
    assert len(jobs) == 1
    assert jobs[0].status == QueueStatus.sending

    result = apply_queue_results(
        db_session,
        branch_id=branch.id,
        items=[{"queue_id": jobs[0].id, "status": "sent", "external_message_id": "abc123"}],
    )
    db_session.commit()
    sent_count = db_session.execute(
        select(func.count(MessageQueue.id)).where(MessageQueue.status == QueueStatus.sent),
    ).scalar_one()
    assert result["sent"] == 1
    assert sent_count == 1
    db_session.refresh(campaign)
    assert campaign.status == CampaignStatus.sent

    queue_rows = list_queue(
        branch_id=branch.id,
        status_filter=None,
        db=db_session,
        current_user=user,
    )
    assert queue_rows[0].campaign_name == "Lifecycle"
    assert queue_rows[0].sent_at is not None

    recipient_rows = list_campaign_recipients(
        campaign_id=campaign.id,
        db=db_session,
        current_user=user,
    )["items"]
    assert len(recipient_rows) == 1
    assert recipient_rows[0]["contact_name"] == "Juan Dela Cruz"
    assert recipient_rows[0]["phone_number"] == "+639221111111"
    assert recipient_rows[0]["message_body"] == "Hello members"
    assert recipient_rows[0]["status"] == "sent"
    assert recipient_rows[0]["attempts"] == 1
    assert recipient_rows[0]["sent_at"] is not None
    assert recipient_rows[0]["error_message"] is None
