from fastapi import APIRouter

from app.api.v1.routes import auth, datasets, gpu, health, training

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(gpu.router, prefix="/gpu", tags=["gpu"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
