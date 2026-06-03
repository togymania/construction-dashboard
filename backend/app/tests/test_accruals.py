"""Tests for Accruals / CVR (Prompt 3) + the data-trust penalty."""
from __future__ import annotations

from app.services.accruals import (
    ContractAccrualSignal,
    accrual_warning,
    assess_accruals,
    is_unreliable_accrual,
    missing_accrual_flag,
    progress_payment_gap,
)
from app.services.data_reliability import apply_accrual_penalty


def _sig(pid, phys, pay, days):
    return ContractAccrualSignal(pid, phys, pay, days)


class TestMissingAccrual:
    def test_progress_but_stale_cost_is_flagged(self):
        assert missing_accrual_flag(_sig(1, 40, 5, 45)) is True

    def test_progress_but_never_booked_is_flagged(self):
        assert missing_accrual_flag(_sig(1, 40, 0, None)) is True

    def test_recent_cost_not_flagged(self):
        assert missing_accrual_flag(_sig(1, 40, 35, 10)) is False

    def test_no_progress_not_flagged(self):
        assert missing_accrual_flag(_sig(1, 0, 0, None)) is False


class TestGap:
    def test_large_gap_is_unreliable(self):
        # site 40% but only 5% paid -> 35-point gap
        s = _sig(1, 40, 5, 10)  # recent cost, so flag is only the gap
        assert progress_payment_gap(s) == 35.0
        assert is_unreliable_accrual(s) is True

    def test_small_gap_is_ok(self):
        s = _sig(1, 40, 35, 10)
        assert is_unreliable_accrual(s) is False


class TestAssess:
    def test_flagged_ratio(self):
        sigs = [
            _sig(1, 40, 5, 10),    # gap 35 -> flagged
            _sig(2, 50, 48, 5),    # ok
            _sig(3, 30, 30, None),  # stale/never booked + progress -> flagged
            _sig(4, 0, 0, None),   # no progress -> ok
        ]
        r = assess_accruals(sigs)
        assert r.total == 4
        assert r.flagged == 2
        assert set(r.flagged_contracts) == {1, 3}
        assert r.flagged_ratio == 0.5

    def test_empty(self):
        r = assess_accruals([])
        assert r.flagged_ratio == 0.0


class TestWarning:
    def test_high_ratio_warns(self):
        r = assess_accruals([_sig(1, 40, 5, 99), _sig(2, 40, 5, 99)])
        assert accrual_warning(r, lang="TR") is not None
        assert "tahakkuk" in accrual_warning(r, lang="TR")
        assert accrual_warning(r, lang="EN") is not None

    def test_low_ratio_no_warning(self):
        r = assess_accruals([_sig(i, 40, 39, 5) for i in range(10)])
        assert accrual_warning(r) is None


class TestPenalty:
    def test_penalty_scales_with_ratio(self):
        assert apply_accrual_penalty(60, 0.0) == 60.0
        assert apply_accrual_penalty(60, 0.5) == 40.0   # 60 - 0.5*40
        assert apply_accrual_penalty(60, 1.0) == 20.0   # 60 - 40

    def test_penalty_clamped_at_zero(self):
        assert apply_accrual_penalty(10, 1.0) == 0.0

    def test_ratio_clamped(self):
        assert apply_accrual_penalty(60, 2.0) == 20.0  # ratio capped at 1
