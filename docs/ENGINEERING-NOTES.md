# 🔧 Engineering Notes — CivicPulse

> Design rationale, architectural decisions, technical debt, and lessons learned.

---

## Architecture Overview

CivicPulse follows a **layered monorepo** structure with clear separation:

```
┌─────────────┐     ┌─────────────┐
│   Frontend   │────▶│   Backend   │
│  React + TS  │ API │  FastAPI    │
└─────────────┘     └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │             │
               ┌────▼───┐  ┌─────▼────┐
               │ Postgres│  │  Redis   │
               │  (data) │  │ (cache)  │
               └─────────┘  └──────────┘
```

### Key Design Decisions

1. **Monorepo over polyrepo** — Simplifies CI/CD, atomic cross-stack changes, and onboarding.
2. **FastAPI over Django** — Async-first, auto-generated OpenAPI docs, lightweight.
3. **Vite over CRA** — Faster HMR, ESM-native, better DX for TypeScript.
4. **PostgreSQL over MySQL** — Superior JSON support, PostGIS for geolocation features.
5. **Redis for caching** — Session management, rate limiting, and real-time pub/sub.

---

## Technical Debt Tracker

| ID   | Description                    | Priority | Status  |
| ---- | ------------------------------ | -------- | ------- |
| TD-1 | Add pre-commit hooks (ruff, eslint) | Medium | Open |
| TD-2 | Set up Alembic migration scaffold   | High   | Closed (Phase 2) |
| TD-3 | Configure HTTPS for production      | High   | Open |

---

## Phase 2 — Database Schema and Index Justification

### Layered Backend Structure
The backend implements a strict four-layer architecture with one-way dependency flow:
- `routes/` — HTTP handling only (parameter validation, serialization, response codes). No SQL, no business rules, no DB sessions.
- `services/` — Business domain logic, finite state machine validation, triage orchestration, and statistics calculation.
- `repositories/` — Persistence layer where all SQLAlchemy ORM queries and SQL logic reside exclusively.
- `providers/` — Outbound integration layer behind Protocol interfaces (`TriageProvider`), with deterministic offline rule-based and simulated fallback implementations.

### Database Index Justifications
As required by the specification, all indexes on the `complaints` table are explicitly justified by named queries:

1. **`ix_complaints_status_priority` on `(status, priority)`**:
   - **Target Query**: `ComplaintRepository.list_complaints(status=?, priority=?)`
   - **Operational Purpose**: Directly powers the municipal triage queue where administrators query active, high-priority issues (e.g. `WHERE status = 'open' AND priority = 'high'`). Without this composite B-tree index, filtering requires a full sequential table scan across municipal complaint history.

2. **`ix_complaints_created_at` on `created_at`**:
   - **Target Query**: `ComplaintRepository.list_complaints(order_by=Complaint.created_at.desc(), limit=?, offset=?)`
   - **Operational Purpose**: Powers chronological paginated listings of complaints across citizen dashboards and staff inspection feeds. It eliminates expensive in-memory sort operations (`SORT_KEY` scan) for reverse chronological sorting.

### Finite State Machine Contract
Complaint status transitions strictly adhere to the transition table:
- `open` → `in_progress`, `rejected`
- `in_progress` → `resolved`, `rejected`
- `resolved` and `rejected` are terminal states (no further transitions permitted).
- Any illegal or out-of-order transition immediately raises an `InvalidStateTransitionError`, resulting in an HTTP `409 Conflict` response naming the attempted transition.

---

## Phase 3 — Redis Caching and Distributed Rate Limiting

### Read-Through Statistics Cache
- **Target Endpoint**: `GET /api/stats`
- **Cache Key**: `civicpulse:stats:summary`
- **TTL**: 30 seconds (`REDIS_STATS_CACHE_TTL = 30`)
- **Cache Hit / Miss Telemetry**: Every response sets header `X-Cache: HIT` or `X-Cache: MISS`.
- **Write-Time Invalidation**: Invalidation occurs immediately on `POST /api/complaints` and `PATCH /api/complaints/{id}/status`, ensuring fresh analytics after state changes without waiting for TTL expiry.

### Distributed Rate Limiter
- **Design**: Implemented with atomic operations (Lua script on Redis 7 / MULTI-EXEC pipeline) tracking request timestamps within a sliding window.
- **Sliding Window Log**: Eliminates boundary burst vulnerabilities that allow double-quota usage in fixed-window limiters.
- **Headers & Codes**: Emits `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and HTTP 429 with `Retry-After: <seconds>` when exceeded.
- **Exempt Routes**: `/health`, `/ready`, `/docs`, `/redoc`, and `/openapi.json` are strictly exempt to protect orchestrator liveness/readiness probes.
- **Multi-Instance Verification**: Validated by integration tests (`test_multi_instance_redis.py`) where multiple backend instances share the same Redis cluster to enforce quotas collectively.

### Readiness Probe Separation
- `/health` remains pure liveness (zero DB, zero Redis dependency).
- `/ready` verifies both PostgreSQL (`SELECT 1`) and Redis (`PING`), returning HTTP 503 if either dependency fails.

---

## Lessons Learned

*To be updated as the project progresses.*
