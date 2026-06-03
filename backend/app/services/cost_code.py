"""Cost Code Normalization Engine (Faz 0 — Data Integrity foundation).

The single, canonical place where a *cost code* is reduced to its
comparable form. Both sides of the budget<->ledger relationship are
free text entered by humans (``BudgetItem.cost_code`` from the ÇMI
budget sheet, ``LedgerEntry.budget_code`` typed in by the finance team),
so the same logical code shows up in many surface forms:

    "3", "03", "3.0", " 3 ", "3<NBSP>", full-width digits, "3.00"

Until now matching was a bare ``str.strip().lower()``, which treats all
of the above as *different* codes. In production this caused ~99% of
ledger rows to never match a budget item. This module collapses every
surface form to one canonical string so that ``"03"`` and ``"3.0"`` and
``"3"`` all match.

Design rules (intentionally conservative so we never *merge* two codes
that are genuinely different):

* ``None`` / empty / whitespace-only  -> ``""`` (caller treats as "no code").
* Unicode is NFKC-normalised (full-width digits -> ASCII), zero-width and
  non-breaking spaces are stripped, internal whitespace collapsed, then
  lower-cased.
* A pure integer keeps only its numeric value: ``"03" -> "3"``,
  ``"0" -> "0"``.
* A trailing-zero decimal (an Excel float artifact like ``3`` stored as
  ``3.0``) drops the fraction: ``"3.0" -> "3"``, ``"29,00" -> "29"``.
* A segmented / hierarchical code keeps every segment but strips each
  segment's leading zeros: ``"03.05" -> "3.5"``, ``"3-2-1" -> "3.2.1"``.
  Note we deliberately do **not** decimal-collapse ``"3.10"`` to
  ``"3.1"`` — in construction WBS codes ``3.10`` means chapter 3 / item
  10, not the number 3.1.
* Anything else (alphanumeric codes, category slugs like ``"bina"``) is
  returned cleaned and lower-cased, unchanged otherwise.

The function is pure, dependency-free (stdlib only) and idempotent:
``normalize_cost_code(normalize_cost_code(x)) == normalize_cost_code(x)``.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

__all__ = ["normalize_cost_code", "codes_match"]

# Zero-width and BOM characters that must be deleted entirely:
# ZWSP, ZWNJ, ZWJ, word-joiner, BOM.
_ZERO_WIDTH = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF], None
)

_PURE_INT = re.compile(r"^\d+$")
# digits, then a '.'/',' followed by only zeros -> Excel float artifact
_TRAILING_ZERO_DECIMAL = re.compile(r"^(\d+)[.,]0+$")
# integer segments joined by . - / (hierarchical WBS codes)
_SEGMENTED = re.compile(r"^\d+(?:[.,\-/]\d+)+$")
_SEGMENT_SPLIT = re.compile(r"[.,\-/]")


def normalize_cost_code(raw: object) -> str:
    """Return the canonical comparable form of a cost / budget code.

    See module docstring for the full rule set. Always returns a string;
    an empty string means "no usable code".
    """
    if raw is None or isinstance(raw, bool):
        return ""

    # Numeric inputs come straight from openpyxl (Excel stores everything
    # as float). Handle them before stringifying so 3.0 -> "3".
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, float):
        if raw != raw or raw in (float("inf"), float("-inf")):  # NaN / inf
            return ""
        if raw.is_integer():
            return str(int(raw))
        # Drop binary-float noise: 3.5 -> "3.5", not "3.500000".
        raw = format(Decimal(str(raw)).normalize(), "f")

    s = str(raw)
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_ZERO_WIDTH)
    s = s.replace("\u00a0", " ")  # NBSP -> normal space (NFKC also handles this)
    s = re.sub(r"\s+", " ", s).strip().lower()
    if not s:
        return ""

    if _PURE_INT.match(s):
        return str(int(s))  # "03" -> "3", "0" -> "0"

    m = _TRAILING_ZERO_DECIMAL.match(s)
    if m:
        return str(int(m.group(1)))  # "3.0"/"3,00" -> "3"

    if _SEGMENTED.match(s):
        parts = _SEGMENT_SPLIT.split(s)
        try:
            return ".".join(str(int(p)) for p in parts)  # "03.05" -> "3.5"
        except ValueError:  # pragma: no cover - guarded by regex
            return s

    return s


def codes_match(a: object, b: object) -> bool:
    """True when two codes normalise to the same non-empty canonical form.

    Empty / missing codes never match (we don't want every uncoded row to
    collide on ``""``).
    """
    na = normalize_cost_code(a)
    return bool(na) and na == normalize_cost_code(b)
