from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import Campaign, CampaignRecipient, CampaignStatus, Contact, MessageQueue, ScheduleRule, ScheduleRuleRun, Template
from app.schemas import RuleCreate
from app.services.queue import expand_recipients_for_campaign
from app.services.scheduler import dispatch_due_scheduled_campaigns, evaluate_rules_once, rule_matches


def test_rule_matches_timezone_and_day():
    # 2026-04-17 01:30 UTC -> 09:30 Asia/Singapore (Friday, local_day = 5 in Sunday=0 convention)
    now = datetime(2026, 4, 17, 1, 30, tzinfo=timezone.utc)
    rule = ScheduleRule(
        branch_id=uuid.uuid4(),
        name="Morning",
        minute_of_day=(9 * 60) + 30,
        days_of_week="5",
        timezone="Asia/Singapore",
        is_active=True,
    )
    assert rule_matches(rule, now) is True

    rule.days_of_week = "4"
    assert rule_matches(rule, now) is False

    rule.days_of_week = "Monday"
    assert rule_matches(rule, now) is False

    rule.days_of_week = "5"
    rule.timezone = "Not/A_Timezone"
    assert rule_matches(rule, now) is False


def test_rule_schema_normalizes_days_and_rejects_invalid_configuration():
    payload = RuleCreate(
        branch_id=uuid.uuid4(),
        name="Morning",
        minute_of_day=540,
        days_of_week="5,1,3,1",
        timezone="Asia/Manila",
        message_body="Hello",
    )
    assert payload.days_of_week == "1,3,5"

    with pytest.raises(ValidationError):
        RuleCreate(
            branch_id=uuid.uuid4(),
            name="Invalid days",
            minute_of_day=540,
            days_of_week="Monday",
            timezone="Asia/Manila",
        )

    with pytest.raises(ValidationError):
        RuleCreate(
            branch_id=uuid.uuid4(),
            name="Invalid timezone",
            minute_of_day=540,
            days_of_week="1",
            timezone="Manila",
        )


def test_evaluate_rule_queues_once_per_scheduled_minute(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    now = datetime(2026, 4, 17, 1, 30, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Contact(branch_id=branch.id, phone_number="+639111111111", consented=True),
            ScheduleRule(
                branch_id=branch.id,
                name="Morning",
                minute_of_day=(9 * 60) + 30,
                days_of_week="5",
                timezone="Asia/Manila",
                message_body="Scheduled hello",
                created_by=user.id,
                is_active=True,
            ),
        ],
    )
    db_session.commit()

    assert evaluate_rules_once(db_session, now) == 1
    db_session.commit()
    assert evaluate_rules_once(db_session, now) == 0
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(Campaign)) == 1
    assert db_session.scalar(select(func.count()).select_from(MessageQueue)) == 1
    assert db_session.scalar(select(func.count()).select_from(ScheduleRuleRun)) == 1


def test_evaluate_rule_uses_selected_template(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    now = datetime(2026, 4, 17, 1, 30, tzinfo=timezone.utc)
    template = Template(
        id=uuid.uuid4(),
        branch_id=branch.id,
        name="Membership reminder",
        body="Please renew your membership.",
    )
    rule = ScheduleRule(
        branch_id=branch.id,
        name="Repeat membership reminder",
        minute_of_day=(9 * 60) + 30,
        days_of_week="5",
        timezone="Asia/Manila",
        template_id=template.id,
        created_by=user.id,
        is_active=True,
    )
    db_session.add_all(
        [
            template,
            rule,
            Contact(branch_id=branch.id, phone_number="+639111111111", consented=True),
        ],
    )
    db_session.commit()

    assert evaluate_rules_once(db_session, now) == 1
    db_session.commit()

    generated_campaign = db_session.execute(
        select(Campaign).where(Campaign.schedule_rule_id == rule.id),
    ).scalar_one()
    recipient = db_session.execute(
        select(CampaignRecipient).where(CampaignRecipient.campaign_id == generated_campaign.id),
    ).scalar_one()
    assert recipient.message_body == "Please renew your membership."
    assert generated_campaign.template_id == template.id


def test_evaluate_rules_isolates_failure_of_one_rule(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    now = datetime(2026, 4, 17, 1, 30, tzinfo=timezone.utc)

    broken_rule = ScheduleRule(
        branch_id=branch.id,
        name="Broken",
        minute_of_day=(9 * 60) + 30,
        days_of_week="5",
        timezone="Asia/Manila",
        template_id=None,
        message_body=None,
        created_by=user.id,
        is_active=True,
    )
    healthy_rule = ScheduleRule(
        branch_id=branch.id,
        name="Healthy",
        minute_of_day=(9 * 60) + 30,
        days_of_week="5",
        timezone="Asia/Manila",
        message_body="Scheduled hello",
        created_by=user.id,
        is_active=True,
    )
    db_session.add_all(
        [
            Contact(branch_id=branch.id, phone_number="+639111111111", consented=True),
            broken_rule,
            healthy_rule,
        ],
    )
    db_session.commit()

    generated = evaluate_rules_once(db_session, now)
    db_session.commit()

    assert generated == 1

    broken_run = db_session.execute(
        select(ScheduleRuleRun).where(ScheduleRuleRun.rule_id == broken_rule.id),
    ).scalar_one()
    assert broken_run.status == "error"
    assert "message content" in broken_run.details_json["error"]

    healthy_run = db_session.execute(
        select(ScheduleRuleRun).where(ScheduleRuleRun.rule_id == healthy_rule.id),
    ).scalar_one()
    assert healthy_run.status == "queued"

    assert db_session.scalar(select(func.count()).select_from(Campaign)) == 1


def test_dispatch_due_scheduled_campaigns(db_session, seeded_access):
    branch = seeded_access["branch_a"]
    user = seeded_access["user"]
    now = datetime.now(timezone.utc)

    due_campaign = Campaign(
        id=uuid.uuid4(),
        branch_id=branch.id,
        name="Due",
        status=CampaignStatus.approved,
        scheduled_at=now - timedelta(minutes=1),
        timezone="Asia/Manila",
        created_by=user.id,
    )
    future_campaign = Campaign(
        id=uuid.uuid4(),
        branch_id=branch.id,
        name="Future",
        status=CampaignStatus.approved,
        scheduled_at=now + timedelta(hours=1),
        timezone="Asia/Manila",
        created_by=user.id,
    )
    contact = Contact(branch_id=branch.id, phone_number="+639111111111", consented=True)
    db_session.add_all([due_campaign, future_campaign, contact])
    db_session.commit()

    expand_recipients_for_campaign(db_session, due_campaign, group_id=None, raw_message="Hello")
    expand_recipients_for_campaign(db_session, future_campaign, group_id=None, raw_message="Hello")
    db_session.commit()

    dispatched = dispatch_due_scheduled_campaigns(db_session, now)
    db_session.commit()

    assert dispatched == 1
    assert due_campaign.status == CampaignStatus.queued
    assert future_campaign.status == CampaignStatus.approved
