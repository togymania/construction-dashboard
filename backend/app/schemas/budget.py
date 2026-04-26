"""Pydantic schemas for BudgetItem domain."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CategorySummary(BaseModel):
    """Minimal category info embedded in budget item responses."""

    id: int
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class BudgetItemBase(BaseModel):
    """Shared fields between create and update.

    Category resolution: callers must provide EXACTLY ONE of:
      * category_id        — reference to an existing budget_categories row
      * category_name_new  — free-text name; auto-created if not found
                             (case-insensitive lookup, normalised whitespace)
    """

    category_id: int | None = None
    category_name_new: str | None = Field(None, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    planned_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_exactly_one_category(self):
        if (self.category_id is None) == (self.category_name_new is None):
            raise ValueError(
                "Provide exactly one of category_id or category_name_new"
            )
        return self


class BudgetItemCreate(BudgetItemBase):
    """Payload for creating a budget item under a specific project."""

    pass


class BudgetItemUpdate(BaseModel):
    """Payload for updating a budget item. All fields optional.

    Category change: provide category_id (existing) OR category_name_new
    (auto-create). Providing both is rejected.
    """

    category_id: int | None = None
    category_name_new: str | None = Field(None, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=500)
    planned_amount: Decimal | None = Field(None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_at_most_one_category(self):
        if self.category_id is not None and self.category_name_new is not None:
            raise ValueError(
                "Cannot provide both category_id and category_name_new"
            )
        return self


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

# ---------- Excel import ----------


class BudgetImportRowError(BaseModel):
    """A single row that failed validation during budget item import."""

    row: int
    reason: str


class BudgetImportRowWarning(BaseModel):
    """A row that was skipped or modified with a warning during import."""

    row: int
    reason: str


class BudgetImportResult(BaseModel):
    """Summary returned after a budget item Excel import."""

    imported_count: int
    skipped_count: int
    deleted_count: int = 0  # only relevant for replace mode
    errors: list[BudgetImportRowError]
    warnings: list[BudgetImportRowWarning] = []