"""LLM layer for AI budget-code suggestion (Claude + web_search tool).

``suggest_with_ai`` sends one ledger row, the candidate budget items and
the prior evidence to Claude, lets it research the company online via the
Anthropic ``web_search`` server tool, and returns a parsed
``BudgetSuggestion``. Any failure (no key, timeout, bad JSON) falls back
to the deterministic ``rule_based_suggestion`` so the feature never hard
-fails.
"""
from __future__ import annotations

import json
import re

from app.core.config import settings
from app.services.ai_budget_suggester import (
    BudgetSuggestion,
    Candidate,
    LedgerRow,
    PriorEvidence,
    parse_ai_suggestion,
    rule_based_suggestion,
)

_SYSTEM_EN = (
    "You are a construction-finance controller assigning a budget code to "
    "a ledger payment. Decide the single best code from the provided "
    "candidates. The team's prior decisions for the SAME company are the "
    "strongest signal; use the web_search tool to research the company's "
    "line of business when that helps. Never invent a code outside the "
    "candidate list. Be conservative: if nothing fits, return null and a "
    "low confidence. Reply with ONLY a JSON object."
)
_SYSTEM_TR = (
    "Sen bir inşaat-finans kontrolörüsün ve bir defter ödemesine bütçe "
    "kodu atıyorsun. Verilen adaylar arasından en uygun TEK kodu seç. "
    "AYNI firma için ekibin geçmiş kararları en güçlü sinyaldir; firmanın "
    "iş kolunu anlamak için gerektiğinde web_search aracıyla araştır. Aday "
    "listesi dışında kod UYDURMA. Temkinli ol: hiçbiri uymuyorsa null ve "
    "düşük güven döndür. SADECE bir JSON nesnesi yanıtla."
)


def _build_prompt(
    row: LedgerRow,
    candidates: list[Candidate],
    priors: list[PriorEvidence],
    *,
    lang: str = "EN",
) -> str:
    is_tr = (lang or "EN").upper() == "TR"
    cand_lines = "\n".join(
        f'  - code "{c.code}": {c.text}' for c in candidates if c.code
    ) or "  (none)"
    if priors:
        prior_lines = "\n".join(
            f'  - code "{p.budget_code}" — {p.support}x via {p.via} (e.g. {p.example})'
            for p in priors
        )
    else:
        prior_lines = "  (no prior evidence)"

    header = "Ödeme:" if is_tr else "Payment:"
    cands_h = "Aday bütçe kodları:" if is_tr else "Candidate budget codes:"
    prior_h = "Geçmiş kanıt (ekibin önceki atamaları):" if is_tr else \
        "Prior evidence (the team's past assignments):"
    ask = (
        'Şu JSON ile yanıtla: {"budget_code": "<aday kod ya da null>", '
        '"confidence": <0-100>, "rationale": "<1-2 cümle, web bulgusunu da '
        'belirt>"}'
        if is_tr else
        'Reply with: {"budget_code": "<candidate code or null>", '
        '"confidence": <0-100>, "rationale": "<1-2 sentences, mention any web '
        'finding>"}'
    )

    return (
        f"{header}\n"
        f"  description: {row.description}\n"
        f"  company: {row.company_name}\n"
        f"  amount: {row.amount}\n"
        f"  kod: {row.kod}\n\n"
        f"{cands_h}\n{cand_lines}\n\n"
        f"{prior_h}\n{prior_lines}\n\n"
        f"{ask}"
    )


def _extract_json(raw: str) -> str:
    raw = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL)
    if fence:
        raw = fence.group(1)
    first, last = raw.find("{"), raw.rfind("}")
    if first >= 0 and last > first:
        return raw[first : last + 1]
    return "{}"


def suggest_with_ai(
    row: LedgerRow,
    candidates: list[Candidate],
    priors: list[PriorEvidence],
    api_key: str,
    *,
    lang: str = "EN",
    use_web: bool = True,
    max_web_uses: int = 3,
) -> BudgetSuggestion:
    """Ask Claude (with web research) for the best budget code. Falls back
    to the deterministic rule on any failure."""
    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(
            api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS
        )
        kwargs: dict = {
            "model": settings.ANTHROPIC_MODEL,
            "max_tokens": 900,
            "system": _SYSTEM_TR if (lang or "EN").upper() == "TR" else _SYSTEM_EN,
            "messages": [
                {"role": "user", "content": _build_prompt(row, candidates, priors, lang=lang)}
            ],
        }
        if use_web:
            kwargs["tools"] = [
                {"type": "web_search_20250305", "name": "web_search", "max_uses": max_web_uses}
            ]

        msg = client.messages.create(**kwargs)
        text = "".join(
            getattr(b, "text", "") for b in msg.content
            if getattr(b, "type", None) == "text"
        )
        data = json.loads(_extract_json(text))
        suggestion = parse_ai_suggestion(data, row, candidates)
        # Tag whether web research was actually used.
        if not use_web:
            suggestion = BudgetSuggestion(
                suggestion.entry_id, suggestion.proposed_code,
                suggestion.candidate_id, suggestion.candidate_label,
                suggestion.confidence, suggestion.rationale, "ai_rule",
            )
        return suggestion
    except Exception:
        return rule_based_suggestion(row, candidates, priors)
