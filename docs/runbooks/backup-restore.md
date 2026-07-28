# Backup and Recovery Runbook

## Backup
1. Export API env and set `DATABASE_URL`.
2. Run:
   ```bash
   bash infra/scripts/backup.sh /opt/textblast/backups
   ```
3. Confirm directory contains `postgres.sql`, `env/`, and `nginx.conf`.

## Restore
1. Export `DATABASE_URL` for target restore DB.
2. Run:
   ```bash
   bash infra/scripts/restore.sh /opt/textblast/backups/<timestamp>
   ```
3. Validate:
- `systemctl status textblast-api.service`
- `curl http://127.0.0.1:8000/health`
- Nginx config test passes

## Drill cadence
- Monthly restore drill in staging.
- Quarterly branch-node reconnect test after restore.
