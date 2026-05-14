"""Pydantic schemas for the OZET financial summary."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class FinancialSummaryRead(BaseModel):
    id: int
    project_id: int
    company_label: str
    as_of_date: date

    isveren_tahsilatlari: Decimal
    firma_odemeleri: Decimal
    ucret_giderleri: Decimal
    vergi_odemeleri: Decimal
    gelir_vergisi: Decimal
    kdv: Decimal
    faiz_gelirleri: Decimal
    banka_giderleri: Decimal
    diger_gelir_giderler: Decimal
    toplam: Decimal

    source_filename: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
