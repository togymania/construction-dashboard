"""Pydantic schemas for Project domain."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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
    """Shared fields between create and update."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.PLANNING
    health: ProjectHealth = ProjectHealth.ON_TRACK
    budget_rub: Decimal = Field(default=Decimal("0"), ge=0)
    start_date: date
    end_date: date
    progress_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    location: str = Field(..., min_length=1, max_length=255)


class ProjectCreate(ProjectBase):
    """Payload for creating a project."""

    pass


class ProjectUpdate(BaseModel):
    """Payload for updating a project. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None
    health: ProjectHealth | None = None
    budget_rub: Decimal | None = Field(None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    progress_pct: Decimal | None = Field(None, ge=0, le=100)
    location: str | None = Field(None, min_length=1, max_length=255)


class OwnerSummary(BaseModel):
    """Minimal user info embedded in project responses."""

    id: int
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class ProjectResponse(ProjectBase):
    """Project data returned from the API."""

    id: int
    owner_id: int
    owner: OwnerSummary
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Project Executive Report (Faz 5)
# =============================================================================


class ExecutiveReportSections(BaseModel):
    """Six narrative sections that make up the executive report body."""

    executive_summary: str
    financial_status: str
    critical_risks: str
    subcontractor_performance: str
    workforce_health: str
    next_30_days: str


class ProjectExecutiveReport(BaseModel):
    """One-to-two page AI-narrated digest of a project's current state."""

    project_id: int
    project_name: str
    generated_at: datetime
    headline: str
    sections: ExecutiveReportSections
    recommended_actions: list[str] = Field(default_factory=list)
    facts: dict = Field(default_factory=dict)
    source: str = "rule"  # "rule" | "llm"
