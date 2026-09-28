from app.routes.complaints import router as complaints_router
from app.routes.health import router as health_router
from app.routes.meta import router as meta_router
from app.routes.ready import router as ready_router
from app.routes.stats import router as stats_router

__all__ = [
    "complaints_router",
    "health_router",
    "meta_router",
    "ready_router",
    "stats_router",
]
