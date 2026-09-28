# 🤖 AI Usage Log — CivicPulse

> This document tracks every instance where AI tools were used during development.
> Required for transparency, academic integrity, and engineering audit trails.

---

## Format

Each entry follows this template:

```
### YYYY-MM-DD — <Short Description>

- **Tool:** <AI tool name and model>
- **Prompt summary:** <What was asked>
- **Output used:** <What was kept / modified / discarded>
- **Human review:** <What the developer verified or changed>
```

---

## Log

### 2026-09-28 — Phase 7: Backend Testing Architecture, Validation, and Full-Path Verification (Member A)

- **Tool:** Google Antigravity (Gemini)
- **Prompt summary:** Implement Member A backend testing architecture and quality gates for Phase 7 per assignment specifications. Add comprehensive schema validation test suite (`test_validation.py`) testing boundaries, enums, parameter constraints, and malformed UUID rejection. Add full-path backend integration test (`test_full_path_integration.py`) validating the complete lifecycle (probes, stats caching, auto-triage intake, write invalidation, duplicate content-hash cache, telemetry hit_rate, multi-filter pagination, state machine progression, conflict rejection, and stats consistency). Configure `[tool.coverage.run]` and `[tool.coverage.report]` with `fail_under = 85` in `pyproject.toml`. Verify clean SQLite engine disposal in migration tests and ensure complete air-gapped test execution with zero external paid AI dependencies.
- **Output used:** `backend/pyproject.toml`, `backend/tests/test_validation.py`, `backend/tests/test_full_path_integration.py`, `backend/tests/test_migrations.py`, `backend/app/schemas/complaint.py`, `docs/ENGINEERING-NOTES.md`, and `docs/AI-USAGE.md`.
- **Human review:** Executed complete test suite (84 passed, 1 skipped) with 90% total statement coverage on `backend/app/`, verified 0 linting errors (`ruff check`), and confirmed strict typing (`mypy`).

### 2026-09-27 — Phase 7: Testing, Quality, and Full-Path Verification (Member B)


- **Tool:** Google Antigravity (Gemini)
- **Prompt summary:** Implement Member B testing and quality gates for Phase 7 per assignment specifications. Add comprehensive full application integration test (`AppIntegration.test.tsx`) validating the complete user journey (Navbar navigation, complaint intake, automated triage feedback, detail inspection, status transition, list queue return). Fix cross-platform test execution in backend tests (`sys.executable -m alembic` and SQLAlchemy engine disposal on Windows SQLite temporary files). Verify frontend lint (`npm run lint`), type checking (`tsc --noEmit`), production build (`npm run build`), Vitest suite (15 passed tests across 6 suites), and backend test suite (72 passed tests with 90% coverage on `app/`).
- **Output used:** `frontend/src/tests/AppIntegration.test.tsx`, `backend/tests/test_postgres_compatibility.py`, `backend/tests/test_migrations.py`, `docs/ENGINEERING-NOTES.md`, and `docs/AI-USAGE.md`.
- **Human review:** Verified all 6 Vitest suites (15 tests) pass, verified backend pytest suite passes with 90% statement coverage on `app/` (exceeding 65% threshold), confirmed 0 ESLint warnings, and verified production build bundling.

### 2026-09-27 — Phase 6: Docker Compose, Network Segmentation, and Cloud-Native Stack (Member B)

- **Tool:** Google Antigravity (Gemini)
- **Prompt summary:** Implement Phase 6 Docker Compose cloud-native stack per assignment specifications. Configure two isolated bridge networks (`edge` and `internal` with `internal: true`). Connect frontend strictly to edge and backend to edge + internal. Configure PostgreSQL and Redis on internal without exposing ports in production. Use service names for container-to-container communication. Configure named volumes (`pgdata`, `redisdata`, `ollama_models`) and Redis AOF persistence (`--appendonly yes --appendfsync everysec`). Implement healthchecks and `depends_on: service_healthy` startup orchestration. Build production Nginx reverse proxy for `/api/` and `/health`. Keep development bind mounts only in development Compose configuration. Validate stack convergence, network isolation, and end-to-end complaint intake/triage/stats flow.
- **Output used:** `compose.yaml`, `compose.prod.yaml`, `docker-compose.yml`, `docker-compose.prod.yml`, `.env.example`, `backend/requirements.txt` (added `httpx`), `docs/ENGINEERING-NOTES.md`, and `docs/AI-USAGE.md`.
- **Human review:** Verified all 4 containers healthy (`docker compose ps`), confirmed frontend cannot resolve or reach postgres/redis (`nc: bad address`), verified backend connects to postgres and redis, verified Redis AOF enabled (`aof_enabled:1`), verified `/health`, `/api/stats` cache hit/miss, and verified POST `/api/complaints` auto-triage and status transition PATCH.

### 2026-09-27 — PR #12 Review Fixes: Elimination of Duplicated FSM, ErrorBoundary Mount, Reverse Proxy, Intake Form Cleanup, and Resilient API Client

- **Tool:** Google Antigravity (Gemini)
- **Prompt summary:** Address code review findings for PR #12 (`feature/frontend-ui`). Remove duplicated status state machine from frontend and make allowed transitions backend-owned, mount ErrorBoundary around application tree, fix `/health` client endpoint, implement production Nginx reverse proxy configuration and pin container images (`node:22-alpine`, `nginx:1.27-alpine`), remove category/priority pre-assignment controls from citizen intake form, prevent multiple-read body stream issues in API client, prevent duplicate status submissions and out-of-order response overwrites with AbortController, and fix 409 transition test consistency.
- **Output used:** Updated `backend/app/schemas/complaint.py` (`allowed_transitions` computed field), `frontend/src/types/complaint.ts`, `frontend/src/api/client.ts`, `frontend/src/pages/ComplaintsPage.tsx`, `frontend/src/pages/ComplaintDetailPage.tsx`, `frontend/src/pages/SubmitPage.tsx`, `frontend/src/App.tsx`, `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`, Vitest test suites, ADR-0003, and engineering notes.
- **Human review:** Verified backend unit/integration tests (`pytest`, 15 passed), frontend component tests (`vitest run`, 14 passed across 5 suites), ESLint (`npm run lint`), TypeScript checking (`tsc --noEmit`), and production build (`npm run build`).

### 2026-09-27 — Phase 5: Frontend Implementation, Typed Client, and Component Tests

- **Tool:** Claude (Anthropic) via Cline VS Code extension
- **Prompt summary:** Implement Phase 5 React TypeScript frontend according to the assignment rubric and master AI specification. Create typed API models matching backend schemas, implement central API client with relative `/api` paths, develop views (SubmitPage with honest loading state, DashboardPage with X-Cache badge and provider observability, ComplaintsPage with filters and pagination, ComplaintDetailPage with status transitions), implement ErrorBoundary, configure Vitest suite with >= 5 meaningful component tests, and document ADR-0003 for frontend runtime configuration.
- **Output used:** React views, components, CSS styles, Vitest component test suites (14 tests across 5 test suites), ADR-0003, and engineering notes.
- **Human review:** Verified TypeScript compilation (`npx tsc --noEmit`), linting (`npm run lint`), production build (`npm run build`), all 14 Vitest component tests (`npm test`), and documented findings.

- **Tool:** Claude (Anthropic) via Cline VS Code extension
- **Prompt summary:** Create a production-oriented folder structure for a full-stack civic issue reporting platform using React TypeScript frontend, FastAPI backend, PostgreSQL, Redis, Docker Compose, Kubernetes, and GitHub Actions.
- **Output used:** Complete repository scaffold — directories, Dockerfiles, docker-compose configs, README, .gitignore, .env.example, documentation templates.
- **Human review:** Developer reviewed all generated files, verified alignment with project requirements, and committed to `dev` branch.
