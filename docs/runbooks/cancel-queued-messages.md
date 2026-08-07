# Runbook: stop queued messages from sending

For when a campaign was submitted by mistake and its messages have not all gone
out yet. Stops pending messages; does not delete the campaign or its history.

## What can and cannot be stopped

| Queue status | Can it be stopped? |
| --- | --- |
| `pending` | Yes. Not yet claimed by any branch agent. |
| `sending` | No. Already handed to an agent and possibly at the modem. |
| `sent` | No. Already delivered. |

The script reports all three counts before it writes anything, so you always see
how much was already beyond recall.

## Fastest possible stop

If a large campaign is actively going out and every second counts, stop the
branch agents first. Messages are only ever delivered when an agent polls for
work, so with the agents down nothing new leaves, and you can cancel calmly
afterwards.

## Procedure

Run from the VPS shell, or Dokploy's terminal for the app container.

```bash
# 1. List campaigns that still have stoppable work, and copy the campaign id.
docker exec -it <container> cancel-queued --list

# 2. Dry run. Writes nothing; confirm the counts look right.
docker exec -it <container> cancel-queued --campaign <uuid>

# 3. Apply.
docker exec -it <container> cancel-queued --campaign <uuid> --apply
```

Several campaigns at once: repeat `--campaign <uuid>` for each.

Without `--apply` the script always rolls back, so step 2 is safe to repeat.

## Known consequence: cancelled shows as "Failed"

`QueueStatus` has no `cancelled` member, so cancelled rows are marked `failed`
with `error_message = "cancelled by operator"`.

Two things follow from this:

1. The campaign displays as **Failed** in the UI, not "Cancelled" —
   indistinguishable at a glance from a genuine delivery failure.
2. **The retry-failed endpoint would re-send them.** `POST
   /queue/campaigns/{id}/retry-failed` re-queues every failed row for a
   campaign, cancelled ones included. Do not run retry-failed on a campaign you
   cancelled.

The script sets `attempts = max_attempts` as a guard so the automatic backoff
path cannot revive a cancelled message on its own, but an explicit
retry-failed click resets that.

Removing this footgun properly means adding a `cancelled` value to the
`QueueStatus` enum (an Alembic migration, since it is a Postgres `ENUM` type)
and excluding it from the retry paths. Worth doing if cancelling becomes
routine.

## Why this is not automatic

The script is intentionally not called from `docker-entrypoint.sh`. Cancelling
is destructive to whatever is in flight at the moment it runs; on the startup
path it would execute on every deploy and would eventually kill a legitimate
campaign during an unrelated hotfix.

## Verification

After applying, confirm nothing is left to send:

```bash
docker exec -it <container> cancel-queued --list
```

The cancelled campaign should no longer appear, or should show `pending=0`.
Each cancelled message also writes a `queue_cancelled` row to `message_logs`,
and the run writes one `queue_campaign_cancelled` audit event.
