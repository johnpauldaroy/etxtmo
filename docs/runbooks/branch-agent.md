# Branch Agent Runbook

## Purpose
Branch agent connects branch modem/Gammu storage to central TextBlast API over outbound HTTPS.

## Setup
1. Install Python and create virtual environment in `/opt/textblast/branch-agent`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `infra/env/branch-agent.env.example` to `/opt/textblast/infra/env/branch-agent.env` and fill values.
4. Install and start `textblast-branch-agent.service`.

## Health checks
- Confirm heartbeat records under `/api/modems/heartbeats?branch_id=<id>`.
- Confirm queue drain by monitoring `/api/queue?branch_id=<id>`.
- Confirm inbound sync by checking `/api/incoming?branch_id=<id>`.

## Common failures
- `401` from API: update agent credentials.
- No jobs pulled: check branch assignment and modem registration.
- Jobs stuck in sending: inspect local Gammu DB (`outbox`, `sentitems`) and modem signal/power.
