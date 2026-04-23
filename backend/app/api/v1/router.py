"""API v1 router - aggregates all v1 endpoints."""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, dashboard, projects

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(dashboard.router)
