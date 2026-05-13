"""Tender (ihale) ORM models.

A Tender groups the offers we collect for a specific work package on a
project (örn. "Karot", "Pencere doğraması imalatı", "Mekanik tesisat").
Each Tender has N line items (a metraj-keşif row: description + unit +
quantity) and M bids -- one per company that submitted a quotation.
Every bid carries unit prices per line item; prices may be split into
labor (işçilik) and material (malzeme) when the source document
separates them, or kept as a single combined price when it doesn't.

Schema overview:

    tenders ──┬─< tender_line_items
              └─< bids ──< bid_line_items >── tender_line_items

The full cross of (line items × bids) sits in `bid_line_items` so the
comparison grid can render one row per line item with one cell per
company without N+1 queries on the frontend.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TenderStatus(str, PyEnum):
    """Lifecycle of a tender package."""

    DRAFT = "draft"        # being prepared (line items not finalized)
    OPEN = "open"          # collecting bids
    EVALUATING = "evaluating"  # all bids in, AI analysis run
    AWARDED = "awarded"    # winner picked; further bids ignored
    CANCELLED = "cancelled"


class BidStatus(str, PyEnum):
    """Per-company bid state inside a tender."""

    INVITED = "invited"    # company invited, no bid yet
    RECEIVED = "received"  # bid recorded
    WITHDRAWN = "withdrawn"
    SELECTED = "selected"  # the awarded bid; mirrors tender.awarded_bid_id
    SUPERSEDED = "superseded"  # an older revision; replaced by a newer bid


class LineType(str, PyEnum):
    """Classification of a tender line item.

    Drives display + AI extraction. A "package" is an outer rollup
    (1, 2, 3); "work"/"material"/"misc" are typically sub-lines under
    a package. The default is "misc" so legacy rows that don't set
    a value still render unchanged.
    """

    PACKAGE = "package"
    WORK = "work"
    MATERIAL = "material"
    MISC = "misc"


class BidPriceType(str, PyEnum):
    """How a single bid_line_item's price was given by the bidder."""

    FIXED = "fixed"            # numeric price, the normal path
    NEGOTIABLE = "negotiable"  # "Договорная", "по запросу", etc.
    NOT_INCLUDED = "not_included"  # "не включена", "за отд. плату"
    ON_REQUEST = "on_request"  # requires further clarification


# ---------------------------------------------------------------------------
# Tender (the work package being put out to bid)
# ---------------------------------------------------------------------------


class Tender(Base):
    """A work package put out to bid within a project."""

    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Header / meta
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    object_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Currency for all prices on this tender (RUB by default; can be EUR/USD)
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="RUB", server_default=text("'RUB'")
    )

    # Soft text fields (the "В стоимость входит / не входит" etc. on the
    # template's footer). Keep them on the tender too so the user can
    # pre-write expected terms before any bid arrives.
    payment_terms_expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_terms_expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, name="tender_status", values_callable=_enum_values),
        default=TenderStatus.DRAFT,
        server_default=text("'draft'"),
        nullable=False,
        index=True,
    )

    awarded_bid_id: Mapped[int | None] = mapped_column(
        ForeignKey("bids.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # Provenance: which file did we parse this tender from?
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_by_llm: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    line_items: Mapped[list["TenderLineItem"]] = relationship(
        back_populates="tender",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TenderLineItem.order_num",
    )
    bids: Mapped[list["Bid"]] = relationship(
        back_populates="tender",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Bid.tender_id",
    )

    __table_args__ = (
        Index("ix_tenders_project_status", "project_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Tender id={self.id} title={self.title!r} status={self.status.value}>"


class TenderLineItem(Base):
    """One row of the metraj-keşif tablosu for a tender.

    Lines can nest one level deep: an outer "package" (e.g. "1. Asphalt
    paving") may have child rows (1.1 prep, 1.2 asphalt mix, 1.3 finish).
    Children carry ``parent_id`` pointing at the package and use a
    ``line_type`` of "work" / "material" so the UI can render them with
    indentation and the AI knows what kind of price to expect.
    """

    __tablename__ = "tender_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("tender_line_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    order_num: Mapped[int] = mapped_column(Integer, nullable=False)
    # Free-form label users see (e.g. "1", "1.1", "2.a"). When the AI
    # extracts a hierarchical document we preserve the original numbering.
    display_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    line_type: Mapped[LineType] = mapped_column(
        Enum(LineType, name="tender_line_type", values_callable=_enum_values),
        default=LineType.MISC,
        server_default=text("'misc'"),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tender: Mapped[Tender] = relationship(back_populates="line_items")
    bid_lines: Mapped[list["BidLineItem"]] = relationship(
        back_populates="tender_line_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("tender_id", "order_num", name="uq_tender_line_order"),
        CheckConstraint("quantity >= 0", name="ck_tender_line_qty_nonneg"),
    )


# ---------------------------------------------------------------------------
# Bid (one company's offer for the tender)
# ---------------------------------------------------------------------------


class Bid(Base):
    """One company's quotation against a tender."""

    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional link to a Subcontractor record (when the bidder already
    # exists in the company database). When the AI extracts a bid from
    # an unknown company we keep `company_name` free-text and leave the
    # link null until the user confirms or creates the sub.
    subcontractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Contact block (matches the Контактное лицо row in the КП Form)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Commentary block
    included_in_price: Mapped[str | None] = mapped_column(Text, nullable=True)
    not_included_in_price: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cached totals (re-computed whenever a bid_line_item is upserted).
    # Stored to avoid summing across the join every comparison-grid load.
    total_labor: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    total_material: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )

    # VAT bookkeeping. ``total_amount`` is the "with VAT" figure for
    # legacy reasons. ``total_without_vat`` is the net the bidder
    # actually quotes; both are stored so the UI can flip between them.
    total_without_vat: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("20"), server_default=text("20")
    )

    # Optional variant label — same company sometimes submits two or
    # three different proposed solutions (e.g. material A vs B). The
    # uniqueness constraint below lets a (tender_id, company_name) pair
    # exist multiple times as long as variant_label differs.
    variant_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Date the BIDDER put on their quotation (extracted from the PDF /
    # КП header, NOT the timestamp we received it on our side). Drives
    # the "negotiation timeline" rendered under each bidder card.
    quote_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Revision tracking — when the same supplier sends a second offer
    # for the same (tender, variant) pair we don't open a new card. The
    # incoming bid gets revision_no=N+1 and points back to its
    # predecessor; older rows flip to BidStatus.SUPERSEDED so the
    # comparison grid ignores them. The full chain is rendered as a
    # mini-timeline under the latest revision's card.
    revision_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    parent_bid_id: Mapped[int | None] = mapped_column(
        ForeignKey("bids.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[BidStatus] = mapped_column(
        Enum(BidStatus, name="bid_status", values_callable=_enum_values),
        default=BidStatus.INVITED,
        server_default=text("'invited'"),
        nullable=False,
        index=True,
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(
        back_populates="bids", foreign_keys=[tender_id]
    )
    line_items: Mapped[list["BidLineItem"]] = relationship(
        back_populates="bid",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # A company can submit multiple "variant" proposals per tender
        # as long as variant_label distinguishes them. NULL variants
        # collapse to the company-name-only key (Postgres treats NULLs
        # as distinct, so two NULLs are allowed — service layer enforces
        # the no-duplicate rule when no variant is set).
        UniqueConstraint("tender_id", "company_name", "variant_label",
                         name="uq_bid_tender_company_variant"),
        CheckConstraint("total_amount >= 0", name="ck_bid_total_nonneg"),
        CheckConstraint("delivery_days IS NULL OR delivery_days >= 0", name="ck_bid_delivery_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<Bid id={self.id} tender={self.tender_id} company={self.company_name!r} total={self.total_amount}>"


class BidLineItem(Base):
    """One company's quoted price for one line item.

    Stores labor and material as separate optional fields so the source
    file's level of detail is preserved:

    * Both filled    -> the bidder broke the price into işçilik + malzeme
    * Only `total`   -> the bidder gave a combined unit price
    * `labor` only   -> labor-only quote (rare; treated as total in display)

    The cached `unit_price_total` is what drives `line_total = qty *
    unit_price_total` so the comparison grid always has a definitive
    "what does this row cost from this bidder" number.
    """

    __tablename__ = "bid_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bid_id: Mapped[int] = mapped_column(
        ForeignKey("bids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tender_line_item_id: Mapped[int] = mapped_column(
        ForeignKey("tender_line_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    unit_price_labor: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    unit_price_material: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    # Definitive unit price. Either:
    #   - the source's single combined unit price, OR
    #   - labor + material when those were split
    unit_price_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    # qty (from tender_line_item) * unit_price_total, materialised so we
    # don't recompute on every comparison-grid render
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )

    # How the bidder gave the price. FIXED is the normal path; the
    # other values let us keep "Договорная" or "не включена" rows in
    # the grid without breaking the numeric totals (raw_text_price
    # carries the original wording for display).
    price_type: Mapped[BidPriceType] = mapped_column(
        Enum(BidPriceType, name="bid_price_type", values_callable=_enum_values),
        default=BidPriceType.FIXED,
        server_default=text("'fixed'"),
        nullable=False,
    )
    raw_text_price: Mapped[str | None] = mapped_column(String(120), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    bid: Mapped[Bid] = relationship(back_populates="line_items")
    tender_line_item: Mapped[TenderLineItem] = relationship(back_populates="bid_lines")

    __table_args__ = (
        UniqueConstraint(
            "bid_id",
            "tender_line_item_id",
            name="uq_bid_line_per_tender_item",
        ),
        CheckConstraint("unit_price_total >= 0", name="ck_bid_line_unit_nonneg"),
        CheckConstraint("line_total >= 0", name="ck_bid_line_total_nonneg"),
    )
