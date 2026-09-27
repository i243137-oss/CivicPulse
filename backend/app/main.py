"""
CivicPulse backend — application entry point.

Phase 1 scope only:
  - construct the FastAPI app
  - wire up CORS from settings
  - mount the initial liveness health endpoint

Persistence, caching, AI triage, structured logging, request-id propagation
and graceful shutdown are introduced in later phases and are intentionally
absent here.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes.health import router as health_router

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Municipal complaint intake, triage and operations platform.",
)

# CORS: explicit origin allow-list only, never "*" together with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Minimal root route so a bare GET / doesn't 404 during manual checks."""
    return {"service": settings.APP_NAME, "environment": settings.ENVIRONMENT}
