#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup-directory>"
  exit 1
fi

SRC=$1
if [ ! -f "$SRC/postgres.sql" ]; then
  echo "postgres.sql not found in backup directory"
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL env var is required"
  exit 1
fi

psql "$DATABASE_URL" < "$SRC/postgres.sql"
cp -r "$SRC/env"/* /opt/textblast/infra/env/
cp "$SRC/nginx.conf" /etc/nginx/sites-enabled/textblast.conf
nginx -t
systemctl reload nginx

echo "Restore completed from $SRC"
