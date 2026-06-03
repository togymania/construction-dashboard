"""Earned Value Analysis (Prompt 2 — proper EVA, not a heuristic).

Replaces the old cost-consistency heuristic ``(spent/BAC) - (progress/100)``
with the standard Earned Value metrics every construction controller
expects:

* **BCWS** (Planned Value)  = BAC x planned %% complete (from the S-curve)
* **BCWP** (Earned Value)   = BAC x physical %% complete
* **ACWP** (Actual Cost)    = paid + pending accruals to date
* **CPI** = BCWP / ACWP   (cost efficiency; < 1 = over budget)
* **SPI** = BCWP / BCWS   (schedule efficiency; < 1 = behind)
* **EAC** = BAC / CPI     (forecast cost at completion)
* **VAC** = BAC - EAC     (projected over/under at completion)

Cost rule (per spec): CPI < 0.90 -> over budget (red); CPI > 1.0 ->
favourable (green); in between -> on target (amber).

Pure; ``Decimal`` for money.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class CostBand:
    OVER_BUDGET = "over_budget"   # red
    ON_TARGET = "on_target"       # amber
    FAVOURABLE = "favourable"     # green
    UNKNOWN = "unknown"


class ScheduleBand:
    BEHIND = "behind"
    ON_SCHEDULE = "on_schedule"
    AHEAD = "ahead"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EVAResult:
    bac: Decimal
    bcws: Decimal       # planned value
    bcwp: Decimal       # earned value
    acwp: Decimal       # actual cost
    cv: Decimal         # cost variance  = BCWP - ACWP
    sv: Decimal         # schedule variance = BCWP - BCWS
    cpi: float | None
    spi: float | None
    eac: Decimal | None
    etc: Decimal | None  # estimate to complete = EAC - ACWP
    vac: Decimal | None  # variance at completion = BAC - EAC
    cost_band: str
    schedule_band: str


def _q(d: Decimal) -> Decimal:
    return d.quantize(Decimal("1"))


def compute_eva(
    *,
    bac: Decimal,
    physical_progress_pct: float,
    acwp: Decimal,
    planned_progress_pct: float | None,
) -> EVAResult:
    """Compute the full EVA set. ``planned_progress_pct`` is the S-curve
    planned %% (BCWS basis); pass ``None`` if the schedule is unknown."""
    bac = Decimal(bac)
    acwp = Decimal(acwp)
    phys = max(0.0, min(100.0, float(physical_progress_pct))) / 100.0
    bcwp = bac * Decimal(str(phys))

    if planned_progress_pct is None:
        bcws = Decimal("0")
        spi: float | None = None
        schedule_band = ScheduleBand.UNKNOWN
    else:
        pv = max(0.0, min(100.0, float(planned_progress_pct))) / 100.0
        bcws = bac * Decimal(str(pv))
        spi = float(bcwp / bcws) if bcws > 0 else None
        if spi is None:
            schedule_band = ScheduleBand.UNKNOWN
        elif spi < 0.9:
            schedule_band = ScheduleBand.BEHIND
        elif spi > 1.0:
            schedule_band = ScheduleBand.AHEAD
        else:
            schedule_band = ScheduleBand.ON_SCHEDULE

    cv = bcwp - acwp
    sv = bcwp - bcws

    if acwp <= 0:
        cpi: float | None = None
        eac = etc = vac = None
        cost_band = CostBand.UNKNOWN
    else:
        cpi = float(bcwp / acwp)
        if cpi <= 0:
            eac = etc = vac = None
            cost_band = CostBand.UNKNOWN
        else:
            eac = bac / Decimal(str(cpi))
            etc = eac - acwp
            vac = bac - eac
            if cpi < 0.9:
                cost_band = CostBand.OVER_BUDGET
            elif cpi > 1.0:
                cost_band = CostBand.FAVOURABLE
            else:
                cost_band = CostBand.ON_TARGET

    return EVAResult(
        bac=_q(bac), bcws=_q(bcws), bcwp=_q(bcwp), acwp=_q(acwp),
        cv=_q(cv), sv=_q(sv),
        cpi=round(cpi, 4) if cpi is not None else None,
        spi=round(spi, 4) if spi is not None else None,
        eac=_q(eac) if eac is not None else None,
        etc=_q(etc) if etc is not None else None,
        vac=_q(vac) if vac is not None else None,
        cost_band=cost_band,
        schedule_band=schedule_band,
    )


def _fmt(amount: Decimal) -> str:
    return f"{int(amount):,} ₽"


def eva_projection_sentence(eva: EVAResult, *, lang: str = "EN") -> str:
    """The mandatory 'Mali Durum' sentence: how far the finish budget may
    drift at the current performance. Always returns a sentence."""
    is_tr = (lang or "EN").upper() == "TR"
    if eva.eac is None or eva.vac is None or eva.cpi is None:
        return (
            "Yetersiz maliyet verisi nedeniyle bitiş bütçesi projeksiyonu yapılamıyor."
            if is_tr
            else "Insufficient cost data to project the budget at completion."
        )
    over = eva.vac < 0
    mag = _fmt(abs(eva.vac))
    if is_tr:
        yon = "aşabilir" if over else "altında kalabilir"
        return (
            f"Mevcut performansa göre (CPI={eva.cpi:.2f}) projenin bitiş bütçesi "
            f"{mag} tutarında {yon} (EAC {_fmt(eva.eac)})."
        )
    direction = "over" if over else "under"
    return (
        f"At the current performance (CPI={eva.cpi:.2f}), the project budget "
        f"at completion may run {mag} {direction} (EAC {_fmt(eva.eac)})."
    )
