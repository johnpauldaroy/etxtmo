from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Campaign,
    CampaignStatus,
    CampaignRecipient,
    Contact,
    ContactGroupMember,
    FailoverPolicy,
    FailoverRoute,
    MessageLog,
    MessageQueue,
    Modem,
    ModemStatus,
    OptOut,
    QueueStatus,
    RecipientStatus,
    Template,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_backoff(attempt: int) -> timedelta:
    # 1m, 2m, 4m, ... capped at 60m
    minutes = min(60, 2 ** max(0, attempt - 1))
    return timedelta(minutes=minutes)


def render_contact_message(message: str, contact: Contact) -> str:
    first_name = (contact.first_name or "").strip()
    last_name = (contact.last_name or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part)
    replacements = {
        "{{first_name}}": first_name,
        "{{last_name}}": last_name,
        "{{full_name}}": full_name,
        "{{phone_number}}": contact.phone_number,
    }
    if not any(placeholder in message for placeholder in replacements):
        return message
    rendered = message
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    rendered = re.sub(r"[ \t]{2,}", " ", rendered)
    return re.sub(r" +([,.;:!?])", r"\1", rendered)


# PH mobile numbers: 11 digits as 09XXXXXXXXX, or +639XXXXXXXXX / 639XXXXXXXXX.
_PH_MOBILE_RE = re.compile(r"^(?:0|63|\+63)9\d{9}$")


def is_valid_phone_number(phone_number: str | None) -> bool:
    """True when this is a dialable PH mobile number, in either the 09XXXXXXXXX
    or +639XXXXXXXXX form. Separators callers paste from spreadsheets (spaces,
    dashes, parentheses) are ignored when checking.

    Deliberately only validates -- the stored number keeps whatever form it came
    in as. Rewriting it would change the value shown in the UI and break the
    exact-string matching used for opt-out and duplicate detection."""
    if not phone_number:
        return False
    cleaned = re.sub(r"[\s()\-.]", "", phone_number.strip())
    return bool(_PH_MOBILE_RE.match(cleaned))


DEFAULT_MODEM_OFFLINE_AFTER_SECONDS = 90

# How long a row may sit in `sending` before we treat the claim as lost. Only a
# result posted back by the agent moves a claimed row, so an agent that dies
# mid-send (crash, restart, modem swallowing the number without answering)
# strands it in `sending` forever -- there is no other path out.
DEFAULT_STALE_LOCK_SECONDS = 300


def healthy_modem_count(db: Session, branch_id: uuid.UUID, offline_after_seconds: int = 90) -> int:
    cutoff = now_utc() - timedelta(seconds=offline_after_seconds)
    return db.execute(
        select(func.count(Modem.id)).where(
            Modem.branch_id == branch_id,
            Modem.status == ModemStatus.online,
            Modem.last_seen_at.is_not(None),
            Modem.last_seen_at >= cutoff,
        ),
    ).scalar_one()


def effective_modem_status(
    modem: Modem,
    offline_after_seconds: int = DEFAULT_MODEM_OFFLINE_AFTER_SECONDS,
) -> ModemStatus:
    """Nothing flips Modem.status back to offline when a branch-agent goes
    silent (crash, unplugged modem, PC powered off) -- only a successful
    heartbeat ever sets it, so the stored value can go stale indefinitely.
    Derive the displayed status from last_seen_at age instead of trusting
    the column directly."""
    if modem.status != ModemStatus.online:
        return modem.status
    if modem.last_seen_at is None:
        return ModemStatus.offline
    cutoff = now_utc() - timedelta(seconds=offline_after_seconds)
    return ModemStatus.online if modem.last_seen_at >= cutoff else ModemStatus.offline


def _eligible_failover_sources(
    db: Session,
    *,
    execution_branch_id: uuid.UUID,
) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    """Return (source branch, route, delay) only when this is the highest-priority healthy backup."""
    policies = db.execute(
        select(FailoverPolicy).where(FailoverPolicy.enabled.is_(True)),
    ).scalars().all()
    eligible: list[tuple[uuid.UUID, uuid.UUID, int]] = []
    for policy in policies:
        if healthy_modem_count(db, policy.branch_id, policy.offline_after_seconds) > 0:
            continue
        routes = db.execute(
            select(FailoverRoute)
            .where(FailoverRoute.source_branch_id == policy.branch_id, FailoverRoute.enabled.is_(True))
            .order_by(FailoverRoute.priority.asc(), FailoverRoute.created_at.asc()),
        ).scalars().all()
        for route in routes:
            if healthy_modem_count(db, route.backup_branch_id, policy.offline_after_seconds) <= 0:
                continue
            if route.backup_branch_id == execution_branch_id:
                eligible.append((policy.branch_id, route.id, policy.failover_delay_seconds))
            break
    return eligible


def expand_recipients_for_campaign(
    db: Session,
    campaign: Campaign,
    *,
    group_id: uuid.UUID | None,
    raw_message: str | None = None,
) -> int:
    template_body = None
    if campaign.template_id:
        template = db.get(Template, campaign.template_id)
        if template:
            template_body = template.body

    message_body = raw_message or template_body
    if not message_body:
        raise ValueError("Campaign message content is required")

    contact_stmt = select(Contact).where(
        Contact.branch_id == campaign.branch_id,
        Contact.deleted_at.is_(None),
        Contact.consented.is_(True),
    )

    if group_id:
        contact_stmt = (
            select(Contact)
            .join(ContactGroupMember, ContactGroupMember.contact_id == Contact.id)
            .where(
                ContactGroupMember.group_id == group_id,
                Contact.branch_id == campaign.branch_id,
                Contact.deleted_at.is_(None),
                Contact.consented.is_(True),
            )
        )

    contacts = db.execute(contact_stmt).scalars().all()
    if not contacts:
        return 0

    opted_out = set(
        db.execute(
            select(OptOut.phone_number).where(OptOut.branch_id == campaign.branch_id),
        ).scalars(),
    )

    created = 0
    for contact in contacts:
        if contact.phone_number in opted_out:
            continue

        existing = db.execute(
            select(CampaignRecipient.id).where(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.phone_number == contact.phone_number,
            ),
        ).scalar_one_or_none()
        if existing:
            continue

        # Unusable numbers are recorded as failed rather than queued: the modem
        # can never deliver them, and queueing them leaves the row sitting in
        # "sending" until a human notices.
        valid = is_valid_phone_number(contact.phone_number)
        recipient = CampaignRecipient(
            campaign_id=campaign.id,
            branch_id=campaign.branch_id,
            contact_id=contact.id,
            phone_number=contact.phone_number,
            message_body=render_contact_message(message_body, contact),
            status=RecipientStatus.pending if valid else RecipientStatus.failed,
        )
        db.add(recipient)
        if valid:
            created += 1
    db.flush()
    return created


def queue_campaign(db: Session, campaign: Campaign) -> int:
    recipients = db.execute(
        select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status.in_([RecipientStatus.pending, RecipientStatus.failed]),
        ),
    ).scalars().all()
    existing_recipient_ids = set(
        db.execute(
            select(MessageQueue.campaign_recipient_id).where(MessageQueue.campaign_id == campaign.id),
        ).scalars(),
    )

    queued_count = 0
    for recipient in recipients:
        if recipient.id in existing_recipient_ids:
            continue
        # Also covers the retry path: failed recipients are re-queued here, so
        # an unusable number would otherwise come straight back into the queue.
        if not is_valid_phone_number(recipient.phone_number):
            recipient.status = RecipientStatus.failed
            continue
        queue_item = MessageQueue(
            id=uuid.uuid4(),
            branch_id=campaign.branch_id,
            campaign_id=campaign.id,
            campaign_recipient_id=recipient.id,
            status=QueueStatus.pending,
            attempts=0,
            max_attempts=3,
            next_attempt_at=now_utc(),
        )
        db.add(queue_item)
        recipient.message_queue_id = queue_item.id
        queued_count += 1
    db.flush()
    return queued_count


def pull_pending_queue_items(
    db: Session,
    *,
    execution_branch_id: uuid.UUID | None = None,
    modem_id: uuid.UUID | None = None,
    limit: int = 50,
    branch_id: uuid.UUID | None = None,
) -> list[MessageQueue]:
    execution_branch_id = execution_branch_id or branch_id
    if execution_branch_id is None:
        raise ValueError("execution_branch_id is required")
    candidates: list[tuple[MessageQueue, uuid.UUID | None]] = []
    local_stmt = (
        select(MessageQueue)
        .where(
            MessageQueue.branch_id == execution_branch_id,
            MessageQueue.status == QueueStatus.pending,
            MessageQueue.next_attempt_at <= now_utc(),
            MessageQueue.modem_id.is_(None),
        )
        .order_by(MessageQueue.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    candidates.extend((row, None) for row in db.execute(local_stmt).scalars().all())

    remaining = max(0, limit - len(candidates))
    if remaining:
        # Superadmin manually reassigned these to this branch -- claim them
        # immediately regardless of branch_id/failover eligibility, same as a
        # local claim (no route, no failover delay).
        forced_stmt = (
            select(MessageQueue)
            .where(
                MessageQueue.forced_execution_branch_id == execution_branch_id,
                MessageQueue.branch_id != execution_branch_id,
                MessageQueue.status == QueueStatus.pending,
                MessageQueue.next_attempt_at <= now_utc(),
                MessageQueue.modem_id.is_(None),
            )
            .order_by(MessageQueue.created_at.asc())
            .limit(remaining)
            .with_for_update(skip_locked=True)
        )
        forced_rows = db.execute(forced_stmt).scalars().all()
        candidates.extend((row, None) for row in forced_rows)
        remaining -= len(forced_rows)
    if remaining and modem_id is not None:
        for source_branch_id, route_id, delay_seconds in _eligible_failover_sources(
            db,
            execution_branch_id=execution_branch_id,
        ):
            if remaining <= 0:
                break
            cutoff = now_utc() - timedelta(seconds=delay_seconds)
            failover_stmt = (
                select(MessageQueue)
                .where(
                    MessageQueue.branch_id == source_branch_id,
                    MessageQueue.status == QueueStatus.pending,
                    MessageQueue.next_attempt_at <= now_utc(),
                    MessageQueue.created_at <= cutoff,
                    MessageQueue.modem_id.is_(None),
                )
                .order_by(MessageQueue.created_at.asc())
                .limit(remaining)
                .with_for_update(skip_locked=True)
            )
            rows = db.execute(failover_stmt).scalars().all()
            candidates.extend((row, route_id) for row in rows)
            remaining -= len(rows)

    claimed: list[MessageQueue] = []
    for job, route_id in candidates:
        claimed_at = now_utc()
        result = db.execute(
            update(MessageQueue)
            .where(
                MessageQueue.id == job.id,
                MessageQueue.status == QueueStatus.pending,
                MessageQueue.modem_id.is_(None),
            )
            .values(
                status=QueueStatus.sending,
                locked_at=claimed_at,
                modem_id=modem_id,
                execution_branch_id=execution_branch_id,
                failover_route_id=route_id,
                forced_execution_branch_id=None,
            )
            .execution_options(synchronize_session=False),
        )
        if result.rowcount != 1:
            continue
        db.expire(job)
        db.refresh(job)
        claimed.append(job)
        if job.branch_id != execution_branch_id:
            db.add(
                MessageLog(
                    branch_id=job.branch_id,
                    campaign_id=job.campaign_id,
                    queue_id=job.id,
                    recipient_phone="",
                    event_type="failover_claimed",
                    event_status="sending",
                    details_json={
                        "execution_branch_id": str(execution_branch_id),
                        "modem_id": str(modem_id),
                        "failover_route_id": str(job.failover_route_id),
                    },
                ),
            )
    db.flush()
    return claimed


def apply_queue_results(
    db: Session,
    *,
    execution_branch_id: uuid.UUID | None = None,
    modem_id: uuid.UUID | None = None,
    items: list[dict[str, Any]],
    branch_id: uuid.UUID | None = None,
) -> dict[str, int]:
    execution_branch_id = execution_branch_id or branch_id
    if execution_branch_id is None:
        raise ValueError("execution_branch_id is required")
    sent = 0
    failed = 0
    affected_campaign_ids: set[uuid.UUID] = set()
    for item in items:
        queue_id = item["queue_id"]
        status = QueueStatus(item["status"])
        queue_filters = [MessageQueue.id == queue_id]
        if modem_id is None:
            queue_filters.append(MessageQueue.branch_id == execution_branch_id)
        else:
            queue_filters.extend(
                [
                    MessageQueue.execution_branch_id == execution_branch_id,
                    MessageQueue.modem_id == modem_id,
                ],
            )
        queue_item = db.execute(select(MessageQueue).where(*queue_filters)).scalar_one_or_none()
        if not queue_item:
            continue

        recipient = db.execute(
            select(CampaignRecipient).where(CampaignRecipient.id == queue_item.campaign_recipient_id),
        ).scalar_one_or_none()
        if not recipient:
            continue

        queue_item.attempts += 1
        queue_item.external_message_id = item.get("external_message_id")
        queue_item.error_message = item.get("error_message")
        affected_campaign_ids.add(queue_item.campaign_id)

        if status == QueueStatus.sent:
            queue_item.status = QueueStatus.sent
            recipient.status = RecipientStatus.sent
            sent += 1
        else:
            if queue_item.attempts >= queue_item.max_attempts:
                queue_item.status = QueueStatus.failed
                recipient.status = RecipientStatus.failed
                failed += 1
            else:
                queue_item.status = QueueStatus.pending
                queue_item.next_attempt_at = now_utc() + compute_backoff(queue_item.attempts)
                queue_item.modem_id = None
                queue_item.execution_branch_id = None
                queue_item.failover_route_id = None
                queue_item.locked_at = None
                recipient.status = RecipientStatus.pending

        db.add(
            MessageLog(
                branch_id=queue_item.branch_id,
                campaign_id=queue_item.campaign_id,
                queue_id=queue_item.id,
                recipient_phone=recipient.phone_number,
                event_type="queue_result",
                event_status=queue_item.status.value,
                details_json={
                    "attempts": queue_item.attempts,
                    "external_message_id": queue_item.external_message_id,
                    "error_message": queue_item.error_message,
                    "execution_branch_id": str(execution_branch_id),
                    "modem_id": str(modem_id),
                    "used_failover": queue_item.branch_id != execution_branch_id,
                },
            ),
        )

    # Session autoflush is disabled. Persist the queue/recipient changes before
    # deriving campaign totals, otherwise the count queries still see the old
    # "sending" rows and completed campaigns remain stuck in that state.
    db.flush()

    for campaign_id in affected_campaign_ids:
        recalculate_campaign_status(db, campaign_id)

    db.flush()
    return {"sent": sent, "failed": failed}


def stale_lock_cutoff(stale_after_seconds: int | None = None) -> datetime:
    """Rows claimed before this moment have outlived a plausible send."""
    if stale_after_seconds is None:
        stale_after_seconds = DEFAULT_STALE_LOCK_SECONDS
    return now_utc() - timedelta(seconds=stale_after_seconds)


def reclaim_stale_sending(db: Session, stale_after_seconds: int | None = None) -> dict[str, int]:
    """Return rows whose claiming agent never reported a result.

    Deliberately mirrors the failure branch of `record_results`: an attempt is
    counted, then the row either goes back to `pending` for another modem or --
    once it has burned `max_attempts` -- lands in `failed`. Treating a lost
    claim as a failed attempt rather than an instant failure keeps a merely
    slow or restarted agent from writing off a message it may have delivered.

    `locked_at IS NOT NULL` guards the sweep: a row is only stale if we can see
    when it was claimed, so rows predating the timestamp are left alone rather
    than reclaimed on the strength of a null.
    """
    rows = db.execute(
        select(MessageQueue)
        .where(
            MessageQueue.status == QueueStatus.sending,
            MessageQueue.locked_at.is_not(None),
            MessageQueue.locked_at < stale_lock_cutoff(stale_after_seconds),
        )
        .with_for_update(skip_locked=True),
    ).scalars().all()

    requeued = 0
    failed = 0
    affected_campaign_ids: set[uuid.UUID] = set()

    for row in rows:
        row.attempts += 1
        row.error_message = "Modem never reported a result; send timed out"
        row.locked_at = None
        row.modem_id = None
        row.execution_branch_id = None
        row.failover_route_id = None
        affected_campaign_ids.add(row.campaign_id)

        recipient = db.get(CampaignRecipient, row.campaign_recipient_id)

        if row.attempts >= row.max_attempts:
            row.status = QueueStatus.failed
            if recipient is not None:
                recipient.status = RecipientStatus.failed
            failed += 1
        else:
            row.status = QueueStatus.pending
            row.next_attempt_at = now_utc() + compute_backoff(row.attempts)
            if recipient is not None:
                recipient.status = RecipientStatus.pending
            requeued += 1

        db.add(
            MessageLog(
                branch_id=row.branch_id,
                campaign_id=row.campaign_id,
                queue_id=row.id,
                recipient_phone=recipient.phone_number if recipient else "",
                event_type="queue_stale_reclaimed",
                event_status=row.status.value,
                details_json={
                    "attempts": row.attempts,
                    "max_attempts": row.max_attempts,
                    "error_message": row.error_message,
                },
            ),
        )

    # Same ordering constraint as record_results: autoflush is off, so the
    # status writes must land before the campaign totals are recounted.
    db.flush()
    for campaign_id in affected_campaign_ids:
        recalculate_campaign_status(db, campaign_id)
    db.flush()

    return {"requeued": requeued, "failed": failed}


def recalculate_campaign_status(db: Session, campaign_id: uuid.UUID) -> CampaignStatus | None:
    """
    Derive a campaign's status from its queue rows. Safe to call any number of
    times (e.g. from a reconciliation pass) since it only reads current counts.
    """
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        return None

    # Cancellation is an operator decision, not a transient delivery result.
    # Keep it even when an already-claimed message reports its final result.
    if campaign.status == CampaignStatus.cancelled:
        return campaign.status

    pending_count = db.execute(
        select(func.count(MessageQueue.id)).where(
            MessageQueue.campaign_id == campaign_id,
            MessageQueue.status.in_([QueueStatus.pending, QueueStatus.sending]),
        ),
    ).scalar_one()
    failed_count = db.execute(
        select(func.count(MessageQueue.id)).where(
            MessageQueue.campaign_id == campaign_id,
            MessageQueue.status == QueueStatus.failed,
        ),
    ).scalar_one()
    sent_count = db.execute(
        select(func.count(MessageQueue.id)).where(
            MessageQueue.campaign_id == campaign_id,
            MessageQueue.status == QueueStatus.sent,
        ),
    ).scalar_one()

    if pending_count > 0:
        campaign.status = CampaignStatus.sending
    elif failed_count > 0:
        campaign.status = CampaignStatus.failed
    elif sent_count > 0:
        campaign.status = CampaignStatus.sent

    return campaign.status
