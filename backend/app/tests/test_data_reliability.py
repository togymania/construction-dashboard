"""Tests for the Data Reliability Score + verdict gate (Faz 2)."""
from __future__ import annotations

import pytest

from app.services.data_reliability import (
    ReliabilityBand,
    ReliabilitySignals,
    Verdict,
    freshness_score,
    gate_verdict,
    reliability_band,
    reliability_caveat,
    reliability_from_ledger_counts,
    reliability_score,
)


class TestFreshness:
    @pytest.mark.parametrize(
        "days,expected",
        [(0, 100.0), (2, 100.0), (30, 0.0), (60, 0.0), (None, 0.0)],
    )
    def test_endpoints(self, days, expected):
        assert freshness_score(days) == expected

    def test_midpoint_decays(self):
        assert 40 < freshness_score(16) < 60


class TestScore:
    def test_perfect_data_scores_high(self):
        s = ReliabilitySignals(
            total_rows=100,
            rows_with_budget_code=100,
            expense_rows=100,
            rows_with_subcontractor=100,
            freshness_days=1,
        )
        assert reliability_score(s) == 100.0

    def test_live_scenario_scores_low(self):
        # Central Moscow Hippodrome: ~70 of 9258 linked, stale ~20 days.
        s = ReliabilitySignals(
            total_rows=9258,
            rows_with_budget_code=70,
            expense_rows=9258,
            rows_with_subcontractor=70,
            freshness_days=20,
        )
        score = reliability_score(s)
        assert score < 20
        assert reliability_band(score) is ReliabilityBand.LOW

    def test_missing_components_are_renormalised(self):
        # No expense rows -> subcontractor component dropped, not penalised.
        s = ReliabilitySignals(
            total_rows=10,
            rows_with_budget_code=10,
            expense_rows=0,
            rows_with_subcontractor=0,
            freshness_days=1,
        )
        # Only budget (100) + freshness (100) remain -> 100.
        assert reliability_score(s) == 100.0

    def test_no_signals_is_zero(self):
        assert reliability_score(ReliabilitySignals()) == 0.0


class TestBand:
    @pytest.mark.parametrize(
        "score,band",
        [
            (95, ReliabilityBand.HIGH),
            (70, ReliabilityBand.HIGH),
            (69.9, ReliabilityBand.MEDIUM),
            (40, ReliabilityBand.MEDIUM),
            (39.9, ReliabilityBand.LOW),
            (0, ReliabilityBand.LOW),
        ],
    )
    def test_bands(self, score, band):
        assert reliability_band(score) is band


class TestGateVerdict:
    def test_low_reliability_blocks_optimism(self):
        assert gate_verdict(Verdict.ON_TRACK, 10) is Verdict.DATA_UNRELIABLE
        assert gate_verdict(Verdict.WATCH, 10) is Verdict.DATA_UNRELIABLE

    def test_low_reliability_keeps_pessimism(self):
        # The whole point of the live fix: bad data must NOT read "on track".
        assert gate_verdict(Verdict.CRITICAL, 0) is Verdict.CRITICAL
        assert gate_verdict(Verdict.AT_RISK, 5) is Verdict.AT_RISK

    def test_medium_softens_on_track_to_watch(self):
        assert gate_verdict(Verdict.ON_TRACK, 50) is Verdict.WATCH
        assert gate_verdict(Verdict.WATCH, 50) is Verdict.WATCH

    def test_high_reliability_passes_through(self):
        assert gate_verdict(Verdict.ON_TRACK, 90) is Verdict.ON_TRACK
        assert gate_verdict(Verdict.CRITICAL, 90) is Verdict.CRITICAL


class TestCaveat:
    def test_high_has_no_caveat(self):
        assert reliability_caveat(90) is None

    def test_low_has_caveat_both_langs(self):
        assert "reliability" in reliability_caveat(10, "EN").lower()
        assert "güvenilir" in reliability_caveat(10, "TR").lower()


class TestLedgerCounts:
    def test_live_counts_are_low(self):
        # Central Moscow Hippodrome live counts.
        score = reliability_from_ledger_counts(9188, 8069, 9258)
        assert reliability_band(score) is ReliabilityBand.LOW

    def test_clean_counts_are_high(self):
        score = reliability_from_ledger_counts(0, 0, 1000)
        assert reliability_band(score) is ReliabilityBand.HIGH

    def test_zero_total_is_zero(self):
        assert reliability_from_ledger_counts(0, 0, 0) == 0.0

    def test_both_ai_features_gate_identically(self):
        # The governance property: same counts -> same score -> same gate,
        # so the Executive Report and AI Director can't contradict.
        score = reliability_from_ledger_counts(9188, 8069, 9258)
        assert gate_verdict(Verdict.ON_TRACK, score) is Verdict.DATA_UNRELIABLE
