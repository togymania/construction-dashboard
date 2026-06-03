"""Generic fuzzy matching pipeline (Faz 1 — Data Integrity Recovery).

The reusable core behind reconciling unmatched ledger rows to budget
items (via cost code / description) and to subcontractors (via company
name). It is pure and isolated so it can be unit-tested exhaustively,
exactly like the cost-code engine it builds on.

Given a free-text query (plus an optional code) and a set of candidates,
``rank`` returns ranked suggestions. Each suggestion carries a 0-100
confidence score and a decision bucket:

    AUTO    score >= AUTO_THRESHOLD    -> safe to apply automatically
    REVIEW  score >= REVIEW_THRESHOLD  -> queue for human approval
    REJECT  score <  REVIEW_THRESHOLD  -> discard

Per candidate the score is the better of:
  1. exact code match (cost-code normalised)  -> 100, reason "exact_code"
  2. fuzzy text similarity (rapidfuzz)         -> 0-100, reason "fuzzy_text"

Safety rail: the top candidate is only ever labelled AUTO when it also
beats the runner-up by ``AMBIGUITY_MARGIN``. Two near-tied candidates are
therefore both downgraded to REVIEW, so we never silently auto-apply an
ambiguous match. Thresholds live here, in one place, on purpose
(mirroring the existing subcontractor matcher: 75 propose / 90 high).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz

from app.services.cost_code import normalize_cost_code

AUTO_THRESHOLD = 90.0
REVIEW_THRESHOLD = 75.0
# AUTO additionally requires (best - second_best) >= this, so ties never
# auto-apply.
AMBIGUITY_MARGIN = 5.0

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS = re.compile(r"\s+")


class Decision(str, Enum):
    AUTO = "auto"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(frozen=True)
class Candidate:
    """A thing a query row could be matched to (a budget item, a sub...)."""

    id: int
    text: str = ""
    code: str | None = None


@dataclass(frozen=True)
class Suggestion:
    """A scored, bucketed match proposal for one candidate."""

    candidate_id: int
    score: float
    decision: Decision
    reason: str  # "exact_code" | "fuzzy_text"


def normalize_text(value: object) -> str:
    """Lower-case, strip punctuation/accents noise, collapse whitespace.

    Used for fuzzy text comparison only (codes go through
    ``normalize_cost_code``). Returns ``""`` for blank input.
    """
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value))
    s = s.replace(" ", " ")  # NBSP -> space
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip().lower()
    return s


def score_pair(
    query_text: str,
    query_code: object,
    candidate: Candidate,
) -> tuple[float, str]:
    """Score one (query, candidate) pair. Returns ``(score, reason)``.

    Exact normalised code equality short-circuits to a perfect score; we
    never let a weaker fuzzy text score override a hard code match.
    """
    if query_code is not None and candidate.code is not None:
        qc = normalize_cost_code(query_code)
        if qc and qc == normalize_cost_code(candidate.code):
            return 100.0, "exact_code"

    qt = normalize_text(query_text)
    ct = normalize_text(candidate.text)
    if not qt or not ct:
        return 0.0, "fuzzy_text"
    return float(fuzz.token_set_ratio(qt, ct)), "fuzzy_text"


def classify(score: float, *, is_unambiguous: bool = True) -> Decision:
    """Bucket a raw score, downgrading AUTO to REVIEW when ambiguous."""
    if score >= AUTO_THRESHOLD and is_unambiguous:
        return Decision.AUTO
    if score >= REVIEW_THRESHOLD:
        return Decision.REVIEW
    return Decision.REJECT


def rank(
    query_text: str,
    candidates: list[Candidate],
    *,
    query_code: object = None,
    limit: int = 5,
) -> list[Suggestion]:
    """Rank candidates for a query, best first, with decision buckets.

    Only the single best candidate is eligible for AUTO, and only when it
    clears ``AMBIGUITY_MARGIN`` over the runner-up. All other returned
    suggestions are REVIEW/REJECT by their own score.
    """
    scored: list[tuple[float, str, Candidate]] = []
    for cand in candidates:
        score, reason = score_pair(query_text, query_code, cand)
        scored.append((score, reason, cand))

    # Sort by score desc, then by candidate id for a stable order.
    scored.sort(key=lambda t: (-t[0], t[2].id))

    best_score = scored[0][0] if scored else 0.0
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    unambiguous = (best_score - second_score) >= AMBIGUITY_MARGIN

    out: list[Suggestion] = []
    for idx, (score, reason, cand) in enumerate(scored[:limit]):
        is_top = idx == 0
        decision = classify(score, is_unambiguous=is_top and unambiguous)
        out.append(
            Suggestion(
                candidate_id=cand.id,
                score=round(score, 2),
                decision=decision,
                reason=reason,
            )
        )
    return out


def best_suggestion(
    query_text: str,
    candidates: list[Candidate],
    *,
    query_code: object = None,
) -> Suggestion | None:
    """Convenience: the single top suggestion, or ``None`` if no candidates."""
    ranked = rank(query_text, candidates, query_code=query_code, limit=1)
    return ranked[0] if ranked else None
