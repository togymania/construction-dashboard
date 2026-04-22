"""Pydantic schemas for Project domain."""
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectHealth(str, Enum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    DELAYED = "delayed"


class ProjectBase(BaseModel):
    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Short description")
    status: ProjectStatus
    health: ProjectHealth
    budget_usd: float = Field(..., description="Total budget in USD")
    budget_spent_usd: float = Field(..., description="Amount spent to date")
    start_date: date
    end_date: date
    progress_pct: float = Field(..., ge=0, le=100)
    location: str


class ProjectResponse(ProjectBase):
    id: int

    model_config = {"from_attributes": True}
