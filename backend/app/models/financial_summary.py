"""Project-level financial OZET summary per company.

Two rows per project: one for "Monotek" and one for "Monart" company
perspective. Values come from the "OZET" sheet of the company's
internal Harcama Takip Excel file. Stored as a flat row of cached
totals — service layer overwrites on each upload.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FinancialSummary(Base):
    """One row per (project, company) OZET snapshot.

    Stores the bottom-line cash flow items exactly as they appear on
    the Excel OZET sheet — gelir + gider kalemleri ham para birimi
    olarak (₽). UI tarafı bu rakamları doğrudan tabloya basar.
    """

    __tablename__ = "financial_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Şirket etiketi — "Monotek" veya "Monart". Aynı projede her iki şirket
    # için ayrı OZET tutulur. Heuristic: dosya adından parse edilir.
    company_label: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # OZET kalemleri (₽). İşaretler Excel'deki gibi tutulur:
    #   tahsilat/faiz pozitif, ödeme/gider negatif.
    isveren_tahsilatlari: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    firma_odemeleri: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    ucret_giderleri: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    vergi_odemeleri: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    # vergi alt kırılım
    gelir_vergisi: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    kdv: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )

    faiz_gelirleri: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    banka_giderleri: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    diger_gelir_giderler: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )
    toplam: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, default=Decimal("0")
    )

    # Provenance
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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

    __table_args__ = (
        UniqueConstraint(
            "project_id", "company_label", name="uq_financial_summary_project_company"
        ),
        Index(
            "ix_financial_summary_project_company",
            "project_id",
            "company_label",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialSummary id={self.id} project={self.project_id} "
            f"company={self.company_label!r} toplam={self.toplam}>"
        )
