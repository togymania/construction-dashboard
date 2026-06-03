"""Predictive risk scoring (Faz 3 — Construction Intelligence cores).

Two pure, explainable scoring functions that the dashboards and AI
narratives can surface:

* ``subcontractor_risk_score`` — a 0-100 risk score per subcontractor,
  driven mainly by overdue contracts, with smaller contributions from
  weak payment progress, thin payment history and low rating.
* ``forecast_eac`` — classic Earned-Value cost-overrun forecast
  (EV / CPI / EAC / variance-at-completion) with an overrun band.

Both are deterministic and unit-tested. Heavier ML (trained predictive
models) can replace these later behind the same interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

# ---------------------------------------------------------------------------
# Subcontractor risk
# ---------------------------------------------------------------------------

_W_OVERDUE = 0.55
_W_UNDERPAY = 0.20
_W_RATING = 0.15
_W_HISTORY = 0.10

_HEALTHY_HISTORY_MONTHS = 12


class RiskBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class SubcontractorSignals:
    active_contracts: int = 0
    overdue_contracts: int = 0
    total_contract_value: Decimal = Decimal("0")
    paid_value: Decimal = Decimal("0")
    months_of_history: int = 0
    rating: float | None = None  # 0-5 stars, or None when unrated


def _ratio(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return max(0.0, min(1.0, part / whole))


def subcontractor_risk_score(s: SubcontractorSignals) -> float:
    """0-100, higher = riskier. Deterministic and explainable."""
    overdue = _ratio(s.overdue_contracts, s.active_contracts) * 100.0

    # Under-payment relative to contract value is a mild risk signal; only
    # meaningful when there is contract value to compare against.
    paid_ratio = _ratio(float(s.paid_value), float(s.total_contract_value))
    underpay = (1.0 - paid_ratio) * 100.0 if s.total_contract_value > 0 else 0.0

    rating_pen = ((5.0 - s.rating) / 5.0 * 100.0) if s.rating is not None else 0.0

    if s.months_of_history >= _HEALTHY_HISTORY_MONTHS:
        history_pen = 0.0
    else:
        history_pen = (
            (_HEALTHY_HISTORY_MONTHS - s.months_of_history)
            / _HEALTHY_HISTORY_MONTHS
            * 100.0
        )

    score = (
        _W_OVERDUE * overdue
        + _W_UNDERPAY * underpay
        + _W_RATING * rating_pen
        + _W_HISTORY * history_pen
    )
    return round(max(0.0, min(100.0, score)), 2)


def risk_band(score: float) -> RiskBand:
    if score >= 66:
        return RiskBand.HIGH
    if score >= 33:
        return RiskBand.MEDIUM
    return RiskBand.LOW


# ---------------------------------------------------------------------------
# Cost-overrun forecast (Earned Value)
# ---------------------------------------------------------------------------


class OverrunBand(str, Enum):
    UNKNOWN = "unknown"
    UNDER_OR_ON = "under_or_on"  # CPI >= 1.0
    WATCH = "watch"              # 0.9 <= CPI < 1.0
    OVERRUN_RISK = "overrun_risk"  # CPI < 0.9


@dataclass(frozen=True)
class EACResult:
    bac: Decimal           # budget at completion (planned)
    ev: Decimal            # earned value = progress * bac
    ac: Decimal            # actual cost to date
    cpi: float | None      # cost performance index = EV / AC
    eac: Decimal | None    # estimate at completion = BAC / CPI
    variance_at_completion: Decimal | None  # BAC - EAC (positive = under)
    band: OverrunBand


def forecast_eac(
    bac: Decimal, actual_cost: Decimal, progress_pct: float
) -> EACResult:
    """Earned-Value cost forecast. Mirrors the project overview EAC card.

    EV  = progress * BAC
    CPI = EV / AC
    EAC = BAC / CPI   (how much the whole job will cost at the current rate)
    VAC = BAC - EAC   (positive == projected under budget)
    """
    bac = Decimal(bac)
    ac = Decimal(actual_cost)
    progress = max(0.0, min(100.0, float(progress_pct))) / 100.0
    ev = bac * Decimal(str(progress))

    if ac <= 0:
        return EACResult(bac, ev, ac, None, None, None, OverrunBand.UNKNOWN)

    cpi = float(ev / ac)
    if cpi <= 0:
        return EACResult(bac, ev, ac, cpi, None, None, OverrunBand.UNKNOWN)

    eac = bac / Decimal(str(cpi))
    vac = bac - eac
    if cpi >= 1.0:
        band = OverrunBand.UNDER_OR_ON
    elif cpi >= 0.9:
        band = OverrunBand.WATCH
    else:
        band = OverrunBand.OVERRUN_RISK
    return EACResult(
        bac=bac,
        ev=ev,
        ac=ac,
        cpi=round(cpi, 4),
        eac=eac.quantize(Decimal("1")),
        variance_at_completion=vac.quantize(Decimal("1")),
        band=band,
    )
