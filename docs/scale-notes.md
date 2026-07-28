# Scale Trigger Notes

Current implementation uses DB-backed queue workers (API + dispatch worker + branch agents).

Move to Celery + Redis when either condition is true for 2+ consecutive weeks:
- Sustained throughput exceeds ~100,000 SMS/month.
- P95 queue wait time breaches agreed SLA repeatedly.

Migration approach:
1. Keep database schema unchanged.
2. Move queue-pick and retry execution into Celery workers.
3. Keep branch-agent API contracts stable.
4. Add Redis-backed rate control per branch/modem.
