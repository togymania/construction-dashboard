"""Data Reliability Score + verdict gate (Faz 2 — AI Governance keystone).

This is the piece that stops the two AI features from contradicting each
other on the same data. In the live audit the Executive Report said
"project on track / under budget" while the AI Project Director said
"CRITICAL — data reliability 0%", because each judged the project from a
different, ungoverned view of the same numbers.

The fix, encoded here as pure functions:

1. Derive ONE objective ``reliability_score`` (0-100) from data-quality
   signals — how much of the financial data is actually linked, and how
   fresh it is.
2. ``gate_verdict`` then forbids any optimistic verdict ("on track",
   "under budget") when reliability is low: the data simply does not
   support a positive call. Both AI features call this, so they can no
   longer disagree about whether the project is healthy.

Pure and dependency-free; the AI services pass in the signals they
already gather.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Weights for the composite score. Coverage dominates (an unlinked ledger
# makes every financial number meaningless); freshness is a smaller factor.
_W_BUDGET = 0.45
_W_SUB = 0.35
_W_FRESHNESS = 0.20

# Reliability bands.
HIGH_BAND = 70.0
MEDIUM_BAND = 40.0

# Freshness decays linearly from full marks at <= 2 days to zero at 30.
_FRESH_FULL_DAYS = 2.0
_FRESH_ZERO_DAYS = 30.0


@dataclass(frozen=True)
class ReliabilitySignals:
    """Objective data-quality inputs (whatever the AI service can count)."""

    total_rows: int = 0
    rows_with_budget_code: int = 0
    expense_rows: int = 0
    rows_with_subcontractor: int = 0
    freshness_days: float | None = None  # days since newest data; None = unknown


class ReliabilityBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Verdict(str, Enum):
    """Normalised project verdicts, worst-last so we can clamp upward."""

    ON_TRACK = "on_track"
    WATCH = "watch"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    DATA_UNRELIABLE = "data_unreliable"


# Verdicts that are "optimistic" and therefore unsafe to emit on bad data.
_OPTIMISTIC = {Verdict.ON_TRACK, Verdict.WATCH}


def _coverage(part: int, whole: int) -> float | None:
    """Fraction in [0, 1], or None when there is nothing to measure."""
    if whole <= 0:
        return None
    return max(0.0, min(1.0, part / whole))


def freshness_score(days: float | None) -> float:
    """0-100 score for how recent the newest data is."""
    if days is None:
        return 0.0
    if days <= _FRESH_FULL_DAYS:
        return 100.0
    if days >= _FRESH_ZERO_DAYS:
        return 0.0
    span = _FRESH_ZERO_DAYS - _FRESH_FULL_DAYS
    return round((1.0 - (days - _FRESH_FULL_DAYS) / span) * 100.0, 2)


def reliability_score(signals: ReliabilitySignals) -> float:
    """Composite 0-100 reliability score.

    Components with no denominator (e.g. no expense rows yet) are dropped
    and the remaining weights are renormalised, so a project with no
    subcontractor expenses isn't punished for it.
    """
    components: list[tuple[float, float]] = []  # (weight, 0-100 score)

    budget_cov = _coverage(signals.rows_with_budget_code, signals.total_rows)
    if budget_cov is not None:
        components.append((_W_BUDGET, budget_cov * 100.0))

    sub_cov = _coverage(signals.rows_with_subcontractor, signals.expense_rows)
    if sub_cov is not None:
        components.append((_W_SUB, sub_cov * 100.0))

    if signals.freshness_days is not None:
        components.append((_W_FRESHNESS, freshness_score(signals.freshness_days)))

    if not components:
        return 0.0
    total_weight = sum(w for w, _ in components)
    weighted = sum(w * s for w, s in components)
    return round(weighted / total_weight, 2)


def reliability_from_ledger_counts(
    uncategorized: int, unassigned: int, total: int
) -> float:
    """Score straight from the ledger data-quality counts both AI services
    already query (rows missing a budget code / a subcontractor link, out
    of the total). Using this in both places guarantees they gate on the
    *same* number and can no longer contradict each other.
    """
    if total <= 0:
        return 0.0
    return reliability_score(
        ReliabilitySignals(
            total_rows=total,
            rows_with_budget_code=max(0, total - uncategorized),
            expense_rows=total,
            rows_with_subcontractor=max(0, total - unassigned),
        )
    )


# Maximum points the missing-accrual ratio can subtract from the score.
ACCRUAL_MAX_PENALTY = 40.0


def apply_accrual_penalty(
    score: float, flagged_ratio: float, *, max_penalty: float = ACCRUAL_MAX_PENALTY
) -> float:
    """Lower the data-trust score by the share of contracts with missing
    accruals (Prompt 3 — CVR). A project where booked cost lags physical
    work is *less* trustworthy even if every ledger row is coded.
    """
    flagged = max(0.0, min(1.0, float(flagged_ratio)))
    return round(max(0.0, float(score) - flagged * max_penalty), 2)


def reliability_band(score: float) -> ReliabilityBand:
    if score >= HIGH_BAND:
        return ReliabilityBand.HIGH
    if score >= MEDIUM_BAND:
        return ReliabilityBand.MEDIUM
    return ReliabilityBand.LOW


def gate_verdict(proposed: Verdict, score: float) -> Verdict:
    """Clamp an optimistic verdict when the data can't support it.

    * LOW reliability  -> any optimistic verdict becomes DATA_UNRELIABLE.
    * MEDIUM reliability -> ON_TRACK is softened to WATCH (WATCH stays).
    * HIGH reliability  -> the proposed verdict passes through unchanged.

    Pessimistic verdicts (AT_RISK / CRITICAL) are never softened — bad data
    plus a bad signal is still bad.
    """
    band = reliability_band(score)
    if band is ReliabilityBand.LOW and proposed in _OPTIMISTIC:
        return Verdict.DATA_UNRELIABLE
    if band is ReliabilityBand.MEDIUM and proposed is Verdict.ON_TRACK:
        return Verdict.WATCH
    return proposed


def reliability_caveat(score: float, lang: str = "EN") -> str | None:
    """A one-line caveat to attach to any AI narrative, or None if HIGH."""
    band = reliability_band(score)
    if band is ReliabilityBand.HIGH:
        return None
    if lang.upper() == "TR":
        return (
            f"Veri güvenilirliği {score:.0f}/100 ({band.value}). "
            "Finansal kayıtların önemli kısmı eşleşmemiş; rakamlar temkinli yorumlanmalı."
        )
    return (
        f"Data reliability {score:.0f}/100 ({band.value}). "
        "A significant share of financial records is unlinked; treat figures with caution."
    )
