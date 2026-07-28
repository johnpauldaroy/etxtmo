# Deployment Runbook

## 1. Provision VPS
- Ubuntu 22.04+
- Install PostgreSQL, Nginx, Python 3.12, Node 20+, npm

## 2. Application setup
- Clone repository to `/opt/textblast`
- Copy `infra/env/api-core.env.example` to `/opt/textblast/infra/env/api-core.env`
- Copy `infra/nginx/textblast.conf` to `/etc/nginx/sites-enabled/textblast.conf`
- Run `infra/scripts/deploy.sh`

## 3. Services
Enable and start:
- `textblast-api.service`
- `textblast-scheduler.service`
- `textblast-dispatch.service`
- `textblast-branch-agent.service` (on each branch node)

## 4. Initial bootstrap
- Create first superuser using `POST /api/auth/users`
- Create branches and assign users to branches
- Register branch agents for each branch modem node
