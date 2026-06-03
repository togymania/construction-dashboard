"""Tests for the reconciliation planner (Faz 1) — pure planner only, no DB.

Verifies that unmatched rows get the right proposals, that values map to
cost codes / subcontractor ids, and that the summary stats add up.
"""
from __future__ import annotations

from app.services.matching import Candidate, Decision
from app.services.reconciliation import (
    UnmatchedRow,
    match_rate,
    plan_reconciliation,
)

BUDGET = [
    Candidate(id=10, text="Главное здание ОКН", code="3"),
    Candidate(id=11, text="Призовые дороги скачка асфальт", code="29"),
    Candidate(id=12, text="Электроснабжение кабельные линии", code="40"),
]
SUBS = [
    Candidate(id=100, text="ООО МЦПИС"),
    Candidate(id=101, text="ООО ПАМП-ГРУПП"),
    Candidate(id=102, text="ООО Проектное бюро АрКо"),
]


def _plan(rows):
    return plan_reconciliation(rows, budget_candidates=BUDGET, sub_candidates=SUBS)


class TestBudgetProposals:
    def test_clear_description_match_proposes_cost_code(self):
        rows = [UnmatchedRow(id=1, description="Главное здание ОКН", needs_budget_code=True)]
        plan = _plan(rows)
        assert len(plan.rows) == 1
        p = plan.rows[0].proposals[0]
        assert p.field == "budget_code"
        assert p.value == "3"  # the matched item's cost_code, not its id
        assert p.candidate_id == 10
        assert p.decision is Decision.AUTO

    def test_unrelated_description_makes_no_proposal(self):
        rows = [UnmatchedRow(id=1, description="зарплата банк комиссия", needs_budget_code=True)]
        plan = _plan(rows)
        assert plan.rows == []
        assert plan.stats.budget_reject == 1


class TestSubcontractorProposals:
    def test_company_name_match_proposes_sub_id(self):
        rows = [UnmatchedRow(id=1, company_name="МЦПИС", needs_subcontractor=True)]
        plan = _plan(rows)
        p = plan.rows[0].proposals[0]
        assert p.field == "subcontractor_id"
        assert p.value == 100
        assert p.decision is Decision.AUTO

    def test_legal_form_tokens_do_not_break_match(self):
        # token_set_ratio handles the extra "ООО" token.
        rows = [UnmatchedRow(id=1, company_name="ООО ПАМП ГРУПП", needs_subcontractor=True)]
        plan = _plan(rows)
        assert plan.rows[0].proposals[0].candidate_id == 101


class TestBothFields:
    def test_row_needing_both_gets_two_proposals(self):
        rows = [
            UnmatchedRow(
                id=1,
                description="Электроснабжение кабельные линии",
                company_name="Проектное бюро АрКо",
                needs_budget_code=True,
                needs_subcontractor=True,
            )
        ]
        plan = _plan(rows)
        fields = {p.field for p in plan.rows[0].proposals}
        assert fields == {"budget_code", "subcontractor_id"}


class TestStats:
    def test_counts_add_up(self):
        rows = [
            UnmatchedRow(id=1, description="Главное здание ОКН", needs_budget_code=True),
            UnmatchedRow(id=2, description="ничего общего", needs_budget_code=True),
            UnmatchedRow(id=3, company_name="МЦПИС", needs_subcontractor=True),
        ]
        plan = _plan(rows)
        assert plan.stats.total_rows == 3
        assert plan.stats.needing_budget_code == 2
        assert plan.stats.needing_subcontractor == 1
        assert plan.stats.budget_auto == 1
        assert plan.stats.budget_reject == 1
        assert plan.stats.sub_auto == 1
        assert plan.stats.auto_total == 2

    def test_proposals_for_bucket(self):
        rows = [UnmatchedRow(id=1, description="Главное здание ОКН", needs_budget_code=True)]
        plan = _plan(rows)
        autos = plan.proposals_for(Decision.AUTO)
        assert len(autos) == 1
        assert autos[0][0] == 1  # row id


class TestMatchRate:
    def test_basic(self):
        assert match_rate(70, 100) == 70.0

    def test_zero_total_is_none(self):
        assert match_rate(0, 0) is None

    def test_projected_lift_example(self):
        # 70 of 9258 matched today -> auto-applying 8000 lifts to ~83%.
        assert match_rate(70, 9258) < 1.0
        assert match_rate(70 + 8000, 9258) > 80.0
