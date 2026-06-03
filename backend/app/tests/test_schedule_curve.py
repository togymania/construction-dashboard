"""Tests for the S-curve schedule model (Prompt 1)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.schedule_curve import (
    planned_s_curve_progress,
    s_curve_fraction,
    schedule_variance_pct,
)


class TestSCurveFraction:
    def test_endpoints_and_midpoint(self):
        assert s_curve_fraction(0) == 0.0
        assert s_curve_fraction(1) == 1.0
        assert s_curve_fraction(0.5) == pytest.approx(0.5)

    def test_k1_is_linear(self):
        assert s_curve_fraction(0.25, steepness=1) == pytest.approx(0.25)
        assert s_curve_fraction(0.8, steepness=1) == pytest.approx(0.8)

    def test_default_is_s_shaped(self):
        # slow start: planned < time early; fast finish: planned > time late
        assert s_curve_fraction(0.25) < 0.25
        assert s_curve_fraction(0.75) > 0.75

    def test_monotonic(self):
        vals = [s_curve_fraction(t / 10) for t in range(11)]
        assert vals == sorted(vals)

    def test_clamps_out_of_range(self):
        assert s_curve_fraction(-1) == 0.0
        assert s_curve_fraction(2) == 1.0


class TestPlannedProgress:
    def test_none_dates(self):
        assert planned_s_curve_progress(None, date(2026, 1, 1)) is None
        assert planned_s_curve_progress(date(2026, 1, 1), None) is None

    def test_before_start_is_zero(self):
        r = planned_s_curve_progress(
            date(2026, 6, 1), date(2026, 12, 1), as_of=date(2026, 1, 1)
        )
        assert r == 0.0

    def test_after_end_is_100(self):
        r = planned_s_curve_progress(
            date(2025, 1, 1), date(2025, 6, 1), as_of=date(2026, 1, 1)
        )
        assert r == 100.0

    def test_midpoint_is_50(self):
        r = planned_s_curve_progress(
            date(2025, 1, 1), date(2025, 3, 2), as_of=date(2025, 1, 31)
        )
        assert r == pytest.approx(50.0, abs=2.0)

    def test_early_stage_below_linear(self):
        # 25% through the schedule -> planned < 25%
        start = date(2025, 1, 1)
        r = planned_s_curve_progress(
            start, start + timedelta(days=100), as_of=start + timedelta(days=25)
        )
        assert r is not None and r < 25.0


class TestScheduleVariance:
    def test_behind_is_negative(self):
        assert schedule_variance_pct(40, 55) == -15.0

    def test_none_planned(self):
        assert schedule_variance_pct(40, None) is None
