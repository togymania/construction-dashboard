"""Match evaluation harness (Faz 2.5 — measure, don't guess).

The reconciliation report could only *project* a match rate
("8070/9258 -> 80%+"). That is a guess. This module turns it into
measured numbers by running the matching pipeline over a **labeled** set
of cases and computing precision / recall / F1, false-positive and
false-negative rates, and -- most importantly for an ERP where a wrong
match is worse than no match -- the **accuracy of the AUTO tier**, which
must clear a high bar (default 95%) before auto-apply is trusted.

Counting rules (single-label retrieval, strict/honest):

  expected = None (row should NOT match)
      predicted None        -> TN
      predicted some id      -> FP
  expected = an id
      predicted == expected  -> TP
      predicted None         -> FN                 (missed the correct one)
      predicted a wrong id   -> FP and FN          (wrong AND missed)

The same harness can later be pointed at a hand-labeled sample of the
real production data to report the true precision/recall.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.matching import Candidate, Decision, rank

DEFAULT_AUTO_TARGET = 0.95


@dataclass(frozen=True)
class LabeledCase:
    """A query whose correct answer is known."""

    query_text: str
    expected_candidate_id: int | None  # None means "should not match anything"
    query_code: object = None


@dataclass(frozen=True)
class EvalResult:
    total: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None
    recall: float | None
    f1: float | None
    fp_rate: float | None
    fn_rate: float | None
    auto_total: int
    auto_correct: int
    auto_accuracy: float | None
    review_total: int
    review_correct: int
    review_accuracy: float | None


def _safe_div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b > 0 else None


def evaluate(
    cases: list[LabeledCase],
    candidates: list[Candidate],
) -> EvalResult:
    """Run the pipeline over labeled cases and compute the metrics."""
    tp = fp = fn = tn = 0
    auto_total = auto_correct = 0
    review_total = review_correct = 0

    for case in cases:
        ranked = rank(
            case.query_text, candidates, query_code=case.query_code, limit=1
        )
        top = ranked[0] if ranked else None
        decision = top.decision if top else Decision.REJECT
        predicted = (
            top.candidate_id
            if (top is not None and decision is not Decision.REJECT)
            else None
        )
        correct = predicted == case.expected_candidate_id

        # Confusion matrix.
        if case.expected_candidate_id is None:
            if predicted is None:
                tn += 1
            else:
                fp += 1
        else:
            if predicted == case.expected_candidate_id:
                tp += 1
            elif predicted is None:
                fn += 1
            else:
                fp += 1
                fn += 1

        # Per-bucket accuracy.
        if decision is Decision.AUTO:
            auto_total += 1
            auto_correct += int(correct)
        elif decision is Decision.REVIEW:
            review_total += 1
            review_correct += int(correct)

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = (
        _safe_div(2 * precision * recall, precision + recall)
        if precision and recall
        else None
    )
    return EvalResult(
        total=len(cases),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=precision,
        recall=recall,
        f1=f1,
        fp_rate=_safe_div(fp, fp + tn),
        fn_rate=_safe_div(fn, fn + tp),
        auto_total=auto_total,
        auto_correct=auto_correct,
        auto_accuracy=_safe_div(auto_correct, auto_total),
        review_total=review_total,
        review_correct=review_correct,
        review_accuracy=_safe_div(review_correct, review_total),
    )


def meets_auto_target(result: EvalResult, target: float = DEFAULT_AUTO_TARGET) -> bool:
    """True when the AUTO tier is accurate enough to be trusted.

    An empty AUTO tier (nothing auto-applied) trivially meets the target —
    there are no wrong auto-applies.
    """
    if result.auto_total == 0:
        return True
    return (result.auto_accuracy or 0.0) >= target
