"""Basic contract document parser — extracts key fields using regex patterns.

Phase 1: Regex-based extraction (no LLM dependency).
Supports: amounts, dates, company names, payment terms.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any


# ---------- Amount extraction ----------

_AMOUNT_PATTERNS = [
    # "1,500,000.00 ₽" or "₽1,500,000"
    r"(?:₽|RUB|руб\.?)\s*([\d,.\s]+)",
    r"([\d,.\s]+)\s*(?:₽|RUB|руб\.?)",
    # "$1,500,000" or "1,500,000 USD"
    r"(?:\$|USD)\s*([\d,.\s]+)",
    r"([\d,.\s]+)\s*(?:\$|USD)",
    # "TL 1,500,000" or "1,500,000 TL"
    r"(?:TL|₺)\s*([\d,.\s]+)",
    r"([\d,.\s]+)\s*(?:TL|₺)",
    # Generic large number after keywords
    r"(?:amount|tutar|bedel|toplam|sözleşme\s+bedeli)[:\s]*([\d,.\s]+)",
]


def _parse_number(raw: str) -> Decimal | None:
    """Parse a raw number string like '1,500,000.00' into Decimal."""
    cleaned = raw.strip().replace(" ", "").replace(",", "")
    try:
        val = Decimal(cleaned)
        return val if val > 0 else None
    except Exception:
        return None


def extract_amount(text: str) -> Decimal | None:
    """Extract the most likely contract amount from text."""
    amounts: list[Decimal] = []
    for pattern in _AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = _parse_number(match.group(1))
            if val and val > 1000:  # Filter tiny false positives
                amounts.append(val)
    return max(amounts) if amounts else None


# ---------- Date extraction ----------

_DATE_PATTERNS = [
    r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",  # DD/MM/YYYY or DD.MM.YYYY
    r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})",  # YYYY-MM-DD
]

_START_KEYWORDS = ["başlangıç", "start", "yürürlük", "geçerlilik"]
_END_KEYWORDS = ["bitiş", "end", "son", "sona erme", "tamamlanma"]


def _find_dates_near_keyword(text: str, keywords: list[str]) -> str | None:
    """Find a date near one of the given keywords."""
    for keyword in keywords:
        pattern = rf"{keyword}[^.]*?(\d{{1,2}}[./\-]\d{{1,2}}[./\-]\d{{4}}|\d{{4}}[./\-]\d{{1,2}}[./\-]\d{{1,2}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_dates(text: str) -> tuple[str | None, str | None]:
    """Extract start and end dates from text."""
    start = _find_dates_near_keyword(text, _START_KEYWORDS)
    end = _find_dates_near_keyword(text, _END_KEYWORDS)

    # Fallback: grab first two dates found
    if not start or not end:
        all_dates = []
        for pattern in _DATE_PATTERNS:
            all_dates.extend(re.finditer(pattern, text))
        if len(all_dates) >= 2 and not start:
            start = all_dates[0].group(0)
        if len(all_dates) >= 2 and not end:
            end = all_dates[-1].group(0)

    return start, end


# ---------- Company name extraction ----------

_COMPANY_SUFFIXES = [
    r"(?:Ltd\.?|LLC|Inc\.?|A\.?Ş\.?|Ş(?:ti|irketi)\.?|Co\.?|Corp\.?)",
    r"(?:İnşaat|Mühendislik|Elektrik|Yapı|Taahhüt)",
]


def extract_companies(text: str) -> list[str]:
    """Extract company-like names from text."""
    companies: list[str] = []
    for suffix in _COMPANY_SUFFIXES:
        pattern = rf"([A-ZА-ЯÜĞŞÖÇİ][A-Za-zА-Яа-яüğşöçı\s&.\-]{{2,40}}\s*{suffix})"
        for match in re.finditer(pattern, text):
            name = match.group(1).strip()
            if name and name not in companies:
                companies.append(name)
    return companies[:5]


# ---------- Payment terms ----------

_PAYMENT_KEYWORDS = [
    "hakediş", "hakedis", "ödeme", "payment", "installment",
    "taksit", "vade", "fatura", "invoice", "milestone",
    "peşin", "avans", "advance", "net 30", "net 60",
]


def extract_payment_terms(text: str) -> list[str]:
    """Extract payment-related terms and sentences."""
    terms: list[str] = []
    sentences = re.split(r"[.\n]", text)
    for sentence in sentences:
        lower = sentence.strip().lower()
        for kw in _PAYMENT_KEYWORDS:
            if kw in lower and len(sentence.strip()) > 10:
                terms.append(sentence.strip()[:200])
                break
    return terms[:10]


# ---------- Main parser ----------

def parse_contract_text(text: str) -> dict[str, Any]:
    """Extract key fields from contract text using regex patterns.

    Returns a dict with:
        - contract_amount: Decimal | None
        - start_date: str | None
        - end_date: str | None
        - company_names: list[str]
        - payment_terms: list[str]
        - confidence: float (0-1)
    """
    amount = extract_amount(text)
    start_date, end_date = extract_dates(text)
    companies = extract_companies(text)
    payment_terms = extract_payment_terms(text)

    # Simple confidence score based on how many fields were extracted
    found = sum([
        amount is not None,
        start_date is not None,
        end_date is not None,
        len(companies) > 0,
        len(payment_terms) > 0,
    ])
    confidence = found / 5.0

    return {
        "contract_amount": str(amount) if amount else None,
        "start_date": start_date,
        "end_date": end_date,
        "company_names": companies,
        "payment_terms": payment_terms,
        "confidence": round(confidence, 2),
        "source": "regex",
    }


# ============================================================================
# Day 11 — PDF text extraction + LLM-based structured parsing
# ============================================================================

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Pull plain text from a PDF using pdfplumber. Returns empty string on failure."""
    import io
    try:
        import pdfplumber
    except ImportError:
        return ""

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages_text: list[str] = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    pages_text.append(t)
            return "\n\n".join(pages_text)
    except Exception:
        return ""


def parse_contract_with_llm(
    text: str,
    *,
    hints: dict[str, Any] | None = None,
    api_key: str | None = None,
    model: str = "claude-sonnet-4-5",
    timeout: int = 30,
) -> dict[str, Any]:
    """Send contract text to Claude for structured extraction.

    If `api_key` is empty/None, returns a mock response (Day 11 — key not yet
    obtained). The mock blends regex output with placeholder LLM-style fields
    so the frontend can be developed and tested end-to-end.
    """
    from datetime import datetime, timezone

    hints = hints or {}
    extracted_at = datetime.now(timezone.utc).isoformat()

    # Always run regex first as a baseline / fallback safety net
    base = parse_contract_text(text)

    # Take a small sample for debugging/diagnostics
    raw_sample = text[:500] if text else ""

    if not api_key:
        # ---- Mock path (no API key configured) ----
        return _mock_llm_response(base, raw_sample, extracted_at, hints)

    # ---- Real LLM path (placeholder wiring for when key is added) ----
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        prompt = _build_extraction_prompt(text, hints)
        msg = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        # Expect JSON in response — parse defensively
        import json as _json
        raw = msg.content[0].text if msg.content else "{}"
        parsed = _json.loads(_extract_json_block(raw))
        merged = {**base, **parsed}
        merged.update({
            "raw_text_sample": raw_sample,
            "source": "llm",
            "extracted_at": extracted_at,
        })
        return merged
    except Exception as exc:
        # On any LLM failure, fall back to regex-only with a low confidence
        return {
            **base,
            "raw_text_sample": raw_sample,
            "source": "regex",
            "extracted_at": extracted_at,
            "summary": f"LLM call failed, regex only used: {type(exc).__name__}",
        }


# ---------- Mock + prompt helpers ----------

def _mock_llm_response(
    base: dict[str, Any],
    raw_sample: str,
    extracted_at: str,
    hints: dict[str, Any],
) -> dict[str, Any]:
    """Synthetic 'as-if' LLM response so frontend/integration can be tested
    without an API key. Uses regex output for amount/dates and fabricates
    plausible structured fields where possible.
    """
    company_names = base.get("company_names") or []
    counterparty_name = None
    company_name = None
    if len(company_names) >= 2:
        counterparty_name = company_names[0]
        company_name = company_names[1]
    elif len(company_names) == 1:
        company_name = company_names[0]

    # Detect currency from raw sample
    currency = None
    sample_upper = (raw_sample or "").upper()
    for cur, marker in (("RUB", "₽"), ("RUB", "RUB"), ("RUB", "РУБ"), ("USD", "$"), ("USD", "USD"), ("TRY", "TL"), ("TRY", "₺")):
        if marker in sample_upper:
            currency = cur
            break

    # Fake some penalty / key-date entries when we have any extracted text
    penalty_clauses: list[dict[str, Any]] = []
    key_dates: list[dict[str, Any]] = []
    risk_flags: list[str] = []
    if "ceza" in sample_upper.lower() or "penalty" in sample_upper.lower() or "штраф" in sample_upper.lower():
        penalty_clauses.append({
            "trigger": "Delay (mock)",
            "penalty_type": "percentage",
            "amount": None,
            "percentage": 5.0,
            "description": "Mock: 5% penalty detected for 30-day delay (awaiting LLM API key).",
        })
        risk_flags.append("Penalty clause present")
    if base.get("end_date"):
        key_dates.append({
            "date": base["end_date"][:10] if isinstance(base["end_date"], str) else str(base["end_date"])[:10],
            "label": "Contract end (mock)",
            "description": "End date extracted via regex.",
        })

    summary_bits = []
    if base.get("contract_amount"):
        summary_bits.append(f"Contract value approximately {base['contract_amount']} {currency or ''}".strip())
    if base.get("start_date") and base.get("end_date"):
        summary_bits.append(f"duration: {base['start_date']} - {base['end_date']}")
    if not summary_bits:
        summary_bits.append("Synthetic (mock) summary — add ANTHROPIC_API_KEY for real LLM extraction")

    return {
        **base,
        "currency": currency,
        "company_name": company_name,
        "counterparty_name": counterparty_name,
        "payment_terms_summary": (base.get("payment_terms") or [None])[0],
        "penalty_clauses": penalty_clauses,
        "key_dates": key_dates,
        "risk_flags": risk_flags,
        "summary": "; ".join(summary_bits) + ".",
        "raw_text_sample": raw_sample,
        "source": "llm_mock",
        "extracted_at": extracted_at,
        "confidence": min(0.6, base.get("confidence", 0) + 0.1),  # mock biraz daha emin
    }


def _build_extraction_prompt(text: str, hints: dict[str, Any]) -> str:
    """Construct the extraction prompt for the real LLM path."""
    # Truncate text to keep tokens reasonable
    snippet = text[:25000]
    hint_str = ""
    if hints:
        hint_str = "\n\nUser-provided hints (treat as suggestions, not facts):\n" + "\n".join(
            f"- {k}: {v}" for k, v in hints.items()
        )
    return f"""You are a construction contract analyst. Analyze the contract text below
and return structured data in JSON format. Reply with JSON ONLY, no commentary.

The contract may be in Turkish, Russian, or English — handle all three.

Fields to fill:
- contract_amount: number (digits only, no currency symbol)
- currency: "RUB" | "USD" | "TRY"
- start_date: YYYY-MM-DD
- end_date: YYYY-MM-DD
- company_name: subcontractor company name
- counterparty_name: main contractor (e.g. Mono / Monart)
- payment_terms_summary: short sentence (e.g. "30-day net progress payments")
- penalty_clauses: [{{trigger, penalty_type, amount?, percentage?, description}}]
- key_dates: [{{date, label, description?}}]
- risk_flags: list (e.g. "long contract end-date", "high penalty rate")
- summary: 2-3 sentence general overview
- confidence: 0-1 range (your own confidence)
{hint_str}

Contract text:
\"\"\"
{snippet}
\"\"\"

JSON response:"""


def _extract_json_block(raw: str) -> str:
    """Pull the JSON object from a possibly-noisy LLM response."""
    raw = raw.strip()
    # Code-fence stripping
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Drop opening fence line
        lines = lines[1:]
        # Drop closing fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines)
    # First { to last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start:end + 1]
    return raw or "{}"
