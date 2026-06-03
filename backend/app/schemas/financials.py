"""Canonical project financials schema (Faz 1 — Single Source of Truth).

The shape returned by ``GET /projects/{id}/financials``. Every surface
that needs a "spent" figure or a utilisation percentage should read this
endpoint (or the underlying ``app.services.metrics``) instead of deriving
its own, so the dashboard, budget page, project list and AI all agree.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class ProjectFinancialsRead(BaseModel):
    project_id: int
    budget_total: Decimal          # approved ceiling (Project.budget_rub)
    planned_total: Decimal         # sum of budget item planned amounts
    committed_total: Decimal
    spent_total: Decimal           # canonical actual cash-out
    remaining: Decimal             # planned_total - spent_total
    utilization_pct: float | None      # spent / planned  (headline "harcanan %")
    budget_consumed_pct: float | None  # spent / approved budget
