"""Pydantic schemas for BudgetCategory domain."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BudgetCategoryBase(BaseModel):
    """Shared fields between create and update."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


class BudgetCategoryCreate(BudgetCategoryBase):
    """Payload for creating a new category. Always non-system."""

    pass


class BudgetCategoryUpdate(BaseModel):
    """Payload for updating a category. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=100)
    slug: str | None = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class BudgetCategoryReorder(BaseModel):
    """Payload for bulk reordering categories."""

    order: list[int] = Field(..., description="List of category IDs in desired display order")


class BudgetCategoryResponse(BudgetCategoryBase):
    """Category data returned from the API."""

    id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
