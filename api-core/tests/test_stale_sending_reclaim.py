"""A row in `sending` only moves when its agent reports a result, so an agent
that dies mid-send strands it there permanently. These cover the sweeper that
reclaims those rows and the operator escape hatch that cancels them."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.api.routes.queue import cancel_campaign
from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignStatus,
    MessageLog,
    MessageQueue,
    QueueStatus,
    RecipientStatus,
)
from app.services.queue import DEFAULT_STALE_LOCK_SECONDS, reclaim_stale_sending


def _sending_message(db_session, branch, user, *, locked_seconds_ago: int, attempts: int = 0) -> MessageQueue:
    """A row claimed `locked_seconds_ago` and never reported back."""
    campaign = Campaign(
        branch_id=branch.id,
        name="Stuck campaign",
        status=CampaignStatus.sending,
        timezone="Asia/Manila",
        created_by=user.id,
    )
    db_session.add(campaign)
    db_session.flush()
    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        branch_id=branch.id,
        phone_number="+639171234567",
        message_body="Service notice",
        status=RecipientStatus.sending,
    )
    db_session.add(recipient)
    db_session.flush()
    item = MessageQueue(
        branch_id=branch.id,
        campaign_id=campaign.id,
        campaign_recipient_id=recipient.id,
        status=QueueStatus.sending,
        attempts=attempts,
        max_attempts=3,
        locked_at=datetime.now(timezone.utc) - timedelta(seconds=locked_seconds_ago),
    )
    db_session.add(item)
    db_session.flush()
    recipient.message_queue_id = item.id
    return item


def test_stale_claim_is_requeued_for_another_modem(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    item = _sending_message(db_session, branch, seeded_access["user"], locked_seconds_ago=600)
    db_session.commit()

    result = reclaim_stale_sending(db_session)
    db_session.commit()

    assert result == {"requeued": 1, "failed": 0}
    db_session.refresh(item)
    assert item.status == QueueStatus.pending
    # The lost claim counts as a spent attempt, so a row cannot loop forever.
    assert item.attempts == 1
    # Cleared so another modem can claim it; pull filters on modem_id IS NULL.
    assert item.locked_at is None
    assert item.modem_id is None
    assert item.next_attempt_at is not None


def test_stale_claim_fails_once_attempts_are_exhausted(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    # attempts=2 of max 3: this reclaim is the last one available.
    item = _sending_message(db_session, branch, seeded_access["user"], locked_seconds_ago=600, attempts=2)
    db_session.commit()

    result = reclaim_stale_sending(db_session)
    db_session.commit()

    assert result == {"requeued": 0, "failed": 1}
    db_session.refresh(item)
    assert item.status == QueueStatus.failed
    recipient = db_session.get(CampaignRecipient, item.campaign_recipient_id)
    assert recipient.status == RecipientStatus.failed
    log = db_session.execute(
        select(MessageLog).where(
            MessageLog.queue_id == item.id,
            MessageLog.event_type == "queue_stale_reclaimed",
        ),
    ).scalar_one()
    assert log.event_status == QueueStatus.failed.value


def test_fresh_claim_is_left_with_its_modem(db_session, seeded_access):
    """The whole point of the timeout: a send in progress must not be stolen."""
    branch = seeded_access["branch_a"]
    item = _sending_message(db_session, branch, seeded_access["user"], locked_seconds_ago=5)
    db_session.commit()

    result = reclaim_stale_sending(db_session)
    db_session.commit()

    assert result == {"requeued": 0, "failed": 0}
    db_session.refresh(item)
    assert item.status == QueueStatus.sending
    assert item.attempts == 0
    assert item.locked_at is not None


def test_reclaim_ignores_rows_with_no_claim_timestamp(db_session, seeded_access):
    """A null locked_at is unknown, not old -- it must not read as stale."""
    branch = seeded_access["branch_a"]
    item = _sending_message(db_session, branch, seeded_access["user"], locked_seconds_ago=600)
    item.locked_at = None
    db_session.commit()

    assert reclaim_stale_sending(db_session) == {"requeued": 0, "failed": 0}
    db_session.refresh(item)
    assert item.status == QueueStatus.sending


def test_cancel_stops_a_stale_row_but_not_a_fresh_one(db_session, seeded_access):
    """The dead end this fixes: Cancel used to report 0 stopped, 1 in flight."""
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    stale = _sending_message(
        db_session,
        branch,
        user,
        locked_seconds_ago=DEFAULT_STALE_LOCK_SECONDS + 60,
    )
    db_session.commit()

    response = cancel_campaign(stale.campaign_id, db=db_session, current_user=user)

    assert response["cancelled"] == 1
    # The row just cancelled must not also be counted as unrecallable.
    assert response["in_flight"] == 0
    assert response["status"] == CampaignStatus.cancelled.value
    db_session.refresh(stale)
    assert stale.status == QueueStatus.cancelled
    recipient = db_session.get(CampaignRecipient, stale.campaign_recipient_id)
    assert recipient.status == RecipientStatus.cancelled

    fresh = _sending_message(db_session, branch, user, locked_seconds_ago=5)
    db_session.commit()

    response = cancel_campaign(fresh.campaign_id, db=db_session, current_user=user)

    assert response["cancelled"] == 0
    assert response["in_flight"] == 1
    db_session.refresh(fresh)
    assert fresh.status == QueueStatus.sending
