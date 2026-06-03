"""Tests for Earned Value Analysis (Prompt 2)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.earned_value import (
    CostBand,
    ScheduleBand,
    compute_eva,
    eva_projection_sentence,
)


def _eva(bac, physical, acwp, planned):
    return compute_eva(
        bac=Decimal(str(bac)),
        physical_progress_pct=physical,
        acwp=Decimal(str(acwp)),
        planned_progress_pct=planned,
    )


class TestLiveHippodrome:
    def test_favourable_cpi(self):
        e = _eva("11940000000", 74, "7330000000", 74)
        assert e.cpi == pytest.approx(1.206, abs=0.01)
        assert e.cost_band == CostBand.FAVOURABLE
        assert e.eac < e.bac
        assert e.vac > 0  # projected under budget


class TestCostBands:
    def test_over_budget_red(self):
        e = _eva("100", 50, "80", 50)  # BCWP 50, CPI 0.625
        assert e.cpi == pytest.approx(0.625, abs=0.001)
        assert e.cost_band == CostBand.OVER_BUDGET
        assert e.eac > e.bac
        assert e.vac < 0

    def test_on_target_amber(self):
        e = _eva("100", 95, "100", 95)  # CPI 0.95
        assert e.cost_band == CostBand.ON_TARGET

    def test_unknown_when_no_actual_cost(self):
        e = _eva("100", 10, "0", 10)
        assert e.cpi is None
        assert e.cost_band == CostBand.UNKNOWN
        assert e.eac is None


class TestScheduleBands:
    def test_behind_when_spi_low(self):
        e = _eva("100", 40, "40", 55)  # SPI 40/55 = 0.727
        assert e.spi == pytest.approx(0.727, abs=0.01)
        assert e.schedule_band == ScheduleBand.BEHIND

    def test_ahead_when_spi_high(self):
        e = _eva("100", 60, "60", 50)  # SPI 1.2
        assert e.schedule_band == ScheduleBand.AHEAD

    def test_unknown_when_no_plan(self):
        e = compute_eva(
            bac=Decimal("100"), physical_progress_pct=50,
            acwp=Decimal("50"), planned_progress_pct=None,
        )
        assert e.spi is None
        assert e.schedule_band == ScheduleBand.UNKNOWN


class TestVariances:
    def test_cv_and_sv(self):
        e = _eva("100", 50, "80", 40)
        assert e.bcwp == Decimal("50")
        assert e.cv == Decimal("-30")   # 50 - 80
        assert e.sv == Decimal("10")    # 50 - 40


class TestProjectionSentence:
    def test_over_budget_sentence_tr(self):
        e = _eva("100", 50, "80", 50)
        s = eva_projection_sentence(e, lang="TR")
        assert "aşabilir" in s and "EAC" in s

    def test_under_budget_sentence_en(self):
        e = _eva("11940000000", 74, "7330000000", 74)
        s = eva_projection_sentence(e, lang="EN")
        assert "under" in s and "EAC" in s

    def test_unknown_sentence(self):
        e = _eva("100", 10, "0", 10)
        s = eva_projection_sentence(e, lang="TR")
        assert "yapılamıyor" in s
