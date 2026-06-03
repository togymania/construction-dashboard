"""Accruals / Cost-Value Reconciliation (Prompt 3 — CVR data trust).

The old "dirty data" measure only counted invoices with no budget code or
no subcontractor. It missed a subtler, more dangerous problem: work that
has physically progressed on site but whose **cost has not been booked**
(no recent invoice / accrual). When that happens the project *looks*
cheap and profitable while real liabilities are piling up off the books.

This module flags it with CVR (Cost-Value Reconciliation) principles:

* ``missing_accrual_flag`` — a contract that has physical progress but no
  cost recorded in the last 30 days.
* ``progress_payment_gap`` — physical %% minus paid %%; a gap above 20
  points means cost recording is lagging reality ("Unreliable / Missing
  Accrual").

The flagged ratio feeds the Data Trust Score as a negative weight, and a
high ratio triggers an explicit AI warning. Pure.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GAP_THRESHOLD_PCT = 20.0
STALE_COST_DAYS = 30


@dataclass(frozen=True)
class ContractAccrualSignal:
    contract_id: int
    physical_progress_pct: float          # site progress (e.g. 40)
    payment_rate_pct: float               # paid / contract value * 100 (e.g. 5)
    days_since_last_cost: float | None = None  # None = never booked


def missing_accrual_flag(s: ContractAccrualSignal) -> bool:
    """True when there is physical progress but no recent cost booking."""
    if s.physical_progress_pct <= 0:
        return False
    return s.days_since_last_cost is None or s.days_since_last_cost > STALE_COST_DAYS


def progress_payment_gap(s: ContractAccrualSignal) -> float:
    """Physical %% minus paid %% (positive = cost recording lags reality)."""
    return round(float(s.physical_progress_pct) - float(s.payment_rate_pct), 2)


def is_unreliable_accrual(s: ContractAccrualSignal) -> bool:
    """A contract is accrual-unreliable if cost recording lags reality."""
    return missing_accrual_flag(s) or progress_payment_gap(s) > GAP_THRESHOLD_PCT


@dataclass
class CVRResult:
    total: int = 0
    flagged: int = 0
    flagged_contracts: list[int] = field(default_factory=list)

    @property
    def flagged_ratio(self) -> float:
        return round(self.flagged / self.total, 4) if self.total > 0 else 0.0


def assess_accruals(signals: list[ContractAccrualSignal]) -> CVRResult:
    """Run CVR over all contracts and report which are accrual-unreliable."""
    res = CVRResult(total=len(signals))
    for s in signals:
        if is_unreliable_accrual(s):
            res.flagged += 1
            res.flagged_contracts.append(s.contract_id)
    return res


# A high share of missing accruals makes the financial picture misleading.
WARN_RATIO = 0.30


def accrual_warning(cvr: CVRResult, *, lang: str = "EN") -> str | None:
    """The mandatory AI warning when too much cost is unbooked, else None."""
    if cvr.flagged_ratio < WARN_RATIO:
        return None
    if (lang or "EN").upper() == "TR":
        return (
            "Sahada yapılan işlerin maliyet kayıtları (tahakkuklar) sisteme "
            "işlenmemiştir; mevcut kâr/zarar durumu yanıltıcı olabilir."
        )
    return (
        "Costs for work already done on site have not been booked (missing "
        "accruals); the current profit/loss picture may be misleading."
    )
