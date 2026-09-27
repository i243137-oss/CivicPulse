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

### 2026-09-26 — Project Structure Initialization

- **Tool:** Claude (Anthropic) via Cline VS Code extension
- **Prompt summary:** Create a production-oriented folder structure for a full-stack civic issue reporting platform using React TypeScript frontend, FastAPI backend, PostgreSQL, Redis, Docker Compose, Kubernetes, and GitHub Actions.
- **Output used:** Complete repository scaffold — directories, Dockerfiles, docker-compose configs, README, .gitignore, .env.example, documentation templates.
- **Human review:** Developer reviewed all generated files, verified alignment with project requirements, and committed to `dev` branch.
