# Combined single-container deploy: nginx serves the web-app SPA and
# reverse-proxies /api/ to a uvicorn process running in the same container.
# Exists because Dokploy's cross-app Traefik-to-container routing was
# unreliable for a two-app split on this VPS; running both under one nginx
# on one domain avoids that hop entirely (see docs/runbooks/dokploy-deploy.md).

FROM node:20-slim AS web-build

WORKDIR /web

ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

COPY web-app/package.json web-app/package-lock.json ./
RUN npm ci

COPY web-app/ ./
RUN npm run build

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    nginx \
    zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY api-core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api-core/ .

COPY --from=web-build /web/dist /var/www/etxtmo

RUN rm -f /etc/nginx/sites-enabled/default
COPY nginx.combined.conf /etc/nginx/conf.d/default.conf

# Standalone branch-agent package for branch PCs to download, so they don't
# need a full git clone of this repo (see infra/scripts/windows/bootstrap-branch.ps1).
# Rebuilt from source on every image build, so it's always in sync with the code.
COPY branch-agent/agent /tmp/branch-agent-pkg/branch-agent/agent
COPY branch-agent/requirements.txt /tmp/branch-agent-pkg/branch-agent/requirements.txt
COPY branch-agent/README.md /tmp/branch-agent-pkg/branch-agent/README.md
COPY infra/scripts/windows/setup-branch-agent.ps1 /tmp/branch-agent-pkg/scripts/setup-branch-agent.ps1
COPY infra/scripts/windows/bootstrap-branch.ps1 /tmp/branch-agent-pkg/scripts/bootstrap-branch.ps1
COPY infra/scripts/windows/onboard-branch.ps1 /tmp/branch-agent-pkg/scripts/onboard-branch.ps1
RUN mkdir -p /var/www/etxtmo-downloads \
    && cd /tmp/branch-agent-pkg \
    && zip -qr /var/www/etxtmo-downloads/branch-agent.zip . \
    && rm -rf /tmp/branch-agent-pkg

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Operator tool, run by hand via `docker exec` -- never on the startup path.
# See infra/scripts/cancel-queued.sh for why.
COPY infra/scripts/cancel-queued.sh /usr/local/bin/cancel-queued
RUN chmod +x /usr/local/bin/cancel-queued

EXPOSE 80

CMD ["/entrypoint.sh"]
