# 🏛️ CivicPulse

> **AI-powered civic issue reporting platform** — empowering citizens to report, track, and resolve community issues in real time.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Overview

CivicPulse is a full-stack civic issue reporting platform that allows residents to:

- 📝 Submit civic issues (potholes, broken streetlights, graffiti, etc.)
- 📍 Geolocate issues on an interactive map
- 🤖 Leverage AI to auto-categorize, prioritize, and summarize reports
- 📊 Track issue status from submission through resolution
- 🔔 Receive real-time updates on reported issues

---

## Tech Stack

| Layer          | Technology                          |
| -------------- | ----------------------------------- |
| **Frontend**   | React 18, TypeScript, Vite          |
| **Backend**    | Python 3.12, FastAPI, SQLAlchemy    |
| **Database**   | PostgreSQL 16                       |
| **Cache**      | Redis 7                             |
| **AI**         | OpenAI API (GPT-4)                  |
| **Containers** | Docker, Docker Compose              |
| **Orchestration** | Kubernetes (K8s)                 |
| **CI/CD**      | GitHub Actions                      |

---

## Repository Structure

```
CivicPulse/
│
├── backend/                    # FastAPI backend application
│   ├── app/                    #   Application package (routes, models, services)
│   ├── tests/                  #   Backend unit & integration tests
│   ├── requirements.txt        #   Pinned Python dependencies
│   ├── Dockerfile              #   Backend container image definition
│   └── pyproject.toml          #   Python project metadata & tool config
│
├── frontend/                   # React TypeScript frontend application
│   ├── src/                    #   Source code (components, pages, hooks)
│   ├── public/                 #   Static assets served as-is
│   ├── package.json            #   Node.js dependencies & scripts
│   ├── vite.config.ts          #   Vite bundler configuration
│   └── Dockerfile              #   Frontend container image definition
│
├── infra/                      # Infrastructure-as-Code
│   ├── docker/                 #   Extra Docker configs (nginx, etc.)
│   └── k8s/                    #   Kubernetes manifests
│
├── tests/                      # Cross-cutting tests
│   └── integration/            #   End-to-end / integration test suites
│
├── docs/                       # Project documentation
│   ├── adr/                    #   Architecture Decision Records
│   ├── RUNBOOK.md              #   Operational runbook
│   ├── AI-USAGE.md             #   AI usage log
│   └── ENGINEERING-NOTES.md    #   Engineering notes & design rationale
│
├── .github/                    # GitHub-specific configuration
│   └── workflows/              #   CI/CD pipeline definitions
│
├── docker-compose.yml          # Development orchestration
├── docker-compose.prod.yml     # Production orchestration
├── .env.example                # Example environment variables
├── .gitignore                  # Git ignore rules
└── README.md                   # ← You are here
```

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.x
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.x
- [Node.js](https://nodejs.org/) ≥ 20.x (for local frontend development)
- [Python](https://python.org/) ≥ 3.12 (for local backend development)
- [Git](https://git-scm.com/) ≥ 2.x

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/i243137-oss/CivicPulse.git
cd CivicPulse

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your actual values

# 3. Start all services
docker compose up --build

# 4. Open in browser
#    Frontend  → http://localhost:5173
#    Backend   → http://localhost:8000
#    API Docs  → http://localhost:8000/docs
```

---

## Environment Variables

See [`.env.example`](.env.example) for all available configuration options.

| Variable             | Description                        | Default       |
| -------------------- | ---------------------------------- | ------------- |
| `APP_ENV`            | Runtime environment                | `development` |
| `BACKEND_PORT`       | Port the FastAPI server listens on | `8000`        |
| `POSTGRES_PASSWORD`  | PostgreSQL password                | *(required)*  |
| `REDIS_HOST`         | Redis hostname                     | `redis`       |
| `OPENAI_API_KEY`     | OpenAI API key for AI features     | *(optional)*  |

---

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Testing

```bash
# Backend unit tests
cd backend && pytest

# Frontend tests
cd frontend && npm test

# Integration tests (requires running services)
cd tests/integration && pytest
```

---

## Deployment

### Docker Compose (Production)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Kubernetes

```bash
kubectl apply -f infra/k8s/
```

---

## Contributing

1. Create a feature branch from `dev` (e.g., `feature/backend`)
2. Make your changes
3. Submit a Pull Request targeting `dev`
4. After review, `dev` merges into `master` for releases

### Branch Strategy

```
master          ← production-ready releases
  └── dev       ← integration branch
       ├── feature/backend
       ├── feature/frontend
       ├── feature/ai
       ├── feature/kubernetes
       └── feature/ci
```

---

## License

This project is part of an academic/professional portfolio. All rights reserved.


