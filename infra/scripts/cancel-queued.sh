#!/bin/bash
# Stop pending messages for one or more campaigns, inside the running container.
#
# Deliberately NOT part of docker-entrypoint.sh: cancelling is destructive to
# whatever happens to be in flight when it runs, so on the startup path it
# would eventually kill a legitimate campaign during an unrelated redeploy.
#
# Usage (from the VPS, or Dokploy's terminal for the app):
#
#   # 1. see what is stoppable, and copy the campaign id
#   docker exec -it <container> /app/../infra/scripts/cancel-queued.sh --list
#
#   # 2. dry run, confirm the counts look right
#   docker exec -it <container> /app/../infra/scripts/cancel-queued.sh --campaign <uuid>
#
#   # 3. write it
#   docker exec -it <container> /app/../infra/scripts/cancel-queued.sh --campaign <uuid> --apply
#
# If this file is not in the image, the same thing works directly:
#   docker exec -it <container> python -m app.scripts.cancel_queued --list

set -e

cd /app
export PYTHONPATH=/app

exec python -m app.scripts.cancel_queued "$@"
