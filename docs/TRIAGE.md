# CivicPulse AI Triage Architecture & Operations

## Overview
CivicPulse implements an automated, fault-tolerant AI triage engine that categorizes citizen complaints into standardized municipal domains and assigns operational urgency without blocking intake workflows.

## Providers
The system supports four distinct implementations under `backend/app/providers/triage/`:

| Provider | Implementation Class | Description | Network Dependency | Default Environment |
| :--- | :--- | :--- | :--- | :--- |
| **`llm`** | `LLMTriage` | Hosted OpenAI-compatible model (Groq, Google Gemini) | External HTTPS | Production |
| **`ollama`** | `OllamaTriage` | Local containerized model (`llama3.2:1b`) | Internal Compose | Air-gapped / Local |
| **`rules`** | `RuleBasedTriage` | Deterministic keyword heuristic | None | Universal Fallback |
| **`simulated`** | `SimulatedTriage` | Deterministic test fake with failure injection | None | CI / Automated Tests |

Selected at runtime via the environment variable `TRIAGE_PROVIDER`.

## Resilience Patterns
1. **Hard-Cap Timeout**: 10.0-second timeout on all network inference calls (`httpx.Timeout(10.0)`).
2. **Jittered Retry**: At most one retry with exponential backoff and randomized jitter (`0.5s + uniform(0.1, 0.4)`), triggered exclusively on timeouts, HTTP 429 (rate limits), and HTTP 5xx (server errors). Never retries HTTP 400 or connection errors.
3. **Deterministic Fallback Chain**: If the primary provider raises or returns malformed output, the system seamlessly invokes `RuleBasedTriage`, logs provider diagnostics, and persists `triaged_by = "rules:fallback"`. Citizen intake never returns HTTP 500 due to AI failure.
4. **Content-Hash Caching (24h TTL & Hit Rate Reporting)**: Duplicate complaints with identical normalized text and location are cached in Redis (`civicpulse:triage:cache:<sha256>`), eliminating redundant inference cost. Real-time hits, misses, total requests, and calculated hit rate are reported via `GET /api/meta/providers`.
5. **Prompt-Injection Guardrails**: Citizen text is encapsulated in `<complaint_untrusted_input>` delimiters, with explicit instructions forbidding prompt override, role changes, or instructions execution.
6. **PII Governance**: Citizen contact details (`reporter_contact`) are completely excluded from AI payloads (see `docs/adr/0004-pii-and-data-governance.md`).
