# ADR 0001: AI Provider Abstraction and Triage Architecture

## Status
Accepted

## Date
2026-09-27

## Context
CivicPulse requires automated intake and triage of citizen municipal complaints. When citizens report urgent issues (e.g. burst water mains, sparking transformers, severe road hazards), free-text descriptions must be rapidly categorized into municipal domains (`water`, `electricity`, `sanitation`, `roads`, `streetlights`, `other`) and assigned an appropriate operational priority (`low`, `normal`, `high`, `critical`).

However, real-world municipal environments face divergent constraints:
1. **Production Hosting**: Access to fast, high-accuracy hosted models (e.g., Groq, Gemini).
2. **Local/Air-Gapped Operation**: Municipal networks with strict data residency requiring local containerized execution (Ollama) with zero external network connectivity.
3. **High Availability & Fault Tolerance**: Hosted APIs experience network timeouts, transient HTTP 5xx errors, and HTTP 429 rate limit throttles. A citizen complaint submission must **never** fail with HTTP 500 because an external AI provider is unavailable.
4. **Deterministic Testing**: Automated CI/CD pipelines require 100% deterministic, green test runs without consuming external API credits or requiring secret API keys.

## Decision
We implement a four-tier pluggable provider strategy behind a formal Python `TriageProvider` protocol with a unified structured output schema (`TriageResult`):

```python
class TriageResult(BaseModel):
    category: CategoryEnum
    priority: PriorityEnum
    summary: str = Field(max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)

class TriageProvider(Protocol):
    name: str
    async def triage(self, text: str, location: str) -> TriageResult: ...
```

Four distinct providers are implemented:
1. **`LLMTriage` (Hosted Production Path)**:
   - Connects to OpenAI-compatible endpoints (Groq, Google AI Studio Gemini).
   - Enforces a strict 10.0-second request timeout (`httpx.Timeout(10.0)`).
   - Implements a single jittered retry for timeout, HTTP 429, and HTTP 5xx. Never retries client error HTTP 400.
   - Enforces structured JSON mode and schema validation.
2. **`OllamaTriage` (Offline Zero-Dependency Container Path)**:
   - Connects to local Ollama instance (`http://ollama:11434/api/chat`).
   - Runs lightweight 1B models with zero external network dependency.
3. **`RuleBasedTriage` (Deterministic Heuristic Baseline & Fallback)**:
   - Deterministic keyword and urgency classification.
   - Zero network calls, zero failure modes, execution time < 1ms.
4. **`SimulatedTriage` (Deterministic Test Fake for CI)**:
   - Seeded, non-network test fake supporting failure injection (`timeout`, `rate_limit`, `server_error`, `malformed_json`).

### Fallback Chain
All provider calls are orchestrated by `TriageService`. If the primary provider (`LLMTriage` or `OllamaTriage`) fails for any reason after its single retry, the system immediately falls back to `RuleBasedTriage`, logs a warning with provider details and latency, and records `triaged_by = "rules fallback"` on the persisted complaint. The citizen submission always returns HTTP 201 Created.

### Content-Hash Caching
To prevent redundant inference on duplicate complaints (e.g. multiple neighbors reporting the same burst water pipe), `TriageService` hashes normalized complaint text and location (`SHA-256`) and caches results in Redis with a 24-hour TTL.

## Consequences
- **Positive**:
  - Zero vendor lock-in; swapping between Groq, Gemini, Ollama, and local rules requires only altering the `TRIAGE_PROVIDER` environment variable.
  - CI test suites run deterministically in seconds without network access or API keys.
  - Resilient: External AI provider outages never impede municipal complaint intake.
  - Duplicate complaints are served instantly from cache, conserving inference quota.
- **Negative**:
  - Heuristic fallback (`RuleBasedTriage`) lacks nuanced contextual understanding compared to full LLM inference, but ensures guaranteed business continuity.
