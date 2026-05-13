"""Convert an uploaded tender quotation file into a structured draft.

Supports:
* Excel (.xlsx, .xlsm) -- openpyxl reads the sheet, we flatten cells
  to a compact text grid for Claude.
* PDF (.pdf) -- pdfplumber pulls text per page, we feed Claude the
  raw text.

The output is a ``TenderExtraction`` (defined in
``app.schemas.tender``) which the frontend renders as an editable
draft. Nothing is persisted at this stage -- the user reviews, fixes
any AI mistakes, then submits the cleaned-up payload through
``POST /projects/{id}/tenders``.
"""
from __future__ import annotations

import io
import json
import re
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.models.tender import TenderLineItem
from app.schemas.tender import (
    ExtractedBid,
    ExtractedBidLine,
    ExtractedLineItem,
    TenderExtraction,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_tender_from_file(
    *,
    raw_bytes: bytes,
    filename: str,
    lang: str = "EN",
) -> TenderExtraction:
    """Return the AI-built draft for a tender quotation file.

    On any failure (file unreadable, no API key, parse error) returns
    a near-empty TenderExtraction with the failure recorded in
    ``warnings`` so the frontend can still display *something*.
    """
    warnings: list[str] = []
    text_blob, fallback_title = _file_to_text(raw_bytes, filename, warnings)

    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    if not api_key:
        warnings.append("ANTHROPIC_API_KEY missing -- returning empty draft.")
        return TenderExtraction(
            title=fallback_title,
            source_filename=filename,
            source="rule",
            warnings=warnings,
        )

    try:
        parsed = _llm_extract(text_blob, fallback_title, api_key, lang=lang)
    except Exception as exc:  # noqa: BLE001 - bubble up as warning
        warnings.append(f"LLM extraction failed: {exc!r}")
        return TenderExtraction(
            title=fallback_title,
            source_filename=filename,
            source="rule",
            warnings=warnings,
        )

    parsed.source_filename = filename
    if warnings:
        parsed.warnings = warnings + parsed.warnings
    return parsed


# ---------------------------------------------------------------------------
# File -> text helpers
# ---------------------------------------------------------------------------


def _file_to_text(raw: bytes, filename: str, warnings: list[str]) -> tuple[str, str]:
    """Return (claude_input_text, fallback_title)."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    fallback_title = _strip_ext(filename)

    if ext in {"xlsx", "xlsm"}:
        try:
            text, t = _excel_to_text(raw)
            return text, t or fallback_title
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Excel parse failed: {exc!r}")
            return "", fallback_title

    if ext == "pdf":
        try:
            text = _pdf_to_text(raw)
            return text, fallback_title
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"PDF parse failed: {exc!r}")
            return "", fallback_title

    warnings.append(
        f"Unsupported file extension '.{ext}'. "
        "Upload .xlsx / .xlsm / .pdf for best results."
    )
    # Last-resort: treat as UTF-8 text
    try:
        return raw.decode("utf-8", errors="ignore"), fallback_title
    except Exception:
        return "", fallback_title


def _strip_ext(name: str) -> str:
    return name.rsplit(".", 1)[0] if "." in name else name


def _excel_to_text(raw: bytes) -> tuple[str, str]:
    """Flatten the first sheet's cells into a compact tab-separated grid.

    Empty rows are kept (as blank lines) so Claude can see the layout.
    Cell values are stringified; merged-cell anchors keep their value
    (downstream blanks let the LLM know "this is the same as above").
    """
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    if not wb.sheetnames:
        return "", ""
    ws = wb[wb.sheetnames[0]]

    rows_out: list[str] = []
    title_guess = ""
    max_col = min(ws.max_column or 0, 40)  # hard cap so Claude doesn't drown
    max_row = min(ws.max_row or 0, 400)

    for r in range(1, max_row + 1):
        cells: list[str] = []
        for c in range(1, max_col + 1):
            v = ws.cell(row=r, column=c).value
            if v is None:
                cells.append("")
            else:
                s = str(v).strip().replace("\t", " ").replace("\n", " ")
                # Heuristic title guess: first "Тема" / "Konu" / "Subject" row
                if not title_guess and s.lower() in {"тема", "konu", "subject", "тема:", "konu:"}:
                    nxt = ws.cell(row=r, column=c + 1).value
                    if nxt:
                        title_guess = str(nxt).strip()
                cells.append(s)
        rows_out.append("\t".join(cells))

    return "\n".join(rows_out), title_guess


def _pdf_to_text(raw: bytes) -> str:
    import pdfplumber

    out: list[str] = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            out.append(f"--- Page {i} ---\n{txt}")
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------


def _llm_extract(
    text_blob: str,
    fallback_title: str,
    api_key: str,
    *,
    lang: str = "EN",
) -> TenderExtraction:
    import anthropic  # type: ignore

    client = anthropic.Anthropic(
        api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS
    )
    # Keep the text within Claude's reasonable input range
    snippet = text_blob[:60_000]
    lang_name = "Turkish" if lang.upper() == "TR" else "English"
    prompt = _build_extraction_prompt(snippet, lang_name)

    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text if msg.content else "{}"
    parsed = json.loads(_extract_json_block(raw))

    return _shape_to_extraction(parsed, fallback_title)


def _build_extraction_prompt(text_blob: str, lang_name: str) -> str:
    """Compose the structured-extraction prompt for Claude.

    Pricing rule: per line, return ``unit_price_labor`` and
    ``unit_price_material`` ONLY when the source itself splits them.
    When the source has a single combined unit price, return only
    ``unit_price_total`` and leave the other two NULL. Never invent the
    split.
    """
    return (
        "You are a structured-extraction assistant for a construction "
        "company. Below is the raw text or grid of a tender quotation "
        "file (a 'КП Форма' / 'Teklif Değerlendirme Formu'). "
        "Extract the work package and every company's quotation into the "
        "JSON shape below.\n\n"
        f"Write any descriptive / narrative text in {lang_name}. Keep "
        "company names, proper nouns and units in the original script "
        "(e.g. 'ООО Стройка', 'm²').\n\n"
        "Pricing rules — IMPORTANT:\n"
        "  - When the source breaks a line item's unit price into "
        "labor (işçilik / трудозатраты / рабочие) AND material "
        "(malzeme / материал), return BOTH unit_price_labor and "
        "unit_price_material; unit_price_total = labor + material.\n"
        "  - When the source gives only a single combined unit price, "
        "return ONLY unit_price_total and leave unit_price_labor / "
        "unit_price_material as null. NEVER guess the split.\n"
        "  - When a company didn't quote a line, omit that ExtractedBidLine "
        "entry entirely (don't fill zeros).\n\n"
        "File content:\n"
        "```\n"
        f"{text_blob}\n"
        "```\n\n"
        "Return ONLY this JSON object, no prose around it:\n"
        "{\n"
        '  "title": "the work package title (e.g. \\"Karot işleri\\")",\n'
        '  "object_name": "project / building name if mentioned",\n'
        '  "currency": "RUB | EUR | USD | TRY",\n'
        '  "payment_terms_expected": "if specified",\n'
        '  "delivery_terms_expected": "if specified",\n'
        '  "notes": "any other useful header notes",\n'
        '  "line_items": [\n'
        '    { "order_num": 1, "description": "...", "unit": "m²", "quantity": 12.5 }\n'
        "  ],\n"
        '  "bids": [\n'
        "    {\n"
        '      "company_name": "...",\n'
        '      "contact_name": "...",\n'
        '      "contact_phone": "...",\n'
        '      "contact_email": "...",\n'
        '      "included_in_price": "what the bidder said is included",\n'
        '      "not_included_in_price": "...",\n'
        '      "payment_terms": "...",\n'
        '      "delivery_days": 30,\n'
        '      "notes": "...",\n'
        '      "lines": [\n'
        '        { "order_num": 1, "unit_price_labor": 200, "unit_price_material": 800, "unit_price_total": 1000 }\n'
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "warnings": ["any ambiguity you want the user to verify"]\n'
        "}\n"
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


def _shape_to_extraction(parsed: dict[str, Any], fallback_title: str) -> TenderExtraction:
    """Validate Claude's dict into our Pydantic shape with graceful fallbacks."""
    line_items: list[ExtractedLineItem] = []
    for li in parsed.get("line_items") or []:
        try:
            line_items.append(
                ExtractedLineItem(
                    order_num=int(li.get("order_num") or len(line_items) + 1),
                    description=str(li.get("description") or "").strip() or "—",
                    unit=str(li.get("unit") or "").strip() or None,
                    quantity=_to_decimal(li.get("quantity")),
                )
            )
        except Exception:
            continue

    bids: list[ExtractedBid] = []
    for b in parsed.get("bids") or []:
        try:
            lines: list[ExtractedBidLine] = []
            for bl in b.get("lines") or []:
                lab = _to_decimal_opt(bl.get("unit_price_labor"))
                mat = _to_decimal_opt(bl.get("unit_price_material"))
                tot = _to_decimal(bl.get("unit_price_total"))
                # If split was given but total wasn't, synthesize total
                if (lab is not None or mat is not None) and tot == 0:
                    tot = (lab or Decimal(0)) + (mat or Decimal(0))
                lines.append(
                    ExtractedBidLine(
                        order_num=int(bl.get("order_num") or 0),
                        unit_price_labor=lab,
                        unit_price_material=mat,
                        unit_price_total=tot,
                    )
                )
            bids.append(
                ExtractedBid(
                    company_name=str(b.get("company_name") or "Unknown").strip(),
                    contact_name=_str_or_none(b.get("contact_name")),
                    contact_phone=_str_or_none(b.get("contact_phone")),
                    contact_email=_str_or_none(b.get("contact_email")),
                    included_in_price=_str_or_none(b.get("included_in_price")),
                    not_included_in_price=_str_or_none(b.get("not_included_in_price")),
                    payment_terms=_str_or_none(b.get("payment_terms")),
                    delivery_days=_to_int_opt(b.get("delivery_days")),
                    notes=_str_or_none(b.get("notes")),
                    lines=lines,
                )
            )
        except Exception:
            continue

    return TenderExtraction(
        title=str(parsed.get("title") or fallback_title or "Untitled tender").strip(),
        object_name=_str_or_none(parsed.get("object_name")),
        currency=(str(parsed.get("currency") or "RUB").strip().upper() or "RUB"),
        payment_terms_expected=_str_or_none(parsed.get("payment_terms_expected")),
        delivery_terms_expected=_str_or_none(parsed.get("delivery_terms_expected")),
        notes=_str_or_none(parsed.get("notes")),
        line_items=line_items,
        bids=bids,
        source="llm",
        warnings=[str(w) for w in (parsed.get("warnings") or []) if w],
    )


# ---------------------------------------------------------------------------
# Per-bid extraction (single company's quote against an existing tender)
# ---------------------------------------------------------------------------


def extract_bid_from_file(
    *,
    raw_bytes: bytes,
    filename: str,
    line_items: list[TenderLineItem],
    lang: str = "EN",
) -> ExtractedBid:
    """Extract a single company's bid from a quote file.

    Unlike :func:`extract_tender_from_file`, the tender already exists and
    its line items are known; the LLM's job is just to identify the
    bidder, pull contact info and quote terms, and match each priced row
    to one of the supplied ``line_items`` by description similarity. The
    matched prices come back keyed by ``order_num`` so the caller can
    look up the real ``tender_line_item.id``.
    """
    warnings: list[str] = []
    text_blob, fallback_company = _file_to_text(raw_bytes, filename, warnings)

    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    if not api_key:
        return ExtractedBid(
            company_name=fallback_company or "Unknown",
            notes="ANTHROPIC_API_KEY missing — manual entry required",
        )

    try:
        bid = _llm_extract_single_bid(
            text_blob,
            line_items,
            fallback_company,
            api_key,
            lang=lang,
        )
        return bid
    except Exception as exc:  # noqa: BLE001
        return ExtractedBid(
            company_name=fallback_company or "Unknown",
            notes=f"AI extraction failed: {exc!r}",
        )


def _llm_extract_single_bid(
    text_blob: str,
    line_items: list[TenderLineItem],
    fallback_company: str,
    api_key: str,
    *,
    lang: str = "EN",
) -> ExtractedBid:
    import anthropic  # type: ignore

    client = anthropic.Anthropic(
        api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS
    )
    snippet = text_blob[:60_000]
    lang_name = "Turkish" if lang.upper() == "TR" else "English"

    # Present the existing line items so Claude can match against them
    items_block = "\n".join(
        f"  #{li.order_num} | {li.description} | unit: {li.unit or '-'} | qty: {li.quantity}"
        for li in line_items
    )

    prompt = (
        "You are a structured-extraction assistant for a construction "
        "company. The user already created a tender with the line items "
        "listed below. The attached file is ONE company's quotation for "
        "this tender. Your job is to:\n"
        "  1. Identify the company name and contact info.\n"
        "  2. For each priced line in the file, match it to one of the "
        "tender line items below by description similarity and return the "
        "unit price keyed by `order_num`. If a line in the file doesn't "
        "match any tender line item, skip it (don't invent matches).\n"
        "  3. If the source separates işçilik (labor) and malzeme "
        "(material) per line, fill both unit_price_labor and "
        "unit_price_material (total = labor + material). If only a "
        "combined unit price is given, fill ONLY unit_price_total and "
        "leave labor/material as null.\n\n"
        f"Write narrative fields in {lang_name}; keep company names and "
        "units in their original script.\n\n"
        "TENDER LINE ITEMS (match against these):\n"
        f"{items_block}\n\n"
        "BIDDER FILE CONTENT:\n"
        "```\n"
        f"{snippet}\n"
        "```\n\n"
        "Return ONLY this JSON object (no prose around it):\n"
        "{\n"
        '  "company_name": "...",\n'
        '  "contact_name": "...",\n'
        '  "contact_phone": "...",\n'
        '  "contact_email": "...",\n'
        '  "included_in_price": "what the bidder said is included",\n'
        '  "not_included_in_price": "...",\n'
        '  "payment_terms": "...",\n'
        '  "delivery_days": <int|null>,\n'
        '  "notes": "...",\n'
        '  "lines": [\n'
        '    { "order_num": 1, "unit_price_labor": null, "unit_price_material": null, "unit_price_total": 1500 }\n'
        "  ]\n"
        "}\n"
    )
    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text if msg.content else "{}"
    parsed = json.loads(_extract_json_block(raw))

    lines: list[ExtractedBidLine] = []
    valid_orders = {li.order_num for li in line_items}
    for bl in parsed.get("lines") or []:
        try:
            order_num = int(bl.get("order_num") or 0)
            if order_num not in valid_orders:
                continue
            lab = _to_decimal_opt(bl.get("unit_price_labor"))
            mat = _to_decimal_opt(bl.get("unit_price_material"))
            tot = _to_decimal(bl.get("unit_price_total"))
            if (lab is not None or mat is not None) and tot == 0:
                tot = (lab or Decimal(0)) + (mat or Decimal(0))
            lines.append(
                ExtractedBidLine(
                    order_num=order_num,
                    unit_price_labor=lab,
                    unit_price_material=mat,
                    unit_price_total=tot,
                )
            )
        except Exception:
            continue

    return ExtractedBid(
        company_name=str(parsed.get("company_name") or fallback_company or "Unknown").strip(),
        contact_name=_str_or_none(parsed.get("contact_name")),
        contact_phone=_str_or_none(parsed.get("contact_phone")),
        contact_email=_str_or_none(parsed.get("contact_email")),
        included_in_price=_str_or_none(parsed.get("included_in_price")),
        not_included_in_price=_str_or_none(parsed.get("not_included_in_price")),
        payment_terms=_str_or_none(parsed.get("payment_terms")),
        delivery_days=_to_int_opt(parsed.get("delivery_days")),
        notes=_str_or_none(parsed.get("notes")),
        lines=lines,
    )


# ---------------------------------------------------------------------------
# Tiny coercion helpers
# ---------------------------------------------------------------------------


def _to_decimal(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal(0)
    try:
        return Decimal(str(v).replace(",", "."))
    except Exception:
        return Decimal(0)


def _to_decimal_opt(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).replace(",", "."))
    except Exception:
        return None


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
