"""Tests for the generic matching pipeline (Faz 1).

Pure-function tests (rapidfuzz is the only dependency, no DB), locking in
the exact/fuzzy scoring and the confidence-bucket safety rails that the
reconciliation engine relies on.
"""
from __future__ import annotations

from app.services.matching import (
    AMBIGUITY_MARGIN,
    AUTO_THRESHOLD,
    REVIEW_THRESHOLD,
    Candidate,
    Decision,
    best_suggestion,
    classify,
    normalize_text,
    rank,
    score_pair,
)


class TestNormalizeText:
    def test_lowercases_and_collapses(self):
        assert normalize_text("  Главное   ЗДАНИЕ ") == "главное здание"

    def test_strips_punctuation(self):
        assert normalize_text("ООО «Компания», 2024!") == "ооо компания 2024"

    def test_blank(self):
        assert normalize_text(None) == ""
        assert normalize_text("   ") == ""


class TestExactCode:
    def test_exact_code_short_circuits_to_100(self):
        cand = Candidate(id=1, text="totally different words", code="3")
        score, reason = score_pair("anything", "03", cand)
        assert score == 100.0
        assert reason == "exact_code"

    def test_code_mismatch_falls_back_to_text(self):
        cand = Candidate(id=1, text="главное здание", code="29")
        score, reason = score_pair("главное здание", "3", cand)
        assert reason == "fuzzy_text"
        assert score > 90

    def test_missing_code_uses_text(self):
        cand = Candidate(id=1, text="asphalt road", code=None)
        score, reason = score_pair("asphalt road works", None, cand)
        assert reason == "fuzzy_text"


class TestFuzzyText:
    def test_identical_text_scores_100(self):
        cand = Candidate(id=1, text="дорожки скачки")
        score, _ = score_pair("дорожки скачки", None, cand)
        assert score == 100.0

    def test_unrelated_text_scores_low(self):
        cand = Candidate(id=1, text="электроснабжение")
        score, _ = score_pair("банковские расходы зарплата", None, cand)
        assert score < REVIEW_THRESHOLD

    def test_empty_sides_score_zero(self):
        assert score_pair("", None, Candidate(id=1, text="x"))[0] == 0.0
        assert score_pair("x", None, Candidate(id=1, text=""))[0] == 0.0


class TestClassify:
    def test_auto_when_high_and_unambiguous(self):
        assert classify(95, is_unambiguous=True) is Decision.AUTO

    def test_high_but_ambiguous_downgrades_to_review(self):
        assert classify(95, is_unambiguous=False) is Decision.REVIEW

    def test_review_band(self):
        assert classify(REVIEW_THRESHOLD) is Decision.REVIEW
        assert classify(89.9) is Decision.REVIEW

    def test_reject_below_threshold(self):
        assert classify(REVIEW_THRESHOLD - 0.1) is Decision.REJECT
        assert classify(0) is Decision.REJECT


class TestRank:
    def _budget_candidates(self):
        return [
            Candidate(id=10, text="Главное здание (ОКН)", code="3"),
            Candidate(id=11, text="Призовые дороги скачка", code="29"),
            Candidate(id=12, text="Электроснабжение кабельные линии", code="40"),
        ]

    def test_exact_code_wins_and_auto(self):
        out = rank("hakedis odemesi", self._budget_candidates(), query_code="029")
        assert out[0].candidate_id == 11
        assert out[0].score == 100.0
        assert out[0].decision is Decision.AUTO

    def test_strong_unique_text_match_is_auto(self):
        out = rank("Главное здание ОКН", self._budget_candidates())
        assert out[0].candidate_id == 10
        assert out[0].decision is Decision.AUTO

    def test_ambiguous_top_two_downgraded(self):
        # Two near-identical candidates -> best can't clear the margin.
        cands = [
            Candidate(id=1, text="бетонные работы корпус а"),
            Candidate(id=2, text="бетонные работы корпус б"),
        ]
        out = rank("бетонные работы корпус", cands)
        assert out[0].decision is Decision.REVIEW
        assert (out[0].score - out[1].score) < AMBIGUITY_MARGIN

    def test_no_match_is_reject(self):
        out = rank("совершенно несвязанный текст", self._budget_candidates())
        assert out[0].decision is Decision.REJECT

    def test_limit_respected(self):
        out = rank("дорога", self._budget_candidates(), limit=2)
        assert len(out) == 2

    def test_results_sorted_descending(self):
        out = rank("Призовые дороги", self._budget_candidates())
        scores = [s.score for s in out]
        assert scores == sorted(scores, reverse=True)


class TestBestSuggestion:
    def test_returns_top(self):
        cands = [Candidate(id=1, text="asphalt"), Candidate(id=2, text="cabling")]
        best = best_suggestion("asphalt road", cands)
        assert best is not None
        assert best.candidate_id == 1

    def test_none_when_no_candidates(self):
        assert best_suggestion("anything", []) is None
