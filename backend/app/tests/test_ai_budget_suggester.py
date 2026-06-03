"""Tests for the AI budget-code suggester core (pure parts)."""
from __future__ import annotations

from app.services.ai_budget_suggester import (
    CodedRow,
    LedgerRow,
    find_prior_evidence,
    parse_ai_suggestion,
    rule_based_suggestion,
)
from app.services.matching import Candidate

CANDS = [
    Candidate(id=10, text="Главное здание ОКН", code="3"),
    Candidate(id=11, text="Призовые дороги скачка асфальт", code="29"),
    Candidate(id=12, text="Электроснабжение кабельные линии", code="40"),
]


class TestPriorEvidence:
    def test_same_company_is_found(self):
        row = LedgerRow(1, description="оплата", company_name="ООО МЦПИС")
        coded = [
            CodedRow("работа 1", "ООО МЦПИС", "3"),
            CodedRow("работа 2", "ооо  мцпис", "3"),  # normalises to same
        ]
        ev = find_prior_evidence(row, coded)
        assert ev[0].budget_code == "3"
        assert ev[0].support == 2
        assert ev[0].via == "same_company"

    def test_similar_description_is_found(self):
        row = LedgerRow(1, description="Электроснабжение кабельные линии 0,4 кВ",
                        company_name="Unknown LLC")
        coded = [CodedRow("Электроснабжение кабельные линии", "Other", "40")]
        ev = find_prior_evidence(row, coded)
        assert ev and ev[0].budget_code == "40"
        assert ev[0].via == "similar_description"

    def test_unrelated_rows_yield_nothing(self):
        row = LedgerRow(1, description="зарплата", company_name="ACME")
        coded = [CodedRow("асфальт дорога", "Roadworks", "29")]
        assert find_prior_evidence(row, coded) == []

    def test_same_company_ranks_before_similar(self):
        row = LedgerRow(1, description="Электроснабжение кабельные линии",
                        company_name="ООО МЦПИС")
        coded = [
            CodedRow("Электроснабжение кабельные линии", "Other", "40"),  # sim desc
            CodedRow("что угодно", "ООО МЦПИС", "3"),                      # same company
        ]
        ev = find_prior_evidence(row, coded)
        assert ev[0].via == "same_company"
        assert ev[0].budget_code == "3"


class TestRuleSuggestion:
    def test_same_company_prior_wins(self):
        row = LedgerRow(1, description="hakedis", company_name="ООО МЦПИС")
        priors = find_prior_evidence(
            row,
            [CodedRow("x", "ООО МЦПИС", "3"), CodedRow("y", "ООО МЦПИС", "3")],
        )
        s = rule_based_suggestion(row, CANDS, priors)
        assert s.proposed_code == "3"
        assert s.candidate_id == 10
        assert s.confidence >= 80
        assert "firma" in s.rationale.lower()

    def test_description_match_when_no_prior(self):
        row = LedgerRow(1, description="Электроснабжение кабельные линии 0,4 кВ")
        s = rule_based_suggestion(row, CANDS, [])
        assert s.proposed_code == "40"
        assert s.candidate_id == 12

    def test_no_signal_returns_none(self):
        row = LedgerRow(1, description="совершенно несвязанный платеж")
        s = rule_based_suggestion(row, CANDS, [])
        assert s.proposed_code is None
        assert s.confidence == 0.0


class TestParseAi:
    def test_known_code_maps_to_candidate(self):
        row = LedgerRow(1)
        s = parse_ai_suggestion(
            {"budget_code": "03", "confidence": 88, "rationale": "Yol firması."},
            row, CANDS,
        )
        assert s.proposed_code == "3"
        assert s.candidate_id == 10
        assert s.confidence == 88
        assert s.source == "ai_web"

    def test_unknown_code_has_no_candidate(self):
        row = LedgerRow(1)
        s = parse_ai_suggestion({"budget_code": "99", "confidence": 50}, row, CANDS)
        assert s.proposed_code == "99"
        assert s.candidate_id is None

    def test_bad_confidence_defaults_zero(self):
        row = LedgerRow(1)
        s = parse_ai_suggestion({"budget_code": "3", "confidence": "abc"}, row, CANDS)
        assert s.confidence == 0.0

    def test_confidence_clamped(self):
        row = LedgerRow(1)
        s = parse_ai_suggestion({"budget_code": "3", "confidence": 250}, row, CANDS)
        assert s.confidence == 100.0
