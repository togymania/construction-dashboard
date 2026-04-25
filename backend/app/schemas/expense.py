"""Pydantic schemas for Expense domain."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.budget import CategorySummary


# ---------- Single expense CRUD ----------


class ExpenseBase(BaseModel):
    """Shared fields for create / update."""

    category_id: int
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., gt=0)
    expense_date: date
    vendor: str | None = Field(None, max_length=255)
    invoice_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    budget_item_id: int | None = None


class ExpenseCreate(ExpenseBase):
    """Payload for creating a single expense (POST)."""

    pass


class ExpenseUpdate(BaseModel):
    """Payload for updating an expense. All fields optional."""

    category_id: int | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    amount: Decimal | None = Field(None, gt=0)
    expense_date: date | None = None
    vendor: str | None = Field(None, max_length=255)
    invoice_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    budget_item_id: int | None = None


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
