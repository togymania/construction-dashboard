"""Tests for the adaptive match memory (Faz 2.5 — Learning Match Engine)."""
from __future__ import annotations

from app.services.match_memory import (
    MAX_BOOST,
    PER_APPROVAL_BOOST,
    MatchMemory,
    boosted_rank,
)
from app.services.matching import Candidate, Decision, rank

CANDS = [
    Candidate(id=10, text="Главное здание ОКН"),
    Candidate(id=11, text="Электроснабжение кабельные линии 0,4 кВ"),
    Candidate(id=12, text="Призовые дороги скачка асфальт"),
]


class TestMemoryCounts:
    def test_record_and_approvals(self):
        m = MatchMemory()
        m.record("ООО Монарт", 12)
        m.record("ооо  монарт", 12)  # normalises to the same key
        assert m.approvals("ООО МОНАРТ", 12) == 2

    def test_boost_scales_then_caps(self):
        m = MatchMemory()
        m.record("x", 1, times=1)
        assert m.boost_for("x", 1) == PER_APPROVAL_BOOST
        m.record("x", 1, times=2)  # total 3
        assert m.boost_for("x", 1) == 3 * PER_APPROVAL_BOOST
        m.record("x", 1, times=10)  # total 13 -> capped
        assert m.boost_for("x", 1) == MAX_BOOST

    def test_blank_text_not_recorded(self):
        m = MatchMemory()
        m.record("   ", 1)
        assert m.approvals("   ", 1) == 0

    def test_unknown_mapping_has_no_boost(self):
        assert MatchMemory().boost_for("anything", 99) == 0.0


class TestBoostedRank:
    def test_no_memory_matches_plain_rank(self):
        m = MatchMemory()
        a = rank("кабельные линии монтаж", CANDS, limit=1)[0]
        b = boosted_rank("кабельные линии монтаж", CANDS, m, limit=1)[0]
        assert b.candidate_id == a.candidate_id
        assert b.score == a.score
        assert b.decision is a.decision

    def test_learning_lifts_review_to_auto(self):
        q = "кабельные линии монтаж"  # base ~81 REVIEW for candidate 11
        base = rank(q, CANDS, limit=1)[0]
        assert base.decision is Decision.REVIEW  # precondition

        m = MatchMemory()
        m.record(q, 11, times=5)  # +15 -> ~96
        top = boosted_rank(q, CANDS, m, limit=1)[0]
        assert top.candidate_id == 11
        assert top.score > base.score
        assert top.decision is Decision.AUTO

    def test_boost_is_bounded_cannot_manufacture_auto(self):
        # A weak (REJECT-band) match can be lifted to REVIEW but not AUTO
        # from a single learned mapping.
        q = "электроснабжение наружное освещение"  # base ~65 REJECT for 11
        base = rank(q, CANDS, limit=1)[0]
        assert base.decision is Decision.REJECT

        m = MatchMemory()
        m.record(q, base.candidate_id, times=10)  # capped +15 -> ~80
        top = boosted_rank(q, CANDS, m, limit=1)[0]
        assert top.score > base.score
        assert top.decision is Decision.REVIEW  # lifted, but NOT auto

    def test_perfect_score_stays_capped_at_100(self):
        q = "Главное здание ОКН"  # exact -> 100 AUTO
        m = MatchMemory()
        m.record(q, 10, times=5)
        top = boosted_rank(q, CANDS, m, limit=1)[0]
        assert top.score == 100.0
