# ═══════════════════════════════════════════════════════════════
#  CivicPulse Frontend — Dockerfile
# ═══════════════════════════════════════════════════════════════
#  Build:  docker build -t civicpulse-frontend .
#  Run:    docker run -p 5173:5173 civicpulse-frontend
#
#  Production variant serves static files via nginx (see below).
# ═══════════════════════════════════════════════════════════════

# ── Stage 1: Build ──────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# ── Stage 2: Serve (Production) ────────────────────────────
FROM nginx:alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
