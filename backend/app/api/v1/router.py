"""API v1 router - aggregates all v1 endpoints."""
from fastapi import APIRouter

from app.api.v1.endpoints import dashboard, projects

api_v1_router = APIRouter()
api_v1_router.include_router(projects.router)
api_v1_router.include_router(dashboard.router)
