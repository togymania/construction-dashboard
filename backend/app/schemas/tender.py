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

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


LineTypeStr = Literal["package", "work", "material", "misc"]
BidPriceTypeStr = Literal["fixed", "negotiable", "not_included", "on_request"]


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------


class TenderLineItemBase(BaseModel):
    order_num: int = Field(..., ge=1)
    description: str
    unit: str | None = None
    quantity: Decimal = Decimal("0")
    notes: str | None = None
    # Optional hierarchy + classification. Default values keep legacy
    # clients (and the simple "flat" tender form) working unchanged.
    parent_order_num: int | None = None
    display_label: str | None = None
    line_type: LineTypeStr = "misc"


class TenderLineItemCreate(TenderLineItemBase):
    pass


class TenderLineItemUpdate(BaseModel):
    order_num: int | None = None
    description: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    notes: str | None = None
    parent_order_num: int | None = None
    display_label: str | None = None
    line_type: LineTypeStr | None = None


class TenderLineItemRead(BaseModel):
    id: int
    tender_id: int
    parent_id: int | None = None
    order_num: int
    description: str
    unit: str | None = None
    quantity: Decimal = Decimal("0")
    notes: str | None = None
    display_label: str | None = None
    line_type: LineTypeStr = "misc"

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
      * `price_type` of anything other than "fixed" means the numeric
        fields are zero and `raw_text_price` carries the wording
        ("Договорная", "не включена", …).
    """

    tender_line_item_id: int
    unit_price_labor: Decimal | None = None
    unit_price_material: Decimal | None = None
    unit_price_total: Decimal = Decimal("0")
    price_type: BidPriceTypeStr = "fixed"
    raw_text_price: str | None = None
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


BidStatusStr = Literal[
    "invited", "received", "withdrawn", "selected", "superseded"
]


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
    # When the same company submits multiple proposals (e.g. material
    # A vs B) this distinguishes them. Empty/None for the common case.
    variant_label: str | None = None
    # Date the bidder put on their quotation (the КП-form / PDF header
    # tarihi). Stored separately from received_at so the negotiation
    # timeline reflects the supplier's clock, not ours.
    quote_date: date | None = None
    # VAT bookkeeping. The default 20% matches Russia's standard НДС.
    vat_rate: Decimal = Decimal("20")


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
    variant_label: str | None = None
    quote_date: date | None = None
    vat_rate: Decimal | None = None
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
    total_without_vat: Decimal = Decimal("0")
    revision_no: int = 1
    parent_bid_id: int | None = None
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
    """A draft tender line item produced by the AI extractor.

    `parent_order_num` references another line's `order_num` in the
    same extraction payload — at extraction time we don't yet have
    database ids, so the AI links children to parents by order number.
    """

    order_num: int
    description: str
    unit: str | None = None
    quantity: Decimal = Decimal("0")
    display_label: str | None = None
    parent_order_num: int | None = None
    line_type: LineTypeStr = "misc"


class ExtractedBidLine(BaseModel):
    """Per-line price for one extracted bid.

    `order_num` references the corresponding ExtractedLineItem.order_num.
    Both labor and material are optional — the AI fills them only when
    the source document splits the price. `price_type` lets us preserve
    "Договорная" / "не включена" rows without coercing them to 0₽.
    """

    order_num: int
    unit_price_labor: Decimal | None = None
    unit_price_material: Decimal | None = None
    unit_price_total: Decimal = Decimal("0")
    price_type: BidPriceTypeStr = "fixed"
    raw_text_price: str | None = None


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
    variant_label: str | None = None
    quote_date: date | None = None
    vat_rate: Decimal = Decimal("20")
    total_without_vat: Decimal | None = None
    total_with_vat: Decimal | None = None
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
# Market price help-box (Seviye 1 — Claude'un eğitim bilgisinden)
# ---------------------------------------------------------------------------


class MarketPriceEstimate(BaseModel):
    """One row of the comparison-grid help-box.

    Returned per tender_line_item_id. ``min`` / ``typical`` / ``max``
    are a rough market band in the tender's currency; ``source`` is
    "training" for Seviye 1 and will be "web" once we wire up live
    search. ``confidence`` is the model's self-rated reliability
    (LOW / MEDIUM / HIGH).
    """

    tender_line_item_id: int
    description: str
    unit: str | None = None
    currency: str = "RUB"
    min: Decimal | None = None
    typical: Decimal | None = None
    max: Decimal | None = None
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    note: str | None = None
    source: Literal["training", "web", "rule"] = "training"


class TenderMarketPrices(BaseModel):
    tender_id: int
    generated_at: datetime
    currency: str = "RUB"
    items: list[MarketPriceEstimate] = []
    disclaimer: str = ""


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
