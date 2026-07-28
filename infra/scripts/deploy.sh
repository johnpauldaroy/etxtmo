#!/usr/bin/env bash
set -euo pipefail

ROOT=/opt/textblast

cd "$ROOT/api-core"
python3 -m venv .venv || true
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.workers.seed

cd "$ROOT/web-app"
npm ci
npm run build

systemctl daemon-reload
systemctl restart textblast-api.service
systemctl restart textblast-scheduler.service
systemctl restart textblast-dispatch.service
nginx -t
systemctl reload nginx

echo "Deployment complete"
