"""AI-assisted budget-code suggestion (Harcamalar → "AI ile bütçe kodu öner").

For user-selected ledger rows, propose a ``budget_code`` for each by
combining three signals, then route every proposal to the human review
queue (``MatchSuggestion``) — nothing is written to the ledger without
approval:

1. **Budget-item match** — the row description scored against the
   project's budget items (cost_code + description) via the matching
   pipeline.
2. **Prior evidence** — other ledger rows from the SAME company (or a very
   similar description) that ALREADY carry a budget code. The team's past
   decisions are the strongest signal.
3. **AI + web research** — Claude reads the row, the candidates and the
   prior evidence, researches the company online (web_search tool) and
   picks the best code with a rationale. Falls back to the deterministic
   rule below when no API key is set.

This module holds the PURE, testable pieces. The live LLM call lives in
``suggest_with_ai`` (``ai_budget_llm.py``).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz import fuzz

from app.services.cost_code import normalize_cost_code
from app.services.matching import Candidate, Decision, normalize_text, rank

# A coded row's description must reach this similarity to count as prior
# evidence (company match is exact-normalised, so it doesn't need this).
SIMILAR_DESC_THRESHOLD = 88.0


@dataclass(frozen=True)
class LedgerRow:
    id: int
    description: str = ""
    company_name: str = ""
    amount: float = 0.0
    kod: str = ""


@dataclass(frozen=True)
class CodedRow:
    """A ledger row that already has a budget code (the prior corpus)."""

    description: str
    company_name: str
    budget_code: str


@dataclass(frozen=True)
class PriorEvidence:
    budget_code: str
    support: int          # how many prior rows back this code
    via: str              # "same_company" | "similar_description"
    example: str          # a sample company/description for display


@dataclass(frozen=True)
class BudgetSuggestion:
    entry_id: int
    proposed_code: str | None
    candidate_id: int | None      # the budget item id, when matched
    candidate_label: str | None
    confidence: float             # 0-100
    rationale: str
    source: str                   # "ai_web" | "ai_rule" | "rule"


def find_prior_evidence(
    row: LedgerRow, coded_rows: list[CodedRow], *, limit: int = 5
) -> list[PriorEvidence]:
    """Find budget codes the team already used for the same company or a
    very similar description. Same-company evidence ranks first."""
    norm_company = normalize_text(row.company_name)
    norm_desc = normalize_text(row.description)
    agg: dict[str, dict] = {}

    for c in coded_rows:
        code = normalize_cost_code(c.budget_code)
        if not code:
            continue
        via: str | None = None
        if norm_company and normalize_text(c.company_name) == norm_company:
            via = "same_company"
        elif (
            norm_desc
            and fuzz.token_set_ratio(norm_desc, normalize_text(c.description))
            >= SIMILAR_DESC_THRESHOLD
        ):
            via = "similar_description"
        if via is None:
            continue
        slot = agg.setdefault(
            code, {"support": 0, "via": via, "example": c.company_name or c.description}
        )
        slot["support"] += 1
        if via == "same_company":
            slot["via"] = "same_company"

    out = [
        PriorEvidence(code, d["support"], d["via"], d["example"])
        for code, d in agg.items()
    ]
    # same_company first, then by support desc, then code for stability.
    out.sort(key=lambda e: (e.via != "same_company", -e.support, e.budget_code))
    return out[:limit]


def rule_based_suggestion(
    row: LedgerRow,
    candidates: list[Candidate],
    priors: list[PriorEvidence],
) -> BudgetSuggestion:
    """Deterministic fallback (also used when no API key): combine the
    budget-item text match with the prior evidence."""
    by_id = {c.id: c for c in candidates}
    by_code = {normalize_cost_code(c.code): c for c in candidates if c.code}

    top = rank(row.description, candidates, limit=1) if candidates else []
    best = top[0] if top else None
    prior = priors[0] if priors else None
    prior_cand = by_code.get(prior.budget_code) if prior else None

    # Same company already coded → strongest signal.
    if prior is not None and prior.via == "same_company" and prior_cand is not None:
        conf = min(95.0, 70.0 + prior.support * 5.0)
        return BudgetSuggestion(
            row.id, prior_cand.code, prior_cand.id, prior_cand.text, round(conf, 2),
            f"Aynı firma daha önce {prior.support} kez '{prior_cand.code}' "
            f"koduna atanmış ({prior.example}).",
            "rule",
        )

    # Strong description match against a budget item.
    if best is not None and best.decision is not Decision.REJECT:
        cand = by_id[best.candidate_id]
        conf = best.score
        if prior is not None and normalize_cost_code(cand.code) == prior.budget_code:
            conf = min(98.0, conf + 10.0)  # prior agrees → boost
        return BudgetSuggestion(
            row.id, cand.code, cand.id, cand.text, round(conf, 2),
            f"Açıklama '{cand.text}' bütçe kalemiyle eşleşiyor (skor {best.score}).",
            "rule",
        )

    # Weaker: a similar-description prior.
    if prior_cand is not None:
        return BudgetSuggestion(
            row.id, prior_cand.code, prior_cand.id, prior_cand.text, 60.0,
            f"Benzer kayıtlar '{prior_cand.code}' koduna atanmış.",
            "rule",
        )

    return BudgetSuggestion(
        row.id, None, None, None, 0.0,
        "Yeterli sinyal yok; manuel inceleme gerekli.",
        "rule",
    )


def parse_ai_suggestion(
    data: dict, row: LedgerRow, candidates: list[Candidate]
) -> BudgetSuggestion:
    """Turn Claude's JSON ({budget_code, confidence, rationale}) into a
    suggestion, mapping the code back to a budget item when possible."""
    by_code = {normalize_cost_code(c.code): c for c in candidates if c.code}
    code = normalize_cost_code(data.get("budget_code"))
    try:
        conf = max(0.0, min(100.0, float(data.get("confidence") or 0)))
    except (TypeError, ValueError):
        conf = 0.0
    rationale = str(data.get("rationale") or "").strip()
    cand = by_code.get(code) if code else None

    if cand is None:
        return BudgetSuggestion(
            row.id, code or None, None, None, conf,
            rationale or "AI önerisi (bütçe kalemiyle birebir eşleşmedi).",
            "ai_web",
        )
    return BudgetSuggestion(
        row.id, cand.code, cand.id, cand.text, conf,
        rationale or "AI önerisi.",
        "ai_web",
    )


# ---------------------------------------------------------------------------
# Async orchestrator (DB)
# ---------------------------------------------------------------------------


async def generate_ai_budget_suggestions(
    db,
    project_id: int,
    entry_ids: list[int],
    *,
    lang: str = "EN",
    use_web: bool = True,
):
    """For selected ledger rows, produce budget-code suggestions and write
    them to the review queue (PENDING ``MatchSuggestion`` rows). Returns the
    created suggestions. Nothing is applied to the ledger here — approval is
    a separate step.
    """
    from sqlalchemy import delete, select

    from app.core.config import settings
    from app.models.budget import BudgetItem
    from app.models.ledger_entry import LedgerEntry
    from app.models.match_suggestion import (
        MatchSuggestion,
        SuggestionField,
        SuggestionStatus,
    )
    from app.services.ai_budget_llm import suggest_with_ai

    rows = (
        await db.execute(select(LedgerEntry).where(LedgerEntry.id.in_(entry_ids)))
    ).scalars().all()

    items = (
        await db.execute(
            select(BudgetItem).where(BudgetItem.project_id == project_id)
        )
    ).scalars().all()
    candidates = [
        Candidate(id=b.id, text=b.description or "", code=b.cost_code)
        for b in items
        if b.cost_code
    ]

    # Prior corpus: ledger rows that already carry a budget code (small —
    # most rows are uncoded). Used for same-company / similar-description
    # evidence.
    coded_q = (
        await db.execute(
            select(
                LedgerEntry.description,
                LedgerEntry.company_name,
                LedgerEntry.budget_code,
            ).where(LedgerEntry.budget_code.is_not(None))
        )
    ).all()
    coded = [
        CodedRow(description=d or "", company_name=cn or "", budget_code=bc or "")
        for d, cn, bc in coded_q
    ]

    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    created: list = []

    for e in rows:
        lrow = LedgerRow(
            id=e.id,
            description=e.description or "",
            company_name=e.company_name or "",
            amount=float(e.amount or 0),
            kod=e.kod or "",
        )
        priors = find_prior_evidence(lrow, coded)
        if api_key:
            sug = suggest_with_ai(
                lrow, candidates, priors, api_key, lang=lang, use_web=use_web
            )
        else:
            sug = rule_based_suggestion(lrow, candidates, priors)

        # Replace any existing pending budget-code suggestion for this row.
        await db.execute(
            delete(MatchSuggestion).where(
                MatchSuggestion.ledger_entry_id == e.id,
                MatchSuggestion.field == SuggestionField.BUDGET_CODE,
                MatchSuggestion.status == SuggestionStatus.PENDING,
            )
        )
        if not sug.proposed_code:
            continue

        ms = MatchSuggestion(
            ledger_entry_id=e.id,
            field=SuggestionField.BUDGET_CODE,
            proposed_value=str(sug.proposed_code),
            candidate_id=sug.candidate_id or 0,
            candidate_label=sug.candidate_label,
            score=Decimal(str(round(sug.confidence, 2))),
            reason=sug.source,
            rationale=sug.rationale,
            status=SuggestionStatus.PENDING,
        )
        db.add(ms)
        await db.flush()
        created.append(ms)

    await db.commit()
    return created

