"""Tests for predictive risk scoring (Faz 3)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.risk_scoring import (
    EACResult,
    OverrunBand,
    RiskBand,
    SubcontractorSignals,
    forecast_eac,
    risk_band,
    subcontractor_risk_score,
)


class TestSubcontractorRisk:
    def test_healthy_sub_scores_low(self):
        s = SubcontractorSignals(
            active_contracts=4,
            overdue_contracts=0,
            total_contract_value=Decimal("100"),
            paid_value=Decimal("100"),
            months_of_history=24,
            rating=5.0,
        )
        assert subcontractor_risk_score(s) == 0.0
        assert risk_band(subcontractor_risk_score(s)) is RiskBand.LOW

    def test_all_overdue_scores_high(self):
        s = SubcontractorSignals(
            active_contracts=6,
            overdue_contracts=6,
            total_contract_value=Decimal("100"),
            paid_value=Decimal("10"),
            months_of_history=3,
            rating=2.0,
        )
        score = subcontractor_risk_score(s)
        assert score > 66
        assert risk_band(score) is RiskBand.HIGH

    def test_overdue_dominates(self):
        half = SubcontractorSignals(active_contracts=4, overdue_contracts=2)
        none = SubcontractorSignals(active_contracts=4, overdue_contracts=0)
        assert subcontractor_risk_score(half) > subcontractor_risk_score(none)

    def test_unrated_has_no_rating_penalty(self):
        s = SubcontractorSignals(
            active_contracts=2,
            overdue_contracts=0,
            total_contract_value=Decimal("100"),
            paid_value=Decimal("100"),
            months_of_history=24,
            rating=None,
        )
        assert subcontractor_risk_score(s) == 0.0

    def test_no_contract_value_no_underpay_penalty(self):
        s = SubcontractorSignals(
            active_contracts=2,
            overdue_contracts=0,
            months_of_history=24,
            total_contract_value=Decimal("0"),
        )
        # only history(0) + overdue(0); rating None -> 0
        assert subcontractor_risk_score(s) == 0.0


class TestEAC:
    def test_matches_live_hippodrome_card(self):
        # BAC 11.94B, AC 7.33B, progress 74% -> CPI ~1.21, under budget.
        r = forecast_eac(Decimal("11940000000"), Decimal("7330000000"), 74)
        assert r.cpi == pytest.approx(1.205, abs=0.01)
        assert r.band is OverrunBand.UNDER_OR_ON
        assert r.variance_at_completion > 0  # projected under budget
        assert r.eac < r.bac

    def test_overrun_risk_when_cpi_low(self):
        r = forecast_eac(Decimal("100"), Decimal("80"), 50)  # EV 50, CPI 0.625
        assert r.cpi == pytest.approx(0.625, abs=0.001)
        assert r.band is OverrunBand.OVERRUN_RISK
        assert r.eac > r.bac
        assert r.variance_at_completion < 0

    def test_watch_band(self):
        r = forecast_eac(Decimal("100"), Decimal("100"), 95)  # CPI 0.95
        assert r.band is OverrunBand.WATCH

    def test_zero_actual_is_unknown(self):
        r = forecast_eac(Decimal("100"), Decimal("0"), 10)
        assert r.band is OverrunBand.UNKNOWN
        assert r.cpi is None
        assert r.eac is None

    def test_returns_eac_result(self):
        assert isinstance(forecast_eac(Decimal("10"), Decimal("5"), 50), EACResult)
