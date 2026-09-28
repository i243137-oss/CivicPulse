# ═══════════════════════════════════════════════════════════════
#  CivicPulse Frontend — Dockerfile (Security Hardened)
# ═══════════════════════════════════════════════════════════════

# ── Stage 1: Build ──────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# ── Stage 2: Serve (Hardened Production Nginx) ─────────────
FROM nginx:1.27-alpine AS production

# Security hardening: upgrade base OS packages to patch known CVEs and configure non-root dirs
RUN apk upgrade --no-cache && \
    touch /var/run/nginx.pid && \
    chown -R 101:101 /var/run/nginx.pid /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d

COPY --from=build --chown=101:101 /app/dist /usr/share/nginx/html
COPY --chown=101:101 nginx.conf /etc/nginx/conf.d/default.conf

# Execute as non-root user (nginx: UID 101 in alpine)
USER 101

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
