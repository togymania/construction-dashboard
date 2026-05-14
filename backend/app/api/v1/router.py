"""API v1 router - aggregates all v1 endpoints."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    budget_categories,
    budget_items,
    dashboard,
    expenses,
    financial_summary,
    ledger,
    projects,
    subcontractors,
    tenders,
    workforce,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(budget_categories.router)
api_v1_router.include_router(budget_items.router)
api_v1_router.include_router(expenses.router)
api_v1_router.include_router(financial_summary.router)
api_v1_router.include_router(ledger.router)
api_v1_router.include_router(subcontractors.router)
api_v1_router.include_router(tenders.router)
api_v1_router.include_router(workforce.router)
