"""
CivicPulse backend — application entry point.

Follows the four-layer architecture:
- routes/ -> services/ -> repositories/ / providers/
No SQL outside repositories, no business rules in routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes.complaints import router as complaints_router
from app.routes.health import router as health_router
from app.routes.meta import router as meta_router
from app.routes.ready import router as ready_router
from app.routes.stats import router as stats_router

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

# Mount API routers
app.include_router(health_router)
app.include_router(ready_router)
app.include_router(complaints_router)
app.include_router(stats_router)
app.include_router(meta_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Minimal root route so a bare GET / doesn't 404 during manual checks."""
    return {"service": settings.APP_NAME, "environment": settings.ENVIRONMENT}
