"""Pydantic schemas for Workforce domain (positions, snapshots, counts, KPIs, import)."""
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------- Enums (mirrored from models for API contract isolation) ----------

class WorkforceCategory(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    SUBCONTRACTOR = "subcontractor"


# =============================================================================
# WorkforcePosition schemas
# =============================================================================

class WorkforcePositionBase(BaseModel):
    """Shared fields between create and update."""

    category: WorkforceCategory
    name: str = Field(..., min_length=1, max_length=150)
    display_order: int = Field(default=999, ge=0)
    is_active: bool = True


class WorkforcePositionCreate(WorkforcePositionBase):
    """Payload for creating a position."""

    pass


class WorkforcePositionUpdate(BaseModel):
    """Payload for updating a position. All fields optional."""

    category: WorkforceCategory | None = None
    name: str | None = Field(None, min_length=1, max_length=150)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class WorkforcePositionResponse(WorkforcePositionBase):
    """Position read model with computed fields."""

    id: int
    name_normalized: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Embedded summaries (mini-views inside responses)
# =============================================================================

class CreatorSummary(BaseModel):
    """Minimal user info embedded in responses."""

    id: int
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class PositionSummary(BaseModel):
    """Minimal position info embedded in count rows."""

    id: int
    category: WorkforceCategory
    name: str
    display_order: int

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# WorkforceCount schemas
# =============================================================================

class WorkforceCountInput(BaseModel):
    """A single count row in upsert payloads.

    Either provide position_id (existing position) or position_name + category
    (auto-create if missing - used by Excel import).
    """

    position_id: int | None = None
    position_name: str | None = Field(None, min_length=1, max_length=150)
    category: WorkforceCategory | None = None
    general_staff: int = Field(..., ge=0)
    absent: int = Field(default=0, ge=0)
    leave_sick: int = Field(default=0, ge=0)
    present: int | None = Field(None, ge=0)  # if omitted, computed = general - absent - leave

    @model_validator(mode="after")
    def validate_position_ref(self):
        """Either position_id, or both name + category, must be supplied."""
        if self.position_id is None:
            if not self.position_name or self.category is None:
                raise ValueError(
                    "Either position_id or (position_name + category) must be provided"
                )
        return self

    @model_validator(mode="after")
    def compute_present_if_missing(self):
        """Auto-compute present from general - absent - leave when not supplied."""
        if self.present is None:
            self.present = max(0, self.general_staff - self.absent - self.leave_sick)
        return self


class WorkforceCountResponse(BaseModel):
    """A count row in snapshot responses, with embedded position."""

    id: int
    general_staff: int
    absent: int
    leave_sick: int
    present: int
    position: PositionSummary

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# WorkforceSnapshot schemas
# =============================================================================

class WorkforceSnapshotBase(BaseModel):
    """Shared fields for snapshot upsert."""

    snapshot_date: date
    notes: str | None = None


class WorkforceSnapshotCreate(WorkforceSnapshotBase):
    """Payload for creating/upserting a snapshot.

    counts is the per-position breakdown. Aggregates (totals, per-category)
    are recomputed by the service layer from counts.
    """

    counts: list[WorkforceCountInput] = Field(default_factory=list)
    source: str = Field(default="manual", max_length=20)
    source_filename: str | None = Field(None, max_length=255)


class WorkforceSnapshotListItem(BaseModel):
    """Lightweight snapshot row for list pages (no nested counts)."""

    id: int
    project_id: int
    snapshot_date: date
    company_label: str
    source: str
    source_filename: str | None
    total_general_staff: int
    total_absent: int
    total_leave_sick: int
    total_present: int
    direct_present: int
    indirect_present: int
    subcontractor_present: int
    uploaded_by_user: CreatorSummary | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkforceSnapshotResponse(WorkforceSnapshotListItem):
    """Full snapshot detail with embedded counts."""

    notes: str | None = None
    counts: list[WorkforceCountResponse] = Field(default_factory=list)


# =============================================================================
# KPI bundle schemas (dashboard top-line numbers + charts data)
# =============================================================================

class WorkforceKPICategoryToday(BaseModel):
    """One category card on the dashboard."""

    category: WorkforceCategory
    present_today: int
    delta_vs_yesterday: int  # present_today - present_yesterday (signed)
    delta_pct: float | None = None  # null if yesterday was 0
    position_count: int  # how many distinct positions reported today




class WorkforceKPICompanyToday(BaseModel):
    """Per-company breakdown for the dashboard 'today' view.

    Shows current-day totals split by company (Monotekstroy / Monart) so each
    can be tracked independently alongside the project-wide totals.
    """

    company_label: str
    snapshot_date: date | None
    direct_present: int
    indirect_present: int
    subcontractor_present: int
    total_present: int
class WorkforceKPIDailyPoint(BaseModel):
    """A single point in the 30-day trend chart."""

    snapshot_date: date
    direct_present: int
    indirect_present: int
    subcontractor_present: int
    total_present: int


class WorkforceKPIWeeklyBucket(BaseModel):
    """One bar in the weekly comparison chart (8-week window)."""

    week_start: date
    avg_total_present: float
    avg_direct: float
    avg_indirect: float
    avg_subcontractor: float
    days_recorded: int  # 1..7


class WorkforceKPITopPosition(BaseModel):
    """Top-N positions by present count today, for the position pie chart."""

    position_id: int
    position_name: str
    category: WorkforceCategory
    present: int


class WorkforceKPIBundle(BaseModel):
    """Everything the dashboard page needs in one round-trip."""

    project_id: int
    as_of_date: date | None  # most recent snapshot date, or None if no data
    snapshot_count: int  # total snapshots for this project
    by_category_today: list[WorkforceKPICategoryToday] = Field(default_factory=list)
    by_company_today: list[WorkforceKPICompanyToday] = Field(default_factory=list)
    daily_trend: list[WorkforceKPIDailyPoint] = Field(default_factory=list)  # last 30 days
    weekly_buckets: list[WorkforceKPIWeeklyBucket] = Field(default_factory=list)  # last 8 weeks
    top_positions: list[WorkforceKPITopPosition] = Field(default_factory=list)  # top 8 today


# =============================================================================
# Excel import schemas
# =============================================================================

class WorkforceImportWarning(BaseModel):
    """Non-fatal issue surfaced to the user after parsing."""

    code: str  # e.g. "GRAND_TOTAL_MISMATCH", "UNKNOWN_POSITION_CREATED", "ROW_SKIPPED"
    message: str
    detail: dict | None = None


class WorkforceImportResponse(BaseModel):
    """Result of a single-file Excel import.

    On success, snapshot is the upserted row. Warnings carry GRAND TOTAL
    discrepancies, auto-created positions, skipped rows, etc.
    """

    project_id: int
    snapshot_date: date | None
    company_label: str | None  # detected company; None if file rejected before save
    source_filename: str | None  # original filename for UI feedback
    success: bool  # False if file was rejected (e.g. company not detected)
    error: str | None = None  # set when success=False
    rows_imported: int
    rows_skipped: int
    positions_created: int  # how many new positions auto-added during this import
    warnings: list[WorkforceImportWarning] = Field(default_factory=list)
    snapshot: WorkforceSnapshotResponse | None = None


class WorkforceMultiImportResponse(BaseModel):
    """Result of a multi-file Excel import - one entry per uploaded file."""

    project_id: int
    files_total: int
    files_succeeded: int
    files_failed: int
    results: list[WorkforceImportResponse] = Field(default_factory=list)
