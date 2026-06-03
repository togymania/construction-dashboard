"""Tests for the Critical Path Method engine (Prompt 1)."""
from __future__ import annotations

import pytest

from app.services.critical_path import (
    Activity,
    compute_cpm,
    critical_path_delayed_days,
)


class TestCPM:
    def _network(self):
        # A(2) -> B(3) -> D(2) ; A -> C(1) -> D
        # Critical path A-B-D (7 days). C has 2 days of float.
        return [
            Activity("A", 2),
            Activity("B", 3, ("A",)),
            Activity("C", 1, ("A",)),
            Activity("D", 2, ("B", "C")),
        ]

    def test_project_duration(self):
        r = compute_cpm(self._network())
        assert r.project_duration == 7

    def test_critical_path_is_zero_float_chain(self):
        r = compute_cpm(self._network())
        assert set(r.critical_ids) == {"A", "B", "D"}
        assert r.total_float["C"] == 2  # the slack one is not critical

    def test_parallel_no_dependency_longest_is_critical(self):
        # Degenerate network (e.g. contracts with no links): the longest
        # activity is the critical one.
        acts = [Activity("X", 5), Activity("Y", 3), Activity("Z", 7)]
        r = compute_cpm(acts)
        assert r.project_duration == 7
        assert r.critical_ids == ["Z"]
        assert r.total_float["X"] == 2
        assert r.total_float["Y"] == 4

    def test_cycle_raises(self):
        acts = [Activity("A", 1, ("B",)), Activity("B", 1, ("A",))]
        with pytest.raises(ValueError):
            compute_cpm(acts)

    def test_unknown_predecessor_raises(self):
        with pytest.raises(ValueError):
            compute_cpm([Activity("A", 1, ("ghost",))])

    def test_empty_network(self):
        r = compute_cpm([])
        assert r.project_duration == 0.0
        assert r.critical_ids == []


class TestCriticalDelay:
    def test_only_critical_delay_counts(self):
        # C is not on the critical path; its delay must be ignored.
        acts = [
            Activity("A", 2, overdue_days=1),       # critical
            Activity("B", 3, ("A",), overdue_days=10),  # critical
            Activity("C", 1, ("A",), overdue_days=99),  # has float -> ignored
            Activity("D", 2, ("B", "C")),
        ]
        assert critical_path_delayed_days(acts) == 10

    def test_no_delay(self):
        acts = [Activity("A", 2), Activity("B", 3, ("A",))]
        assert critical_path_delayed_days(acts) == 0.0
