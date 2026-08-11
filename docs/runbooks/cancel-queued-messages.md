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

For ordinary campaigns, the **Cancel** action in Campaign deliveries performs
the same operation and reports any messages that were already in flight.

## Fastest possible stop

If a large campaign is actively going out and every second counts, stop the
branch agents first. Messages are only ever delivered when an agent polls for
work, so with the agents down nothing new leaves, and you can cancel calmly
afterwards.

## Procedure

Run these **inside the container** -- Dokploy's Docker Terminal for the app is
already a shell in the container, so there is no `docker exec` prefix there.
From the VPS host instead, prefix each with `docker exec -it <container>`.

### API messages (the "API - <label>" rows)

Each message sent through the SMS gateway API creates its **own** campaign, so
an API key showing "2805 API messages" is 2805 single-recipient campaigns.
Select those by API key, which is exactly how the UI groups them:

```bash
# 1. List API keys with stoppable work, and copy the api_key_id.
cancel-queued --list-api-keys

# 2. Dry run. Writes nothing; confirm the campaign and pending counts.
cancel-queued --api-key <api_key_id>

# 3. Apply.
cancel-queued --api-key <api_key_id> --apply
```

### Ordinary campaigns

```bash
cancel-queued --list
cancel-queued --campaign <uuid>            # dry run
cancel-queued --campaign <uuid> --apply
```

Several at once: repeat `--campaign` or `--api-key` for each. The two can be
mixed in one run, and a campaign selected twice is only cancelled once.

Without `--apply` the script always rolls back, so the dry run is safe to
repeat as often as you like.

If `cancel-queued` is not found, the deployed image predates it; use
`cd /app && PYTHONPATH=/app python -m app.scripts.cancel_queued` instead.

## Cancelled status

Cancelled campaigns and their stopped recipients display as **Cancelled** in
the UI. Cancelled queue rows are separate from genuine failures, so neither the
automatic retry path nor **Resend all failed** can queue them again.

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
