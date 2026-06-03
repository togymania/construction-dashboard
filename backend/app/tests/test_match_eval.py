"""Tests for the match evaluation harness (Faz 2.5)."""
from __future__ import annotations

from app.services.match_eval import (
    EvalResult,
    LabeledCase,
    evaluate,
    meets_auto_target,
)
from app.services.matching import Candidate

CANDS = [
    Candidate(id=10, text="Главное здание ОКН", code="3"),
    Candidate(id=11, text="Призовые дороги скачка", code="29"),
    Candidate(id=12, text="Электроснабжение кабельные линии", code="40"),
]


class TestRealisticSet:
    def _cases(self):
        return [
            LabeledCase("Главное здание ОКН", 10),
            LabeledCase("Электроснабжение кабельные линии", 12),
            LabeledCase("Призовые дороги скачка", 11),
            # These should NOT match any construction line item.
            LabeledCase("зарплата сотрудников за май", None),
            LabeledCase("налоговый платеж ндс банк", None),
        ]

    def test_clean_set_has_perfect_precision(self):
        r = evaluate(self._cases(), CANDS)
        assert r.precision == 1.0
        assert r.fp == 0
        assert r.tp == 3
        assert r.tn == 2

    def test_auto_tier_meets_95_target(self):
        r = evaluate(self._cases(), CANDS)
        assert meets_auto_target(r) is True
        # every AUTO prediction on this set is correct
        assert r.auto_accuracy in (None, 1.0)


class TestConfusionMath:
    def test_should_not_match_predicted_match_is_fp(self):
        # Force a positive prediction where expected is None by using text
        # that strongly matches candidate 10.
        cases = [LabeledCase("Главное здание ОКН", None)]
        r = evaluate(cases, CANDS)
        assert r.fp == 1
        assert r.tn == 0
        assert r.precision == 0.0
        assert r.fp_rate == 1.0

    def test_wrong_id_counts_as_fp_and_fn(self):
        # Text matches candidate 12, but we labeled the correct answer as 11.
        cases = [LabeledCase("Электроснабжение кабельные линии", 11)]
        r = evaluate(cases, CANDS)
        assert r.fp == 1
        assert r.fn == 1
        assert r.tp == 0
        assert r.recall == 0.0

    def test_missed_match_is_fn(self):
        cases = [LabeledCase("совершенно несвязанный текст", 10)]
        r = evaluate(cases, CANDS)
        assert r.fn == 1
        assert r.fp == 0
        assert r.recall == 0.0

    def test_f1_combines_precision_recall(self):
        cases = [
            LabeledCase("Главное здание ОКН", 10),       # TP
            LabeledCase("совершенно несвязанный", 11),   # FN (missed)
        ]
        r = evaluate(cases, CANDS)
        assert r.precision == 1.0
        assert r.recall == 0.5
        assert r.f1 is not None and 0.6 < r.f1 < 0.7

    def test_empty_auto_tier_meets_target(self):
        # No cases produce AUTO -> trivially meets target (no wrong applies).
        r = EvalResult(
            total=0, tp=0, fp=0, fn=0, tn=0, precision=None, recall=None,
            f1=None, fp_rate=None, fn_rate=None, auto_total=0, auto_correct=0,
            auto_accuracy=None, review_total=0, review_correct=0,
            review_accuracy=None,
        )
        assert meets_auto_target(r) is True

    def test_low_auto_accuracy_fails_target(self):
        r = EvalResult(
            total=10, tp=5, fp=5, fn=0, tn=0, precision=0.5, recall=1.0,
            f1=0.6667, fp_rate=None, fn_rate=0.0, auto_total=10, auto_correct=5,
            auto_accuracy=0.5, review_total=0, review_correct=0,
            review_accuracy=None,
        )
        assert meets_auto_target(r) is False
