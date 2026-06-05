"""AI Asistan — soru-cevap over subcontractor contract documents.

Pure helpers (context building, history trimming, fallback answers) are
separated from the Anthropic call so they can be unit-tested without a
network or API key. The orchestrating endpoint lives in
app/api/v1/endpoints/subcontractors.py.

Design rules
------------
* The assistant answers ONLY from the supplied documents + contract
  metadata. The system prompt forbids inventing clauses or numbers.
* When no API key is configured we degrade to an honest rule-based
  answer instead of failing.
* X-User-Lang drives the answer language (TR/EN).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---- Limits (chars, not tokens; ~4 chars/token heuristic) ----
MAX_PER_DOC_CHARS = 24_000
MAX_TOTAL_CONTEXT_CHARS = 90_000
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_MSG_CHARS = 2_000
MAX_QUESTION_CHARS = 4_000


@dataclass(frozen=True)
class DocSnippet:
    """One document's contribution to the QA context."""

    name: str
    text: str
    doc_type: str = "CONTRACT"
    contract_label: str = ""


@dataclass(frozen=True)
class QaResult:
    answer: str
    source: str  # "ai" | "fallback"
    used_documents: list[str] = field(default_factory=list)


def trim_history(history: list[dict]) -> list[dict]:
    """Keep only the last few messages, each capped, roles sanitised."""
    out: list[dict] = []
    for msg in history[-MAX_HISTORY_MESSAGES:]:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        out.append({"role": role, "content": content[:MAX_HISTORY_MSG_CHARS]})
    # Anthropic requires alternating roles starting with user; rather than
    # enforce strictly, just drop a leading assistant message if present.
    while out and out[0]["role"] == "assistant":
        out.pop(0)
    return out


def build_context(snippets: list[DocSnippet], contract_lines: list[str]) -> tuple[str, list[str]]:
    """Assemble the grounding context. Returns (context, used_doc_names).

    Documents are added newest-first by caller order until the total budget
    is exhausted; each document is individually capped so one huge contract
    cannot crowd out the rest.
    """
    parts: list[str] = []
    used: list[str] = []
    total = 0

    if contract_lines:
        head = "SOZLESME OZETI / CONTRACT SUMMARY:\n" + "\n".join(contract_lines[:40])
        parts.append(head)
        total += len(head)

    for s in snippets:
        text = (s.text or "").strip()
        if not text:
            continue
        body = text[:MAX_PER_DOC_CHARS]
        block = (
            f"\n===== DOKUMAN: {s.name} (tur: {s.doc_type}"
            + (f", sozlesme: {s.contract_label}" if s.contract_label else "")
            + f") =====\n{body}\n"
        )
        if total + len(block) > MAX_TOTAL_CONTEXT_CHARS:
            break
        parts.append(block)
        used.append(s.name)
        total += len(block)

    return "\n".join(parts), used


def system_prompt(lang: str) -> str:
    if (lang or "").upper() == "TR":
        return (
            "Sen bir insaat sirketinin sozlesme asistanisin. SADECE sana verilen "
            "dokuman icerikleri ve sozlesme ozetine dayanarak cevap ver. "
            "Bilgi dokumanlarda yoksa bunu acikca soyle; asla madde, tutar veya "
            "tarih uydurma. Tutarlari ve tarihleri dokumanda gectigi gibi aynen aktar. "
            "Hangi dokumana dayandigini belirt. Kisa, net ve maddeler halinde cevapla. "
            "Turkce cevap ver."
        )
    return (
        "You are a construction-company contracts assistant. Answer ONLY from the "
        "provided document contents and contract summary. If the information is not "
        "in the documents, say so explicitly; never invent clauses, amounts or dates. "
        "Quote amounts and dates exactly as written. Mention which document you are "
        "relying on. Be concise and structured. Answer in English."
    )


def fallback_answer(
    question: str,
    snippets: list[DocSnippet],
    contract_lines: list[str],
    lang: str,
) -> str:
    """Rule-based degradation when no API key (or the LLM call failed)."""
    tr = (lang or "").upper() == "TR"
    names = [s.name for s in snippets if (s.text or "").strip()]
    lines: list[str] = []
    if tr:
        lines.append(
            "AI asistan su anda kural tabanli modda (ANTHROPIC_API_KEY yapilandirilmamis "
            "veya AI cagrisi basarisiz oldu); dokuman icerigini yorumlayamiyorum."
        )
        if names:
            lines.append("Yuklu dokumanlar: " + ", ".join(names[:10]))
        if contract_lines:
            lines.append("Sozlesme ozeti:")
            lines.extend(contract_lines[:8])
        lines.append(
            "API anahtari eklendiginde ayni soruyu tekrar sorabilirsin; "
            "dokumanlardan gercek icerikle cevaplayacagim."
        )
    else:
        lines.append(
            "The AI assistant is in rule-based mode (ANTHROPIC_API_KEY is not configured "
            "or the AI call failed), so I cannot interpret document contents."
        )
        if names:
            lines.append("Uploaded documents: " + ", ".join(names[:10]))
        if contract_lines:
            lines.append("Contract summary:")
            lines.extend(contract_lines[:8])
        lines.append("Once an API key is added, ask again for a real answer.")
    return "\n".join(lines)


def no_documents_answer(lang: str, has_contracts: bool) -> str:
    if (lang or "").upper() == "TR":
        if has_contracts:
            return (
                "Bu taserona ait okunabilir dokuman bulamadim. Dokumanlar sekmesinden "
                "PDF veya .md dosyasi yukledikten sonra sorularini cevaplayabilirim."
            )
        return (
            "Bu taseronun henuz sozlesmesi ve dokumani yok. Once Sozlesmeler sekmesinden "
            "sozlesme olustur, sonra Dokumanlar sekmesinden dosya yukle."
        )
    if has_contracts:
        return (
            "I could not find any readable documents for this subcontractor. Upload a "
            "PDF or .md file from the Documents tab and ask again."
        )
    return (
        "This subcontractor has no contracts or documents yet. Create a contract first, "
        "then upload documents."
    )


def answer_with_ai(
    question: str,
    context: str,
    history: list[dict],
    *,
    lang: str = "EN",
    api_key: str | None = None,
    model: str = "claude-sonnet-4-5",
    timeout: int = 60,
) -> str | None:
    """Real Claude call. Returns None on any failure so the caller can degrade."""
    if not api_key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        messages: list[dict] = list(trim_history(history))
        user_block = (
            "Belgeler ve sozlesme ozeti asagida.\n\n"
            f"{context}\n\n"
            "SORU / QUESTION:\n"
            f"{question[:MAX_QUESTION_CHARS]}"
        )
        messages.append({"role": "user", "content": user_block})
        msg = client.messages.create(
            model=model,
            max_tokens=1500,
            system=system_prompt(lang),
            messages=messages,
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        ).strip()
        return text or None
    except Exception:
        return None
