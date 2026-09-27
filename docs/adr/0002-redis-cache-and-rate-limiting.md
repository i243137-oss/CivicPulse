# ADR-0002: Redis Statistics Caching and Distributed Rate Limiting

## Status
**Accepted** (Phase 3)

## Context
CivicPulse operates in a containerized, horizontally scaled architecture where multiple backend instances handle incoming citizen complaints and administrative analytics concurrently.

Two critical operational requirements emerge:
1. **Administrative Analytics Performance**: The `/api/stats` endpoint performs aggregation queries (counting records grouped by status, category, and priority) across the entire complaints dataset. Repeated un-cached calls under high dashboard refresh traffic would place unnecessary load on PostgreSQL.
2. **Abuse and Overload Protection**: Citizen-facing intake and inspection APIs must be protected from high-frequency automated scraping or denial-of-service attempts. Because the backend runs across multiple container replicas, per-process in-memory rate limiting would fail: a client distributing requests across $N$ instances could consume $N \times$ the intended quota.

## Considered Options

### 1. In-Memory Process Caching & Rate Limiting (e.g., Python `cachetools` / `slowapi` with in-memory storage)
- **Pros**: Zero external dependencies; low latency.
- **Cons**: Severe state drift across replicas. Cache invalidation on one instance does not clear the cache on other instances, returning stale statistics to dashboard users. Rate limits are multiplied by replica count.

### 2. Distributed Redis 7 Architecture (Selected)
- **Pros**: Single shared source of truth for cache and rate-limiting counters. Immediate cross-instance cache invalidation. Atomic atomic operations guarantee exact sliding window enforcement across any number of backend replicas.
- **Cons**: Introduces Redis 7 service dependency. Requires AOF persistence and connection resilience.

## Decision

We adopt **Redis 7** with the following technical design:

### 1. Persistence & Infrastructure
- Redis is configured with **Append-Only File (AOF)** persistence (`--appendonly yes --appendfsync everysec`) mounted to a named persistent volume (`redis_data:/data`).
- Service-to-service communication uses the internal DNS name `redis` (or `REDIS_HOST`), never exposing Redis ports to the public edge network.

### 2. Read-Through Statistics Cache
- **Cache Key**: `civicpulse:stats:summary`
- **TTL**: 30 seconds (`REDIS_STATS_CACHE_TTL = 30`).
- **Telemetry**: The `/api/stats` endpoint inspects Redis on incoming requests:
  - On Cache HIT: returns cached JSON immediately with HTTP header `X-Cache: HIT`.
  - On Cache MISS: queries PostgreSQL via `ComplaintRepository`, writes serialized JSON to Redis with 30s TTL, and returns HTTP header `X-Cache: MISS`.
- **Write-Time Invalidation**: Any state-changing write (`POST /api/complaints` and `PATCH /api/complaints/{id}/status`) immediately executes an atomic delete on the statistics cache key, guaranteeing freshness on the subsequent read.

### 3. Distributed Sliding-Window Rate Limiter
- **Atomic Lua Script**: Rate limiting is evaluated entirely inside Redis using an atomic Lua script executing `ZREMRANGEBYSCORE`, `ZCARD`, `ZADD`, and `PEXPIRE`.
- **Sliding Window Log**: Eliminates boundary burst vulnerabilities present in fixed-window counters.
- **Standard HTTP Headers**:
  - `X-RateLimit-Limit`: Maximum requests per window (default 60/min).
  - `X-RateLimit-Remaining`: Remaining request quota for the current window.
  - `Retry-After`: Returned on HTTP 429 Too Many Requests, indicating seconds until the earliest slot frees up.
- **Exempt Endpoints**: Health and readiness endpoints (`/health`, `/ready`, `/docs`, `/openapi.json`) bypass rate limiting to ensure Kubernetes liveness probes are never throttled.

### 4. Readiness Dependency
- The `/ready` probe verifies both PostgreSQL database connectivity (`SELECT 1`) and Redis reachability (`PING`), returning HTTP 503 if either dependency is offline.

## Consequences

- **Positive**: 
  - Cross-instance consistency: Instance A's writes immediately invalidate Instance B's cache reads.
  - Multi-replica rate enforcement: Quotas are strictly respected regardless of request routing across pods.
  - Fail-open resilience: If Redis is temporarily unreachable, rate limiting fails open with logged warnings rather than blocking legitimate citizens.
- **Negative / Trade-offs**:
  - Additional container dependency in development and production compose stacks.
  - Small network hop (~0.5ms) for Redis lookups on rate-limited endpoints.
