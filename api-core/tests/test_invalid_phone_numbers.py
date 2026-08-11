from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignStatus,
    Contact,
    MessageQueue,
    RecipientStatus,
)
from app.services.queue import (
    expand_recipients_for_campaign,
    is_valid_phone_number,
    queue_campaign,
)


@pytest.mark.parametrize(
    "phone_number",
    [
        "09171234567",
        "+639171234567",
        "639171234567",
        "0917 123 4567",
        "0917-123-4567",
    ],
)
def test_accepts_dialable_numbers(phone_number):
    assert is_valid_phone_number(phone_number) is True


@pytest.mark.parametrize(
    "phone_number",
    [
        "099798907555",  # 12 digits -- one too many
        "0912345678",  # 10 digits -- one too few
        "08171234567",  # PH mobile numbers are 09xx, never 08xx
        "abc",
        "",
        None,
    ],
)
def test_rejects_undialable_numbers(phone_number):
    assert is_valid_phone_number(phone_number) is False


def test_invalid_contacts_are_failed_not_queued(db_session, seeded_access):
    """An unusable number must land in `failed` immediately. Queueing it leaves
    the row stuck in `sending` forever, because the modem never reports a
    result for a number it cannot dial."""
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    campaign = Campaign(
        branch_id=branch.id,
        name="Mixed validity",
        status=CampaignStatus.draft,
        timezone="Asia/Manila",
        created_by=user.id,
    )
    db_session.add_all(
        [
            campaign,
            Contact(
                branch_id=branch.id,
                phone_number="09067808830",
                first_name="Valid",
                consented=True,
            ),
            Contact(
                branch_id=branch.id,
                phone_number="099798907555",
                first_name="Invalid",
                consented=True,
            ),
        ],
    )
    db_session.flush()

    created = expand_recipients_for_campaign(
        db_session,
        campaign,
        group_id=None,
        raw_message="Hello {{first_name}}",
    )
    queued = queue_campaign(db_session, campaign)
    db_session.commit()

    # Only the dialable contact counts as created and reaches the queue.
    assert created == 1
    assert queued == 1

    recipients = {
        recipient.phone_number: recipient
        for recipient in db_session.execute(
            select(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id),
        ).scalars()
    }
    assert recipients["09067808830"].status == RecipientStatus.pending
    assert recipients["099798907555"].status == RecipientStatus.failed

    # The stored number keeps its original form -- validation must not rewrite it.
    assert set(recipients) == {"09067808830", "099798907555"}

    queue_rows = db_session.execute(
        select(MessageQueue).where(MessageQueue.campaign_id == campaign.id),
    ).scalars().all()
    assert [row.campaign_recipient_id for row in queue_rows] == [recipients["09067808830"].id]


def test_requeue_does_not_revive_invalid_recipients(db_session, seeded_access):
    """queue_campaign re-queues failed recipients for retry, so it must skip the
    ones that failed for being undialable."""
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    campaign = Campaign(
        branch_id=branch.id,
        name="Retry pass",
        status=CampaignStatus.draft,
        timezone="Asia/Manila",
        created_by=user.id,
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(
        CampaignRecipient(
            campaign_id=campaign.id,
            branch_id=branch.id,
            phone_number="099798907555",
            message_body="Hello",
            status=RecipientStatus.failed,
        ),
    )
    db_session.flush()

    assert queue_campaign(db_session, campaign) == 0
    db_session.commit()

    assert db_session.execute(
        select(MessageQueue).where(MessageQueue.campaign_id == campaign.id),
    ).scalars().all() == []
