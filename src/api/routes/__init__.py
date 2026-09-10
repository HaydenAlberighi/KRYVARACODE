"""
API Routes for KRYVARACODE AI System Stack
"""

from fastapi import APIRouter

from src.api.agent.router import router as agent_router

# NOTE: must be ``.router.router`` -- ``from src.api.auth import router`` binds
# the submodule, not the APIRouter instance.
from src.api.auth.router import router as auth_router
from src.api.data.router import router as data_router
from src.api.experiments.router import router as experiments_router
from src.api.items.router import router as items_router
from src.api.models.router import router as models_router
from src.api.prediction.router import router as prediction_router

# Create API router and mount sub-routers
api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(models_router, prefix="", tags=["models"])
api_router.include_router(data_router, prefix="", tags=["data"])
api_router.include_router(prediction_router, prefix="", tags=["prediction"])
api_router.include_router(experiments_router, prefix="", tags=["experiments"])
api_router.include_router(items_router, prefix="", tags=["items"])
api_router.include_router(agent_router, prefix="", tags=["agent"])


@api_router.get("/")
async def api_root():
    """Root endpoint returning API identity."""
    return {"message": "KRYVARACODE API v1"}


@api_router.get("/status")
async def api_status():
    """Health-check / status probe."""
    return {"status": "operational", "service": "KRYVARACODE API"}
