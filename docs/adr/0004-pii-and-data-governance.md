# ADR 0004: PII Protection and Data Governance in AI Triage

## Status
Accepted

## Date
2026-09-27

## Context
When citizens submit complaints to CivicPulse, reports often contain Personally Identifiable Information (PII), including:
- Citizen contact details (`reporter_contact`: phone numbers, email addresses, WhatsApp identifiers)
- Personal identity data (names, CNIC numbers, household identifiers)
- Exact residential addresses

Municipal data protection guidelines and privacy regulations mandate that citizen PII must not be transferred to third-party commercial organizations without explicit consent and data processing agreements. Furthermore, free-tier cloud AI providers (such as Google AI Studio or public inference tiers) reserve the right under standard developer terms to log prompt payloads and retain data for model quality improvements.

If unredacted citizen complaints are transmitted to hosted LLM endpoints, citizen phone numbers, emails, and identity markers could enter third-party logging pipelines and model training corpora.

## Decision
We enforce strict data minimization, architectural field isolation, and local inference guarantees:

1. **Architectural PII Stripping at Service Boundary**:
   The `ComplaintService` accepts `reporter_contact` for municipal record-keeping and updates the local PostgreSQL database. However, the triage interface:
   ```python
   async def triage(self, text: str, location: str) -> TriageResult:
   ```
   deliberately excludes `reporter_contact`. Under no circumstances is `reporter_contact` passed to `TriageService`, `LLMTriage`, `OllamaTriage`, or any external API.

2. **Data Minimization Payload**:
   The external AI payload consists exclusively of:
   - Public municipal location descriptor (e.g. `Sector G-11/3, Street 7`)
   - Untrusted issue text describing the infrastructure malfunction (e.g. `Transformer sparking near pole 4`)
   No session cookies, user IDs, IP addresses, or contact information are attached to AI requests.

3. **Untrusted Data Isolation & Prompt Guardrails**:
   All user text is isolated inside `<complaint_untrusted_input>` XML tags in the system prompt. This enforces clear demarcation between system instructions and citizen text, neutralizing prompt-injection attempts where malicious text instructs the model to exfiltrate system data.

4. **Zero-Transmission Local Path (Ollama & Rules)**:
   For municipal deployments with complete data-residency mandates, CivicPulse provides `OllamaTriage` (in-cluster containerized execution) and `RuleBasedTriage` (in-process heuristics). When `TRIAGE_PROVIDER=ollama` or `TRIAGE_PROVIDER=rules`, 0 bytes of data ever leave the municipal deployment perimeter.

5. **Secrets Governance**:
   API keys (`LLM_API_KEY`) are injected strictly via Kubernetes Secrets and environment variables. Keys are never logged in application traces, never written to disk, and never surfaced through telemetry or API responses.

## Consequences
- **Positive**:
  - Full compliance with municipal data protection mandates and privacy standards.
  - Zero citizen phone numbers, emails, or identity markers are ever leaked to third-party model providers.
  - Transparent audit trail: the exact data sent to external endpoints is limited strictly to public infrastructure problem descriptions.
  - Clear compliance documentation for municipal data protection officers (DPO).
- **Negative & Trade-off Analysis**:
  - **Citizen Free-Text Inline Contact Exposure**: If a citizen voluntarily types their name or phone number directly inside the free-text description body (e.g., *"Call me, Ali, at 0300-1234567 regarding the leak"*), that string reaches the selected inference provider.
  - **Rationale for Deferring Inline Regex Masking**:
    1. *Context Preservation for Physical Infrastructure*: Automated aggressive regex redaction frequently corrupts vital municipal location cues (e.g., redacting "House 14, Street 9, Pole #302" into "House [REDACTED], Street [REDACTED]"). Municipal field crews require uncorrupted text to locate and repair hazards.
    2. *Performance and Latency*: Applying multi-pattern regex scrubbing or NER tokenizers on the critical submission path introduces latency overhead and risks catastrophic backtracking on untrusted user strings.
    3. *Data Minimization by Architectural Boundary*: The high-risk structured identifier (`reporter_contact`) is 100% stripped at the interface layer before provider execution.
    4. *Offline Alternative for Strict Privacy Mandates*: For municipal jurisdictions with strict zero-third-party leakage requirements, `TRIAGE_PROVIDER=ollama` or `TRIAGE_PROVIDER=rules` is deployed, providing complete data residency where zero bytes leave municipal hardware.
    5. Masking in free-text is therefore intentionally deferred to future pipeline enhancements, backed by existing local-inference options for privacy-critical deployments.

