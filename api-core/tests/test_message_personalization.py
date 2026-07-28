from __future__ import annotations

from sqlalchemy import select

from app.models import Campaign, CampaignRecipient, CampaignStatus, Contact
from app.services.queue import expand_recipients_for_campaign


def test_campaign_messages_render_contact_placeholders(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    campaign = Campaign(
        branch_id=branch.id,
        name="Personalized greeting",
        status=CampaignStatus.draft,
        timezone="Asia/Manila",
        created_by=user.id,
    )
    db_session.add_all(
        [
            campaign,
            Contact(
                branch_id=branch.id,
                phone_number="+639111111111",
                first_name="Juan",
                last_name="Dela Cruz",
                consented=True,
            ),
            Contact(
                branch_id=branch.id,
                phone_number="+639222222222",
                first_name=None,
                last_name="Santos",
                consented=True,
            ),
        ],
    )
    db_session.commit()

    created = expand_recipients_for_campaign(
        db_session,
        campaign,
        group_id=None,
        raw_message="Hi {{first_name}} {{last_name}} ({{full_name}}), your number is {{phone_number}}.",
    )
    db_session.commit()

    assert created == 2
    recipients = db_session.execute(
        select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id),
    ).scalars().all()
    messages = {recipient.phone_number: recipient.message_body for recipient in recipients}
    assert messages["+639111111111"] == "Hi Juan Dela Cruz (Juan Dela Cruz), your number is +639111111111."
    assert messages["+639222222222"] == "Hi Santos (Santos), your number is +639222222222."
