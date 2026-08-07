"""Stop pending messages for one or more campaigns from being sent.

Run manually, NOT on every deploy: cancelling is destructive to whatever is
in flight at the moment it runs, so an unattended copy on the startup path
would eventually kill a legitimate campaign during an unrelated hotfix.

    python -m app.scripts.cancel_queued --list
    python -m app.scripts.cancel_queued --campaign <uuid> [--campaign <uuid>...]
    python -m app.scripts.cancel_queued --campaign <uuid> --apply

Defaults to a dry run; nothing is written until --apply is passed.

Cancellation marks pending rows as `failed` with a recognisable
error_message, because QueueStatus has no `cancelled` member. Consequence
worth knowing: the campaign then reads as "Failed" in the UI, and the
retry-failed endpoint would re-queue these rows if anyone clicks it. Pass
--include-failed only if you accept re-cancelling genuine delivery
failures alongside them.
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import func, select

from app.core.database import SessionLocal, engine
from app.models import Campaign, CampaignRecipient, MessageLog, MessageQueue, QueueStatus, RecipientStatus
from app.services.audit import record_audit_event
from app.services.queue import recalculate_campaign_status

CANCEL_MARKER = "cancelled by operator"


def _counts_for(db, campaign_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(MessageQueue.status, func.count(MessageQueue.id))
        .where(MessageQueue.campaign_id == campaign_id)
        .group_by(MessageQueue.status),
    ).all()
    return {status.value: count for status, count in rows}


def list_campaigns(db) -> None:
    """Print every campaign that still has stoppable work, newest first."""
    campaign_ids = db.execute(
        select(MessageQueue.campaign_id)
        .where(MessageQueue.status.in_([QueueStatus.pending, QueueStatus.sending]))
        .group_by(MessageQueue.campaign_id),
    ).scalars().all()

    if not campaign_ids:
        print("No campaigns have pending or sending messages.")
        return

    campaigns = db.execute(
        select(Campaign).where(Campaign.id.in_(campaign_ids)).order_by(Campaign.created_at.desc()),
    ).scalars().all()

    print(f"{len(campaigns)} campaign(s) with stoppable work:\n")
    for campaign in campaigns:
        counts = _counts_for(db, campaign.id)
        print(f"  {campaign.name}")
        print(f"    id={campaign.id}  status={campaign.status.value}  created={campaign.created_at}")
        print(
            f"    pending={counts.get('pending', 0)}  sending={counts.get('sending', 0)}  "
            f"sent={counts.get('sent', 0)}  failed={counts.get('failed', 0)}",
        )
        print()


def cancel_campaign(db, campaign_id: uuid.UUID, *, apply: bool, include_failed: bool) -> int:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        print(f"  !! campaign {campaign_id} not found, skipping")
        return 0

    counts = _counts_for(db, campaign_id)
    in_flight = counts.get("sending", 0)
    already_sent = counts.get("sent", 0)

    target_statuses = [QueueStatus.pending]
    if include_failed:
        target_statuses.append(QueueStatus.failed)

    items = db.execute(
        select(MessageQueue).where(
            MessageQueue.campaign_id == campaign_id,
            MessageQueue.status.in_(target_statuses),
        ),
    ).scalars().all()

    print(f"  {campaign.name}  ({campaign_id})")
    print(f"    already sent : {already_sent:>6}  (cannot be recalled)")
    print(f"    in flight    : {in_flight:>6}  (handed to an agent; left untouched)")
    print(f"    to cancel    : {len(items):>6}")

    if not apply or not items:
        return len(items)

    for item in items:
        # Re-check under the same transaction: an agent may have claimed this
        # row between the SELECT above and now. Only pending rows are ours to
        # take; anything already flipped to sending stays with the agent.
        if item.status not in target_statuses:
            continue
        item.status = QueueStatus.failed
        item.error_message = CANCEL_MARKER
        item.attempts = item.max_attempts  # keeps the dispatch backoff path from reviving it
        item.locked_at = None
        item.modem_id = None
        item.execution_branch_id = None
        item.failover_route_id = None
        item.forced_execution_branch_id = None

        recipient = db.get(CampaignRecipient, item.campaign_recipient_id)
        if recipient is not None:
            recipient.status = RecipientStatus.failed

        db.add(
            MessageLog(
                branch_id=item.branch_id,
                campaign_id=item.campaign_id,
                queue_id=item.id,
                recipient_phone=recipient.phone_number if recipient else "",
                event_type="queue_cancelled",
                event_status=QueueStatus.failed.value,
                details_json={"reason": CANCEL_MARKER},
            ),
        )

    db.flush()
    record_audit_event(
        db,
        action="queue_campaign_cancelled",
        entity_type="campaign",
        entity_id=str(campaign_id),
        branch_id=campaign.branch_id,
        payload={"cancelled": len(items), "reason": CANCEL_MARKER},
    )
    recalculate_campaign_status(db, campaign_id)
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stop pending messages for campaigns.")
    parser.add_argument("--list", action="store_true", help="show campaigns with stoppable work, then exit")
    parser.add_argument("--campaign", action="append", default=[], metavar="UUID", help="campaign id (repeatable)")
    parser.add_argument("--apply", action="store_true", help="actually write; omit for a dry run")
    parser.add_argument("--include-failed", action="store_true", help="also mark existing failed rows as cancelled")
    args = parser.parse_args()

    print(f"database: {engine.url}\n")

    db = SessionLocal()
    try:
        if args.list or not args.campaign:
            list_campaigns(db)
            if not args.campaign:
                print("Pass --campaign <uuid> to cancel. Add --apply to write.")
                return

        try:
            campaign_ids = [uuid.UUID(value) for value in args.campaign]
        except ValueError as exc:
            raise SystemExit(f"invalid campaign id: {exc}") from exc

        mode = "APPLY" if args.apply else "DRY RUN (nothing will be written)"
        print(f"mode: {mode}\n")

        total = 0
        for campaign_id in campaign_ids:
            total += cancel_campaign(db, campaign_id, apply=args.apply, include_failed=args.include_failed)
            print()

        if args.apply:
            db.commit()
            print(f"Cancelled {total} message(s).")
        else:
            db.rollback()
            print(f"Dry run: {total} message(s) would be cancelled. Re-run with --apply to write.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
