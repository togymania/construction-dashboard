"""Fuzzy-match company names from imported ledger rows against existing
Subcontractor records.

Strategy:
  1. Group parsed rows by `company_name` so each unique company is reviewed
     once (regardless of occurrence count).
  2. For each unique company, score it against every active Subcontractor.name
     using rapidfuzz token_set_ratio (handles word reordering, abbreviations).
  3. Keep the best candidate if its score >= MIN_PROPOSAL_SCORE; otherwise
     return the company as unmatched.

The user reviews proposals in the import wizard and accepts/rejects each.
A separate "create new subcontractor" flow is out of scope for v1.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subcontractor import Subcontractor, SubcontractorStatus


# Below this score we don't propose a match; the company is shown as unmatched.
MIN_PROPOSAL_SCORE = 75

# Above this score we mark proposals as "high confidence" in the UI.
HIGH_CONFIDENCE_SCORE = 90

# Legal-entity suffixes that don't carry matching signal (RU/TR/EN).
# They're stripped before scoring so "ABC ООО" doesn't collide with "DEF ООО".
_LEGAL_ENTITY_TOKENS = {
    # Russian
    "ооо", "оао", "ао", "пао", "зао", "ип", "тоо",
    # Turkish
    "a.s.", "as", "aş", "as.", "ltd", "ltd.", "şti", "sti", "san.", "tic.",
    # English
    "llc", "inc.", "inc", "co.", "co", "corp", "corp.", "limited",
    # Generic
    "&", "and", "ve",
}


@dataclass(frozen=True)
class CandidateSub:
    """Lightweight subcontractor reference used for scoring."""

    id: int
    name: str


@dataclass
class MatchProposal:
    """One unique company name and the best matching subcontractor (if any)."""

    company_name: str
    occurrences: int           # how many ledger rows used this company name
    candidate_id: int | None   # None if no match >= MIN_PROPOSAL_SCORE
    candidate_name: str | None
    score: float               # 0–100 (rapidfuzz scale); 0 if no candidate
    high_confidence: bool      # True if score >= HIGH_CONFIDENCE_SCORE


def _normalize(s: str) -> str:
    """Casefold + drop legal-entity tokens + collapse whitespace.

    Legal-entity suffixes (ООО, A.S., LLC, etc.) carry no matching signal
    and would otherwise collide every Russian company name with every
    other (since they all end in ООО). We strip them before scoring.

    Cyrillic / Latin characters are preserved as-is — rapidfuzz handles
    Unicode. Aggressive transliteration is deliberately avoided.
    """
    tokens = s.casefold().split()
    kept = [t for t in tokens if t not in _LEGAL_ENTITY_TOKENS]
    return " ".join(kept) if kept else " ".join(tokens)


async def load_active_subcontractors(db: AsyncSession) -> list[CandidateSub]:
    """Fetch all currently active subcontractors as scoring candidates."""
    stmt = select(Subcontractor.id, Subcontractor.name).where(
        Subcontractor.is_active.is_(True),
        Subcontractor.status == SubcontractorStatus.ACTIVE,
    )
    rows = (await db.execute(stmt)).all()
    return [CandidateSub(id=row.id, name=row.name) for row in rows]


def propose_matches(
    company_names: Iterable[str | None],
    candidates: list[CandidateSub],
) -> list[MatchProposal]:
    """Build a deduplicated list of MatchProposals.

    Args:
        company_names: company_name values from parsed ledger rows
            (None / blank values are silently dropped).
        candidates: active subcontractors to score against.

    Returns:
        One MatchProposal per unique non-blank company name, ordered by
        descending occurrence count (so the user sees the most impactful
        matches first).
    """
    # Count occurrences of each unique non-blank company name
    counts: dict[str, int] = {}
    for name in company_names:
        if not name:
            continue
        cleaned = name.strip()
        if not cleaned:
            continue
        counts[cleaned] = counts.get(cleaned, 0) + 1

    # Build scoring index once
    if candidates:
        choices = {c.id: _normalize(c.name) for c in candidates}
        id_lookup = {c.id: c for c in candidates}
    else:
        choices = {}
        id_lookup = {}

    proposals: list[MatchProposal] = []
    for company, occ in counts.items():
        norm_company = _normalize(company)

        if not choices:
            proposals.append(
                MatchProposal(
                    company_name=company,
                    occurrences=occ,
                    candidate_id=None,
                    candidate_name=None,
                    score=0.0,
                    high_confidence=False,
                )
            )
            continue

        match = process.extractOne(
            norm_company,
            choices,
            scorer=fuzz.token_set_ratio,
        )
        # process.extractOne returns (matched_value, score, key) or None
        if match is None:
            proposals.append(
                MatchProposal(
                    company_name=company,
                    occurrences=occ,
                    candidate_id=None,
                    candidate_name=None,
                    score=0.0,
                    high_confidence=False,
                )
            )
            continue

        _, score, sub_id = match
        if score < MIN_PROPOSAL_SCORE:
            proposals.append(
                MatchProposal(
                    company_name=company,
                    occurrences=occ,
                    candidate_id=None,
                    candidate_name=None,
                    score=float(score),
                    high_confidence=False,
                )
            )
            continue

        cand = id_lookup[sub_id]
        proposals.append(
            MatchProposal(
                company_name=company,
                occurrences=occ,
                candidate_id=cand.id,
                candidate_name=cand.name,
                score=float(score),
                high_confidence=score >= HIGH_CONFIDENCE_SCORE,
            )
        )

    # Sort: matched proposals first (so user reviews real candidates),
    # then by occurrence count desc (most impactful first).
    proposals.sort(key=lambda p: (p.candidate_id is None, -p.occurrences))
    return proposals
