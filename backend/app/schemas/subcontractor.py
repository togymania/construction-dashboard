"""Pydantic schemas for Subcontractor domain (companies, contracts, payments)."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# ---------- Enums (mirrored from models for API contract isolation) ----------

class SubcontractorStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"


class ContractStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


# =============================================================================
# Subcontractor schemas
# =============================================================================

class SubcontractorBase(BaseModel):
    """Shared fields between create and update."""

    name: str = Field(..., min_length=1, max_length=255)
    tax_id: str | None = Field(None, max_length=50)
    contact_person: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)  # not EmailStr - we allow free format
    address: str | None = None
    specialization: str | None = Field(None, max_length=255)
    status: SubcontractorStatus = SubcontractorStatus.ACTIVE
    rating: Decimal | None = Field(None, ge=0, le=5)
    notes: str | None = None


class SubcontractorCreate(SubcontractorBase):
    """Payload for creating a subcontractor."""

    pass


class SubcontractorUpdate(BaseModel):
    """Payload for updating a subcontractor. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    tax_id: str | None = Field(None, max_length=50)
    contact_person: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    address: str | None = None
    specialization: str | None = Field(None, max_length=255)
    status: SubcontractorStatus | None = None
    rating: Decimal | None = Field(None, ge=0, le=5)
    notes: str | None = None


class CreatorSummary(BaseModel):
    """Minimal user info embedded in responses."""

    id: int
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class SubcontractorResponse(SubcontractorBase):
    """Subcontractor data returned from the API."""

    id: int
    is_active: bool
    created_by: int
    creator: CreatorSummary | None = None
    created_at: datetime
    updated_at: datetime

    # Computed fields (filled by endpoint)
    active_contract_count: int = 0
    total_contract_value: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class SubcontractorListItem(BaseModel):
    """Lightweight subcontractor item for list endpoint with aggregates."""

    id: int
    name: str
    tax_id: str | None = None
    specialization: str | None = None
    status: SubcontractorStatus
    rating: Decimal | None = None
    is_active: bool
    active_contract_count: int = 0
    total_contract_value: Decimal = Decimal("0")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Contract schemas
# =============================================================================

class ContractBase(BaseModel):
    """Shared fields between create and update."""

    project_id: int
    contract_number: str | None = Field(None, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    contract_amount: Decimal = Field(default=Decimal("0"), ge=0)
    start_date: date
    end_date: date
    status: ContractStatus = ContractStatus.DRAFT
    scope_of_work: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ContractCreate(ContractBase):
    """Payload for creating a contract under a subcontractor."""

    pass


class ContractUpdate(BaseModel):
    """Payload for updating a contract. All fields optional."""

    project_id: int | None = None
    contract_number: str | None = Field(None, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=500)
    contract_amount: Decimal | None = Field(None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    status: ContractStatus | None = None
    scope_of_work: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_date_range(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class SubcontractorSummary(BaseModel):
    """Minimal subcontractor info embedded in contract responses."""

    id: int
    name: str
    specialization: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectSummary(BaseModel):
    """Minimal project info embedded in contract responses."""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ContractResponse(ContractBase):
    """Contract data returned from the API."""

    id: int
    subcontractor_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    # Nested
    subcontractor: SubcontractorSummary | None = None
    project: ProjectSummary | None = None

    # Computed (filled by endpoint)
    paid_amount: Decimal = Decimal("0")
    pending_amount: Decimal = Decimal("0")
    payment_count: int = 0
    is_overdue: bool = False  # end_date < today AND status=ACTIVE

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Payment schemas
# =============================================================================

class PaymentBase(BaseModel):
    """Shared fields between create and update."""

    payment_number: int | None = Field(None, ge=1)  # null on create -> backend auto-assigns
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., gt=0)
    payment_date: date
    due_date: date | None = None
    status: PaymentStatus = PaymentStatus.PENDING
    invoice_number: str | None = Field(None, max_length=100)
    notes: str | None = None


class PaymentCreate(PaymentBase):
    """Payload for creating a payment under a contract."""

    pass


class PaymentUpdate(BaseModel):
    """Payload for updating a payment. All fields optional."""

    description: str | None = Field(None, min_length=1, max_length=500)
    amount: Decimal | None = Field(None, gt=0)
    payment_date: date | None = None
    due_date: date | None = None
    status: PaymentStatus | None = None
    invoice_number: str | None = Field(None, max_length=100)
    notes: str | None = None


class ContractMiniSummary(BaseModel):
    """Minimal contract info embedded in payment responses."""

    id: int
    contract_number: str | None = None
    description: str
    subcontractor_id: int

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    """Payment data returned from the API."""

    id: int
    contract_id: int
    payment_number: int
    description: str
    amount: Decimal
    payment_date: date
    due_date: date | None
    status: PaymentStatus
    invoice_number: str | None
    notes: str | None
    approved_by: int | None
    approved_at: datetime | None
    created_by: int
    created_at: datetime
    updated_at: datetime

    # Soft warnings (populated by endpoint when relevant)
    over_payment_warning: str | None = None  # set when total payments exceed contract amount

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# KPI dashboard schemas
# =============================================================================

class TopSubcontractor(BaseModel):
    """Top-N subcontractor entry for KPI dashboard."""

    id: int
    name: str
    total_value: Decimal
    contract_count: int


class MonthlyPaymentPoint(BaseModel):
    """One month aggregation for the monthly payments trend chart."""

    month: str  # ISO YYYY-MM
    amount: Decimal
    count: int


class SubcontractorKPIs(BaseModel):
    """Aggregated KPIs for the subcontractor dashboard."""

    total_subcontractors: int
    active_contracts: int
    overdue_contracts: int
    total_contract_value: Decimal
    total_paid: Decimal
    total_pending: Decimal
    payment_completion_pct: float

    top_subcontractors: list[TopSubcontractor] = []
    contracts_by_status: dict[str, int] = {}     # {"draft": 2, "active": 5, ...}
    payments_by_status: dict[str, Decimal] = {}  # {"pending": 100, "paid": 500, ...}
    monthly_payments: list[MonthlyPaymentPoint] = []  # last 6 months


# =============================================================================
# Financial Intelligence schemas (Phase 1)
# =============================================================================

class ContractForecast(BaseModel):
    """Financial forecast for a single contract."""

    contract_id: int
    contract_amount: Decimal
    total_paid: Decimal
    remaining_amount: Decimal
    payment_progress_pct: float
    burn_rate_per_day: Decimal  # ₽/day based on elapsed time
    avg_daily_payment: Decimal  # ₽/day based on last 30 days
    estimated_completion_date: str | None = None  # ISO date or null
    next_30_days_projected: Decimal  # expected spending in next 30 days
    days_elapsed: int
    days_remaining: int


class MonthlyCashFlowPoint(BaseModel):
    """Stacked monthly cash flow entry for a subcontractor."""

    month: str  # YYYY-MM
    paid_amount: Decimal
    approved_amount: Decimal
    pending_amount: Decimal


class PaymentDiscipline(BaseModel):
    """Payment discipline score (0-100) for a subcontractor."""

    subcontractor_id: int
    score: int  # 0-100
    grade: str  # A / B / C / D / F
    overdue_payment_pct: float
    rejected_payment_pct: float
    avg_approval_days: float
    total_payments_evaluated: int


# =============================================================================
# Risk & Alert schemas (Phase 2)
# =============================================================================

class ContractAlert(BaseModel):
    """Single alert/risk flag for a contract."""

    level: str  # "critical" | "warning" | "info"
    message: str
    category: str  # "budget" | "timeline" | "payment"


class RiskScore(BaseModel):
    """Aggregate risk score for a subcontractor."""

    subcontractor_id: int
    score: int  # 0 (no risk) → 100 (critical)
    level: str  # "critical" | "warning" | "healthy"
    alerts: list[ContractAlert] = []
    summary: str


# =============================================================================
# Document schemas (Phase 3)
# =============================================================================

class DocumentType(str, Enum):
    CONTRACT = "CONTRACT"
    INVOICE = "INVOICE"
    ADDENDUM = "ADDENDUM"
    REPORT = "REPORT"


class ContractDocumentResponse(BaseModel):
    """Contract document metadata returned from the API."""

    id: int
    contract_id: int
    file_name: str
    file_size: int
    mime_type: str
    file_type: DocumentType
    version: int
    extracted_data: dict | None = None
    uploaded_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedContractData(BaseModel):
    """Data extracted from a contract document via parsing."""

    contract_amount: Decimal | None = None
    start_date: str | None = None
    end_date: str | None = None
    company_names: list[str] = []
    payment_terms: list[str] = []
    confidence: float = 0.0  # 0-1


# =============================================================================
# AI Insights schemas (Phase 4)
# =============================================================================

class AIInsight(BaseModel):
    """Single AI-generated insight or prediction."""

    type: str  # "commentary" | "prediction" | "alert"
    severity: str  # "info" | "warning" | "critical"
    message: str
    metric_value: float | None = None
    generated_at: datetime


class SubcontractorInsights(BaseModel):
    """Collection of AI insights for a subcontractor."""

    subcontractor_id: int
    insights: list[AIInsight] = []
    overall_health: str  # "good" | "at_risk" | "critical"

