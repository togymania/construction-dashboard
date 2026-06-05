"""Project financial metrics — the Single Source of Truth (Faz 0 skeleton).

Today the same "spent %" is computed four different ways across the app
(dashboard 0%, project list 72%, budget page 61.4%, AI director 2%),
because each surface re-derives it from a different base. This module is
the one place every surface should call so they all agree.

Canonical definitions used here, once:

* ``budget_total``    -- the approved ceiling (``Project.budget_rub``).
* ``planned_total``   -- sum of budget item planned amounts.
* ``committed_total`` -- sum of budget item committed amounts.
* ``spent_total``     -- actual cash-out, taken from the variance report's
                         ``total_actual`` (already the OZET-derived real
                         spend the budget page shows).
* ``utilization_pct``     -- THE headline "harcanan %": spent / planned.
* ``budget_consumed_pct`` -- spent / approved budget.

Faz 0 ships the canonical definitions, the pure math, and an async
gatherer. Pointing the dashboard / project-list / AI endpoints at
``compute_project_financials`` so they stop disagreeing is Faz 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.budget_variance import build_variance_report


def _pct(numerator: Decimal, denominator: Decimal) -> float | None:
    """Percentage, or ``None`` when the denominator is missing / zero."""
    if denominator is None or denominator <= 0:
        return None
    return float(numerator / denominator * 100)


@dataclass(frozen=True)
class ProjectFinancials:
    """Canonical financial snapshot for one project. Immutable on purpose."""

    project_id: int
    budget_total: Decimal
    planned_total: Decimal
    committed_total: Decimal
    spent_total: Decimal
    remaining: Decimal
    utilization_pct: float | None
    budget_consumed_pct: float | None


def build_financials(
    *,
    project_id: int,
    budget_total: Decimal,
    planned_total: Decimal,
    committed_total: Decimal,
    spent_total: Decimal,
) -> ProjectFinancials:
    """Pure assembler — no DB. This is the *only* place the canonical
    percentages are defined, so every surface produces the same numbers.
    """
    budget_total = Decimal(budget_total)
    planned_total = Decimal(planned_total)
    committed_total = Decimal(committed_total)
    spent_total = Decimal(spent_total)
    return ProjectFinancials(
        project_id=project_id,
        budget_total=budget_total,
        planned_total=planned_total,
        committed_total=committed_total,
        spent_total=spent_total,
        remaining=planned_total - spent_total,
        utilization_pct=_pct(spent_total, planned_total),
        budget_consumed_pct=_pct(spent_total, budget_total),
    )


async def compute_project_financials(
    db: AsyncSession, project_id: int
) -> ProjectFinancials:
    """Gather the canonical financials for a project from the DB.

    ``spent_total`` = real cash-out from the Financial Summary (OZET,
    ``cash_out_total``). The budget page's per-item actuals are match-only
    (ledger budget_code <-> item cost_code) and intentionally smaller until
    the user assigns codes; the dashboard/EAC must still reflect true spend.
    Falls back to the matched total when no OZET rows exist (e.g. tests).
    """
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    budget_total = (
        Decimal(getattr(project, "budget_rub", 0) or 0)
        if project is not None
        else Decimal("0")
    )
    report = await build_variance_report(db, project_id)
    spent = report.cash_out_total if report.cash_out_total > 0 else report.total_actual
    return build_financials(
        project_id=project_id,
        budget_total=budget_total,
        planned_total=report.total_planned,
        committed_total=report.total_committed,
        spent_total=spent,
    )
