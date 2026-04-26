"""Pydantic schemas for Expense domain."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.budget import CategorySummary


# ---------- Single expense CRUD ----------


class ExpenseBase(BaseModel):
    """Shared fields for create / update.

    Category resolution: callers must provide EXACTLY ONE of:
      * category_id        — reference to an existing budget_categories row
      * category_name_new  — free-text name; auto-created if not found
                             (case-insensitive lookup, normalised whitespace)
    """

    category_id: int | None = None
    category_name_new: str | None = Field(None, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., gt=0)
    expense_date: date
    vendor: str | None = Field(None, max_length=255)
    invoice_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    budget_item_id: int | None = None

    @model_validator(mode="after")
    def _check_exactly_one_category(self):
        if (self.category_id is None) == (self.category_name_new is None):
            raise ValueError(
                "Provide exactly one of category_id or category_name_new"
            )
        return self


class ExpenseCreate(ExpenseBase):
    """Payload for creating a single expense (POST)."""

    pass


class ExpenseUpdate(BaseModel):
    """Payload for updating an expense. All fields optional.

    Category change: provide category_id (existing) OR category_name_new
    (auto-create). Providing both is rejected.
    """

    category_id: int | None = None
    category_name_new: str | None = Field(None, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=500)
    amount: Decimal | None = Field(None, gt=0)
    expense_date: date | None = None
    vendor: str | None = Field(None, max_length=255)
    invoice_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    budget_item_id: int | None = None

    @model_validator(mode="after")
    def _check_at_most_one_category(self):
        if self.category_id is not None and self.category_name_new is not None:
            raise ValueError(
                "Cannot provide both category_id and category_name_new"
            )
        return self


class ExpenseResponse(BaseModel):
    """Expense data returned from the API."""

    id: int
    project_id: int
    budget_item_id: int | None
    category_id: int
    category: CategorySummary
    description: str
    amount: Decimal
    expense_date: date
    vendor: str | None
    invoice_number: str | None
    notes: str | None
    status: str
    creator_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Excel import ----------


class ImportRowError(BaseModel):
    """A single row that failed validation during import."""

    row: int
    reason: str


class ImportRowWarning(BaseModel):
    """A row that was skipped or modified with a warning during import."""

    row: int
    reason: str


class ExpenseImportResult(BaseModel):
    """Summary returned after an Excel import."""

    imported_count: int
    skipped_count: int
    errors: list[ImportRowError]
    warnings: list[ImportRowWarning] = []
