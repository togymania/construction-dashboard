"""Dashboard aggregate endpoints."""
from fastapi import APIRouter

from app.db.seed import get_mock_dashboard_stats
from app.schemas.dashboard import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats, summary="Get dashboard KPIs")
async def get_dashboard_stats() -> DashboardStats:
    return DashboardStats(**get_mock_dashboard_stats())
