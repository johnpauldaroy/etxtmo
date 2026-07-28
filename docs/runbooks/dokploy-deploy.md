# Dokploy Deployment Runbook

Deploys `api-core` and `web-app` as two separate Dokploy applications on your
VPS, each built from its own `Dockerfile`. `branch-agent` is **not** part of
this procedure — it must run on a physical PC next to each branch's GSM
modem (see `infra/scripts/windows/setup-branch-agent.ps1`), since Dokploy
containers have no USB/serial device access.

Replace `api.YOURDOMAIN.com` and `app.YOURDOMAIN.com` below with your real
domains, both already pointed at your VPS's IP via DNS A records.

## 1. Provision the database

1. In Dokploy, create a **PostgreSQL** database service (Databases → Create →
   PostgreSQL). Note the generated internal connection details: host, port,
   user, password, database name.
2. Dokploy databases are reachable from other Dokploy apps on the same
   project's internal network by service name — confirm the internal
   hostname Dokploy assigns (shown on the database's detail page).

## 2. Deploy `api-core`

1. Dokploy → **Create Application** → connect this Git repository.
2. **Build settings** (Dokploy → app → General → Build Type → Dockerfile):
   - **Dockerfile Path**: `api-core/Dockerfile`
   - **Docker Context Path**: `api-core`
3. **Environment variables** (Dokploy → app → Environment):
   ```
   APP_NAME=e-txtmo API
   ENVIRONMENT=production
   DATABASE_URL=postgresql+psycopg2://<db_user>:<db_password>@<db_internal_host>:5432/<db_name>
   JWT_SECRET_KEY=<generate a long random value>
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=120
   API_HOST=0.0.0.0
   API_PORT=8000
   CORS_ORIGINS=https://app.YOURDOMAIN.com
   SYSTEM_TIMEZONE=Asia/Manila
   SCHEDULER_ENABLED=true
   ```
   Generate `JWT_SECRET_KEY` with `openssl rand -hex 32` — never reuse the
   dev value.
4. **Domain**: Dokploy → app → Domains → add `api.YOURDOMAIN.com`, container
   port `8000`, enable HTTPS (Dokploy provisions Let's Encrypt automatically).
5. **Deploy**. The container's start command runs `alembic upgrade head`
   before starting `uvicorn`, so the database schema is created/migrated
   automatically on every deploy — no separate migration step needed.
6. Verify: `curl https://api.YOURDOMAIN.com/health` → `{"status":"ok"}`.

## 3. Deploy `web-app`

1. Dokploy → **Create Application** → same repository.
2. **Build settings** (Dokploy → app → General → Build Type → Dockerfile):
   - **Dockerfile Path**: `web-app/Dockerfile`
   - **Docker Context Path**: `web-app`
3. **Build Time Arguments** (Dokploy → app → Environment → Build Time
   Arguments — a separate section from the regular Environment Variables
   box):
   ```
   VITE_API_URL=https://api.YOURDOMAIN.com
   ```
   `VITE_API_URL` is compiled into the JS bundle at build time, not read at
   runtime — it must go in **Build Time Arguments** (which Dokploy passes as
   Docker `--build-arg`), not the regular environment variables box, or the
   frontend will silently keep calling `localhost`.
4. **Domain**: Dokploy → app → Domains → add `app.YOURDOMAIN.com`, container
   port `80`, enable HTTPS.
5. **Deploy**.
6. Verify: open `https://app.YOURDOMAIN.com` — the e-txtmo login screen
   should load and successfully call the API (check the browser network tab
   for `api.YOURDOMAIN.com` requests, not `localhost`).

## 4. Bootstrap the first superuser

The API has no seeded users on a fresh database. Create the first superuser
directly:

```bash
curl -X POST https://api.YOURDOMAIN.com/api/auth/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "username": "admin",
    "full_name": "Admin",
    "password": "<choose a strong password>",
    "is_superuser": true
  }'
```

This only works while the `users` table is empty (see
`api-core/app/api/routes/auth.py::create_user` — after the first user
exists, creating more requires an authenticated superuser token). Log in at
`https://app.YOURDOMAIN.com` with these credentials afterward.

## 5. Create branches and branch-agent API keys

1. In the web app: Administration → Branches → create each branch.
2. Administration → Access control → API Keys tab → generate a key per
   branch if external systems will call `POST /api/v1/sms/send`.
3. For each branch's physical modem PC, run
   `infra/scripts/windows/setup-branch-agent.ps1` with `-ApiBaseUrl
   https://api.YOURDOMAIN.com` (not localhost) and that branch's real
   `-BranchId`, `-ApiUsername`, `-ApiPassword`.

## Notes

- These Dockerfiles were written against this project's dependency files but
  have not been build-tested locally (no Docker available in the authoring
  environment) — the first Dokploy deploy is the first real build. If it
  fails, check the Dokploy build logs first; `api-core/Dockerfile` and
  `web-app/Dockerfile` are simple, standard images and any failure is most
  likely a missing env var or a dependency version conflict, not a
  structural issue.
- `SCHEDULER_ENABLED=true` runs the recurring-rule scheduler as a background
  asyncio task inside the `api-core` process itself (see
  `api-core/app/main.py::scheduler_loop`) — no separate worker container is
  required for Dokploy.
- Re-deploying `api-core` always re-runs `alembic upgrade head` first, so
  schema changes ship automatically with each deploy.
