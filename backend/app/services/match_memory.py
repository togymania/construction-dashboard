"""Adaptive match memory (Faz 2.5 — Learning Match Engine).

When a reviewer keeps approving the same mapping (e.g. "ООО Монарт" ->
subcontractor 12), the system should learn it: a future row with the same
normalized text gets a confidence boost, so it auto-applies instead of
queuing for review again. The boost grows with the number of approvals
and is capped so learning can lift a borderline REVIEW to AUTO but can
never manufacture a match from nothing.

Pure core:
* ``MatchMemory`` accumulates approval counts keyed by (normalized text,
  candidate id). In production it is built from the approved
  ``MatchSuggestion`` rows.
* ``boosted_rank`` re-scores the pipeline's suggestions with the learned
  boost and re-buckets them with the same safety rails as ``rank``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.matching import (
    AMBIGUITY_MARGIN,
    Candidate,
    Suggestion,
    classify,
    normalize_text,
    rank,
)

# Each approval of the same mapping adds this much confidence, up to a cap.
PER_APPROVAL_BOOST = 4.0
MAX_BOOST = 15.0


@dataclass
class MatchMemory:
    """Learned approval counts keyed by (normalized text, candidate id)."""

    _counts: dict[tuple[str, int], int] = field(default_factory=dict)

    def record(self, text: object, candidate_id: int, times: int = 1) -> None:
        key = (normalize_text(text), candidate_id)
        if not key[0]:
            return
        self._counts[key] = self._counts.get(key, 0) + times

    def record_many(self, pairs: list[tuple[object, int]]) -> None:
        for text, cid in pairs:
            self.record(text, cid)

    def approvals(self, text: object, candidate_id: int) -> int:
        return self._counts.get((normalize_text(text), candidate_id), 0)

    def boost_for(self, text: object, candidate_id: int) -> float:
        """Extra confidence (0..MAX_BOOST) for this learned mapping."""
        n = self.approvals(text, candidate_id)
        return min(MAX_BOOST, n * PER_APPROVAL_BOOST)


def boosted_rank(
    query_text: str,
    candidates: list[Candidate],
    memory: MatchMemory,
    *,
    query_code: object = None,
    limit: int = 5,
) -> list[Suggestion]:
    """Like ``matching.rank`` but adds the learned boost, then re-buckets.

    A mapping the team has approved many times can therefore cross from
    REVIEW into AUTO. The ambiguity rail still applies: the top candidate
    only becomes AUTO if it leads the runner-up by ``AMBIGUITY_MARGIN``.
    """
    base = rank(
        query_text,
        candidates,
        query_code=query_code,
        limit=len(candidates) or 1,
    )
    rescored: list[tuple[float, Suggestion]] = []
    for s in base:
        new_score = min(100.0, s.score + memory.boost_for(query_text, s.candidate_id))
        rescored.append((new_score, s))

    rescored.sort(key=lambda t: (-t[0], t[1].candidate_id))
    best = rescored[0][0] if rescored else 0.0
    second = rescored[1][0] if len(rescored) > 1 else 0.0
    unambiguous = (best - second) >= AMBIGUITY_MARGIN

    out: list[Suggestion] = []
    for idx, (score, s) in enumerate(rescored[:limit]):
        decision = classify(score, is_unambiguous=(idx == 0 and unambiguous))
        out.append(
            Suggestion(
                candidate_id=s.candidate_id,
                score=round(score, 2),
                decision=decision,
                reason=s.reason,
            )
        )
    return out


async def build_memory_from_approved(db) -> MatchMemory:
    """Production wiring: build the memory from approved suggestions.

    Joins each APPROVED ``MatchSuggestion`` back to its ledger row to learn
    the (text -> candidate) mapping the reviewer confirmed: the row
    description for budget-code matches, the company name for subcontractor
    matches.
    """
    from sqlalchemy import select

    from app.models.ledger_entry import LedgerEntry
    from app.models.match_suggestion import (
        MatchSuggestion,
        SuggestionField,
        SuggestionStatus,
    )

    rows = (
        await db.execute(
            select(MatchSuggestion, LedgerEntry)
            .join(LedgerEntry, LedgerEntry.id == MatchSuggestion.ledger_entry_id)
            .where(MatchSuggestion.status == SuggestionStatus.APPROVED)
        )
    ).all()

    memory = MatchMemory()
    for sugg, entry in rows:
        text = (
            entry.description
            if sugg.field == SuggestionField.BUDGET_CODE
            else entry.company_name
        )
        memory.record(text or "", sugg.candidate_id)
    return memory
