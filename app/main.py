"""Main entry point for the ResolveAI backend."""

from fastapi import FastAPI

from app.api.routers.policies import router as policies_router
from app.api.routers.support import router as support_router
from app.api.routers.workflow import router as workflow_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for the ResolveAI customer-support copilot.",
    debug=settings.debug,
)

app.include_router(support_router)
app.include_router(policies_router)
app.include_router(workflow_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Check whether the API is running."""

    return {
        "status": "ok",
        "environment": settings.app_env,
    }


@app.get(f"{settings.api_v1_prefix}/about", tags=["system"])
def about() -> dict[str, str]:
    """Return basic information about the API."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "stage": "support-api",
    }
