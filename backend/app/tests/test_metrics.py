"""Tests for the canonical financial metrics (Faz 0 SSOT skeleton).

Only the pure assembler ``build_financials`` is exercised here — no DB —
so these run fast and lock in the *single* definition of "spent %".
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.metrics import ProjectFinancials, build_financials


def _fin(planned, spent, budget="16000000000", committed="0"):
    return build_financials(
        project_id=1,
        budget_total=Decimal(budget),
        planned_total=Decimal(planned),
        committed_total=Decimal(committed),
        spent_total=Decimal(spent),
    )


class TestUtilization:
    def test_matches_budget_page_example(self):
        # Live Central Moscow Hippodrome figures: 7.33B spent of 11.94B planned.
        fin = _fin("11940000000", "7330000000")
        assert fin.utilization_pct == pytest.approx(61.39, abs=0.1)

    def test_budget_consumed_against_ceiling(self):
        fin = _fin("11940000000", "7330000000", budget="16000000000")
        assert fin.budget_consumed_pct == pytest.approx(45.81, abs=0.1)

    def test_remaining_is_planned_minus_spent(self):
        fin = _fin("100", "30")
        assert fin.remaining == Decimal("70")

    def test_full_spend_is_100_pct(self):
        fin = _fin("100", "100")
        assert fin.utilization_pct == pytest.approx(100.0)

    def test_overspend_exceeds_100(self):
        fin = _fin("100", "150")
        assert fin.utilization_pct == pytest.approx(150.0)


class TestEdgeCases:
    def test_zero_planned_yields_none(self):
        fin = _fin("0", "500")
        assert fin.utilization_pct is None

    def test_zero_budget_yields_none(self):
        fin = _fin("100", "50", budget="0")
        assert fin.budget_consumed_pct is None

    def test_zero_spent_is_zero_pct(self):
        fin = _fin("100", "0")
        assert fin.utilization_pct == pytest.approx(0.0)

    def test_returns_immutable_snapshot(self):
        fin = _fin("100", "50")
        assert isinstance(fin, ProjectFinancials)
        with pytest.raises(Exception):
            fin.spent_total = Decimal("999")  # frozen dataclass
