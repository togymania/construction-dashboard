"""Tests for the AI Asistan document-QA core (pure parts)."""
from __future__ import annotations

from app.services.document_qa import (
    MAX_PER_DOC_CHARS,
    MAX_TOTAL_CONTEXT_CHARS,
    DocSnippet,
    build_context,
    fallback_answer,
    no_documents_answer,
    system_prompt,
    trim_history,
)


class TestTrimHistory:
    def test_keeps_last_messages_and_caps_length(self):
        history = [{"role": "user", "content": "x" * 5000}] * 10
        out = trim_history(history)
        assert len(out) == 6
        assert all(len(m["content"]) == 2000 for m in out)

    def test_drops_invalid_roles_and_empty(self):
        history = [
            {"role": "system", "content": "hack"},
            {"role": "user", "content": "  "},
            {"role": "user", "content": "soru"},
            {"role": "assistant", "content": "cevap"},
        ]
        out = trim_history(history)
        assert out == [
            {"role": "user", "content": "soru"},
            {"role": "assistant", "content": "cevap"},
        ]

    def test_leading_assistant_dropped(self):
        history = [
            {"role": "assistant", "content": "merhaba"},
            {"role": "user", "content": "soru"},
        ]
        out = trim_history(history)
        assert out[0]["role"] == "user"


class TestBuildContext:
    def test_includes_docs_and_contract_lines(self):
        ctx, used = build_context(
            [DocSnippet(name="dogovor.pdf", text="Cena 1 000 000 RUB", contract_label="DC-3")],
            ["- DC-3: fasad isleri | 1000000 RUB"],
        )
        assert "CONTRACT SUMMARY" in ctx
        assert "dogovor.pdf" in ctx
        assert "Cena 1 000 000 RUB" in ctx
        assert used == ["dogovor.pdf"]

    def test_per_doc_cap(self):
        big = "a" * (MAX_PER_DOC_CHARS + 10_000)
        ctx, used = build_context([DocSnippet(name="big.md", text=big)], [])
        assert used == ["big.md"]
        assert len(ctx) < MAX_PER_DOC_CHARS + 2_000

    def test_total_budget_stops_adding_docs(self):
        docs = [
            DocSnippet(name=f"d{i}.pdf", text="x" * MAX_PER_DOC_CHARS)
            for i in range(10)
        ]
        ctx, used = build_context(docs, [])
        assert len(ctx) <= MAX_TOTAL_CONTEXT_CHARS + 1_000
        assert 0 < len(used) < 10

    def test_empty_docs_skipped(self):
        ctx, used = build_context(
            [DocSnippet(name="empty.pdf", text="  "), DocSnippet(name="ok.md", text="icerik")],
            [],
        )
        assert used == ["ok.md"]


class TestPrompts:
    def test_turkish_prompt_forbids_invention(self):
        p = system_prompt("TR")
        assert "uydurma" in p
        assert "Turkce" in p

    def test_english_default(self):
        p = system_prompt("EN")
        assert "never invent" in p


class TestFallbacks:
    def test_fallback_lists_documents_tr(self):
        ans = fallback_answer(
            "ceza maddesi var mi?",
            [DocSnippet(name="dogovor.pdf", text="icerik")],
            ["- DC-3: fasad"],
            "TR",
        )
        assert "dogovor.pdf" in ans
        assert "kural tabanli" in ans

    def test_no_documents_answer_variants(self):
        assert "sozlesmesi ve dokumani yok" in no_documents_answer("TR", has_contracts=False)
        assert "Dokumanlar sekmesinden" in no_documents_answer("TR", has_contracts=True)
        assert "no contracts" in no_documents_answer("EN", has_contracts=False)
