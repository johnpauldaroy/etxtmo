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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY api-core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api-core/ .

COPY --from=web-build /web/dist /var/www/etxtmo

RUN rm -f /etc/nginx/sites-enabled/default
COPY nginx.combined.conf /etc/nginx/conf.d/default.conf

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

CMD ["/entrypoint.sh"]
