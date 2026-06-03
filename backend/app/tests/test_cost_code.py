"""Tests for the Cost Code Normalization Engine (Faz 0).

These are pure-function tests with no DB or app dependencies, so they run
fast and in isolation. They lock in the matching behaviour that the
data-integrity recovery work depends on.
"""
from __future__ import annotations

import pytest

from app.services.cost_code import codes_match, normalize_cost_code


class TestEmptyAndNone:
    @pytest.mark.parametrize("value", [None, "", "   ", "\t", "\n", " ", "\u200b"])
    def test_blank_inputs_become_empty(self, value):
        assert normalize_cost_code(value) == ""

    def test_booleans_are_not_codes(self):
        # bool is a subclass of int; must not become "1"/"0".
        assert normalize_cost_code(True) == ""
        assert normalize_cost_code(False) == ""


class TestPureIntegers:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("3", "3"),
            ("03", "3"),
            ("003", "3"),
            ("0030", "30"),
            ("0", "0"),
            ("00", "0"),
            (" 3 ", "3"),
            ("29", "29"),
        ],
    )
    def test_leading_zeros_stripped(self, value, expected):
        assert normalize_cost_code(value) == expected


class TestNumericInputs:
    def test_int_input(self):
        assert normalize_cost_code(3) == "3"
        assert normalize_cost_code(29) == "29"

    def test_float_integer_value(self):
        # openpyxl hands us 3 as 3.0
        assert normalize_cost_code(3.0) == "3"
        assert normalize_cost_code(44.0) == "44"

    def test_float_non_integer(self):
        assert normalize_cost_code(3.5) == "3.5"

    def test_nan_and_inf(self):
        assert normalize_cost_code(float("nan")) == ""
        assert normalize_cost_code(float("inf")) == ""


class TestDecimalArtifacts:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("3.0", "3"),
            ("3.00", "3"),
            ("3,0", "3"),
            ("29,00", "29"),
            ("03.0", "3"),
            ("100.000", "100"),
        ],
    )
    def test_trailing_zero_decimal_collapses(self, value, expected):
        assert normalize_cost_code(value) == expected


class TestSegmentedCodes:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("3.10", "3.10"),   # NOT 3.1 — hierarchical chapter.item
            ("03.05", "3.5"),
            ("3-2-1", "3.2.1"),
            ("3/2", "3.2"),
            ("01.02.03", "1.2.3"),
        ],
    )
    def test_segments_keep_structure(self, value, expected):
        assert normalize_cost_code(value) == expected


class TestUnicodeAndWhitespace:
    def test_full_width_digits(self):
        assert normalize_cost_code("３") == "3"
        assert normalize_cost_code("４４") == "44"

    def test_nbsp_and_zero_width_are_removed(self):
        assert normalize_cost_code("3\u00a0") == "3"
        assert normalize_cost_code("\u200b3\u200b") == "3"

    def test_internal_whitespace_collapsed(self):
        assert normalize_cost_code("a  b") == "a b"


class TestAlphanumericAndSlugs:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("Bina", "bina"),
            ("BINA", "bina"),
            ("bina", "bina"),
            ("B-12", "b-12"),     # alphanumeric: structure preserved
            ("СМР-3", "смр-3"),   # cyrillic lower-cased, kept
        ],
    )
    def test_words_lowercased_unchanged(self, value, expected):
        assert normalize_cost_code(value) == expected


class TestIdempotence:
    @pytest.mark.parametrize(
        "value", ["03", "3.0", "3.10", "Bina", "B-12", "03.05", "  7 ", "３"]
    )
    def test_double_normalization_is_stable(self, value):
        once = normalize_cost_code(value)
        assert normalize_cost_code(once) == once


class TestCodesMatch:
    @pytest.mark.parametrize(
        "a,b",
        [
            ("03", "3"),
            ("3.0", "3"),
            (3.0, "3"),
            ("3", 3),
            (" 3 ", "3"),
            ("Bina", "bina"),
            ("29,00", "29"),
            ("３", "3"),
        ],
    )
    def test_equivalent_codes_match(self, a, b):
        assert codes_match(a, b) is True

    @pytest.mark.parametrize(
        "a,b",
        [
            ("3", "4"),
            ("3.10", "3.1"),
            ("bina", "yollar"),
            ("3", ""),
            ("", ""),
            (None, None),
            (None, "3"),
        ],
    )
    def test_different_or_empty_codes_do_not_match(self, a, b):
        assert codes_match(a, b) is False
