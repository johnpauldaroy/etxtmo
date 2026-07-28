#!/bin/bash
set -e

cd /app
alembic upgrade head

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

nginx -g "daemon off;" &
NGINX_PID=$!

# If either process exits, bring the whole container down so the
# orchestrator restarts it instead of running half-alive.
wait -n "$UVICORN_PID" "$NGINX_PID"
EXIT_CODE=$?

kill "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
exit "$EXIT_CODE"
