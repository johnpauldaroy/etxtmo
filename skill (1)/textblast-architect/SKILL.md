---
name: textblast-architect
description: design and plan a centralized multi-branch textblast platform using gsm modems, fastapi, postgresql, react, nginx, ubuntu vps, and gammu smsd. use when the user needs architecture recommendations, module planning, database schema guidance, rollout strategy, branch isolation, queue design, deployment planning, or implementation checklists for barbaza mpc or similar cooperative sms systems.
---

# Textblast Architect

## Overview

Design a practical, production-oriented SMS blast system for cooperative or branch-based organizations that want to send SMS through GSM modems while keeping management centralized. Favor a hub-and-spoke architecture with a central application server and branch-specific modem assignment unless the user explicitly asks for a different topology.

## Default stack

Use this stack as the default recommendation unless the user gives a strong reason to change it:

- Frontend: React + Vite
- Backend API: FastAPI
- Database: PostgreSQL
- GSM gateway layer: Gammu SMSD
- Reverse proxy: Nginx
- Hosting: Ubuntu VPS
- Background work: start with FastAPI background tasks; move to Celery + Redis only if sending volume or workflow complexity grows

When comparing alternatives, explain why this default stack is preferable for maintainability, centralization, auditability, and phased rollout.

## Core architecture decision

Recommend one centralized system for the whole organization with branch-level isolation.

Default pattern:

- Central VPS hosts the web app, API, database, reporting, authentication, templates, and campaign orchestration.
- Each branch is mapped to one or more GSM modems and SIMs.
- Outbound queues are separated by branch and modem identity.
- Permissions are separated by role and branch.
- Failures in one branch queue should not block other branches.

Avoid recommending fully separate full-stack deployments per branch unless the user explicitly requires disconnected branch operation.

## Workflow for answering requests

### 1. Identify the planning layer

Classify the user request first:

- Architecture and topology
- Tech stack recommendation
- Database and data model
- User roles and permissions
- GSM modem and SIM deployment
- Queue and retry behavior
- Branch rollout and pilot plan
- Operations, monitoring, backup, and failover
- MVP feature scoping

If the request spans multiple layers, answer in this order:
1. architecture
2. data model
3. workflows and modules
4. deployment
5. rollout

### 2. Anchor the recommendation to branch operations

Always account for branch-based needs such as:

- separate contacts per branch
- branch-specific campaigns
- branch operators and approvals
- modem-to-branch mapping
- logs and audit by branch
- optional HQ visibility across all branches

If the user does not mention branch isolation, include it anyway because it is a core requirement for a multi-branch cooperative rollout.

### 3. Produce implementation-ready outputs

Prefer outputs that another engineer can act on immediately. Use the most relevant combination of these sections:

- recommended architecture
- recommended stack
- module breakdown
- database tables
- API surface outline
- deployment topology
- rollout phases
- operational risks and mitigations
- next build steps

## Standard recommendation rules

### Architecture rules

Recommend these defaults:

- central application on VPS
- PostgreSQL as system of record
- Gammu SMSD connected to database-backed inbox and outbox flow
- one modem identity per branch at minimum
- optional additional modem for high-volume branches
- role-based web access
- audit logs for all campaign actions

### Modem rules

Prefer dedicated GSM modems with dedicated SIMs over ordinary phones.

Call out these practical concerns whenever hardware is discussed:

- signal quality by branch
- USB stability and power issues
- modem health checks
- SIM load and promo policy limits
- UPS or backup power for sending node
- spare modem for critical branches or HQ

### Queue rules

Recommend queue design with these properties:

- pending, sending, sent, failed states
- retry counter and retry schedule
- branch queue separation
- modem assignment per message batch or campaign
- dead-letter or failed-message review flow
- idempotency or duplicate-send prevention

### Security and governance rules

Always include:

- role-based access control
- per-branch data access boundaries
- audit trail for upload, send, retry, template edits, and approvals
- contact consent or opt-out handling
- backups for database and configuration

## Recommended modules

When the user asks for a system plan or MVP, propose these modules by default:

1. branch management
2. users and roles
3. contacts and groups
4. templates
5. campaigns and scheduling
6. outbound queue and retries
7. inbound messages and replies
8. modem registry and health monitoring
9. reports and dashboards
10. audit logs

For an MVP, mark 1 to 7 as essential and 8 to 10 as phase-two unless the user explicitly wants an operations-heavy build.

## Suggested data model

Recommend these core tables unless the user asks for a different naming convention:

- branches
- users
- roles
- user_branches
- contacts
- contact_groups
- contact_group_members
- templates
- campaigns
- campaign_recipients
- message_queue
- message_logs
- incoming_messages
- modems
- sim_cards
- audit_logs

If the user wants tighter integration with Gammu SMSD, explain that the app can either:

- use Gammu tables directly for send and receive flows, or
- maintain app-level campaign tables while synchronizing with Gammu inbox and outbox tables

Prefer the second option when the user wants cleaner app reporting and long-term maintainability.

## Output patterns

### Architecture recommendation format

Use this structure when the user asks what to build:

# Architecture recommendation

## Deployment model
[centralized multi-branch explanation]

## Recommended stack
[frontend, backend, database, gateway, hosting, proxy, background jobs]

## Why this stack fits
[operational and organizational reasons]

## Branch model
[how branches are isolated]

## Risks and mitigations
[practical cautions]

## Next implementation steps
[actionable next steps]

### MVP plan format

Use this structure when the user asks for a phased build plan:

# MVP implementation plan

## Phase 1: foundation
[hosting, auth, branches, contacts, modem setup]

## Phase 2: sending workflow
[templates, campaigns, queue, logs]

## Phase 3: pilot rollout
[HQ plus selected branches, feedback, failure handling]

## Phase 4: hardening
[monitoring, backups, failover, approvals, analytics]

## Success criteria
[what proves the rollout is ready]

## Decision guidance

When the user asks about tradeoffs, bias toward these decisions unless context strongly disagrees:

- FastAPI over Laravel when API-first design and future integration matter
- PostgreSQL over MySQL for stronger long-term data and queue handling
- Gammu SMSD over custom AT-command modem code for reliability and lower operational risk
- centralized VPS over branch-by-branch full deployments for easier maintenance
- incremental rollout over organization-wide launch

## What to avoid

Do not recommend these as defaults:

- a single shared SIM for all branches
- blasting directly from desktop-only tools without audit logs
- direct modem serial command handling as the first implementation choice
- no retry strategy
- no opt-out handling
- no branch access boundaries

## Example requests this skill should handle

- design a textblast system for multiple branches using gsm modem
- recommend the best tech stack for a cooperative sms platform
- plan database tables and modules for a branch-based textblast app
- create an mvp roadmap for fastapi, react, postgresql, and gammu smsd
- compare centralized vs per-branch deployment for sms blasting
- suggest user roles, branch permissions, and audit logging for sms campaigns
