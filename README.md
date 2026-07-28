# TextBlast

Centralized multi-branch TextBlast platform with branch-local modem nodes.

## Services
- `api-core`: FastAPI API, RBAC, queue, scheduler, approvals, audit.
- `web-app`: React + Vite control panel.
- `branch-agent`: Branch-side modem sync agent with Gammu DB integration.
- `infra`: Nginx, systemd, env templates, deploy/backup scripts.

## Core workflow
1. Create branches, users, and branch assignments.
2. Import contacts and create templates.
3. Create campaign and submit.
4. Approval policy decides whether campaign queues immediately or waits for approval.
5. Branch agent pulls queue jobs, writes to modem outbox, syncs statuses and inbound replies.

## Local startup (high level)
1. Start PostgreSQL and configure `api-core/.env`.
2. Install API dependencies and run migrations in `api-core`.
3. Start API: `uvicorn app.main:app --reload`.
4. Start web app: `npm run dev` in `web-app`.
5. Configure and run branch agent if testing branch-node flow.
