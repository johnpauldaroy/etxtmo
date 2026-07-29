from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignStatus,
    FailoverPolicy,
    FailoverRoute,
    MessageLog,
    MessageQueue,
    Modem,
    ModemStatus,
    QueueStatus,
    RecipientStatus,
)
from app.api.routes.node import pull_jobs
from app.schemas import QueuePullRequest
from app.services.queue import apply_queue_results, pull_pending_queue_items


def _queued_message(db_session, branch, user) -> MessageQueue:
    campaign = Campaign(
        branch_id=branch.id,
        name="Failover campaign",
        status=CampaignStatus.queued,
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
        status=RecipientStatus.pending,
    )
    db_session.add(recipient)
    db_session.flush()
    item = MessageQueue(
        branch_id=branch.id,
        campaign_id=campaign.id,
        campaign_recipient_id=recipient.id,
        status=QueueStatus.pending,
        attempts=0,
        max_attempts=3,
        next_attempt_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(item)
    db_session.flush()
    recipient.message_queue_id = item.id
    return item


def test_backup_modem_claims_only_when_source_has_no_healthy_modem(db_session, seeded_access):
    source = seeded_access["branch_a"]
    backup = seeded_access["branch_b"]
    user = seeded_access["user"]
    backup_modem = Modem(
        id=uuid.uuid4(),
        branch_id=backup.id,
        node_name="backup-node",
        name="Backup Wavecom",
        status=ModemStatus.online,
        last_seen_at=datetime.now(timezone.utc),
    )
    policy = FailoverPolicy(
        branch_id=source.id,
        enabled=True,
        offline_after_seconds=90,
        failover_delay_seconds=0,
        claim_timeout_seconds=120,
    )
    route = FailoverRoute(source_branch_id=source.id, backup_branch_id=backup.id, priority=1, enabled=True)
    item = _queued_message(db_session, source, user)
    db_session.add_all([backup_modem, policy, route])
    db_session.commit()

    jobs = pull_pending_queue_items(
        db_session,
        execution_branch_id=backup.id,
        modem_id=backup_modem.id,
        limit=10,
    )
    assert [job.id for job in jobs] == [item.id]
    assert jobs[0].branch_id == source.id
    assert jobs[0].execution_branch_id == backup.id
    assert jobs[0].modem_id == backup_modem.id
    assert jobs[0].failover_route_id == route.id
    assert pull_pending_queue_items(
        db_session,
        execution_branch_id=backup.id,
        modem_id=backup_modem.id,
        limit=10,
    ) == []

    result = apply_queue_results(
        db_session,
        execution_branch_id=backup.id,
        modem_id=backup_modem.id,
        items=[{"queue_id": item.id, "status": "sent", "external_message_id": "gammu-1"}],
    )
    db_session.commit()
    assert result == {"sent": 1, "failed": 0}
    log = db_session.execute(
        select(MessageLog).where(MessageLog.queue_id == item.id, MessageLog.event_type == "queue_result"),
    ).scalar_one()
    assert log.branch_id == source.id
    assert log.details_json["used_failover"] is True
    assert log.details_json["execution_branch_id"] == str(backup.id)


def test_healthy_source_modem_prevents_backup_claim(db_session, seeded_access):
    source = seeded_access["branch_a"]
    backup = seeded_access["branch_b"]
    user = seeded_access["user"]
    db_session.add_all(
        [
            Modem(
                branch_id=source.id,
                node_name="source-node",
                name="Source Wavecom",
                status=ModemStatus.online,
                last_seen_at=datetime.now(timezone.utc),
            ),
            Modem(
                id=(backup_modem_id := uuid.uuid4()),
                branch_id=backup.id,
                node_name="backup-node",
                name="Backup Wavecom",
                status=ModemStatus.online,
                last_seen_at=datetime.now(timezone.utc),
            ),
            FailoverPolicy(
                branch_id=source.id,
                enabled=True,
                offline_after_seconds=90,
                failover_delay_seconds=0,
                claim_timeout_seconds=120,
            ),
            FailoverRoute(source_branch_id=source.id, backup_branch_id=backup.id, priority=1, enabled=True),
        ],
    )
    _queued_message(db_session, source, user)
    db_session.commit()

    jobs = pull_pending_queue_items(
        db_session,
        execution_branch_id=backup.id,
        modem_id=backup_modem_id,
        limit=10,
    )
    assert jobs == []


def test_unhealthy_execution_modem_cannot_claim_pending_jobs(db_session, seeded_access):
    source = seeded_access["branch_a"]
    user = seeded_access["user"]
    source_modem = Modem(
        id=uuid.uuid4(),
        branch_id=source.id,
        node_name="source-node",
        name="Broken source modem",
        status=ModemStatus.error,
        last_seen_at=datetime.now(timezone.utc),
    )
    item = _queued_message(db_session, source, user)
    db_session.add(source_modem)
    db_session.commit()

    jobs = pull_jobs(
        QueuePullRequest(branch_id=source.id, modem_id=source_modem.id, limit=10),
        db_session,
        user,
    )

    db_session.refresh(item)
    assert jobs == []
    assert item.status == QueueStatus.pending
    assert item.modem_id is None
