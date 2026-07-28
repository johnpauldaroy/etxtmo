# Dokploy Deployment Runbook

Deploys `api-core` and `web-app` as **one** Dokploy application, built from
the combined `Dockerfile` at the repo root. Inside the container, nginx
serves the built frontend and reverse-proxies `/api/` to a uvicorn process
running on the same container's loopback (`127.0.0.1:8000`) — both behind a
single domain, `etxtmo.barbazampc.cloud`.

This replaced an earlier two-app split (separate `api-core`/`web-app`
Dokploy apps on different subdomains) that hit a persistent "Bad Gateway"
from Traefik being unable to route to a healthy, correctly-serving container
across the two apps' Docker networks — confirmed via `curl` from inside the
container itself, which worked fine. Running both processes in one
container removes that network hop entirely: nginx talks to uvicorn over
localhost, no Traefik-to-container routing between two separate services is
needed for the API path.

`branch-agent` is **not** part of this procedure — it must run on a physical
PC next to each branch's GSM modem (see
`infra/scripts/windows/setup-branch-agent.ps1`), since Dokploy containers
have no USB/serial device access.

## 1. Provision the database

1. In Dokploy, create a **PostgreSQL** database service (Databases → Create →
   PostgreSQL). Note the generated internal connection details: host, port,
   user, password, database name.
2. Dokploy databases are reachable from other Dokploy apps/services on the
   same project's internal network by service name — confirm the internal
   hostname Dokploy assigns (shown on the database's detail page).

## 2. Deploy the combined app

1. Dokploy → **Create Application** → connect this Git repository.
2. **Build settings** (Dokploy → app → General → Build Type → Dockerfile):
   - **Dockerfile Path**: `Dockerfile`
   - **Docker Context Path**: `.` (repo root — the Dockerfile copies from
     both `api-core/` and `web-app/`, so the context must be the root, not a
     subdirectory)
3. **Build Time Arguments** (Dokploy → app → Environment → Build Time
   Arguments — a separate section from the regular Environment Variables
   box):
   ```
   VITE_API_URL=https://etxtmo.barbazampc.cloud
   ```
   `VITE_API_URL` is compiled into the JS bundle at build time, not read at
   runtime. Since the API is now served from the same domain under `/api/`,
   this should be the app's own domain, not a separate API subdomain.
4. **Environment variables** (Dokploy → app → Environment → the regular
   Environment Variables box, not Build Time Arguments):
   ```
   APP_NAME=e-txtmo API
   ENVIRONMENT=production
   DATABASE_URL=postgresql+psycopg2://<db_user>:<db_password>@<db_internal_host>:5432/<db_name>
   JWT_SECRET_KEY=<generate a long random value>
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=120
   CORS_ORIGINS=https://etxtmo.barbazampc.cloud
   SYSTEM_TIMEZONE=Asia/Manila
   SCHEDULER_ENABLED=true
   ```
   Generate `JWT_SECRET_KEY` with `openssl rand -hex 32` — never reuse the
   dev value. `API_HOST`/`API_PORT` are not needed here; the entrypoint
   script always binds uvicorn to `127.0.0.1:8000` internally.
5. **Domain**: Dokploy → app → Domains → add `etxtmo.barbazampc.cloud`,
   container port `80`, enable HTTPS (Dokploy provisions Let's Encrypt
   automatically).
6. **Deploy**. The entrypoint script runs `alembic upgrade head`, then
   starts uvicorn and nginx together — schema migrations ship automatically
   with every deploy, no separate migration step needed.
7. Verify:
   - `curl https://etxtmo.barbazampc.cloud/health` → `{"status":"ok"}`
   - Open `https://etxtmo.barbazampc.cloud` — the e-txtmo login screen
     should load and successfully call `/api/...` (check the browser
     network tab for same-origin `/api/` requests, not `localhost` or a
     different domain).

## 3. Bootstrap the first superuser

The API has no seeded users on a fresh database. Create the first superuser
directly:

```bash
curl -X POST https://etxtmo.barbazampc.cloud/api/auth/users \
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
`https://etxtmo.barbazampc.cloud` with these credentials afterward.

## 4. Create branches and branch-agent API keys

1. In the web app: Administration → Branches → create each branch.
2. Administration → Access control → API Keys tab → generate a key per
   branch if external systems will call `POST /api/v1/sms/send`.
3. For each branch's physical modem PC, run
   `infra/scripts/windows/setup-branch-agent.ps1` with `-ApiBaseUrl
   https://etxtmo.barbazampc.cloud` (not localhost) and that branch's real
   `-BranchId`, `-ApiUsername`, `-ApiPassword`.

## Notes

- This Dockerfile was written against this project's dependency files but
  has not been build-tested locally (no Docker available in the authoring
  environment) — the first Dokploy deploy of the combined image is the
  first real build. If it fails, check the Dokploy build logs first.
- `SCHEDULER_ENABLED=true` runs the recurring-rule scheduler as a background
  asyncio task inside the uvicorn process itself (see
  `api-core/app/main.py::scheduler_loop`) — no separate worker container is
  required.
- `docker-entrypoint.sh` runs uvicorn and nginx as two background jobs and
  waits on whichever exits first, then kills the other and exits with that
  process's status — if either crashes, the whole container exits so Dokploy
  restarts it, instead of running half-alive with a dead API behind a
  seemingly-healthy nginx.
- If you ever need `api-core` and `web-app` reachable as fully independent
  services again (e.g. scaling the API separately from the frontend), the
  split-app Dockerfiles can be recreated from `infra/nginx/textblast.conf`
  and this combined `Dockerfile` as references — but confirm Traefik routing
  between separate Dokploy apps works on your VPS before relying on it again.
