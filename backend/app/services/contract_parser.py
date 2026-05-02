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
    }
