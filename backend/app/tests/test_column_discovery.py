"""Tests for header-based column discovery (Faz 2.5 — Parser Hardening)."""
from __future__ import annotations

from app.services.column_discovery import (
    LEDGER_SPECS,
    ColumnSpec,
    discover_columns,
)


class TestLedgerHeaders:
    def test_standard_order_maps_all(self):
        header = ["Дата", "Описание", "Контрагент", "Код", "Счет", "Сумма"]
        r = discover_columns(header, LEDGER_SPECS)
        assert r.ok
        assert r.missing == []
        assert r.index("entry_date") == 0
        assert r.index("amount") == 5

    def test_shifted_columns_still_map_by_meaning(self):
        # Columns reordered — fixed-index parsing would break, header-based
        # parsing must not.
        header = ["Сумма", "Контрагент", "Дата", "Описание", "Счет", "Код"]
        r = discover_columns(header, LEDGER_SPECS)
        assert r.ok
        assert r.index("amount") == 0
        assert r.index("company_name") == 1
        assert r.index("entry_date") == 2
        assert r.index("description") == 3

    def test_missing_required_is_reported_loudly(self):
        header = ["Дата", "Описание", "Контрагент", "Код", "Счет"]  # no amount
        r = discover_columns(header, LEDGER_SPECS)
        assert r.ok is False
        assert "amount" in r.missing

    def test_fuzzy_alias_with_extra_words(self):
        header = ["Дата операции", "Наименование", "Фирма", "Код", "Счёт", "Сумма операции"]
        r = discover_columns(header, LEDGER_SPECS)
        assert r.ok
        assert r.index("entry_date") == 0
        assert r.index("description") == 1
        assert r.index("company_name") == 2
        assert r.index("amount") == 5

    def test_turkish_headers_map(self):
        header = ["Tarih", "Açıklama", "Firma", "Kod", "Hesap", "Tutar"]
        r = discover_columns(header, LEDGER_SPECS)
        assert r.ok
        assert r.index("entry_date") == 0
        assert r.index("amount") == 5

    def test_unknown_column_is_unmatched_not_crash(self):
        header = ["Дата", "Описание", "Контрагент", "Сумма", "Примечание ревизора"]
        r = discover_columns(header, LEDGER_SPECS)
        # the unrelated "Примечание" column maps to nothing
        assert any(
            i == 4 for i in r.unmatched_headers
        )


class TestGeneric:
    def test_optional_missing_is_ok(self):
        specs = [
            ColumnSpec("a", ("alpha",)),
            ColumnSpec("b", ("beta",), required=False),
        ]
        r = discover_columns(["Alpha"], specs)
        assert r.ok  # b is optional
        assert r.index("a") == 0
        assert r.index("b") is None

    def test_one_to_one_no_double_binding(self):
        # Two columns both look like "amount"; only one binds.
        specs = [ColumnSpec("amount", ("сумма",))]
        r = discover_columns(["Сумма", "Сумма"], specs)
        assert r.index("amount") == 0
        assert 1 in r.unmatched_headers
