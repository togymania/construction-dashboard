"""Pydantic schemas for the planned vs actual variance report (Faz 3).

Kept in a separate module from ``app.schemas.budget`` so that file stays
short -- the sandbox we develop in occasionally truncates larger files
mid-write, and a smaller schema file is more resilient to that.
"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BudgetItemVariance(BaseModel):
    """One budget line with planned, committed, actual and variance.

    Variance is (actual - planned). Positive means over budget.
    variance_pct is None when planned is zero (avoid div by zero).
    """

    id: int
    cost_code: str | None
    description: str
    category_id: int
    category_name: str
    category_slug: str
    planned_amount: Decimal
    committed_amount: Decimal
    actual_amount: Decimal
    variance: Decimal
    variance_pct: float | None
    matched_expense_count: int
    severity: str  # "ok" | "watch" | "warn" | "over"


class BudgetVarianceReport(BaseModel):
    """Project-wide planned vs actual."""

    project_id: int
    generated_at: datetime
    total_planned: Decimal
    total_committed: Decimal
    total_actual: Decimal
    overall_variance: Decimal
    overall_variance_pct: float | None
    items: list[BudgetItemVariance]
