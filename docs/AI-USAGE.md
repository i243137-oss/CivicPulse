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

### 2026-09-27 — Phase 5: Frontend Implementation, Typed Client, and Component Tests

- **Tool:** Claude (Anthropic) via Cline VS Code extension
- **Prompt summary:** Implement Phase 5 React TypeScript frontend according to the assignment rubric and master AI specification. Create typed API models matching backend schemas, implement central API client with relative `/api` paths, develop views (SubmitPage with honest loading state, DashboardPage with X-Cache badge and provider observability, ComplaintsPage with filters and pagination, ComplaintDetailPage with status transitions), implement ErrorBoundary, configure Vitest suite with >= 5 meaningful component tests, and document ADR-0003 for frontend runtime configuration.
- **Output used:** React views, components, CSS styles, Vitest component test suites (14 tests across 5 test suites), ADR-0003, and engineering notes.
- **Human review:** Verified TypeScript compilation (`npx tsc --noEmit`), linting (`npm run lint`), production build (`npm run build`), all 14 Vitest component tests (`npm test`), and documented findings.


- **Tool:** Claude (Anthropic) via Cline VS Code extension
- **Prompt summary:** Create a production-oriented folder structure for a full-stack civic issue reporting platform using React TypeScript frontend, FastAPI backend, PostgreSQL, Redis, Docker Compose, Kubernetes, and GitHub Actions.
- **Output used:** Complete repository scaffold — directories, Dockerfiles, docker-compose configs, README, .gitignore, .env.example, documentation templates.
- **Human review:** Developer reviewed all generated files, verified alignment with project requirements, and committed to `dev` branch.
