"""Market price help-box service (Seviye 1).

Looks up an approximate market price band for each tender line item
purely from Claude's training knowledge — no live web search yet
(that's planned for Seviye 2). The output is a side-panel hint that
the user can compare against incoming bid prices in the comparison
grid.

Workflow:

    1. Pull the tender + its line items (descriptions, units, currency).
    2. Ask Claude for a (min, typical, max) band per line and a one-line
       note (sezon etkisi, marka farkı, vb.). The prompt explicitly
       tells the model "you're working from training data only — if you
       don't know a material, say UNKNOWN."
    3. Cache the response so the comparison grid doesn't burn tokens
       every time the user opens the page.

Falls back to a rule-based "UNKNOWN" response when:

    * ANTHROPIC_API_KEY is missing.
    * The model errors / returns malformed JSON.
    * The tender has no line items.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.tender import Tender, TenderLineItem
from app.schemas.tender import MarketPriceEstimate, TenderMarketPrices


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def build_tender_market_prices(
    db: AsyncSession,
    tender_id: int,
    *,
    lang: str = "EN",
) -> TenderMarketPrices | None:
    tender = (
        await db.execute(
            select(Tender)
            .where(Tender.id == tender_id)
            .options(selectinload(Tender.line_items))
        )
    ).scalar_one_or_none()
    if tender is None:
        return None

    items_payload = [
        {
            "id": li.id,
            "description": li.description,
            "unit": li.unit,
            "quantity": float(li.quantity or 0),
        }
        for li in tender.line_items
    ]
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()

    disclaimer = _disclaimer(lang)
    if not items_payload or not api_key:
        # Empty payload still gets returned so the help-box renders an
        # informative "no estimate available" panel instead of an error.
        return TenderMarketPrices(
            tender_id=tender.id,
            generated_at=datetime.now(timezone.utc),
            currency=tender.currency,
            items=[
                MarketPriceEstimate(
                    tender_line_item_id=li.id,
                    description=li.description,
                    unit=li.unit,
                    currency=tender.currency,
                    confidence="LOW",
                    source="rule",
                    note=None,
                )
                for li in tender.line_items
            ],
            disclaimer=disclaimer,
        )

    try:
        parsed = _llm_market_prices(
            items_payload, currency=tender.currency, api_key=api_key, lang=lang
        )
    except Exception:  # noqa: BLE001 — fall through
        parsed = None

    items_out: list[MarketPriceEstimate] = []
    by_id = {int(p.get("id", -1)): p for p in (parsed or [])}
    for li in tender.line_items:
        row = by_id.get(li.id) or {}
        items_out.append(
            MarketPriceEstimate(
                tender_line_item_id=li.id,
                description=li.description,
                unit=li.unit,
                currency=tender.currency,
                min=_to_decimal(row.get("min")),
                typical=_to_decimal(row.get("typical")),
                max=_to_decimal(row.get("max")),
                confidence=str(row.get("confidence") or "LOW").upper()  # type: ignore[arg-type]
                if str(row.get("confidence") or "LOW").upper()
                in ("LOW", "MEDIUM", "HIGH")
                else "LOW",
                note=row.get("note"),
                source="training" if parsed is not None else "rule",
            )
        )
    return TenderMarketPrices(
        tender_id=tender.id,
        generated_at=datetime.now(timezone.utc),
        currency=tender.currency,
        items=items_out,
        disclaimer=disclaimer,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        d = Decimal(str(v))
    except Exception:  # noqa: BLE001
        return None
    if d <= 0:
        return None
    return d.quantize(Decimal("0.01"))


def _disclaimer(lang: str) -> str:
    if lang.upper() == "TR":
        return (
            "Bu fiyat aralığı Claude'un eğitim verisinden tahmini bir "
            "piyasa bandıdır. Canlı tedarikçi fiyatlarını yansıtmaz; "
            "kesin teklif almadan karar vermeyin."
        )
    return (
        "These figures are a rough market band estimated from training "
        "data — they are NOT live supplier quotes. Always confirm with "
        "a real offer before deciding."
    )


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _llm_market_prices(
    items: list[dict[str, Any]],
    *,
    currency: str,
    api_key: str,
    lang: str,
) -> list[dict[str, Any]] | None:
    import anthropic  # type: ignore

    client = anthropic.Anthropic(
        api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS
    )
    lang_name = "Turkish" if lang.upper() == "TR" else "English"
    prompt = _build_prompt(items, currency=currency, lang_name=lang_name)
    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text if msg.content else "[]"
    block = _extract_json_block(raw)
    parsed = json.loads(block)
    if isinstance(parsed, dict) and "items" in parsed:
        parsed = parsed["items"]
    if not isinstance(parsed, list):
        return None
    return parsed


def _build_prompt(
    items: list[dict[str, Any]], *, currency: str, lang_name: str
) -> str:
    return (
        "You are a construction-cost estimator for the Russian/CIS "
        "market. For each tender line item below, give a rough market "
        "price band (per unit, in "
        f"{currency}) based ONLY on what you already know from training "
        "data — DO NOT pretend to know live supplier prices. If you have "
        "no reliable knowledge of a material, set min/typical/max to "
        "null and use confidence \"LOW\".\n\n"
        f"Write the `note` field in {lang_name}; keep material brand "
        "names in their original script. Each note should be ONE short "
        "sentence: what drives the price (brand, season, shipping zone, "
        "thickness, etc.) — NOT a paragraph.\n\n"
        "Line items:\n"
        f"```json\n{json.dumps(items, ensure_ascii=False, indent=2)}\n```\n\n"
        "Return ONLY a JSON array (no prose around it) with this exact "
        "shape, one element per line item:\n"
        "[\n"
        "  {\n"
        '    "id": <int>,                       // tender_line_item id from input\n'
        '    "min": <number|null>,              // low end of market band, per unit\n'
        '    "typical": <number|null>,          // typical market price, per unit\n'
        '    "max": <number|null>,              // high end of market band, per unit\n'
        '    "confidence": "LOW"|"MEDIUM"|"HIGH",\n'
        '    "note": "<one-line driver>"\n'
        "  }\n"
        "]\n"
    )


def _extract_json_block(text: str) -> str:
    """Strip ```json fences / leading commentary and return the JSON body."""
    text = text.strip()
    # ```json ... ```
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    # Bare JSON: find the first '[' or '{' and the matching last bracket.
    start = min(
        (i for i in (text.find("["), text.find("{")) if i != -1),
        default=-1,
    )
    if start == -1:
        return text
    end = max(text.rfind("]"), text.rfind("}"))
    if end == -1 or end < start:
        return text
    return text[start : end + 1]
