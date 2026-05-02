"""Cash-flow forecast engine for subcontractors.

Computes a 3-month forecast using:
  1. Historical monthly aggregates (last 12 months of paid + approved amounts).
  2. Exponential moving average (EMA) of the last 3 months as a base level.
  3. Linear trend slope across the available history (capped to avoid overfit).
  4. Seasonality adjustment by quarter (Q1/Q2/Q3/Q4 averages vs. overall mean).
  5. Three scenarios (best / likely / worst) by widening the confidence band.

Honest about its limits:
  - When < 12 months of history exists, sets `insufficient_data=True` and
    falls back to naive average without seasonality.
  - Confidence drops sharply with thin data.
  - Months past contract end-dates are zeroed (no forecast beyond a contract's
    valid window if no other contracts cover them).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable


# ----- Public dataclass-like dicts (kept simple, returned to endpoint layer) ----

def build_forecast(
    *,
    subcontractor_id: int,
    history_rows: Iterable[tuple[str, Decimal]],  # (YYYY-MM, paid+approved amount)
    contracts: list[dict],  # [{id, contract_amount, total_paid, end_date, status, label}]
    today: date | None = None,
) -> dict:
    """Build a forecast bundle. Returns a plain dict matching CashFlowForecast schema."""
    today = today or date.today()
    history_map = _normalize_history(history_rows)
    months_of_data = len(history_map)

    # Build last-12-months historical series (with zeros for missing months in range)
    historical = _last_12_months_series(history_map, today)

    # Bail out if no history at all
    if months_of_data == 0:
        return {
            "subcontractor_id": subcontractor_id,
            "historical": historical,
            "forecast": [],
            "confidence": 0.0,
            "insufficient_data": True,
            "months_of_data": 0,
            "insights": ["No payment history yet — forecast cannot be generated."],
            "contract_end_dates": _contract_end_points(contracts),
            "method": "none",
        }

    # Decide method
    insufficient = months_of_data < 12
    method = "naive_average" if insufficient else "ema_seasonal"

    # Compute base level (EMA over last 3 non-zero months, fallback to mean)
    values = [float(v) for _, v in sorted(history_map.items())]
    base_level = _ema(values, span=3) if len(values) >= 1 else 0.0

    # Trend slope (per-month delta), capped
    trend = _linear_trend(values) if len(values) >= 4 else 0.0
    # Cap trend to +/- 25% of base level to avoid runaway extrapolation
    trend = max(min(trend, base_level * 0.25), -base_level * 0.25) if base_level > 0 else 0.0

    # Seasonality factors (only if we have >= 12 months)
    if not insufficient:
        season_factors = _seasonality_factors(history_map)
    else:
        season_factors = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}

    # Active contracts remaining capacity
    active_contracts = [c for c in contracts if c.get("status") == "active"]
    total_remaining = sum(
        max(Decimal("0"), Decimal(str(c["contract_amount"])) - Decimal(str(c.get("total_paid", 0))))
        for c in active_contracts
    )

    # If no active contracts → forecast is zero (firm has no live work)
    if not active_contracts or total_remaining <= 0:
        zero_forecast = [
            {
                "month": _shift_month(today, i).strftime("%Y-%m"),
                "best_case": Decimal("0"),
                "likely": Decimal("0"),
                "worst_case": Decimal("0"),
                "seasonality_factor": 1.0,
            }
            for i in range(1, 4)
        ]
        return {
            "subcontractor_id": subcontractor_id,
            "historical": historical,
            "forecast": zero_forecast,
            "confidence": 0.9,  # high confidence: no active contract = no expected payment
            "insufficient_data": insufficient,
            "months_of_data": months_of_data,
            "insights": ["No active contracts — no new payments expected in the next 3 months."],
            "contract_end_dates": _contract_end_points(contracts),
            "method": method,
        }

    # Build 3-month forecast
    forecast: list[dict] = []
    cumulative = Decimal("0")
    for i in range(1, 4):
        fmonth = _shift_month(today, i)
        quarter = _quarter_of(fmonth)
        season_mult = season_factors.get(quarter, 1.0)

        likely = max(0.0, base_level + trend * i) * season_mult
        # Worst: lower base, lower trend, drop seasonality benefit
        worst = max(0.0, (base_level * 0.7) + (trend * i * 0.5)) * min(season_mult, 1.0)
        # Best: higher base, higher trend, full seasonality up
        best = max(0.0, (base_level * 1.2) + (trend * i * 1.3)) * max(season_mult, 1.0)

        # Cap by remaining contract capacity (cumulative)
        likely_dec = Decimal(str(round(likely, 2)))
        worst_dec = Decimal(str(round(worst, 2)))
        best_dec = Decimal(str(round(best, 2)))

        # If cumulative likely exceeds remaining, taper down all scenarios
        if total_remaining > 0:
            remaining_after_cum = max(Decimal("0"), total_remaining - cumulative)
            if likely_dec > remaining_after_cum:
                ratio = float(remaining_after_cum / likely_dec) if likely_dec > 0 else 0.0
                likely_dec = remaining_after_cum
                worst_dec = Decimal(str(round(float(worst_dec) * ratio, 2)))
                best_dec = Decimal(str(round(float(best_dec) * ratio, 2)))

        cumulative += likely_dec

        forecast.append({
            "month": fmonth.strftime("%Y-%m"),
            "best_case": best_dec,
            "likely": likely_dec,
            "worst_case": worst_dec,
            "seasonality_factor": round(season_mult, 2),
        })

    # Confidence
    if insufficient:
        # 0.4 at 1 month → 0.65 at 11 months
        confidence = round(0.4 + (months_of_data - 1) * 0.025, 2)
        confidence = max(0.4, min(0.65, confidence))
    else:
        confidence = 0.8 if months_of_data >= 18 else 0.7

    # Build insights
    insights = _build_insights(
        history_map=history_map,
        forecast=forecast,
        season_factors=season_factors,
        contracts=contracts,
        insufficient=insufficient,
        months_of_data=months_of_data,
        trend=trend,
        base_level=base_level,
    )

    return {
        "subcontractor_id": subcontractor_id,
        "historical": historical,
        "forecast": forecast,
        "confidence": confidence,
        "insufficient_data": insufficient,
        "months_of_data": months_of_data,
        "insights": insights,
        "contract_end_dates": _contract_end_points(contracts),
        "method": method,
    }


# ----- Helpers ---------------------------------------------------------------

def _normalize_history(rows: Iterable[tuple[str, Decimal]]) -> dict[str, Decimal]:
    """Convert raw rows into a dict keyed by YYYY-MM. Skips zero/null amounts."""
    out: dict[str, Decimal] = {}
    for month, amount in rows:
        if not month:
            continue
        amt = Decimal(str(amount or 0))
        if amt <= 0:
            continue
        out[str(month)[:7]] = amt
    return out


def _last_12_months_series(history_map: dict[str, Decimal], today: date) -> list[dict]:
    """Return last 12 months of history including zero-fill for missing months."""
    series: list[dict] = []
    for i in range(11, -1, -1):
        m = _shift_month(today, -i)
        key = m.strftime("%Y-%m")
        amt = history_map.get(key, Decimal("0"))
        series.append({
            "month": key,
            "paid_amount": amt,
            "approved_amount": Decimal("0"),
            "pending_amount": Decimal("0"),
        })
    return series


def _shift_month(d: date, months: int) -> date:
    """Shift date by N months (positive=forward, negative=backward), keeping day=1."""
    total = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(total, 12)
    return date(year, month0 + 1, 1)


def _ema(values: list[float], span: int = 3) -> float:
    """Exponential moving average over the last `span` values."""
    if not values:
        return 0.0
    window = values[-span:]
    alpha = 2.0 / (span + 1.0)
    ema = window[0]
    for v in window[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def _linear_trend(values: list[float]) -> float:
    """Simple least-squares slope (per-step). Returns 0 if input too short."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    den = sum((x - mean_x) ** 2 for x in xs)
    return num / den if den != 0 else 0.0


def _quarter_of(d: date) -> int:
    return (d.month - 1) // 3 + 1


def _seasonality_factors(history_map: dict[str, Decimal]) -> dict[int, float]:
    """Compute Q1-Q4 multipliers vs. the overall mean."""
    by_q: dict[int, list[float]] = defaultdict(list)
    for key, amt in history_map.items():
        try:
            year, month = key.split("-")
            d = date(int(year), int(month), 1)
            by_q[_quarter_of(d)].append(float(amt))
        except Exception:
            continue

    overall = [v for vs in by_q.values() for v in vs]
    if not overall:
        return {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}
    mean = sum(overall) / len(overall)
    if mean == 0:
        return {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}

    factors: dict[int, float] = {}
    for q in (1, 2, 3, 4):
        if q in by_q and by_q[q]:
            factors[q] = sum(by_q[q]) / len(by_q[q]) / mean
        else:
            factors[q] = 1.0
    # Cap factors to [0.5, 1.5] to avoid extreme swings
    return {q: max(0.5, min(1.5, f)) for q, f in factors.items()}


def _contract_end_points(contracts: list[dict]) -> list[dict]:
    """Build end-date markers for active contracts."""
    points: list[dict] = []
    for c in contracts:
        if c.get("status") not in ("active", "draft"):
            continue
        end = c.get("end_date")
        if not end:
            continue
        amount = Decimal(str(c.get("contract_amount", 0)))
        paid = Decimal(str(c.get("total_paid", 0)))
        points.append({
            "contract_id": c["id"],
            "contract_label": c.get("label") or f"Contract #{c['id']}",
            "end_date": str(end)[:10],
            "remaining_amount": max(Decimal("0"), amount - paid),
        })
    return points


def _build_insights(
    *,
    history_map: dict[str, Decimal],
    forecast: list[dict],
    season_factors: dict[int, float],
    contracts: list[dict],
    insufficient: bool,
    months_of_data: int,
    trend: float,
    base_level: float,
) -> list[str]:
    out: list[str] = []

    if insufficient:
        out.append(
            f"Insufficient data: only {months_of_data} months of history. "
            "Seasonality disabled — forecast based on recent average."
        )
    else:
        # Find dominant quarter
        max_q = max(season_factors, key=season_factors.get)
        max_f = season_factors[max_q]
        if max_f > 1.10:
            out.append(f"Q{max_q} historically runs {int((max_f-1)*100)}% higher payments for this firm.")
        min_q = min(season_factors, key=season_factors.get)
        min_f = season_factors[min_q]
        if min_f < 0.90:
            out.append(f"Q{min_q} historically runs {int((1-min_f)*100)}% lower payments for this firm.")

    # Trend direction
    if base_level > 0:
        if trend > base_level * 0.05:
            out.append(f"Recent months show an upward payment trend (~{int(trend/base_level*100)}%/month).")
        elif trend < -base_level * 0.05:
            out.append(f"Recent months show a downward payment trend (~{int(abs(trend)/base_level*100)}%/month).")

    # Active contract capacity
    active = [c for c in contracts if c.get("status") == "active"]
    if active:
        total_remaining = sum(
            max(Decimal("0"), Decimal(str(c["contract_amount"])) - Decimal(str(c.get("total_paid", 0))))
            for c in active
        )
        likely_3m = sum(Decimal(str(f["likely"])) for f in forecast)
        if total_remaining > 0 and likely_3m > 0:
            months_to_finish = float(total_remaining / (likely_3m / 3)) if likely_3m > 0 else 0.0
            if months_to_finish < 6:
                out.append(
                    f"Remaining on active contracts: {total_remaining:,.0f} RUB — "
                    f"finishes in approximately {months_to_finish:.1f} months at current pace."
                )
            else:
                out.append(
                    f"Remaining on active contracts: {total_remaining:,.0f} RUB. "
                    f"At current pace it would take {months_to_finish:.1f} months (long)."
                )

    return out


def _to_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return None
