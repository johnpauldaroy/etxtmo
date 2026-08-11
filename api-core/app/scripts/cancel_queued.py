"""Stop pending messages for one or more campaigns from being sent.

Run manually, NOT on every deploy: cancelling is destructive to whatever is
in flight at the moment it runs, so an unattended copy on the startup path
would eventually kill a legitimate campaign during an unrelated hotfix.

    python -m app.scripts.cancel_queued --list
    python -m app.scripts.cancel_queued --campaign <uuid> [--campaign <uuid>...]
    python -m app.scripts.cancel_queued --campaign <uuid> --apply

Messages sent through the SMS gateway API get one campaign each, so an API
key that sent 2805 messages is 2805 single-recipient campaigns, not one
campaign with 2805 recipients. Selecting those by --campaign is impractical;
use --api-key instead, which matches exactly the grouping the "API — <label>"
rows use in the UI:

    python -m app.scripts.cancel_queued --list-api-keys
    python -m app.scripts.cancel_queued --api-key <uuid> --apply

Defaults to a dry run; nothing is written until --apply is passed.

Cancellation marks pending rows as `cancelled`, so they remain visible in
delivery history but cannot be picked up by an agent or retry action. Pass
--include-failed only if you also want existing failures marked as cancelled.
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import func, select

from app.api.routes.campaigns import _api_key_id_from_campaign
from app.core.database import SessionLocal, engine
from app.models import (
    ApiKey,
    Campaign,
    CampaignRecipient,
    CampaignStatus,
    MessageLog,
    MessageQueue,
    QueueStatus,
    RecipientStatus,
)
from app.services.audit import record_audit_event

CANCEL_MARKER = "cancelled by operator"


def _campaigns_with_stoppable_work(db) -> list[Campaign]:
    campaign_ids = db.execute(
        select(MessageQueue.campaign_id)
        .where(MessageQueue.status.in_([QueueStatus.pending, QueueStatus.sending]))
        .group_by(MessageQueue.campaign_id),
    ).scalars().all()
    if not campaign_ids:
        return []
    return list(
        db.execute(
            select(Campaign).where(Campaign.id.in_(campaign_ids)).order_by(Campaign.created_at.desc()),
        ).scalars(),
    )


def campaign_ids_for_api_key(db, api_key_id: uuid.UUID) -> list[uuid.UUID]:
    """Campaigns created by one API key.

    Groups on metadata_json.api_key_id via the same helper the campaigns API
    uses, so this matches the "API - <label>" rows in the UI exactly rather
    than guessing from campaign names.
    """
    return [
        campaign.id
        for campaign in db.execute(select(Campaign)).scalars()
        if _api_key_id_from_campaign(campaign) == api_key_id
    ]


def list_api_keys(db) -> None:
    """Print API keys that still have stoppable work, grouped as the UI groups them."""
    grouped: dict[uuid.UUID, list[Campaign]] = {}
    for campaign in _campaigns_with_stoppable_work(db):
        api_key_id = _api_key_id_from_campaign(campaign)
        if api_key_id is not None:
            grouped.setdefault(api_key_id, []).append(campaign)

    if not grouped:
        print("No API keys have campaigns with pending or sending messages.")
        return

    labels = dict(db.execute(select(ApiKey.id, ApiKey.label).where(ApiKey.id.in_(list(grouped)))).all())

    print(f"{len(grouped)} API key(s) with stoppable work:\n")
    for api_key_id, campaigns in sorted(
        grouped.items(),
        key=lambda item: max(c.created_at for c in item[1]),
        reverse=True,
    ):
        pending = db.execute(
            select(func.count(MessageQueue.id)).where(
                MessageQueue.campaign_id.in_([c.id for c in campaigns]),
                MessageQueue.status == QueueStatus.pending,
            ),
        ).scalar_one()
        sending = db.execute(
            select(func.count(MessageQueue.id)).where(
                MessageQueue.campaign_id.in_([c.id for c in campaigns]),
                MessageQueue.status == QueueStatus.sending,
            ),
        ).scalar_one()
        print(f"  API - {labels.get(api_key_id) or f'Key {str(api_key_id)[:8]}'}")
        print(f"    api_key_id={api_key_id}")
        print(f"    campaigns={len(campaigns)}  pending={pending}  sending={sending}")
        print()
    print("Cancel one with:  cancel-queued --api-key <api_key_id> --apply")


def _counts_for(db, campaign_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(MessageQueue.status, func.count(MessageQueue.id))
        .where(MessageQueue.campaign_id == campaign_id)
        .group_by(MessageQueue.status),
    ).all()
    return {status.value: count for status, count in rows}


def list_campaigns(db, limit: int = 20) -> None:
    """Print campaigns that still have stoppable work, newest first."""
    campaigns = _campaigns_with_stoppable_work(db)

    if not campaigns:
        print("No campaigns have pending or sending messages.")
        return

    total = len(campaigns)
    api_backed = sum(1 for c in campaigns if _api_key_id_from_campaign(c) is not None)
    print(f"{total} campaign(s) with stoppable work.")
    if api_backed:
        print(
            f"{api_backed} of them are single-message API campaigns -- "
            f"use --list-api-keys to cancel those by API key instead.",
        )
    if total > limit:
        print(f"Showing the {limit} most recent; pass --limit N for more.\n")
    else:
        print()

    for campaign in campaigns[:limit]:
        counts = _counts_for(db, campaign.id)
        print(f"  {campaign.name}")
        print(f"    id={campaign.id}  status={campaign.status.value}  created={campaign.created_at}")
        print(
            f"    pending={counts.get('pending', 0)}  sending={counts.get('sending', 0)}  "
            f"sent={counts.get('sent', 0)}  failed={counts.get('failed', 0)}",
        )
        print()


def cancel_campaign(db, campaign_id: uuid.UUID, *, apply: bool, include_failed: bool, quiet: bool = False) -> int:
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

    if not quiet:
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
        item.status = QueueStatus.cancelled
        item.error_message = CANCEL_MARKER
        item.attempts = item.max_attempts  # keeps the dispatch backoff path from reviving it
        item.locked_at = None
        item.modem_id = None
        item.execution_branch_id = None
        item.failover_route_id = None
        item.forced_execution_branch_id = None

        recipient = db.get(CampaignRecipient, item.campaign_recipient_id)
        if recipient is not None:
            recipient.status = RecipientStatus.cancelled

        db.add(
            MessageLog(
                branch_id=item.branch_id,
                campaign_id=item.campaign_id,
                queue_id=item.id,
                recipient_phone=recipient.phone_number if recipient else "",
                event_type="queue_cancelled",
                event_status=QueueStatus.cancelled.value,
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
    campaign.status = CampaignStatus.cancelled
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stop pending messages for campaigns.")
    parser.add_argument("--list", action="store_true", help="show campaigns with stoppable work, then exit")
    parser.add_argument("--list-api-keys", action="store_true", help="show API keys with stoppable work, then exit")
    parser.add_argument("--campaign", action="append", default=[], metavar="UUID", help="campaign id (repeatable)")
    parser.add_argument("--api-key", action="append", default=[], metavar="UUID", help="cancel every campaign from this API key (repeatable)")
    parser.add_argument("--limit", type=int, default=20, help="how many campaigns --list prints (default 20)")
    parser.add_argument("--apply", action="store_true", help="actually write; omit for a dry run")
    parser.add_argument("--include-failed", action="store_true", help="also mark existing failed rows as cancelled")
    args = parser.parse_args()

    print(f"database: {engine.url}\n")

    db = SessionLocal()
    try:
        if args.list_api_keys:
            list_api_keys(db)
            return

        if args.list or not (args.campaign or args.api_key):
            list_campaigns(db, limit=args.limit)
            if not (args.campaign or args.api_key):
                print("\nPass --campaign <uuid> or --api-key <uuid> to cancel. Add --apply to write.")
                return

        try:
            campaign_ids = [uuid.UUID(value) for value in args.campaign]
            api_key_ids = [uuid.UUID(value) for value in args.api_key]
        except ValueError as exc:
            raise SystemExit(f"invalid id: {exc}") from exc

        for api_key_id in api_key_ids:
            matched = campaign_ids_for_api_key(db, api_key_id)
            if not matched:
                print(f"  !! no campaigns found for API key {api_key_id}")
                continue
            print(f"API key {api_key_id}: {len(matched)} campaign(s)")
            campaign_ids.extend(matched)

        # Same campaign reachable via both selectors; cancel it once.
        campaign_ids = list(dict.fromkeys(campaign_ids))

        mode = "APPLY" if args.apply else "DRY RUN (nothing will be written)"
        print(f"\nmode: {mode}")
        print(f"campaigns selected: {len(campaign_ids)}\n")

        # Printing five lines per campaign is unreadable past a handful, and
        # API sends routinely select thousands.
        quiet = len(campaign_ids) > 10
        total = 0
        for index, campaign_id in enumerate(campaign_ids, start=1):
            total += cancel_campaign(
                db,
                campaign_id,
                apply=args.apply,
                include_failed=args.include_failed,
                quiet=quiet,
            )
            if quiet and index % 500 == 0:
                print(f"  ... {index}/{len(campaign_ids)} campaigns processed")
            elif not quiet:
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
