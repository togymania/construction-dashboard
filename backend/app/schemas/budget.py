"""Pydantic schemas for BudgetItem domain.

This module declares the request/response shapes used by the budget items
API. Variance schemas (planned vs actual) live in
``app.schemas.budget_variance`` so this file stays compact -- the dev
sandbox occasionally truncates larger files mid-write, so we keep the
hot-path schema module short and pad the tail with comments to ensure
we always overwrite any stale content from a previous version.

Naming conventions
------------------
* ``*Base``      -- shared fields between create + update
* ``*Create``    -- create payload (POST body)
* ``*Update``    -- partial update payload (PATCH/PUT body)
* ``*Response``  -- enriched read model (includes db-side fields)

Backwards-compat policy
-----------------------
New optional fields land here first. Existing endpoints continue to
return ``None`` until the migration that introduces the column has been
applied. See ``alembic/versions/c2d4e6f8a1b3_add_cost_code...`` for the
columns introduced by Faz 2.
"""
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
    """Shared fields between create and update payloads."""

    category_id: int | None = None
    category_name_new: str | None = Field(None, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    cost_code: str | None = Field(None, max_length=50)
    planned_amount: Decimal = Field(default=Decimal("0"), ge=0)
    committed_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_exactly_one_category(self):
        if (self.category_id is None) == (self.category_name_new is None):
            raise ValueError(
                "Provide exactly one of category_id or category_name_new"
            )
        return self


class BudgetItemCreate(BudgetItemBase):
    """Create payload for ``POST /projects/{id}/budget-items``."""

    pass


class BudgetItemUpdate(BaseModel):
    """Partial update payload. All fields optional."""

    category_id: int | None = None
    category_name_new: str | None = Field(None, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=500)
    cost_code: str | None = Field(None, max_length=50)
    planned_amount: Decimal | None = Field(None, ge=0)
    committed_amount: Decimal | None = Field(None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_at_most_one_category(self):
        if self.category_id is not None and self.category_name_new is not None:
            raise ValueError(
                "Cannot provide both category_id and category_name_new"
            )
        return self


class BudgetItemResponse(BudgetItemBase):
    """Read model: budget item + computed/db-side fields."""

    id: int
    project_id: int
    category: CategorySummary
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BudgetCategoryBreakdown(BaseModel):
    """Aggregation per category for one project (used by BudgetSummary)."""

    category_id: int
    category_name: str
    category_slug: str
    planned_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    utilization_pct: float


class BudgetSummary(BaseModel):
    """Full budget summary returned by the per-project summary endpoint."""

    project_id: int
    project_budget_rub: Decimal
    total_planned: Decimal
    total_spent: Decimal
    total_pending: Decimal
    remaining: Decimal
    utilization_pct: float
    by_category: list[BudgetCategoryBreakdown]
    # Number of underlying ledger expense entries that contributed to
    # total_spent. Lets the UI render "N expense records" without
    # re-fetching the ledger list. Defaults to 0 for backwards-compat.
    expense_records_count: int = 0


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
    deleted_count: int = 0
    errors: list[BudgetImportRowError]
    warnings: list[BudgetImportRowWarning] = []


# -------------------------------------------------------------------------
# Padding to keep the file longer than any previously-truncated stale copy
# on disk. The sandbox we develop in occasionally fails to truncate the
# old content when a smaller new payload is written, leaving null-byte
# padding that breaks the Python parser. By keeping the file comfortably
# larger than its prior versions we avoid that failure mode.
# -------------------------------------------------------------------------
