"""LedgerEntry ORM model — HIPODROM-style income/expense ledger imported from Excel.

Distinct from `Expense` (which models project-budget approval workflow).
A LedgerEntry is a single line in a financial transaction log:
    - May be an INCOME (positive Miktar in source) or EXPENSE (negative)
    - Categorised by `kod` (1-HAKEDIS, 2-FIRMA, 3-UCRET, ...)
    - Optionally linked to a Subcontractor (after fuzzy-match approval)
    - Optionally tagged with a budget_code (filled in later by user)
"""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class LedgerEntryType(str, PyEnum):
    """Direction of a ledger entry."""

    INCOME = "income"
    EXPENSE = "expense"


class LedgerEntry(Base):
    """A single income/expense line, typically imported from an Excel ledger."""

    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ---- Core fields (mapped from Excel B/C/E/F/G/J) ----
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    kod: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    account: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Always stored positive; direction in entry_type
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    entry_type: Mapped[LedgerEntryType] = mapped_column(
        Enum(
            LedgerEntryType,
            name="ledger_entry_type",
            values_callable=_enum_values,
        ),
        nullable=False,
        index=True,
    )

    # ---- Budget code (manual fill — Excel's column doesn't match user's coding) ----
    budget_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # ---- Invoice number (Excel column X / Cynteka producerOfferNumber) ----
    # Stored so payments can be joined exactly to Cynteka invoices for
    # automatic budget-code assignment (invoice no + company).
    invoice_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # ---- Subcontractor link (set after match-approval; contract assignment is separate) ----
    subcontractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractor_contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ---- Dedup + provenance ----
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ---- Timestamps ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ---- Relationships ----
    subcontractor = relationship("Subcontractor", lazy="selectin")
    contract = relationship("SubcontractorContract", lazy="selectin")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_ledger_entries_amount_positive"),
        Index("ix_ledger_entries_company_lower", func.lower(company_name)),
    )

    def __repr__(self) -> str:
        return (
            f"<LedgerEntry(id={self.id}, date={self.entry_date}, "
            f"type={self.entry_type.value!r}, amount={self.amount}, "
            f"company={self.company_name!r})>"
        )
