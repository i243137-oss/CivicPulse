# 📘 Operational Runbook — CivicPulse

> Living document for deployment procedures, monitoring, and incident response.

---

## Table of Contents

- [Service Overview](#service-overview)
- [Deployment](#deployment)
- [Health Checks](#health-checks)
- [Common Issues](#common-issues)
- [Rollback Procedure](#rollback-procedure)

---

## Service Overview

| Service    | Port  | Health Endpoint          |
| ---------- | ----- | ------------------------ |
| Backend    | 8000  | `GET /health`            |
| Frontend   | 5173  | N/A (static)             |
| PostgreSQL | 5432  | `pg_isready`             |
| Redis      | 6379  | `redis-cli ping`         |

---

## Deployment

### Development

```bash
docker compose up --build
```

### Production

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Kubernetes

```bash
kubectl apply -f infra/k8s/
kubectl rollout status deployment/civicpulse-backend
```

---

## Health Checks

```bash
# Backend
curl -f http://localhost:8000/health

# PostgreSQL
docker exec civicpulse-postgres pg_isready -U civicpulse

# Redis
docker exec civicpulse-redis redis-cli ping
```

---

## Common Issues

| Symptom                         | Likely Cause              | Fix                                      |
| ------------------------------- | ------------------------- | ---------------------------------------- |
| Backend won't start             | DB not ready              | Check `depends_on` / health checks       |
| Connection refused on 5432      | PostgreSQL down           | `docker compose restart postgres`        |
| Frontend shows blank page       | API URL misconfigured     | Check `/api` proxy in `vite.config.ts` or Nginx `nginx.conf` |

---

## Frontend Development and Testing Commands

### Development Server
```bash
cd frontend
npm run dev
# Starts Vite server on http://localhost:5173 with proxying to http://localhost:8000
```

### Type Checking & Production Build
```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

### Component Test Suite (Vitest)
```bash
cd frontend
npm test
# Executes 14 component tests across 5 test suites with jsdom environment
```


---

## Rollback Procedure

```bash
# Docker Compose
docker compose -f docker-compose.prod.yml down
git checkout <last-known-good-tag>
docker compose -f docker-compose.prod.yml up -d --build

# Kubernetes
kubectl rollout undo deployment/civicpulse-backend
```
