"""Header-based column discovery (Faz 2.5 — Parser Hardening).

The Excel importers (ledger, budget, workforce) currently read **fixed
column indices** (B, C, E, F, G, J ...). If the source template shifts a
single column, they silently read the wrong field — and with the new
matching engine sitting downstream, bad input would quietly poison
everything. This module binds each logical field to a column by matching
the **header row text** against known multilingual aliases (Russian /
Turkish / English), so the parsers bind to *meaning*, not position, and
fail loudly when a required column is missing.

Pure and dependency-light (rapidfuzz only). The parsers call
``discover_columns(header_row, SPECS)`` once and then read by field name.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.services.matching import normalize_text

# A header must reach this fuzzy score (0-100) to bind when it is not an
# exact normalized match to an alias.
DEFAULT_MIN_SCORE = 85.0


@dataclass(frozen=True)
class ColumnSpec:
    """One logical field the parser needs, and the header texts that mean it."""

    field: str
    aliases: tuple[str, ...]
    required: bool = True


@dataclass
class DiscoveryResult:
    mapping: dict[str, int] = field(default_factory=dict)  # field -> col index
    missing: list[str] = field(default_factory=list)       # required, not found
    unmatched_headers: list[int] = field(default_factory=list)  # unclassified cols

    @property
    def ok(self) -> bool:
        """True when every required field was located."""
        return not self.missing

    def index(self, field_name: str) -> int | None:
        return self.mapping.get(field_name)


def _score_header_against_spec(header: str, spec: ColumnSpec) -> tuple[float, bool]:
    """Best score of a header cell against any alias. Returns ``(score,
    is_exact)`` so an exact match can outrank a fuzzy one at the same score
    (otherwise a fuzzy subset like "наименование" ~ "наименование
    контрагента" could steal a column that another field matches exactly).
    """
    h = normalize_text(header)
    if not h:
        return 0.0, False
    best = 0.0
    for alias in spec.aliases:
        a = normalize_text(alias)
        if not a:
            continue
        if h == a:
            return 100.0, True
        # token_set_ratio is robust to extra words ("дата операции" ~ "дата")
        best = max(best, float(fuzz.token_set_ratio(h, a)))
    return best, False


def discover_columns(
    header_row: list,
    specs: list[ColumnSpec],
    *,
    min_score: float = DEFAULT_MIN_SCORE,
) -> DiscoveryResult:
    """Map each spec field to a column index by header text.

    Greedy one-to-one assignment: the highest-scoring (column, field) pair
    is bound first, then the next, never reusing a column or a field.
    Required fields with no binding are reported in ``missing``; unbound
    columns are reported in ``unmatched_headers``.
    """
    # Score every (column, spec) pair above threshold.
    candidates: list[tuple[float, bool, int, str]] = []
    for col_idx, cell in enumerate(header_row):
        for spec in specs:
            score, is_exact = _score_header_against_spec(cell, spec)
            if score >= min_score:
                candidates.append((score, is_exact, col_idx, spec.field))

    # Greedy: highest score first, exact matches before fuzzy at the same
    # score, then stable by (col, field) for determinism.
    candidates.sort(key=lambda t: (-t[0], not t[1], t[2], t[3]))

    mapping: dict[str, int] = {}
    used_cols: set[int] = set()
    for _score, _exact, col_idx, fld in candidates:
        if fld in mapping or col_idx in used_cols:
            continue
        mapping[fld] = col_idx
        used_cols.add(col_idx)

    missing = [s.field for s in specs if s.required and s.field not in mapping]
    unmatched = [
        i for i in range(len(header_row)) if i not in used_cols and str(header_row[i] or "").strip()
    ]
    return DiscoveryResult(mapping=mapping, missing=missing, unmatched_headers=unmatched)


# ---------------------------------------------------------------------------
# Ready-made spec sets for the existing importers (aliases from the real
# Russian/Turkish templates). Parsers can import and use these directly.
# ---------------------------------------------------------------------------

LEDGER_SPECS: list[ColumnSpec] = [
    ColumnSpec("entry_date", ("дата", "tarih", "date")),
    ColumnSpec("description", ("описание", "наименование", "açıklama", "description")),
    ColumnSpec("company_name", ("контрагент", "фирма", "firma", "company")),
    ColumnSpec("kod", ("код", "kod", "code"), required=False),
    ColumnSpec("account", ("счет", "счёт", "hesap", "account"), required=False),
    ColumnSpec("amount", ("сумма", "tutar", "amount")),
]
