"""Pydantic schemas for BudgetItem domain."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CategorySummary(BaseModel):
    """Minimal category info embedded in budget item responses."""

    id: int
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class BudgetItemBase(BaseModel):
    """Shared fields between create and update."""

    category_id: int
    description: str = Field(..., min_length=1, max_length=500)
    planned_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None


class BudgetItemCreate(BudgetItemBase):
    """Payload for creating a budget item under a specific project."""

    pass


class BudgetItemUpdate(BaseModel):
    """Payload for updating a budget item. All fields optional."""

    category_id: int | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    planned_amount: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class BudgetItemResponse(BudgetItemBase):
    """Budget item data returned from the API."""

    id: int
    project_id: int
    category: CategorySummary
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetCategoryBreakdown(BaseModel):
    """Aggregation per category for one project."""

    category_id: int
    category_name: str
    category_slug: str
    planned_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    utilization_pct: float


class BudgetSummary(BaseModel):
    """Full budget summary for one project."""

    project_id: int
    project_budget_rub: Decimal
    total_planned: Decimal
    total_spent: Decimal
    total_pending: Decimal
    remaining: Decimal
    utilization_pct: float
    by_category: list[BudgetCategoryBreakdown]
