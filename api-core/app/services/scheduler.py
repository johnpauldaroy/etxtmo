from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Campaign, CampaignStatus, ScheduleRule, ScheduleRuleRun
from app.services.queue import expand_recipients_for_campaign, queue_campaign


def dispatch_due_scheduled_campaigns(db: Session, now_utc: datetime | None = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    campaigns = db.execute(
        select(Campaign).where(
            Campaign.status == CampaignStatus.approved,
            Campaign.scheduled_at.is_not(None),
            Campaign.scheduled_at <= now_utc,
        ),
    ).scalars().all()

    dispatched = 0
    for campaign in campaigns:
        queued = queue_campaign(db, campaign)
        campaign.status = CampaignStatus.queued if queued > 0 else CampaignStatus.failed
        dispatched += 1
    db.flush()
    return dispatched


def _parse_days(days_of_week: str) -> set[int]:
    return {int(day.strip()) for day in days_of_week.split(",") if day.strip()}


def rule_matches(rule: ScheduleRule, now_utc: datetime) -> bool:
    try:
        localized = now_utc.astimezone(ZoneInfo(rule.timezone))
        allowed_days = _parse_days(rule.days_of_week)
    except (ValueError, ZoneInfoNotFoundError):
        return False
    minute_of_day = localized.hour * 60 + localized.minute
    # Python weekday: Monday=0..Sunday=6. We map 0=Sunday for user-facing convention.
    local_day = (localized.weekday() + 1) % 7
    return rule.is_active and minute_of_day == rule.minute_of_day and local_day in allowed_days


def evaluate_rules_once(db: Session, now_utc: datetime | None = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    rules = db.execute(select(ScheduleRule).where(ScheduleRule.is_active.is_(True))).scalars().all()
    generated_campaigns = 0
    run_key_time = now_utc.replace(second=0, microsecond=0)

    for rule in rules:
        if not rule_matches(rule, now_utc):
            continue

        existing_run = db.execute(
            select(ScheduleRuleRun.id).where(ScheduleRuleRun.rule_id == rule.id, ScheduleRuleRun.run_at == run_key_time),
        ).scalar_one_or_none()
        if existing_run:
            continue

        # Isolate each rule so one bad rule (e.g. missing message content)
        # cannot abort the whole cycle and block every other rule's send.
        try:
            with db.begin_nested():
                campaign = Campaign(
                    branch_id=rule.branch_id,
                    name=f"Auto Rule {rule.name} {run_key_time.isoformat()}",
                    template_id=rule.template_id,
                    schedule_rule_id=rule.id,
                    status=CampaignStatus.approved,
                    scheduled_at=run_key_time,
                    timezone=rule.timezone,
                    metadata_json={
                        "generated_by_rule": str(rule.id),
                        "group_id": str(rule.group_id) if rule.group_id else None,
                        "message_body": rule.message_body,
                        "filters": rule.filter_json,
                    },
                )
                db.add(campaign)
                db.flush()

                recipient_count = expand_recipients_for_campaign(
                    db,
                    campaign,
                    group_id=rule.group_id,
                    raw_message=rule.message_body,
                )
                queued = queue_campaign(db, campaign)
                campaign.status = CampaignStatus.queued if queued > 0 else CampaignStatus.failed

                db.add(
                    ScheduleRuleRun(
                        rule_id=rule.id,
                        run_at=run_key_time,
                        status="queued" if queued > 0 else "no_recipients",
                        campaign_id=campaign.id if queued > 0 else None,
                        details_json={"recipients": recipient_count, "queued": queued},
                    ),
                )
            generated_campaigns += 1
        except Exception as exc:  # noqa: BLE001 - isolate per-rule failures
            db.add(
                ScheduleRuleRun(
                    rule_id=rule.id,
                    run_at=run_key_time,
                    status="error",
                    campaign_id=None,
                    details_json={"error": str(exc)},
                ),
            )

    db.flush()
    return generated_campaigns
