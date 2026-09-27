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

| ID   | Description                         | Priority | Status           |
| ---- | ----------------------------------- | -------- | ---------------- |
| TD-1 | Add pre-commit hooks (ruff, eslint) | Medium   | Open             |
| TD-2 | Set up Alembic migration scaffold   | High     | Closed (Phase 2) |
| TD-3 | Configure HTTPS for production      | High     | Open             |

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

## Phase 4 — AI Triage Engine and Architecture

### Four-Layer Triage Providers

The AI triage system is designed for high reliability, zero-downtime tolerance, and multi-environment portability:

- **`LLMTriage`** (`backend/app/providers/triage/llm.py`): Primary cloud provider targeting OpenAI-compatible endpoints (Groq, Google AI Studio Gemini). Enforces 10.0s hard-cap timeout, structured JSON mode, and single jittered retry (`0.5s + uniform(0.1, 0.4)`).
- **`OllamaTriage`** (`backend/app/providers/triage/ollama.py`): Local, air-gapped containerized provider (`llama3.2:1b`) for environments requiring 100% data residency and zero external network transmission.
- **`RuleBasedTriage`** (`backend/app/providers/triage/rules.py`): Zero-dependency keyword and urgency heuristic engine. Always available, sub-millisecond execution, guaranteed zero exceptions.
- **`SimulatedTriage`** (`backend/app/providers/triage/simulated.py`): Deterministic test fake with failure injection (`timeout`, `rate_limit`, `server_error`, `malformed_json`, `always_raise`) used in CI so automated tests never require a paid API key.

### Resilience and Deterministic Fallback

- **Hard-Cap Timeout**: 10.0 seconds cap on all AI inference requests.
- **Selective Jittered Retry**: Retries at most once strictly for transient failures: timeout, HTTP 429, or HTTP 5xx. Never retries client error HTTP 400 or connection errors.
- **Fallback Chain**: When primary AI provider fails (timeout, rate limit, server error, or invalid JSON output), `TriageService` automatically catches the error, logs diagnostics, invokes `RuleBasedTriage`, and records `triaged_by = 'rules:fallback'` on the persisted complaint. The citizen intake submission succeeds with HTTP 201 Created.
- **Content-Hash Caching (24-Hour TTL & Hit Rate Telemetry)**: SHA-256 hash of normalized complaint text and location (`civicpulse:triage:cache:<hash>`) stores triage outcomes in Redis for 24 hours (86,400s). Duplicate reports of the same municipal malfunction cost zero additional AI tokens. Real-time cache metrics (`hits`, `misses`, `total_requests`, and calculated `hit_rate`) are exposed via `GET /api/meta/providers`.

### Security and PII Governance

- **Prompt-Injection Guardrails**: Citizen text is encapsulated in `<complaint_untrusted_input>` XML tags in the system prompt with strict instructions forbidding prompt overrides, role modifications, or code execution.
- **Structured Schema Validation**: Model output is parsed and strictly validated against `TriageResult` Pydantic schema before acceptance. Prose, code fences, or hallucinated categories outside the enum are rejected safely.
- **PII Stripping at Service Boundary**: Citizen contact information (`reporter_contact`) is stored in PostgreSQL but **never** passed to the triage provider interface (`triage(text, location)`). Formally documented in `docs/adr/0004-pii-and-data-governance.md`.

---

## Phase 5 — Frontend Implementation (Member B)

### Stack and Architectural Boundaries

- **Core Stack**: React 18 + Vite + TypeScript.
- **Strict Presentation Boundary**: The frontend owns 100% presentation, interaction, validation feedback, and telemetry display. It owns **zero** business rules.
  - Triage category, priority, and AI summary are determined by backend LLM/rules providers. The citizen intake form collects strictly complaint text, location, and optional contact; manual category/priority pre-assignment controls are completely excluded from intake.
  - Valid status transitions are decided exclusively by the backend finite state machine and serialized directly on each complaint (`complaint.allowed_transitions`). The frontend maintains **zero** transition tables, eliminating two-sources-of-truth divergence.
  - Terminal statuses (`resolved`, `rejected`) deliver empty `allowed_transitions: []` from the backend, disabling transition actions and rendering terminal state feedback.
  - Action buttons dynamically disable during in-flight status PATCH requests, preventing duplicate submissions.
  - List queries incorporate `AbortController` cancellation to prevent out-of-order response overwrites on rapid filter changes.
  - Any rejected transition surfaces the server's `409 Conflict` message verbatim in the UI rather than a generic error toast.
  - An `ErrorBoundary` is mounted around the complete application tree in `App.tsx` and at root `main.tsx`.

### Key Views Implemented

1. **Intake & Submission (`SubmitPage.tsx`)**:
   - Free-text complaint input (10–2000 chars), location (3–200 chars), and optional contact.
   - Client-side validation mirrors backend Pydantic bounds to prevent unnecessary roundtrips.
   - Honest loading state: displays `"Submitting & Triaging…"` with disabled actions to transparently represent multi-second LLM inference latency.
   - On success, smoothly transitions to the issue detail view showing assigned category, priority, AI summary, and triage provider.
2. **Operations Dashboard (`DashboardPage.tsx`)**:
   - High-level metric cards for total issues and breakdown by status.
   - Progress bar distributions across categories and priorities.
   - Observability card displaying active AI triage provider, content-hash cache hit rate, and latency history table.
   - **`X-Cache` Telemetry**: Directly inspects the `X-Cache` response header (`HIT` or `MISS`) from Redis and renders a prominent status badge.
3. **Complaints Listing & Filter Queue (`ComplaintsPage.tsx`)**:
   - Filterable by Category, Priority, and Status with server-side pagination (10 items/page).
   - Direct status transition actions on list cards for municipal operators powered by `complaint.allowed_transitions`.
   - AbortController request sequencing to eliminate stale query races.
4. **Issue Detail & State Machine Actions (`ComplaintDetailPage.tsx`)**:
   - Full inspection of complaint text, location, reporter information, and AI triage telemetry.
   - Finite state machine transition buttons rendered exclusively from server-provided `allowed_transitions`.
   - In-flight transition disablement and terminal state alert when issue is marked `resolved` or `rejected`.

### Runtime Configuration & Build-Once-Deploy-Many

- Build-time baked backend URLs are strictly forbidden.
- The centralized typed client (`src/api/client.ts`) uses relative `/api` paths and root-relative `/health`.
- In local development, Vite proxies `/api` and `/health` to `http://localhost:8000`.
- In production containers, `frontend/Dockerfile` uses multi-stage build pinned to assignment versions (`node:22-alpine` builder, `nginx:1.27-alpine` runner) and installs `frontend/nginx.conf` reverse proxying `/api/` and `/health` to `http://backend:8000`, guaranteeing that the exact same frontend container image runs in all environments.
- Architectural decision formally documented in `docs/adr/0003-frontend-runtime-config-and-proxy.md`.

### Component Testing Suite (Vitest + React Testing Library)

- ≥ 5 comprehensive component tests passing in CI:
  1. `SubmitPage.test.tsx`: Form validation, honest triage loading state, error display.
  2. `ComplaintsPage.test.tsx`: Listing rendering, filter updates, verbatim 409 error propagation with matching transition assertions.
  3. `DashboardPage.test.tsx`: Total counters, `X-Cache` header display, retry on network failure.
  4. `ComplaintDetailPage.test.tsx`: Full issue telemetry, state transition workflow, terminal state.
  5. `ErrorBoundary.test.tsx`: Unhandled render crash capture, fallback UI, recovery on reset.

---

## Phase 6 — Docker Compose and Local Cloud-Native Stack (Member B)

### Network Segmentation & Architecture

The stack enforces strict zero-trust boundary segmentation using two Docker bridge networks:

1. **`edge` Network**:
   - Public-facing application ingress network.
   - Connected services: `frontend` (Nginx port 80) and `backend` (FastAPI port 8000).
   - Allows browser/client communication with the frontend and allows Nginx to proxy API traffic to the backend.

2. **`internal` Network (`internal: true`)**:
   - Air-gapped database and cache tier.
   - Marked with `internal: true` in Compose, which disables external internet routing and isolates containers completely from host-level or external network traffic.
   - Connected services: `backend`, `postgres`, and `redis`.
   - **Isolation Guarantee**: The `frontend` container is connected solely to `edge` and has zero physical routes or DNS visibility into `postgres` or `redis`.
   - **Verification**: Running `nc -zv -w 2 postgres 5432` from inside `frontend` yields `nc: bad address 'postgres'`, confirming that the persistence layer is unroutable and inaccessible from the presentation tier.

```
[ Browser / Host Traffic ]
         │ (port 80:80)
         ▼
┌─────────────────────────────────┐
│     civicpulse-frontend         │ (edge network only)
│  (Nginx 1.27 + Vite SPA dist)   │
└────────────────┬────────────────┘
                 │ proxy /api/ & /health
                 ▼
┌─────────────────────────────────┐
│      civicpulse-backend         │ (edge & internal networks)
│   (FastAPI 0.115 + Python 3.12) │
└────────┬───────────────┬────────┘
         │ (internal)    │ (internal)
         ▼               ▼
┌────────────────┐ ┌────────────────┐
│ civicpulse-    │ │ civicpulse-    │ (internal network only, internal: true)
│ postgres (16)  │ │ redis (7 AOF)  │ (Zero published host ports in prod)
└────────────────┘ └────────────────┘
```

### Container-to-Container Communication & Service Discovery

- All container-to-container traffic references internal Docker DNS service names (`backend`, `postgres`, `redis`), completely eliminating brittle `localhost` or hardcoded IP bindings.
- Environment variables configure connection endpoints:
  - `POSTGRES_HOST=postgres`
  - `POSTGRES_PORT=5432`
  - `REDIS_HOST=redis`
  - `REDIS_PORT=6379`
- In `frontend/nginx.conf`, the reverse proxy routes `/api/` to `http://backend:8000/api/` and `/health` to `http://backend:8000/health`.

### Persistence & Redis AOF

- **Named Volumes**:
  - `pgdata`: Mounts to `/var/lib/postgresql/data` ensuring durability across container teardown and recreations.
  - `redisdata`: Mounts to `/data` holding Redis AOF transaction logs.
  - `ollama_models`: Mounts to `/root/.ollama` for air-gapped local model weights.
- **Append-Only File (AOF)**:
  - Redis runs with command flags: `redis-server --appendonly yes --appendfsync everysec`.
  - Ensures at most one second of transaction loss in disaster scenarios while maximizing throughput for rate-limiting sliding windows and stats caching.
  - Verified in container via `redis-cli info persistence` (`aof_enabled:1`).

### Healthchecks & Orchestrator Dependencies

All services declare rigorous healthchecks and startup ordering using `depends_on: condition: service_healthy`:

- **PostgreSQL**: `test: ["CMD-SHELL", "pg_isready -U civicpulse -d civicpulse"]` (5s interval, 5 retries).
- **Redis**: `test: ["CMD", "redis-cli", "ping"]` (5s interval, 5 retries).
- **Backend**: `test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')\" || exit 1"]` (10s interval, 15s start period).
  - Starts only after PostgreSQL and Redis are both healthy.
  - Container entrypoint executes automated migration and seeding before launching Uvicorn: `sh -c "alembic upgrade head && python scripts/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"`.
- **Frontend**: `test: ["CMD-SHELL", "wget -q -O - http://127.0.0.1:80/health || exit 1"]`.
  - Starts only after the backend container reaches healthy status.

### Dev vs. Prod Composition Parity

- **Development (`compose.yaml` / `docker-compose.yml`)**:
  - Includes volume bind mount `./backend:/app` for hot-reloading code changes.
  - Exposes debug/inspection ports (`5432`, `6379`, `8000`) for developer tooling.
- **Production (`compose.prod.yaml` / `docker-compose.prod.yml`)**:
  - Image-only deployments (zero `build:` directives) with image tag pinning (`${IMAGE_TAG:-latest}`).
  - Zero host port publishing on internal infrastructure (`postgres` and `redis` publish zero ports to the host).
  - Explicit resource limits and reservations (`deploy.resources.limits` and `reservations`).
  - Production restart policy: `restart: always`.
  - No development bind mounts.

### End-to-End Verification Results

1. **Stack Convergence**: `docker compose up --build -d` brings up all 4 containers (`civicpulse-frontend`, `civicpulse-backend`, `civicpulse-postgres`, `civicpulse-redis`) into `(healthy)` state.
2. **Network Isolation**: `frontend` cannot resolve or connect to `postgres:5432` or `redis:6379`.
3. **HTTP Liveness**: `curl -s -i http://localhost:80/health` returns `200 OK` via Nginx reverse proxy.
4. **Cache & Analytics**: `GET http://localhost:80/api/stats` returns aggregate statistics with `X-Cache: MISS` on first hit and `X-Cache: HIT` on subsequent requests from Redis.
5. **Issue Intake & Auto-Triage**: `POST http://localhost:80/api/complaints` via port 80 successfully creates complaint, triggers rule/LLM triage, returns 201 Created with server-assigned category, priority, AI summary, and `allowed_transitions: ["in_progress", "rejected"]`.
6. **State Machine Progression**: `PATCH http://localhost:80/api/complaints/{id}/status` transitions status to `in_progress` and updates allowed transitions to `["rejected", "resolved"]`.
7. **SPA Routing**: Directly accessing `/` or deep-link `/complaints` serves `index.html` (HTTP 200) through Nginx `try_files` SPA fallback.

---

## Lessons Learned

1. **Structured Output Enforcement in Production**: Free-tier LLMs occasionally wrap JSON in explanatory text or markdown code fences (`json ... `). Robust regex extraction combined with Pydantic model validation prevents runtime crashes and ensures enum compliance.
2. **Resilient Triage Fallback**: AI services are inherently non-deterministic and subject to upstream rate limits and network degradation. An automated intake platform must treat the LLM as an opportunistic optimization, with an immediate, deterministic heuristic fallback path (`RuleBasedTriage`) ensuring uninterrupted citizen service.
3. **Data Residency and Minimization**: By stripping `reporter_contact` prior to invoking external inference, municipal compliance is preserved without compromising classification accuracy.
