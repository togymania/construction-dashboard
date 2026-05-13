"""Pydantic schemas for the tender / bid module.

Two layers:

1. CRUD shapes (TenderCreate, BidCreate, …) used by the REST endpoints
   to validate request bodies and serialize responses for the
   comparison grid.
2. AI extraction shape (TenderExtraction) — what Claude returns when
   we hand it an Excel/PDF tender comparison file. The frontend treats
   that response as a *draft* the user can edit before persisting.
3. AI bid analysis shape (TenderAIAnalysis) — the 6-section
   recommendation Claude produces once all bids are in.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------


class TenderLineItemBase(BaseModel):
    order_num: int = Field(..., ge=1)
    description: str
    unit: str | None = None
    quantity: Decimal = Decimal("0")
    notes: str | None = None


class TenderLineItemCreate(TenderLineItemBase):
    pass


class TenderLineItemUpdate(BaseModel):
    order_num: int | None = None
    description: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    notes: str | None = None


class TenderLineItemRead(TenderLineItemBase):
    id: int
    tender_id: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Bid line items
# ---------------------------------------------------------------------------


class BidLineItemBase(BaseModel):
    """One cell in the comparison grid.

    Pricing rules (mirrors the model):
      * Both `unit_price_labor` and `unit_price_material` filled →
        split pricing, `unit_price_total` should equal their sum.
      * Only `unit_price_total` filled (others None) → single combined
        price; backend leaves labor/material as NULL.
      * `line_total` is always (qty × unit_price_total) — server-computed
        on write, returned to the client read-only.
    """

    tender_line_item_id: int
    unit_price_labor: Decimal | None = None
    unit_price_material: Decimal | None = None
    unit_price_total: Decimal = Decimal("0")
    notes: str | None = None


class BidLineItemUpsert(BidLineItemBase):
    """Used inside BidCreate / BidUpdate to push line prices in one shot."""


class BidLineItemRead(BidLineItemBase):
    id: int
    bid_id: int
    line_total: Decimal

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Bid
# ---------------------------------------------------------------------------


BidStatusStr = Literal["invited", "received", "withdrawn", "selected"]


class BidBase(BaseModel):
    company_name: str
    subcontractor_id: int | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    included_in_price: str | None = None
    not_included_in_price: str | None = None
    payment_terms: str | None = None
    delivery_days: int | None = Field(default=None, ge=0)
    notes: str | None = None


class BidCreate(BidBase):
    line_items: list[BidLineItemUpsert] = []


class BidUpdate(BaseModel):
    company_name: str | None = None
    subcontractor_id: int | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    included_in_price: str | None = None
    not_included_in_price: str | None = None
    payment_terms: str | None = None
    delivery_days: int | None = None
    notes: str | None = None
    status: BidStatusStr | None = None
    # Pass to fully replace the existing line-price rows in one go.
    # Omit (None) to leave them untouched.
    line_items: list[BidLineItemUpsert] | None = None


class BidRead(BidBase):
    id: int
    tender_id: int
    status: BidStatusStr
    total_labor: Decimal
    total_material: Decimal
    total_amount: Decimal
    received_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    line_items: list[BidLineItemRead] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Tender
# ---------------------------------------------------------------------------


TenderStatusStr = Literal["draft", "open", "evaluating", "awarded", "cancelled"]


class TenderBase(BaseModel):
    title: str
    object_name: str | None = None
    description: str | None = None
    currency: str = "RUB"
    payment_terms_expected: str | None = None
    delivery_terms_expected: str | None = None
    notes: str | None = None


class TenderCreate(TenderBase):
    line_items: list[TenderLineItemCreate] = []


class TenderUpdate(BaseModel):
    title: str | None = None
    object_name: str | None = None
    description: str | None = None
    currency: str | None = None
    payment_terms_expected: str | None = None
    delivery_terms_expected: str | None = None
    notes: str | None = None
    status: TenderStatusStr | None = None


class TenderRead(TenderBase):
    id: int
    project_id: int
    status: TenderStatusStr
    awarded_bid_id: int | None = None
    source_filename: str | None = None
    extracted_by_llm: bool
    created_at: datetime
    updated_at: datetime
    line_items: list[TenderLineItemRead] = []
    bids: list[BidRead] = []

    model_config = ConfigDict(from_attributes=True)


class TenderListItem(BaseModel):
    """Trimmed shape for the tenders list page (no nested line items)."""

    id: int
    project_id: int
    title: str
    status: TenderStatusStr
    currency: str
    line_item_count: int = 0
    bid_count: int = 0
    lowest_bid_amount: Decimal | None = None
    lowest_bid_company: str | None = None
    awarded_bid_id: int | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# AI extraction (Excel/PDF -> structured JSON, before persistence)
# ---------------------------------------------------------------------------


class ExtractedLineItem(BaseModel):
    order_num: int
    description: str
    unit: str | None = None
    quantity: Decimal = Decimal("0")


class ExtractedBidLine(BaseModel):
    """Per-line price for one extracted bid.

    `order_num` references the corresponding ExtractedLineItem.order_num.
    Both labor and material are optional — the AI fills them only when
    the source document splits the price.
    """

    order_num: int
    unit_price_labor: Decimal | None = None
    unit_price_material: Decimal | None = None
    unit_price_total: Decimal = Decimal("0")


class ExtractedBid(BaseModel):
    company_name: str
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    included_in_price: str | None = None
    not_included_in_price: str | None = None
    payment_terms: str | None = None
    delivery_days: int | None = None
    notes: str | None = None
    lines: list[ExtractedBidLine] = []


class TenderExtraction(BaseModel):
    """Full draft returned by the extraction service.

    The frontend renders this as an editable form the user can correct
    before pressing 'Save' to persist a real Tender + Bid rows.
    """

    title: str
    object_name: str | None = None
    currency: str = "RUB"
    payment_terms_expected: str | None = None
    delivery_terms_expected: str | None = None
    notes: str | None = None
    line_items: list[ExtractedLineItem] = []
    bids: list[ExtractedBid] = []
    source_filename: str | None = None
    source: Literal["llm", "rule"] = "llm"
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# AI Bid Analysis (6-section recommendation)
# ---------------------------------------------------------------------------


BidSpreadLevel = Literal["NORMAL", "WIDE", "ABNORMAL"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class BidSummary(BaseModel):
    company: str
    total_amount: Decimal = Decimal("0")
    delivery_days: int | None = None
    is_lowest: bool = False
    is_highest: bool = False


class TenderOverviewSection(BaseModel):
    title: str
    bid_count: int = 0
    average_total: Decimal = Decimal("0")
    lowest: BidSummary | None = None
    highest: BidSummary | None = None
    bid_spread_pct: float = 0.0
    bid_spread_level: BidSpreadLevel = "NORMAL"


class ComparisonRow(BaseModel):
    company: str
    total_amount: Decimal
    delivery_days: int | None = None
    notes: str | None = None


class AnalysisSection(BaseModel):
    best_price_company: str | None = None
    fastest_company: str | None = None
    most_balanced_company: str | None = None
    comments: str | None = None


class RiskItem(BaseModel):
    company: str
    risk: str
    cause: str


class RecommendationSection(BaseModel):
    chosen_company: str | None = None
    reason: str = ""
    alternative_company: str | None = None
    confidence_pct: float = Field(0.0, ge=0.0, le=100.0)


class TenderAIAnalysis(BaseModel):
    tender_id: int
    generated_at: datetime
    lang: Literal["EN", "TR"] = "EN"
    source: Literal["llm", "rule"] = "rule"

    overview: TenderOverviewSection
    comparison: list[ComparisonRow] = []
    analysis: AnalysisSection
    risks: list[RiskItem] = []
    recommendation: RecommendationSection
    executive_summary: str = ""
