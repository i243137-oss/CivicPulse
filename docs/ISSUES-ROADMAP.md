# 📋 CivicPulse Phase-by-Phase Issue Roadmap & Work Division

> Complete breakdown of project implementation phases (Phase 8 through Phase 18) divided by roles (**Member A** vs. **Member B**), milestones, descriptions, checklists, and exit gates according to `CivicPulse_AI_Implementation_Specification.docx` and `Software Construction and Design - Assignment 1.pdf`.

---

## Milestone Structure

| Milestone | Target Phases | Core Deliverables |
| :--- | :--- | :--- |
| **Milestone 3: Observability & Kubernetes** | Phase 8, Phase 9, Phase 10 | Structured logging, readiness probes, metrics, K8s manifests, HPA v2, PDB |
| **Milestone 4: Security & CI/CD Automation** | Phase 11, Phase 12, Phase 13, Phase 14 | Security hardening, Trivy CVE scanning, GitHub Actions CI/CD, GHCR, Production Compose |
| **Milestone 5: Documentation & Submission** | Phase 15, Phase 16, Phase 17, Phase 18 | 4 ADRs, Runbook, Rubric traceability, clean verification, release tagging & demo video |

---

## Issues Backlog

### Issue 1: Phase 8 — Observability and Resilience
- **Title**: `[Phase 8] [Both]: Structured Logging, Health vs Readiness Separation, Graceful Shutdown, and Telemetry Metrics`
- **Assignee**: **Both** (Member A: Backend core; Member B: Probe routing & frontend telemetry)
- **Milestone**: `Milestone 3: Observability & Kubernetes`
- **Labels**: `observability`, `backend`, `frontend`, `phase-8`

#### Objective & Work Breakdown
Implement comprehensive production observability, separate liveness from readiness, attach correlated request IDs across all log messages, expose Prometheus metrics, and ensure graceful SIGTERM container termination to prevent request drops during rolling updates.

**Member A (Backend)**:
- [ ] Add JSON structured logging (`python-json-logger`) emitting timestamps, log levels, service names, and correlated request IDs.
- [ ] Implement middleware to generate or propagate `X-Request-ID` across every HTTP request and log context.
- [ ] Ensure strict separation between `/health` (pure liveness with zero external dependencies) and `/ready` (readiness probing PostgreSQL `SELECT 1` and Redis `PING`).
- [ ] Expose Prometheus metrics endpoint (`/metrics`) recording HTTP request counts, request latency histograms, AI triage inference latency, content-hash cache hits/misses, and fallback counters.
- [ ] Configure graceful SIGTERM shutdown in Uvicorn handling in-flight requests and safely closing DB/Redis connection pools.

**Member B (Frontend & Ingress)**:
- [ ] Route `/health`, `/ready`, and `/metrics` through the Nginx reverse proxy configuration (`frontend/nginx.conf`).
- [ ] Update frontend client and dashboard telemetry view to expose live provider latency and cache hit-rate telemetry from `/api/meta/providers`.
- [ ] Verify that `/ready` returns HTTP 503 if PostgreSQL or Redis is stopped, without marking `/health` unready.

#### Exit Gate
- `/health` returns 200 OK without database/redis dependencies.
- `/ready` returns 200 OK when dependencies are healthy and 503 Service Unavailable when DB or Redis is stopped.
- Logs output valid structured JSON containing `request_id`.
- Metrics are scrapable at `/metrics`.
- Application gracefully drains connections on SIGTERM.

---

### Issue 2: Phase 9 — Kubernetes Baseline
- **Title**: `[Phase 9] [Member B]: Kubernetes Baseline Manifests, StatefulSet, Deployments, and Ingress`
- **Assignee**: **Member B**
- **Milestone**: `Milestone 3: Observability & Kubernetes`
- **Labels**: `kubernetes`, `devops`, `infrastructure`, `phase-9`

#### Objective & Work Breakdown
Create production-grade Kubernetes manifests deploying CivicPulse into a dedicated `civicpulse` namespace with high availability, isolated storage, and Ingress routing.

**Scope (Member B)**:
- [x] Create dedicated namespace manifest: `infra/k8s/namespace.yaml` (`civicpulse`).
- [x] Create `ConfigMap` (`configmap.yaml`) for non-sensitive configuration and `Secret` (`secrets.yaml` / template) for database passwords and API keys.
- [x] Create PostgreSQL `StatefulSet` (`postgres-statefulset.yaml`) backed by a PersistentVolumeClaim (`PVC`) to guarantee data durability across pod rescheduling.
- [x] Create Redis `Deployment` (`redis-deployment.yaml`) with persistent volume for AOF logs.
- [x] Create `ClusterIP` Services for backend, frontend, postgres, and redis (zero external port publishing for database or cache).
- [x] Create FastAPI `backend` and React `frontend` `Deployments` with $\ge 2$ replicas each.
- [x] Configure `livenessProbe` (`/health`), `readinessProbe` (`/ready`), and `startupProbe` on application pods.
- [x] Define explicit CPU/Memory resource `requests` and `limits` on every container.
- [x] Create Kubernetes `Ingress` (`ingress.yaml`) routing `/` to `frontend` and `/api` to `backend`.
- [x] Enforce image immutability (disallow `:latest` tag in manifests).

#### Exit Gate
- [x] `kubectl apply -f infra/k8s/` / `kubectl kustomize infra/k8s/` succeeds without errors.
- [x] All pods configured with startup/liveness/readiness probes and $\ge 2$ replicas.
- [x] Ingress successfully routes public traffic to frontend and proxies API requests.
- [x] No database or Redis ports published outside the cluster (ClusterIP only).

---

### Issue 3: Phase 10 — Kubernetes Scaling and Availability
- **Title**: `[Phase 10] [Member B]: Horizontal Pod Autoscaling (HPA v2), PodDisruptionBudget, and Load Test Evidence`
- **Assignee**: **Member B**
- **Milestone**: `Milestone 3: Observability & Kubernetes`
- **Labels**: `kubernetes`, `scaling`, `hpa`, `phase-10`

#### Objective & Work Breakdown
Implement dynamic horizontal pod autoscaling, ensure zero-downtime rolling update safety using PodDisruptionBudgets, configure Vertical Pod Autoscaler in `Off` mode, and capture load-test scaling evidence.

**Scope (Member B)**:
- [x] Configure `HorizontalPodAutoscaler` (`hpa.yaml`) targeting backend Deployment with `minReplicas: 2`, `maxReplicas: 10`, and target CPU utilization `60%`.
- [x] Implement `PodDisruptionBudget` (`pdb.yaml`) for backend and frontend (`minAvailable: 1` or `maxUnavailable: 1`) to preserve service availability during node drains or rolling updates.
- [x] Configure zero-downtime rolling update strategy (`maxSurge: 1`, `maxUnavailable: 0`) in Deployments.
- [x] Configure Vertical Pod Autoscaler (`vpa.yaml`) in `updateMode: "Off"` to capture resource recommendation baseline.
- [x] Ensure cluster `metrics-server` is deployed and operational (`infra/k8s/metrics-server.yaml`).
- [x] Execute an automated load test (`scripts/k8s_load_test.py`) to trigger HPA scaling from 2 to $\ge 4$ replicas.
- [x] Capture evidence artifacts: terminal recording of `kubectl get hpa -w`, `kubectl describe vpa`, and load-test metrics in `docs/evidence/HPA-SCALING-EVIDENCE.md`.

#### Exit Gate
- [x] HPA automatically scales backend pods upwards when traffic spikes and scales back down when traffic subsides.
- [x] PodDisruptionBudget prevents downtime during node maintenance.
- [x] Evidence files saved under `docs/evidence/`.

---

### Issue 4: Phase 11 — Security Hardening and Vulnerability Review
- **Title**: `[Phase 11] [Both]: Non-Root Containers, Capabilities Dropping, Trivy Scanning, and Security Audit`
- **Assignee**: **Both** (Member B: Containers & Trivy; Member A: Dependencies, CORS & injection guardrails)
- **Milestone**: `Milestone 4: Security & CI/CD Automation`
- **Labels**: `security`, `hardening`, `trivy`, `phase-11`

#### Objective & Work Breakdown
Harden container runtimes and Kubernetes configurations according to the principle of least privilege, drop unnecessary Linux capabilities, run automated vulnerability scans, and audit security controls.

**Member B (Infrastructure & Containers)**:
- [ ] Enforce non-root user execution (`USER app`, UID 1000) across backend and frontend containers.
- [ ] Configure Kubernetes `securityContext`: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`.
- [ ] Drop all capabilities (`capabilities: drop: ["ALL"]`) except essential network binding.
- [ ] Set up container vulnerability scanning with Trivy (failing on unmitigated CRITICAL CVEs).
- [ ] Verify Docker container digest/tag pinning.

**Member A (Application Security)**:
- [ ] Run `pip audit` / `safety` and `npm audit` to verify zero high/critical vulnerable dependencies.
- [ ] Restrict CORS policies to trusted domains (disallowing wildcards with credentials in production).
- [ ] Ensure citizen input is strictly sanitized and prompt-injection guardrails wrap all untrusted text in XML tags.
- [ ] Verify secret hygiene: ensure zero passwords, tokens, or API keys exist in git history or logs.

#### Exit Gate
- Containers run non-root with dropped capabilities and read-only root filesystems where applicable.
- Trivy vulnerability scans produce clean reports with 0 unmitigated Critical CVEs.
- `git log` and codebase verify zero committed secrets.

---

### Issue 5: Phase 12 — Continuous Integration Pipeline
- **Title**: `[Phase 12] [Member B]: GitHub Actions CI Workflow with Matrix Testing, Linting, and Kubeconform Gates`
- **Assignee**: **Member B**
- **Milestone**: `Milestone 4: Security & CI/CD Automation`
- **Labels**: `ci`, `github-actions`, `testing`, `phase-12`

#### Objective & Work Breakdown
Create a robust, gated Continuous Integration workflow (`.github/workflows/ci.yml`) triggered on pull requests to `main` and pushes to `dev`, ensuring no untested or unlinted code can be merged.

**Scope (Member B)**:
- [ ] Create `.github/workflows/ci.yml` with strict job dependencies (`needs: [...]`).
- [ ] Job 1: `backend-lint`: Ruff linting, formatting, and MyPy static type checking.
- [ ] Job 2: `backend-test`: Pytest with SQLite/mock redis, enforcing $\ge 65\%$ code coverage (`TRIAGE_PROVIDER=simulated`).
- [ ] Job 3: `frontend-lint`: ESLint (`--max-warnings 0`) and TypeScript build verification (`tsc --noEmit`).
- [ ] Job 4: `frontend-test`: Vitest component and integration testing suite.
- [ ] Job 5: `k8s-validate`: Validate all Kubernetes manifests against schema with `kubeconform`.
- [ ] Job 6: `security-scan`: Run Trivy container and filesystem vulnerability scan.
- [ ] Job 7: `ci-gate`: Aggregate gate job requiring all prerequisite jobs to succeed.
- [ ] Configure least-privilege `permissions:` block in the workflow.

#### Exit Gate
- Pull requests run all 7 jobs in parallel/dependency order.
- A simulated failing test or lint error blocks the merge gate.
- Clean PRs receive a 100% green checkmark.

---

### Issue 6: Phase 13 — Continuous Delivery Pipeline & Ephemeral Deployments
- **Title**: `[Phase 13] [Member B]: GitHub Actions CD Workflow, GHCR Image Publishing, SBOM, and Rollback Verification`
- **Assignee**: **Member B**
- **Milestone**: `Milestone 4: Security & CI/CD Automation`
- **Labels**: `cd`, `github-actions`, `ghcr`, `deployment`, `phase-13`

#### Objective & Work Breakdown
Create an automated Continuous Delivery workflow (`.github/workflows/cd.yml`) triggered on push to `main` or release tag. Build, sign, and publish immutable container images to GitHub Packages (GHCR), generate an SBOM, deploy to a test environment, execute smoke tests, and document rollback.

**Scope (Member B)**:
- [ ] Create `.github/workflows/cd.yml` triggered on push to `main` and version tags (`v*.*.*`).
- [ ] Build multi-platform production container images using `docker/build-push-action`.
- [ ] Tag images with immutable Git commit SHA (`${{ github.sha }}`) and semantic version; strictly avoid deploying `:latest`.
- [ ] Publish images to GitHub Container Registry (GHCR: `ghcr.io/<org>/civicpulse-*`).
- [ ] Generate Software Bill of Materials (SBOM) using Syft or Trivy (`anchore/sbom-action`).
- [ ] Deploy manifests to an ephemeral Kubernetes cluster (KinD or Minikube).
- [ ] Run automated post-deployment smoke tests (`curl` health and stats endpoints).
- [ ] Document and demonstrate the rollback procedure (`kubectl rollout undo deployment/...`).

#### Exit Gate
- Images successfully published to GHCR with commit SHA tags.
- SBOM published as workflow artifact.
- Automated smoke tests verify deployment liveness and readiness.
- Rollback command proven functional in evidence logs.

---

### Issue 7: Phase 14 — Production Docker Compose Parity
- **Title**: `[Phase 14] [Member B]: Production Compose Image-Only Stack and Isolation Hardening`
- **Assignee**: **Member B**
- **Milestone**: `Milestone 4: Security & CI/CD Automation`
- **Labels**: `docker`, `docker-compose`, `production`, `phase-14`

#### Objective & Work Breakdown
Deliver a production-ready, image-only Docker Compose configuration (`compose.prod.yaml` / `docker-compose.prod.yml`) that runs baked GHCR container images with zero development bind mounts and zero database/cache port publishing.

**Scope (Member B)**:
- [ ] Finalize `compose.prod.yaml` and `docker-compose.prod.yml` to rely 100% on immutable images (`image: ...:${IMAGE_TAG}`), eliminating all `build:` directives.
- [ ] Remove all published host ports for `postgres` and `redis` (accessible solely through the internal bridge network).
- [ ] Enforce resource constraints (`deploy.resources.limits` and `reservations`) for all 4 services.
- [ ] Configure `restart: always` on all production services.
- [ ] Verify Redis AOF persistence and automated DB migration on boot.
- [ ] Validate configuration using `docker compose -f compose.prod.yaml config`.

#### Exit Gate
- `docker compose -f compose.prod.yaml config` validates with zero errors.
- Stack contains zero `build:` instructions and zero host-exposed internal database ports.

---

### Issue 8: Phase 15 — System Documentation, Runbook, and Architectural Decision Records (ADRs)
- **Title**: `[Phase 15] [Both]: Comprehensive README, Production Runbook, and Complete ADR Suite`
- **Assignee**: **Both** (Member A: Backend & AI ADRs; Member B: Operations, Runbook & K8s ADRs)
- **Milestone**: `Milestone 5: Documentation & Submission`
- **Labels**: `documentation`, `runbook`, `adr`, `phase-15`

#### Objective & Work Breakdown
Provide comprehensive, production-grade documentation enabling an external engineer to onboard, configure, test, deploy, and troubleshoot CivicPulse from a clean machine.

**Work Division**:
- **Member A**:
  - [ ] Update `README.md` with complete API documentation, request/response samples, and environment variable schema.
  - [ ] Document ADR 0001: AI Provider Strategy (LLM, Ollama, Rules fallback, jittered retry).
  - [ ] Document ADR 0004: PII Masking and Data Residency Governance.
- **Member B**:
  - [ ] Complete `docs/RUNBOOK.md` detailing operational procedures: health checks, disaster recovery, Redis AOF restoration, log inspection, and zero-downtime rollback.
  - [ ] Document ADR 0002: Container Runtime & Network Boundary Segmentation.
  - [ ] Document ADR 0003: Frontend Runtime Configuration & Reverse Proxy Architecture.
  - [ ] Verify `README.md` quickstart instructions from a fresh clone.

#### Exit Gate
- All 4 ADRs finalized and linked in `docs/adr/`.
- `README.md` allows clean startup via single Compose/Kubernetes command.
- `RUNBOOK.md` provides clear recovery steps for simulated service failures.

---

### Issue 9: Phase 16 — Rubric and Evidence Mapping
- **Title**: `[Phase 16] [Both]: Rubric Traceability Matrix, Screenshot/Log Evidence Collection, and Demo Script`
- **Assignee**: **Both**
- **Milestone**: `Milestone 5: Documentation & Submission`
- **Labels**: `evidence`, `rubric`, `compliance`, `phase-16`

#### Objective & Work Breakdown
Systematically map every rubric criterion from Assignment 01 to exact code implementations, test runs, CI logs, and operational evidence, ensuring 100% auditability.

**Scope (Both)**:
- [ ] Create `docs/EVIDENCE-MAPPING.md` mapping every single rubric item to its file, line number, or command output.
- [ ] Archive evidence under `docs/evidence/`:
  - Network segmentation proof (`frontend` cannot ping `postgres`).
  - Redis cache `HIT`/`MISS` headers and sliding-window rate limit 429 response.
  - Deterministic AI triage fallback when LLM fails.
  - HPA scaling under load (`kubectl get hpa -w`).
  - Zero-downtime rolling update with PodDisruptionBudget.
  - Green GitHub Actions CI/CD run links and SBOM output.
- [ ] Draft a crisp, timed 5-minute final video demonstration script.

#### Exit Gate
- Every single rubric requirement is backed by concrete logs, test runs, or screenshots with zero secrets exposed.

---

### Issue 10: Phase 17 & Phase 18 — Final Verification, Release, and Demo
- **Title**: `[Phase 17-18] [Both]: Clean-Clone Verification, Dev-to-Main PR, Release Tagging, and Final Submission`
- **Assignee**: **Both**
- **Milestone**: `Milestone 5: Documentation & Submission`
- **Labels**: `release`, `verification`, `final-submission`, `phase-17`, `phase-18`

#### Objective & Work Breakdown
Perform end-to-end clean-environment verification, review the master pull request from `dev` to `main`, tag the official release, record the 5-minute demo video, and finalize the submission package.

**Scope (Both)**:
- [ ] Clone repository into a clean directory and execute the complete quickstart flow.
- [ ] Audit non-negotiable failure conditions:
  - Zero committed secrets or `.env` files.
  - Zero `:latest` tags in deployment manifests.
  - Zero container-to-container calls using `localhost`.
  - Zero public port publishing on internal PostgreSQL/Redis.
- [ ] Open and peer-review the final Pull Request from `dev` into `main`.
- [ ] Tag release `v1.0.0` with release notes and immutable container SHA references.
- [ ] Record and upload the 5-minute unlisted demo video covering all rubric requirements.
- [ ] Compile final submission links (GitHub repo, GHCR package links, CI/CD run, video URL, `git shortlog -sn`).

#### Exit Gate
- `dev` cleanly merged into `main` via passing, reviewed PR.
- Release tag `v1.0.0` created.
- Demo video recorded and verified.
