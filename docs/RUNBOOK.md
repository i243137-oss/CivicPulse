# 📘 Operational Runbook — CivicPulse

> **System**: CivicPulse (Full-Stack Municipal Issue Triage Platform)  
> **Audience**: Site Reliability Engineers (SRE), DevOps Engineers, Platform Administrators  
> **Key SLA**: 99.9% Uptime, Zero-Downtime Rolling Deployments, Resilient AI Fallback  

---

## Table of Contents
1. [Service Architecture & Port Matrix](#1-service-architecture--port-matrix)
2. [How to Deploy](#2-how-to-deploy)
3. [How to Read & Filter Logs](#3-how-to-read--filter-logs)
4. [Triage Incident Response (What to Do When Triage Fails)](#4-triage-incident-response-what-to-do-when-triage-fails)
5. [How to Roll Back](#5-how-to-roll-back)
6. [Emergency Runbook Checklist](#6-emergency-runbook-checklist)

---

## 1. Service Architecture & Port Matrix

| Service | Container Name | Internal Port | Edge / Host Port | Health Check |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend** | `civicpulse-frontend` | 80 | **80 (Public)** | `wget -q -O - http://127.0.0.1:80/health` |
| **Backend** | `civicpulse-backend` | 8000 | 8000 (Internal/Debug) | `curl -f http://127.0.0.1:8000/health` |
| **PostgreSQL**| `civicpulse-postgres` | 5432 | **None (Internal Only)** | `pg_isready -U civicpulse -d civicpulse` |
| **Redis** | `civicpulse-redis` | 6379 | **None (Internal Only)** | `redis-cli ping` |

---

## 2. How to Deploy

### A. Production Docker Compose (Image-Only)
Production Compose strictly forbids `build:` directives and deploys pre-scanned images from GitHub Container Registry (GHCR):

```bash
# 1. Configure production environment
cp .env.production.example .env
# Edit .env with production passwords and set IMAGE_TAG to the release commit SHA:
# IMAGE_TAG=30585980a044cf2978601e365f6d97509193bda4

# 2. Validate configuration
docker compose -f docker-compose.prod.yml config

# 3. Pull immutable images and bootstrap services
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# 4. Verify stack convergence
docker compose -f docker-compose.prod.yml ps
curl -i http://localhost:80/health
curl -i http://localhost:80/ready
```

### B. Kubernetes Production Deployment (Kustomize)
```bash
# 1. Inspect rendered manifests
kubectl kustomize infra/k8s/overlays/prod

# 2. Deploy into dedicated namespace
kubectl apply -k infra/k8s/overlays/prod

# 3. Monitor rolling updates
kubectl rollout status statefulset/postgres -n civicpulse
kubectl rollout status deployment/redis -n civicpulse
kubectl rollout status deployment/backend -n civicpulse
kubectl rollout status deployment/frontend -n civicpulse

# 4. Confirm HPA and PDB status
kubectl get hpa,pdb -n civicpulse
```

---

## 3. How to Read & Filter Logs

All CivicPulse backend containers emit **structured JSON logs** to `stdout` containing timestamps, log levels, service identifiers, and propagated `request_id` values.

### A. Docker Compose Log Inspection
```bash
# Stream all logs
docker compose -f docker-compose.prod.yml logs -f backend

# Parse and pretty-print JSON logs using jq
docker compose -f docker-compose.prod.yml logs backend --no-log-prefix | jq .

# Filter for errors or warnings only
docker compose -f docker-compose.prod.yml logs backend --no-log-prefix | jq 'select(.level=="ERROR" or .level=="WARNING")'

# Trace a specific request ID across all container log lines
docker compose -f docker-compose.prod.yml logs backend --no-log-prefix | jq 'select(.request_id=="3f8b1c4e-6d2a-4f9e-bc8e-1a2b3c4d5e6f")'
```

### B. Kubernetes Log Inspection
```bash
# Stream logs from all backend deployment pods
kubectl logs -n civicpulse -l app=backend -f --tail=100 | jq .

# Search for AI triage errors or fallback invocations
kubectl logs -n civicpulse -l app=backend | jq 'select(.message | test("fallback|timeout|triage"; "i"))'

# Inspect ingress access logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50
```

---

## 4. Triage Incident Response (What to Do When Triage Fails)

### Symptoms of AI Triage Degradation
1. Citizen complaints stall on intake with high submission latency ($> 5$ seconds).
2. Complaints are tagged with `triaged_by: "rules:fallback"` instead of `llm` or `ollama`.
3. Prometheus metric `triage_fallback_total` is rapidly incrementing.
4. `/api/meta/providers` reports `average_latency_ms > 4000` or upstream HTTP 429/503.

### Diagnostic Steps
```bash
# 1. Query live provider health and cache statistics
curl -s http://localhost:80/api/meta/providers | jq .

# 2. Check backend structured logs for triage error details
kubectl logs -n civicpulse -l app=backend --tail=100 | jq 'select(.service=="triage" or .logger=="triage_service")'

# 3. Check Prometheus metrics for fallback counters
curl -s http://localhost:80/metrics | grep -E "triage_requests_total|triage_fallback_total|triage_latency_seconds"
```

### Root Causes & Remediation Playbook

| Root Cause | Diagnostic Indicator | Immediate Action / Remediation |
| :--- | :--- | :--- |
| **Upstream LLM Rate Limit** | Log shows `HTTP 429 Too Many Requests` from Groq/OpenAI | 1. Switch to secondary fallback model or local Ollama.<br/>2. If persistent, switch to deterministic heuristic rules (see Step 3 below). |
| **Invalid / Expired API Key** | Log shows `HTTP 401 Unauthorized` | Rotate secret: update `LLM_API_KEY` in `infra/k8s/base/secrets.yaml` and patch secret: `kubectl create secret generic civicpulse-secrets -n civicpulse --from-literal=LLM_API_KEY=... --dry-run=client -o yaml \| kubectl apply -f -`. |
| **Upstream Network Outage** | Log shows `httpx.ConnectTimeout` after 5.0 seconds | The system automatically retries once with jitter, then falls back to `RuleBasedTriageProvider`. Service remains operational. |
| **Ollama Daemon Pod Down** | Log shows `Connection refused on ollama:11434` | Verify Ollama pod: `kubectl get pods -n civicpulse -l app=ollama`. Restart pod: `kubectl rollout restart deployment/ollama -n civicpulse`. |
| **Adversarial Prompt Injection** | Log shows `PROMPT_INJECTION_DETECTED` warning | Guardrail successfully intercepted payload and assigned `category: Other`, `priority: Low`. No remediation needed; payload was neutralized. |

### Emergency Mitigation: Force Heuristic Rule-Based Mode
If an upstream AI provider suffers an extended outage, force immediate fallback to local deterministic rules to eliminate latency:

**In Docker Compose:**
```bash
# Update .env
sed -i 's/TRIAGE_PROVIDER=.*/TRIAGE_PROVIDER=rules/' .env
docker compose -f docker-compose.prod.yml up -d backend
```

**In Kubernetes:**
```bash
kubectl set env deployment/backend -n civicpulse TRIAGE_PROVIDER=rules
kubectl rollout status deployment/backend -n civicpulse
```
*Result: All complaint intake processes instantly locally via keyword regex heuristics in $< 5$ ms with 100% availability.*

---

## 5. How to Roll Back

CivicPulse supports both **immediate imperative rollback** (for emergency 3:00 AM recovery) and **declarative GitOps rollback** (for permanent post-incident remediation).

### A. Immediate Imperative Rollback (Kubernetes — Recovery in Seconds)
If a newly deployed backend version introduces crashes or regression:

```bash
# 1. Roll back deployment to the previous stable ReplicaSet
kubectl rollout undo deployment/backend -n civicpulse

# 2. Monitor rollback progress
kubectl rollout status deployment/backend -n civicpulse

# 3. View revision history
kubectl rollout history deployment/backend -n civicpulse

# 4. Verify endpoints
curl -sf http://localhost:80/health
curl -sf http://localhost:80/ready
```

### B. Declarative Rollback (Post-Incident GitOps Reconciliation)
Imperative rollback restores service immediately, but subsequent CI/CD runs would re-deploy the faulty commit unless Git is updated:

```bash
# 1. Revert the problematic commit in Git
git checkout dev
git revert <bad-commit-sha> -m 1

# 2. Or update the Kustomize overlay to the previous immutable SHA tag
# In infra/k8s/overlays/prod/kustomization.yaml:
#   newTag: <previous-working-commit-sha>

# 3. Push to dev / trigger CI/CD pipeline
git commit -m "fix(rollback): revert deployment to stable commit <previous-sha>"
git push origin dev
```

### C. Docker Compose Rollback
```bash
# 1. Pull prior known-good immutable image tag
docker pull ghcr.io/i243137-oss/civicpulse-backend:<previous-sha>

# 2. Update IMAGE_TAG in .env
sed -i 's/IMAGE_TAG=.*/IMAGE_TAG=<previous-sha>/' .env

# 3. Re-deploy containers with zero build
docker compose -f docker-compose.prod.yml up -d
```

---

## 6. Emergency Runbook Checklist

- [ ] Check `/health` endpoint: `curl -f http://localhost:80/health` (Liveness)
- [ ] Check `/ready` endpoint: `curl -f http://localhost:80/ready` (DB + Redis connectivity)
- [ ] Inspect container health: `docker compose ps` or `kubectl get pods -n civicpulse`
- [ ] Check error logs: `kubectl logs -l app=backend -n civicpulse | jq 'select(.level=="ERROR")'`
- [ ] Inspect AI provider status: `curl -s http://localhost:80/api/meta/providers | jq .`
- [ ] Check HPA replica count: `kubectl get hpa -n civicpulse`
- [ ] If triage fails, set `TRIAGE_PROVIDER=rules` for instant zero-latency heuristic recovery.
- [ ] If rollout fails, run `kubectl rollout undo deployment/backend -n civicpulse`.
