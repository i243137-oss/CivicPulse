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

## Phase 7 — Testing, Quality, and Full-Path Verification

### Member A: Backend Test Architecture, Validation, Coverage, and Full-Path Integration

Member A implements the full backend quality engineering deliverables across all architectural tiers:

1. **Backend Unit & Isolation Tests**:
   - **Services Layer**: Verified `ComplaintService` (auto-triage triggers, manual category overrides, 404 handling, allowed transitions dispatch), `CacheService` (read-through cache, write invalidation, TTL expiration), `TriageService` (provider execution, content-hash hashing, fallback chain, cache telemetry), and `StateMachine` (deterministic transition matrix).
   - **Repositories Layer**: Verified `ComplaintRepository` filtering (category, priority, status), pagination bounds, and SQL aggregation (`get_stats()`).
   - **Pydantic Validation & Bounds (`test_validation.py`)**:
     - Strict text length validation (10 to 2000 characters).
     - Strict location length boundaries (3 to 200 characters).
     - Contact metadata constraints (max 255 characters).
     - Strict enum compliance: `CategoryEnum`, `PriorityEnum`, and `StatusEnum`.
     - HTTP parameter boundaries: `page >= 1`, `1 <= page_size <= 100`, malformed UUID rejection with HTTP 422.
   - **Distributed Rate Limiting & Persistence**: Verified sliding-window atomic Lua limiter (`test_rate_limit.py`), IP bucket isolation, probe exemptions, and multi-instance concurrency (`test_multi_instance_redis.py`).
   - **AI Triage Resilience (`test_triage.py`)**: 10s hard cap, strict jittered retry (timeout, 429, 5xx only; zero retries on connection error or 400), prompt injection isolation (`<complaint_untrusted_input>`), and deterministic fallback recording verbatim `triaged_by = "rules:fallback"`.

2. **Complete Application Path Integration Test (`test_full_path_integration.py`)**:
   - Validates the entire citizen-to-operator lifecycle end-to-end on the backend:
     1. Probes: Health (`/health`) and Readiness (`/ready`) checks.
     2. Stats Read-Through Cache: Initial `X-Cache: MISS` followed by `X-Cache: HIT`.
     3. Citizen Intake: Submitting complaint triggers automated triage and returns HTTP 201 with server-assigned category and allowed transitions.
     4. Write Cache Invalidation: Subsequent stats call reflects fresh counts with `X-Cache: MISS`.
     5. Duplicate Caching: Identical complaint submission hits 24h content-hash cache in Redis (`cache:llm:simulated`) in $\le 2$ms.
     6. Telemetry Monitoring: `GET /api/meta/providers` exposes verified non-zero `hit_rate`.
     7. Query & Pagination: Combined multi-criteria filtering and multi-page pagination.
     8. State Machine Progression: Transitioning `open` &rarr; `in_progress` &rarr; `resolved`.
     9. Conflict Rejection: Attempting illegal backward or terminal transitions returns HTTP 409 Conflict.
     10. Final Consistency: Aggregated statistics reflect the resolved issue.

3. **Coverage Configuration (`pyproject.toml`) & Test Metrics**:
   - Configured `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`.
   - Configured `[tool.coverage.run]` (branch coverage on `app/`) and `[tool.coverage.report]` with `fail_under = 85`.
   - **Test Results**: **84 passed, 1 skipped** (live PostgreSQL probe skipped when offline).
   - **Coverage**: **90% total statement coverage** across `backend/app/`, easily surpassing the assignment rubric requirement:
     - `app/services/state_machine.py`: 100%
     - `app/schemas/complaint.py`: 100%
     - `app/repositories/complaint_repository.py`: 100%
     - `app/models/complaint.py`: 97%
     - `app/providers/triage/base.py`: 98%
     - `app/providers/triage/rules.py`: 97%
     - `app/providers/triage/ollama.py`: 96%
     - `app/providers/triage/llm.py`: 95%
     - `app/services/complaint_service.py`: 95%
     - `app/services/triage_service.py`: 89%

---

### Member B: Frontend Quality Gates, Vitest Suite, and Full-Path UI Verification

Member B implements comprehensive frontend linting, type safety, and component verification:

1. **Linting & Type Safety**:
   - `npm run lint`: Enforces zero warnings/errors via `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0`.
   - `tsc --noEmit`: Validates complete TypeScript typing with strict mode compliance.
   - `npm run build`: Multi-stage Vite production compilation guaranteeing clean bundling with zero type regressions.

2. **Component & Integration Test Suite (Vitest + React Testing Library)**:
   - Exceeds the assignment rubric requirement of ≥ 5 component tests, delivering **6 test suites and 15 passed tests**:
     - `SubmitPage.test.tsx`: Form validation (min/max length constraints), honest multi-second triage loading state (`"Submitting & Triaging…"`), error banner propagation.
     - `ComplaintsPage.test.tsx`: Paginated complaint rendering, filter controls (Category, Priority, Status), AbortController query cancellation, verbatim HTTP 409 transition rejection handling.
     - `DashboardPage.test.tsx`: Total counter cards, `X-Cache: HIT|MISS` header badge inspection, telemetry history table, error boundary retry action.
     - `ComplaintDetailPage.test.tsx`: Detailed complaint telemetry, server-provided `allowed_transitions` button rendering, terminal state (`resolved`, `rejected`) locking.
     - `ErrorBoundary.test.tsx`: Uncaught render exception handling, fallback card with reset recovery.
     - `AppIntegration.test.tsx`: **Complete Application Path Integration Test** validating the full user journey: Navbar routing &rarr; citizen intake form completion &rarr; automated triage transition &rarr; issue detail inspection &rarr; state machine status advancement &rarr; return to complaints list queue.

### Deterministic Test Execution & Cross-Platform Verification

- **Air-Gapped & Deterministic Execution**: All tests execute using `TRIAGE_PROVIDER=simulated` or `RuleBasedTriage`, guaranteeing zero dependence on external paid AI APIs and zero flakiness in CI/CD.
- **Cross-Platform Compatibility**:
  - Replaced hardcoded `/home/umair_hassan/...` Linux paths in `backend/tests/test_postgres_compatibility.py` with `sys.executable -m alembic` and dynamic relative path resolution.
  - Added explicit `sync_engine.dispose()` before temporary SQLite database file removal in `backend/tests/test_migrations.py` to prevent Windows file handle contention errors (`PermissionError`).

---

## Phase 8 — Observability and Resilience

### Architecture & Capabilities

Phase 8 elevates CivicPulse to cloud-native production standards with end-to-end observability, distributed tracing correlation, probe separation, graceful connection drainage, and Prometheus instrumentation:

1. **JSON Structured Logging (`backend/app/core/logging.py`)**:
   - Implemented `StructuredJsonFormatter` emitting compact single-line JSON logs for high-throughput stream processing (Logstash, FluentBit, Datadog).
   - Core standard fields guaranteed on every log record:
     - `timestamp`: ISO 8601 UTC format (`YYYY-MM-DDTHH:MM:SS.sssZ`).
     - `level`: Log severity (`INFO`, `WARNING`, `ERROR`, `DEBUG`).
     - `service`: Application identifier (`civicpulse`).
     - `logger`: Originating logger hierarchy (e.g., `app.core.logging`, `app.services.triage_service`).
     - `message`: Formatted human-readable message.
     - `request_id`: Tracing correlation identifier (injected automatically when present in request context).
   - Custom extra attributes supplied via `extra={...}` are preserved as top-level JSON fields.

2. **Request ID Correlation & Context Propagation**:
   - `RequestIdMiddleware` intercepts every incoming HTTP request:
     - Reads client-supplied `X-Request-ID` header or generates a cryptographically random correlation ID formatted as `req-<hex>`.
     - Sets the ID into Python `contextvars.ContextVar` (`request_id_ctx`), making the correlation ID coroutine-safe across asynchronous task boundaries.
     - Logs request initiation (`method`, `path`, `client_ip`) and completion (`status_code`, `duration_ms`).
     - Returns the correlation ID on the outgoing HTTP response via `X-Request-ID` header.

3. **Separation of Liveness (`/health`) and Readiness (`/ready`)**:
   - **Liveness Probe (`/health`)**:
     - Pure zero-dependency probe.
     - Validates that the Python runtime and ASGI event loop are responsive.
     - Never touches PostgreSQL or Redis, preventing cascade restart loops during transient database maintenance.
   - **Readiness Probe (`/ready`)**:
     - Deep dependency probe validating essential infrastructure components.
     - Executes `SELECT 1` on PostgreSQL and `PING` on Redis.
     - Returns HTTP 200 `{"status": "ready", "database": "connected", "redis": "connected"}` when all dependencies are healthy.
     - Returns HTTP 503 `Service Unavailable` with explicit failure details when any dependency is unreachable, signaling orchestrators (Kubernetes / Docker Compose) to divert ingress traffic.

4. **Graceful Shutdown & SIGTERM Drainage**:
   - Handled via FastAPI's unified `lifespan` context manager in `backend/app/main.py`.
   - On `SIGTERM` or `SIGINT`, ASGI server ceases accepting new ingress connections and allows in-flight requests to complete.
   - During shutdown phase, the lifespan sequentially:
     1. Disposes the SQLAlchemy asynchronous database connection pool (`await engine.dispose()`).
     2. Closes and disconnects the Redis asynchronous client pool (`await close_redis_client()`).
   - Ensures zero socket leaks, connection resets, or unclosed file descriptors during rolling updates.

5. **Prometheus Metrics Endpoint (`/metrics`) (`backend/app/core/metrics.py`, `backend/app/routes/metrics.py`)**:
   - Exposes standard Prometheus text exposition format (`text/plain; version=0.0.4`) at `GET /metrics`.
   - Rate limit exempt to ensure monitoring scrapers (Prometheus/Grafana Agent) are never throttled.
   - Core metrics instrumented:
     - `civicpulse_http_requests_total`: Counter tracking inbound requests partitioned by `method`, `endpoint`, and `status`.
     - `civicpulse_http_request_duration_seconds`: Histogram measuring HTTP request latencies across standard latency buckets.
     - `civicpulse_ai_triage_requests_total`: Counter tracking automated triage execution by `provider` and `status` (`success`, `cached`, `fallback`, `error`).
     - `civicpulse_ai_triage_duration_seconds`: Histogram tracking triage inference and rule evaluation latency.
     - `civicpulse_ai_fallback_total`: Dedicated counter tracking heuristic rule-based fallbacks triggered by primary AI provider failures.
     - `civicpulse_cache_requests_total`: Counter recording Redis cache `hit` vs `miss` events across stats and triage hash caches.

6. **Demonstrable Quality Gate Verification (`backend/tests/test_observability.py`)**:
   - 11 dedicated test cases verifying:
     - Structured JSON output format and standard keys.
     - Request ID context propagation and HTTP header reflection.
     - Liveness probe zero-dependency isolation.
     - Readiness probe connectivity verification and 503 failure handling for DB and Redis.
     - Prometheus metrics scraping and traffic counter emission.
     - Lifespan graceful cleanup of database and Redis pools.
   - Full test suite: **95 passed, 1 skipped**, with **88% total statement coverage** across `backend/app/`.

---

---

## Phase 9 — Kubernetes Baseline Manifests and High Availability (Member B)

Member B architected and validated production-grade Kubernetes manifests for CivicPulse under the dedicated `civicpulse` namespace, applying Kubernetes best practices for data persistence, zero-downtime rollouts, and ingress traffic routing.

### 1. Workload Architecture & Workload Types

1. **PostgreSQL as a `StatefulSet` (Architectural Requirement)**:
   - *Design Rationale*: As mandated by the specification and rubric, deploying a stateful relational database like PostgreSQL as a generic `Deployment` is an anti-pattern. Deployments consider pods fungible and stateless, which risks multiple pods concurrently mounting a read-write volume, causing filesystem corruption or split-brain states during rescheduling.
   - *StatefulSet Guarantee*: Configured with `serviceName: postgres` and `volumeClaimTemplates` (`storage: 2Gi`, `ReadWriteOnce`). The StatefulSet guarantees deterministic pod identity (`postgres-0`), ordered startup/shutdown, and permanent binding to its persistent volume across restarts and rescheduling.

2. **Redis Cache as a `Deployment` with Persistent Volume**:
   - Deployed with a dedicated `PersistentVolumeClaim` (`redis-data-pvc`, 1Gi) mounted at `/data`.
   - Enabled Append-Only File (AOF) persistence via container args `--appendonly yes --appendfsync everysec`, ensuring zero loss of cached triage metadata or rate-limiting windows upon container restart.

3. **FastAPI Backend Deployment ($\ge 2$ Replicas)**:
   - Configured with 2 replicas for high availability and load distribution.
   - **InitContainer (`wait-for-postgres`)**: Uses `postgres:16-alpine` and `pg_isready` to poll PostgreSQL availability before launching the application container, eliminating startup race conditions.
   - **Graceful Rolling Updates**: Strategy configured with `maxSurge: 1` and `maxUnavailable: 0`.
   - **Connection Draining Hook**: Implements `preStop: exec: ["sh", "-c", "sleep 5"]` with `terminationGracePeriodSeconds: 30`. This ensures Kubernetes removes the terminating pod from Service endpoints and Ingress routing tables before the Uvicorn process receives `SIGTERM`, preventing dropped citizen requests during deployments.

4. **React Frontend Deployment ($\ge 2$ Replicas)**:
   - Configured with 2 replicas serving the compiled Nginx SPA image.
   - Resource-efficient baseline with sub-second health probe responses on port 80.

### 2. Probe Separation: Startup, Liveness, and Readiness

To prevent cascading restarts and broken service routing, three distinct probe tiers are configured across all application pods:

| Probe Type | Target Endpoint | Timing / Thresholds | Architectural Responsibility |
| :--- | :--- | :--- | :--- |
| **Startup Probe** | `/health` (port 8000) | Period: 2s, Failure: 30 (60s max) | Protects slow application bootstrapping; suspends liveness/readiness checks until Uvicorn has completely initialized. |
| **Liveness Probe** | `/health` (port 8000) | Period: 10s, Timeout: 3s, Failure: 3 | Verifies container process health without database dependencies. Prevents false-positive pod restarts during upstream database latency. |
| **Readiness Probe** | `/ready` (port 8000) | Period: 10s, Timeout: 3s, Failure: 3 | Verifies PostgreSQL and Redis connectivity. Temporarily isolates the pod from traffic if downstream dependencies are degraded. |

Database and cache workloads use native command probes:
- PostgreSQL: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`
- Redis: `redis-cli ping`

### 3. Resource Requests, Limits & Horizontal Scalability

Every container defines explicit CPU and Memory requests and limits to ensure predictable scheduling, prevent noisy neighbor starvation, and establish the denominator for Horizontal Pod Autoscaling (HPA v2):
- **Backend**: `requests: {cpu: 250m, memory: 128Mi}`, `limits: {cpu: 1000m, memory: 512Mi}`
- **Frontend**: `requests: {cpu: 100m, memory: 64Mi}`, `limits: {cpu: 500m, memory: 256Mi}`
- **PostgreSQL**: `requests: {cpu: 250m, memory: 256Mi}`, `limits: {cpu: 1000m, memory: 512Mi}`
- **Redis**: `requests: {cpu: 100m, memory: 64Mi}`, `limits: {cpu: 500m, memory: 256Mi}`

### 4. Network Isolation & Ingress Routing

1. **Zero External Port Exposure**:
   - All 4 internal components (`frontend`, `backend`, `postgres`, `redis`) expose solely `ClusterIP` Services.
   - PostgreSQL (`5432`) and Redis (`6379`) are completely unreachable from outside the cluster network.
2. **Kubernetes Ingress (`civicpulse-ingress`)**:
   - Single ingress controller host routing traffic:
     - `/api` &rarr; `backend:8000` (FastAPI REST endpoints)
     - `/health` &rarr; `backend:8000` (public liveness)
     - `/ready` &rarr; `backend:8000` (public readiness)
     - `/` &rarr; `frontend:80` (React SPA)
3. **Immutable Tagging**:
   - Zero `:latest` tags in any manifest. Images pinned to immutable versions (`ghcr.io/i243137-oss/civicpulse-backend:1.0.0`, `ghcr.io/i243137-oss/civicpulse-frontend:1.0.0`, `postgres:16-alpine`, `redis:7-alpine`).

### 5. Kustomize Multi-Environment Structure

The manifests are structured for Kustomize with declarative base and overlay definitions:
- `infra/k8s/base/`: Contains pure base manifests and base `kustomization.yaml`.
- `infra/k8s/overlays/dev/`: Developer environment overlay with environment overlays.
- `infra/k8s/overlays/prod/`: Production environment overlay.
- `infra/k8s/kustomization.yaml`: Root kustomization referencing manifests for direct `kubectl apply -k infra/k8s/` or `kubectl apply -f infra/k8s/`.

---

## Phase 10 — Kubernetes Scaling and Availability (Member B)

Member B designed, implemented, and validated dynamic autoscaling, high availability disruption budgets, and zero-downtime rolling update mechanisms for CivicPulse.

### 1. HorizontalPodAutoscaler v2 (`infra/k8s/hpa.yaml`)
- **API Version**: `autoscaling/v2` targeting the FastAPI backend `Deployment`.
- **Scaling Bounds**:
  - `minReplicas`: 2 (preserving high availability baseline even under zero load).
  - `maxReplicas`: 10 (capping resource consumption against cluster capacity).
- **Target Utilization**: CPU `averageUtilization: 60%` calculated against container CPU requests (`250m`).
- **Dynamic Behavior Policies**:
  - `scaleUp`: Rapid response with `stabilizationWindowSeconds: 0`. Scaling policy allows adding up to 100% or 4 pods every 15 seconds (`selectPolicy: Max`), accommodating sudden civic incident surges.
  - `scaleDown`: Defensive stabilization with `stabilizationWindowSeconds: 300` (5 minutes) and a maximum reduction rate of 20% per 60 seconds (`selectPolicy: Min`), preventing metric flapping and thrashing during intermittent traffic bursts.

### 2. High Availability via PodDisruptionBudget (`infra/k8s/pdb.yaml`)
- **Backend PDB (`backend-pdb`)**: Enforces `minAvailable: 1` matching `app: backend`.
- **Frontend PDB (`frontend-pdb`)**: Enforces `minAvailable: 1` matching `app: frontend`.
- **Disruption Safety**: During voluntary disruptions (e.g. `kubectl drain`, node OS kernel updates, cluster auto-upgrades), the Kubernetes eviction API halts pod evictions if doing so violates `minAvailable: 1`, guaranteeing uninterrupted public citizen access.

### 3. Zero-Downtime Rolling Update Strategy & Rollout Continuity
Both frontend and backend deployments configure safe rolling update bounds:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```
- `maxSurge: 1`: Launches an extra replacement pod before evicting any existing pod.
- `maxUnavailable: 0`: Guarantees that at no point in time does available capacity drop below 100% of desired replicas.
- **Drainage Hook**: Combined with `preStop: exec: ["sh", "-c", "sleep 5"]` and `terminationGracePeriodSeconds: 30`, ensuring traffic stops routing to the terminating container before Uvicorn receives `SIGTERM`.
- **Continuity Verification**: Tested via continuous 50ms interval polling during `kubectl rollout restart deployment/backend`, achieving 842 successful probes with 0 failures (0.00% drop rate).
- **Production Boundary Qualification**: In cloud-managed multi-zone clusters, achieving zero downtime additionally requires aligning cloud load balancer target group deregistration delays (typically 15–30s) and ingress proxy retries (`proxy_next_upstream`) with container termination periods.

### 4. Non-Intrusive Vertical Pod Autoscaler (`infra/k8s/vpa.yaml`)
- **API Version**: `autoscaling.k8s.io/v1` targeting `backend`.
- **Execution Mode**: Mandated `updateMode: "Off"`.
- *Architectural Rationale*: Running VPA in `Auto` or `Recreate` mode alongside an HPA that targets the same metric (CPU) causes dangerous control-loop thrashing—VPA resizes container requests while HPA recalculates replica counts based on those requests. In `Off` mode, VPA purely analyzes historical consumption telemetry and generates right-sizing recommendations (`lowerBound`, `target`, `upperBound`) without evicting pods.

### 5. Cluster Resource Metrics & In-Cluster Infrastructure
- Provided [`infra/k8s/metrics-server.yaml`](../infra/k8s/metrics-server.yaml) deploying `v0.7.2` of the Kubernetes metrics server.
- **Security Boundary & Local Workaround**: Configured with `--kubelet-insecure-tls` strictly as a local development workaround for clusters (Docker Desktop, KinD, Minikube) where kubelet serving certificates are self-signed. In production enterprise deployments (EKS, GKE, AKS), this flag is omitted and kubelet serving certificates are validated against the cluster root CA.

### 6. Automated Load Testing & Scaling Evidence
- Built [`scripts/k8s_load_test.py`](../scripts/k8s_load_test.py), a portable multi-threaded load generator utilizing the Python standard library.
- Executed high-intensity load test (25 concurrent worker threads, 13,542 requests at 225.40 RPS over 60s against the forwarded `backend` service).
- Verified HPA auto-scaling progression from 2 &rarr; 4 &rarr; 6 replicas as CPU surged past the 60% threshold, followed by 300s gradual cool-down.
- Captured complete terminal logs, cluster context (`docker-desktop`), HPA inspection data, VPA recommendations, and zero-downtime rollout outputs in [`docs/evidence/HPA-SCALING-EVIDENCE.md`](./evidence/HPA-SCALING-EVIDENCE.md).

---

## Phase 11 — Security Hardening and Vulnerability Review

Implemented comprehensive defense-in-depth security hardening across container runtimes, Kubernetes workloads, network isolation, and application boundaries:

### 1. Non-Root Execution & Linux Capabilities Dropping
- **Backend**: Container runs as non-root user `app` (`UID 1000, GID 1000`) with no shell or home directory access. Configured with `capabilities: drop: ["ALL"]` and `allowPrivilegeEscalation: false`.
- **Frontend**: Nginx container runs as non-root user `nginx` (`UID 101, GID 101`). Drops all capabilities with minimal `NET_BIND_SERVICE` permission.
- **Seccomp Profile**: Configured `seccompProfile: {type: RuntimeDefault}` across all workload specifications.

### 2. Read-Only Root Filesystems
- Application containers (`backend` and `frontend`) enforce `readOnlyRootFilesystem: true`.
- Ephemeral scratch directories are strictly mounted via temporary in-memory volumes (`emptyDir: {}`) at `/tmp`, `/var/cache/nginx`, and `/var/run`.
- Python bytecode creation is disabled (`ENV PYTHONDONTWRITEBYTECODE=1`), ensuring the interpreter functions without attempting to write to read-only directories.

### 3. Kubernetes Least-Privilege & Network Microsegmentation
- **ServiceAccount Token Protection**: Pods declare `automountServiceAccountToken: false` to eliminate API credential extraction risk in the event of an application compromise.
- **NetworkPolicies (`infra/k8s/networkpolicy.yaml`)**:
  - `default-deny-all`: Blocks ingress by default.
  - `frontend-allow-ingress`: Permits ingress on port 80; isolates frontend completely from direct DB/cache access.
  - `backend-allow-ingress-and-frontend`: Permits ingress from Nginx reverse proxy and external API router.
  - `postgres-allow-backend-only`: Limits port 5432 ingress exclusively to pods with `app: backend`.
  - `redis-allow-backend-only`: Limits port 6379 ingress exclusively to pods with `app: backend`.

### 4. Secret Hygiene & CORS Hardening
- Audit confirms **0 committed secrets or credentials** across Git history. `.env` is ignored by `.gitignore:35`.
- `backend/app/core/config.py` enforces deliberate CORS validation: raises a `ValueError` if wildcard `"*"` origins are combined with credentials, and forbids wildcards in production environments.
- Rate limiting and XML prompt-injection boundary guardrails remain actively enforced.
- Complete audit report published in [`docs/evidence/SECURITY-HARDENING-AUDIT.md`](./evidence/SECURITY-HARDENING-AUDIT.md).

---

## Phase 12 — Continuous Integration Pipeline (Member B)

Member B architected and implemented the GitHub Actions Continuous Integration pipeline (`.github/workflows/ci.yml`), establishing strict automated quality gates for pull requests and development branch commits:

### 1. Workflow Architecture & Triggers
- **Triggers**: Configured to run on `push: branches: [dev]` and `pull_request: branches: [main, dev]`.
- **Least-Privilege Security**: Root-level `permissions: contents: read` restricts GitHub Actions tokens from unauthorized modifications.
- **Zero Artifact Publishing**: Image build step operates with `push: false`. Release publishing is strictly reserved for Phase 13 CD.

### 2. Job Dependency Gating (`needs: [...]`)
The workflow enforces a directed acyclic graph (DAG) across 8 distinct jobs:
1. `lint-and-type`: Executes Ruff linting (`ruff check`), Ruff format verification (`ruff format --check`), MyPy static type checking (`mypy --config-file backend/pyproject.toml backend/app`), ESLint (`--max-warnings 0`), and TypeScript compiler validation (`tsc --noEmit`).
2. `test-backend`: Depends on `lint-and-type`. Runs Pytest with live PostgreSQL 16 and Redis 7 service containers, enforcing code coverage $\ge 65\%$ (`--cov-fail-under=65`) under deterministic `TRIAGE_PROVIDER=simulated`.
3. `test-frontend`: Depends on `lint-and-type`. Executes the full 15-test Vitest suite covering UI components and integration flows.
4. `manifests`: Depends on `lint-and-type`. Uses `kubeconform` (v0.6.7) to validate Kustomize-rendered production manifests against Kubernetes 1.30 schemas.
5. `build`: Depends on `test-backend` and `test-frontend`. Builds `civicpulse-backend:ci` and `civicpulse-frontend:ci` via Docker Buildx and exports them as workflow artifacts.
6. `scan`: Depends on `build`. Executes container vulnerability scanning with `aquasecurity/trivy-action@0.28.0`, gating on `CRITICAL,HIGH` vulnerabilities with `--ignore-unfixed`.
7. `integration`: Depends on `build`. Spins up the stack via `docker compose up -d --build`, polls `/ready` until healthy, submits a complaint, asserts category persistence, and verifies `X-Cache` transitions from `MISS` to `HIT` before tearing down with `docker compose down -v`.
8. `ci-gate`: Aggregate status evaluator requiring all 7 prerequisite jobs to report `success`. Fails with exit code 1 if any upstream job fails.

### 3. Submission Verification Script (`scripts/check_submission.py`)
- Automated linting script enforcing the non-negotiables of Section 5.3:
  - Zero committed `.env` files.
  - Zero `:latest` image tags.
  - Zero `localhost` service-to-service communication.
  - No database or cache ports published in `compose.prod.yaml`.
  - PostgreSQL configured as StatefulSet with volumeClaimTemplates.
  - Complete CI job and dependency gate validation.
  - Secret placeholder verification.

---

## Phase 13 — Continuous Delivery Pipeline & Ephemeral Deployments (Member B)

Member B architected and implemented the automated Continuous Delivery pipeline (`.github/workflows/cd.yml`) and Release workflow (`.github/workflows/release.yml`):

### 1. Delivery Architecture & Triggers
- **Triggers**: Executed on push to `main` (deployable release branch), version tags (`v*.*.*`), or manual `workflow_dispatch`.
- **Least-Privilege RBAC**: `permissions: contents: read, packages: write` scoped specifically to publishing images to GitHub Container Registry (GHCR).
- **Gating by Needs**: `build-push` is strictly gated on `needs: [test]`, and `deploy-k8s` is strictly gated on `needs: [build-push]`. No artifacts are compiled or deployed from failing code.

### 2. Immutable Image Publishing & SBOM Generation
- **Registry Targets**: `ghcr.io/i243137-oss/civicpulse-backend` and `ghcr.io/i243137-oss/civicpulse-frontend`.
- **Immutable References**: Every deployed container is tagged with the exact Git commit SHA (`${{ github.sha }}`) and tracked by image digest. The `:latest` tag is published solely for discovery and is **strictly prohibited from deployment**.
- **Software Bill of Materials (SBOM)**: Integrated Syft via `anchore/sbom-action@v0` to generate machine-readable SPDX-JSON catalogs for every layer of backend and frontend images, published as workflow artifacts (`sbom-*.spdx.json`).

### 3. Ephemeral Kubernetes Deployment & Smoke Verification
- Provisions an ephemeral KinD cluster with host port mappings (`80`, `443`) via `infra/k8s/kind-config.yaml`.
- Configures `ghcr-secret` image pull credentials and patches `default` ServiceAccount in namespace `civicpulse`.
- Applies declarative Kustomize production manifests (`overlays/prod`) updating image tags to the immutable commit SHA.
- Waits for rollout completion across `statefulset/postgres`, `deployment/redis`, `deployment/backend`, and `deployment/frontend`.
- Executes automated smoke tests verifying `/health`, `/ready`, `/api/stats`, and `kubectl get hpa`.

### 4. Rollback Mechanisms
Demonstrates two industry-standard rollback mechanisms:
1. **Imperative Rollback (`kubectl rollout undo deployment/backend -n civicpulse`)**: The fast, 3:00 AM emergency answer that instantly reverts the ReplicaSet to the previous stable revision.
2. **Declarative Rollback (Git Revert / Kustomize SHA Update)**: The auditable, permanent answer that records the rollback in Git history, prevents configuration drift, and ensures reproducibility.

---

## Phase 14 — Production Docker Compose Parity & Isolation Hardening

### 1. Architectural Scope & Image-Only Parity
Phase 14 delivers an enterprise-grade production Compose stack (`docker-compose.prod.yml` and `compose.prod.yaml`) mirroring production constraints:
- **Zero `build:` Directives**: Eliminates developer build contexts in production, requiring pre-built, security-scanned images from GHCR (`ghcr.io/i243137-oss/*`).
- **Immutable Tag Pinning**: Enforces explicit tag specification `${IMAGE_TAG}` with fallback to immutable semantic version (`v1.0.0`), preventing mutable `:latest` tag risks.
- **Zero Development Bind Mounts**: Application code is fully compiled and baked inside container layers; runtime changes require image deployment.

### 2. Edge vs Internal Network Segmentation
Enforces strict dual-tier bridge isolation:
1. **`edge` Network (`civicpulse_edge`)**:
   - Contains `frontend` (Nginx reverse proxy) and `backend` (FastAPI).
   - Ingress port `80` is mapped on the host, directing citizen traffic to Nginx.
   - Nginx routes `/api/*`, `/health`, `/ready`, `/metrics`, and `/docs` to `backend:8000`.
2. **`internal` Network (`civicpulse_internal`, `internal: true`)**:
   - Contains `backend`, `postgres`, and `redis`.
   - `internal: true` instructs the Docker daemon to block external egress and host port exposure.
   - `postgres` (5432) and `redis` (6379) publish **zero host ports**, rendering them unreachable outside the private container mesh.

### 3. Durability & Startup Ordering
- **Postgres Durability**: Named volume `pgdata` mounted to `/var/lib/postgresql/data`.
- **Redis AOF Persistence**: Named volume `redisdata` mounted to `/data` with `--appendonly yes --appendfsync everysec`.
- **Startup Gating**: `depends_on` with `condition: service_healthy` ensures ordered bootstrapping: DB & Cache $\to$ Backend Migrations/Seed $\to$ Frontend.

---

## Lessons Learned

1. **Structured Output Enforcement in Production**: Free-tier LLMs occasionally wrap JSON in explanatory text or markdown code fences (`json ... `). Robust regex extraction combined with Pydantic model validation prevents runtime crashes and ensures enum compliance.
2. **Resilient Triage Fallback**: AI services are inherently non-deterministic and subject to upstream rate limits and network degradation. An automated intake platform must treat the LLM as an opportunistic optimization, with an immediate, deterministic heuristic fallback path (`RuleBasedTriage`) ensuring uninterrupted citizen service.
3. **Data Residency and Minimization**: By stripping `reporter_contact` prior to invoking external inference, municipal compliance is preserved without compromising classification accuracy.
4. **StatefulSet vs Deployment for Databases**: Using a Deployment for a database causes split-brain risks and mount conflicts upon rescheduling because Deployments assume stateless, interchangeable pods. StatefulSet guarantees ordered deployment, stable network identities, and dedicated persistent volumes per ordinal replica.
5. **HPA and VPA Control Loop Decoupling**: Combining HPA (horizontal scaling) and VPA (vertical scaling) on the same resource metric (CPU) creates antagonistic control loops. Keeping VPA in `updateMode: "Off"` allows non-intrusive baseline recommendation gathering while empowering HPA to dynamically manage traffic spikes.
6. **Container Read-Only Filesystem Isolation**: Enforcing `readOnlyRootFilesystem: true` blocks attackers from downloading or writing executable payloads in the container. However, runtimes require careful emptyDir provisioning for transient sockets and caches (`/tmp`, `/var/run`, `/var/cache/nginx`) and disabling bytecode writes (`PYTHONDONTWRITEBYTECODE=1`).
7. **Strict CI Dependency Gating (`needs`)**: Running builds and integration tests on code that fails basic linting or unit tests wastes expensive compute minutes and obscures root causes. Designing a tiered dependency DAG ensures failures fail fast at the earliest static analysis rung, protecting downstream runners.
8. **Dual-Mechanism Rollback Strategy**: During a live production outage, imperative rollback (`kubectl rollout undo`) restores service in seconds. However, declarative rollback (reverting the commit in Git and updating the Kustomize SHA tag) is essential post-incident to preserve single-source-of-truth GitOps compliance and prevent subsequent CI/CD runs from redeploying faulty code.
9. **Production Compose Parity and Internal Network Flags**: Development compose environments frequently publish database and cache ports (5432, 6379) for developer debugging tools like pgAdmin or RedisInsight. In production Compose, setting `internal: true` on the database network guarantees that Docker prevents both external inbound traffic and accidental outbound leakage, while omitting published ports enforces ingress exclusively through the reverse proxy edge.






