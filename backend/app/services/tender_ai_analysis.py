"""AI bid analysis: compare all bids on a tender and recommend one.

Mirrors the product-owner prompt template (6-section output for the
tender comparison page). Falls back to a rule-based recommendation
when Claude is unavailable so the page never empties.
"""
from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.tender import Bid, BidStatus, Tender
from app.schemas.tender import (
    AnalysisSection,
    BidSummary,
    ComparisonRow,
    RecommendationSection,
    RiskItem,
    TenderAIAnalysis,
    TenderOverviewSection,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def build_tender_ai_analysis(
    db: AsyncSession,
    tender_id: int,
    *,
    lang: str = "EN",
) -> TenderAIAnalysis | None:
    tender = (
        await db.execute(
            select(Tender)
            .where(Tender.id == tender_id)
            .options(
                selectinload(Tender.line_items),
                selectinload(Tender.bids).selectinload(Bid.line_items),
            )
        )
    ).scalar_one_or_none()
    if tender is None:
        return None

    facts = _collect_facts(tender)
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()

    if api_key and facts["bids"]:
        try:
            parsed = _llm_analysis(facts, api_key, lang=lang)
            if parsed is not None:
                return _assemble(tender, lang, parsed, "llm", facts)
        except Exception:  # noqa: BLE001 - fall through to rule engine
            pass

    parsed = _rule_analysis(facts)
    return _assemble(tender, lang, parsed, "rule", facts)


# ---------------------------------------------------------------------------
# Facts collection
# ---------------------------------------------------------------------------


def _collect_facts(tender: Tender) -> dict[str, Any]:
    bids_payload: list[dict[str, Any]] = []
    receivable = [
        b for b in tender.bids
        if b.status in (BidStatus.RECEIVED, BidStatus.SELECTED)
        and Decimal(b.total_amount or 0) > 0
    ]
    for b in receivable:
        bids_payload.append({
            "company": b.company_name,
            "total_amount": float(b.total_amount or 0),
            "total_labor": float(b.total_labor or 0),
            "total_material": float(b.total_material or 0),
            "delivery_days": b.delivery_days,
            "payment_terms": b.payment_terms or "",
            "included": b.included_in_price or "",
            "not_included": b.not_included_in_price or "",
            "notes": b.notes or "",
            "lines": [
                {
                    "order_num": next(
                        (
                            li.order_num
                            for li in tender.line_items
                            if li.id == bl.tender_line_item_id
                        ),
                        0,
                    ),
                    "unit_price_total": float(bl.unit_price_total or 0),
                    "unit_price_labor": float(bl.unit_price_labor)
                        if bl.unit_price_labor is not None else None,
                    "unit_price_material": float(bl.unit_price_material)
                        if bl.unit_price_material is not None else None,
                    "line_total": float(bl.line_total or 0),
                }
                for bl in b.line_items
            ],
        })

    return {
        "title": tender.title,
        "currency": tender.currency,
        "object_name": tender.object_name or "",
        "line_items": [
            {
                "order_num": li.order_num,
                "description": li.description,
                "unit": li.unit or "",
                "quantity": float(li.quantity or 0),
            }
            for li in tender.line_items
        ],
        "bids": bids_payload,
    }


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------


def _rule_analysis(facts: dict[str, Any]) -> dict[str, Any]:
    bids = facts["bids"]
    if not bids:
        return {
            "overview": {
                "title": facts["title"],
                "bid_count": 0,
                "average_total": 0,
                "lowest": None,
                "highest": None,
                "bid_spread_pct": 0.0,
                "bid_spread_level": "NORMAL",
            },
            "comparison": [],
            "analysis": {
                "best_price_company": None,
                "fastest_company": None,
                "most_balanced_company": None,
                "comments": "No bids received yet.",
            },
            "risks": [],
            "recommendation": {
                "chosen_company": None,
                "reason": "",
                "alternative_company": None,
                "confidence_pct": 0.0,
            },
            "executive_summary": "No bids have been submitted on this tender yet.",
        }

    totals = [b["total_amount"] for b in bids]
    avg = statistics.fmean(totals)
    by_price = sorted(bids, key=lambda b: b["total_amount"])
    lowest = by_price[0]
    highest = by_price[-1]
    spread_pct = (
        ((highest["total_amount"] - lowest["total_amount"]) / lowest["total_amount"] * 100)
        if lowest["total_amount"] > 0 else 0.0
    )
    if spread_pct >= 50:
        spread_level = "ABNORMAL"
    elif spread_pct >= 20:
        spread_level = "WIDE"
    else:
        spread_level = "NORMAL"

    bids_with_days = [b for b in bids if b.get("delivery_days") is not None]
    fastest = (
        min(bids_with_days, key=lambda b: b["delivery_days"])
        if bids_with_days else None
    )

    # "Balanced" = bid closest to (price avg + days avg) z-score sum
    if bids_with_days and len(bids_with_days) >= 2:
        price_mean = statistics.fmean(totals)
        days = [b["delivery_days"] for b in bids_with_days]
        days_mean = statistics.fmean(days)
        days_std = statistics.pstdev(days) or 1.0
        price_std = statistics.pstdev(totals) or 1.0
        def _score(b):
            return abs((b["total_amount"] - price_mean) / price_std) + \
                   abs((b["delivery_days"] - days_mean) / days_std)
        balanced = min(bids_with_days, key=_score)
    else:
        balanced = lowest

    risks: list[dict[str, str]] = []
    # 30% below average → too cheap
    for b in bids:
        if b["total_amount"] <= avg * 0.7 and b["total_amount"] > 0:
            risks.append({
                "company": b["company"],
                "risk": "Aşırı düşük teklif (kalite riski)",
                "cause": f"Ortalamanın %{int((1 - b['total_amount']/avg)*100)} altında",
            })
        if b["total_amount"] >= avg * 1.3:
            risks.append({
                "company": b["company"],
                "risk": "Yüksek maliyet riski",
                "cause": f"Ortalamanın %{int((b['total_amount']/avg - 1)*100)} üstünde",
            })
        if b.get("delivery_days") and b["delivery_days"] > 90:
            risks.append({
                "company": b["company"],
                "risk": "Uzun termin riski",
                "cause": f"{b['delivery_days']} gün — takvim baskısı yaratır",
            })

    chosen = balanced or lowest
    alt = (
        next((b for b in by_price if b["company"] != chosen["company"]), None)
    )
    if chosen["total_amount"] <= avg * 1.05:
        confidence = 75.0
    else:
        confidence = 55.0
    if spread_level == "ABNORMAL":
        confidence -= 15.0

    summary = (
        f"{len(bids)} bid(s) received with average {avg:,.0f} {facts['currency']}. "
        f"Lowest: {lowest['company']} ({lowest['total_amount']:,.0f}). "
        f"Recommended: {chosen['company']} based on balance of price and delivery."
    )

    return {
        "overview": {
            "title": facts["title"],
            "bid_count": len(bids),
            "average_total": avg,
            "lowest": {
                "company": lowest["company"],
                "total_amount": lowest["total_amount"],
                "delivery_days": lowest.get("delivery_days"),
                "is_lowest": True,
                "is_highest": False,
            },
            "highest": {
                "company": highest["company"],
                "total_amount": highest["total_amount"],
                "delivery_days": highest.get("delivery_days"),
                "is_lowest": False,
                "is_highest": True,
            },
            "bid_spread_pct": round(spread_pct, 2),
            "bid_spread_level": spread_level,
        },
        "comparison": [
            {
                "company": b["company"],
                "total_amount": b["total_amount"],
                "delivery_days": b.get("delivery_days"),
                "notes": b.get("notes") or None,
            }
            for b in by_price
        ],
        "analysis": {
            "best_price_company": lowest["company"],
            "fastest_company": fastest["company"] if fastest else None,
            "most_balanced_company": balanced["company"] if balanced else None,
            "comments": "",
        },
        "risks": risks[:5],
        "recommendation": {
            "chosen_company": chosen["company"],
            "reason": (
                f"Best price/delivery balance "
                f"({chosen['total_amount']:,.0f} {facts['currency']}"
                + (
                    f", {chosen['delivery_days']} days"
                    if chosen.get("delivery_days") else ""
                )
                + ")."
            ),
            "alternative_company": alt["company"] if alt else None,
            "confidence_pct": max(0.0, min(100.0, confidence)),
        },
        "executive_summary": summary,
    }


# ---------------------------------------------------------------------------
# LLM analysis
# ---------------------------------------------------------------------------


def _llm_analysis(
    facts: dict[str, Any],
    api_key: str,
    *,
    lang: str = "EN",
) -> dict[str, Any] | None:
    import anthropic  # type: ignore

    client = anthropic.Anthropic(
        api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS
    )
    lang_name = "Turkish" if lang.upper() == "TR" else "English"
    prompt = _build_prompt(facts, lang_name)
    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text if msg.content else "{}"
    parsed = json.loads(_extract_json_block(raw))

    required = {"overview", "comparison", "analysis", "risks", "recommendation", "executive_summary"}
    if not required.issubset(parsed.keys()):
        return None
    return parsed


def _build_prompt(facts: dict[str, Any], lang_name: str) -> str:
    return (
        "You are a tender / bid evaluation expert for large-scale "
        "construction projects. Compare every company's bid on this "
        "work package and recommend the best one — balancing price, "
        "delivery time, and risk. Back your reasoning with the supplied "
        f"numbers. Write all narrative text in {lang_name}; keep "
        "company names in their original script.\n\n"
        "Tender facts:\n"
        f"```json\n{json.dumps(facts, ensure_ascii=False, indent=2, default=str)}\n```\n\n"
        "Return ONLY a JSON object with this exact shape (no prose around it):\n"
        "{\n"
        '  "overview": {\n'
        '    "title": "<copy of facts.title>",\n'
        '    "bid_count": <int>,\n'
        '    "average_total": <float>,\n'
        '    "lowest":  { "company":"...", "total_amount":<float>, "delivery_days":<int|null>, "is_lowest": true, "is_highest": false },\n'
        '    "highest": { "company":"...", "total_amount":<float>, "delivery_days":<int|null>, "is_lowest": false, "is_highest": true },\n'
        '    "bid_spread_pct": <float>,\n'
        '    "bid_spread_level": "NORMAL" | "WIDE" | "ABNORMAL"\n'
        '  },\n'
        '  "comparison": [\n'
        '    { "company": "...", "total_amount": <float>, "delivery_days": <int|null>, "notes": "<short>" }\n'
        '  ],\n'
        '  "analysis": {\n'
        '    "best_price_company": "...",\n'
        '    "fastest_company": "...",\n'
        '    "most_balanced_company": "...",\n'
        '    "comments": "1-2 sentence qualitative summary"\n'
        '  },\n'
        '  "risks": [\n'
        '    { "company": "...", "risk": "short label", "cause": "what flagged it" }\n'
        '  ],\n'
        '  "recommendation": {\n'
        '    "chosen_company": "...",\n'
        '    "reason": "1-2 sentence why",\n'
        '    "alternative_company": "...",\n'
        '    "confidence_pct": <0..100>\n'
        '  },\n'
        '  "executive_summary": "max 3 sentence top-line for the decision maker"\n'
        "}\n"
        "Bid-spread rule of thumb: <20% spread = NORMAL, 20-50% = WIDE, "
        ">50% = ABNORMAL (flag in risks).\n"
        "Risks to watch: abnormally low bid → quality risk; abnormally high → cost risk; "
        ">90 day delivery → schedule risk."
    )


def _extract_json_block(raw: str) -> str:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL)
    if fence:
        raw = fence.group(1)
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        return raw[first : last + 1]
    return raw or "{}"


# ---------------------------------------------------------------------------
# Final assembly
# ---------------------------------------------------------------------------


def _assemble(
    tender: Tender,
    lang: str,
    parsed: dict[str, Any],
    source: str,
    facts: dict[str, Any],
) -> TenderAIAnalysis:
    ov = parsed.get("overview") or {}
    lowest = _shape_bid_summary(ov.get("lowest"))
    highest = _shape_bid_summary(ov.get("highest"))

    overview = TenderOverviewSection(
        title=str(ov.get("title") or facts["title"]),
        bid_count=int(ov.get("bid_count") or 0),
        average_total=_to_decimal(ov.get("average_total")),
        lowest=lowest,
        highest=highest,
        bid_spread_pct=float(ov.get("bid_spread_pct") or 0.0),
        bid_spread_level=str(ov.get("bid_spread_level") or "NORMAL"),  # type: ignore[arg-type]
    )

    comparison = [
        ComparisonRow(
            company=str(c.get("company") or "Unknown"),
            total_amount=_to_decimal(c.get("total_amount")),
            delivery_days=_to_int_opt(c.get("delivery_days")),
            notes=str(c.get("notes") or "") or None,
        )
        for c in (parsed.get("comparison") or [])
    ]

    an = parsed.get("analysis") or {}
    analysis = AnalysisSection(
        best_price_company=_str_or_none(an.get("best_price_company")),
        fastest_company=_str_or_none(an.get("fastest_company")),
        most_balanced_company=_str_or_none(an.get("most_balanced_company")),
        comments=_str_or_none(an.get("comments")),
    )

    risks = [
        RiskItem(
            company=str(r.get("company") or "—"),
            risk=str(r.get("risk") or ""),
            cause=str(r.get("cause") or ""),
        )
        for r in (parsed.get("risks") or [])
        if r.get("risk")
    ]

    rec = parsed.get("recommendation") or {}
    recommendation = RecommendationSection(
        chosen_company=_str_or_none(rec.get("chosen_company")),
        reason=str(rec.get("reason") or ""),
        alternative_company=_str_or_none(rec.get("alternative_company")),
        confidence_pct=max(0.0, min(100.0, float(rec.get("confidence_pct") or 0.0))),
    )

    return TenderAIAnalysis(
        tender_id=tender.id,
        generated_at=datetime.now(timezone.utc),
        lang="TR" if lang.upper() == "TR" else "EN",
        source=source,  # type: ignore[arg-type]
        overview=overview,
        comparison=comparison,
        analysis=analysis,
        risks=risks,
        recommendation=recommendation,
        executive_summary=str(parsed.get("executive_summary") or "").strip(),
    )


def _shape_bid_summary(d: dict[str, Any] | None) -> BidSummary | None:
    if not d or not d.get("company"):
        return None
    return BidSummary(
        company=str(d.get("company")),
        total_amount=_to_decimal(d.get("total_amount")),
        delivery_days=_to_int_opt(d.get("delivery_days")),
        is_lowest=bool(d.get("is_lowest")),
        is_highest=bool(d.get("is_highest")),
    )


def _to_decimal(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal(0)
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(0)


def _to_int_opt(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None
