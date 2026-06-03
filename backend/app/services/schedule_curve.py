"""S-Curve schedule model (Prompt 1 — replace linear planned progress).

Construction projects do not progress linearly: they ramp up slowly,
accelerate through the middle, and taper at the end — the classic
**S-curve**. Judging a project by ``elapsed / total`` (a straight line)
makes an early-stage project look "behind" and a late-stage one look
"ahead" when neither is true.

This module gives the **planned cumulative progress** at a point in time
as an S-curve (the basis of BCWS — Budgeted Cost of Work Scheduled).

Model: ``S(t) = t^k / (t^k + (1-t)^k)`` for time fraction ``t`` in [0,1].

* ``k = 1`` reproduces the old linear behaviour.
* ``k > 1`` (default 2.0) produces the slow-start / fast-middle / slow-end
  S shape. ``S(0)=0``, ``S(1)=1``, ``S(0.5)=0.5`` (symmetric), monotonic.

Pure and dependency-free.
"""
from __future__ import annotations

from datetime import date

DEFAULT_STEEPNESS = 2.0


def s_curve_fraction(time_fraction: float, *, steepness: float = DEFAULT_STEEPNESS) -> float:
    """Planned cumulative progress (0..1) at a given fraction of the schedule.

    ``time_fraction`` is clamped to [0, 1]. ``steepness`` (k) >= 1.
    """
    t = max(0.0, min(1.0, float(time_fraction)))
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    k = max(1.0, float(steepness))
    a = t ** k
    b = (1.0 - t) ** k
    return a / (a + b)


def planned_s_curve_progress(
    start: date | None,
    end: date | None,
    as_of: date | None = None,
    *,
    steepness: float = DEFAULT_STEEPNESS,
) -> float | None:
    """Planned % complete (0..100) today, per the S-curve.

    Returns ``None`` when the schedule dates are unusable. Before the start
    it is 0; after the end it is 100.
    """
    if start is None or end is None:
        return None
    today = as_of or date.today()
    span = (end - start).days
    if span <= 0:
        return None
    elapsed = (today - start).days
    if elapsed <= 0:
        return 0.0
    if elapsed >= span:
        return 100.0
    return round(s_curve_fraction(elapsed / span, steepness=steepness) * 100.0, 2)


def schedule_variance_pct(
    earned_progress_pct: float, planned_progress_pct: float | None
) -> float | None:
    """Earned minus planned, in percentage points. Negative == behind plan."""
    if planned_progress_pct is None:
        return None
    return round(float(earned_progress_pct) - float(planned_progress_pct), 2)
