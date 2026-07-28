#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT=${1:-/opt/textblast/backups}
TS=$(date +"%Y%m%d_%H%M%S")
DEST="$BACKUP_ROOT/$TS"
mkdir -p "$DEST"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL env var is required"
  exit 1
fi

pg_dump "$DATABASE_URL" > "$DEST/postgres.sql"
cp -r /opt/textblast/infra/env "$DEST/env"
cp /etc/nginx/sites-enabled/textblast.conf "$DEST/nginx.conf"

echo "Backup completed: $DEST"
