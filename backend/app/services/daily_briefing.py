"""Daily AI briefing for the dashboard (Faz 4).

Pulls a snapshot of the last 24 hours of activity across the portfolio
(new expenses, payments, workforce snapshots, contract documents, project
state changes) and asks Claude to produce a 1-paragraph executive briefing
plus 3-5 bullet "next decisions". When no API key is set, a rule-based
fallback produces analogous copy so the dashboard never empties.

The briefing is cached for 1 hour and force-refreshable.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.expense import Expense, ExpenseStatus
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.project import Project, ProjectHealth, ProjectStatus
from app.models.subcontractor import (
    PaymentStatus as SubPaymentStatus,
    Subcontractor,
    SubcontractorContract,
    SubcontractorPayment,
)
from app.models.workforce import WorkforceSnapshot


# =============================================================================
# Public API
# =============================================================================


async def build_daily_briefing(
    db: AsyncSession,
    lang: str = "EN",
) -> dict[str, Any]:
    """Compute the dashboard daily briefing payload.

    Returns a dict shaped like:
    {
        "generated_at": "...",
        "headline": "1-sentence top-line",
        "summary": "1-paragraph executive summary",
        "highlights": ["bullet 1", "bullet 2", ...],
        "decisions": ["recommended action 1", ...],
        "facts": {...},                # raw numbers powering the narrative
        "source": "rule" | "llm",
    }
    """
    facts = await _collect_facts(db)
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()

    if api_key:
        narrative = _llm_briefing(facts, api_key, lang=lang)
    else:
        narrative = _rule_briefing(facts)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **narrative,
        "facts": facts,
    }


# =============================================================================
# Fact collection
# =============================================================================


async def _collect_facts(db: AsyncSession) -> dict[str, Any]:
    """Gather portfolio-level numbers for the past 24 hours + the broader trend."""
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)

    # ---- Portfolio overview ----
    project_rows = (
        await db.execute(
            select(
                Project.status,
                Project.health,
                func.count(Project.id),
                func.coalesce(func.sum(Project.budget_rub), 0),
            )
            .where(Project.is_active == True)  # noqa: E712
            .group_by(Project.status, Project.health)
        )
    ).all()

    total_active = 0
    total_at_risk = 0
    total_budget = Decimal("0")
    for status_v, health_v, cnt, budget in project_rows:
        cnt = int(cnt)
        total_budget += Decimal(budget or 0)
        if status_v == ProjectStatus.ACTIVE:
            total_active += cnt
            if health_v in (ProjectHealth.AT_RISK, ProjectHealth.DELAYED):
                total_at_risk += cnt

    # ---- New expenses in last 24h ----
    new_expenses_count = (
        await db.execute(
            select(func.count(Expense.id)).where(Expense.created_at >= one_day_ago)
        )
    ).scalar_one()
    new_expense_total = (
        await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.created_at >= one_day_ago,
                Expense.status == ExpenseStatus.PAID,
            )
        )
    ).scalar_one()

    # ---- New ledger entries in last 24h ----
    new_ledger_count = (
        await db.execute(
            select(func.count(LedgerEntry.id)).where(
                LedgerEntry.created_at >= one_day_ago
            )
        )
    ).scalar_one()

    # ---- Subcontractor payments in last 24h ----
    new_payments = (
        await db.execute(
            select(
                func.count(SubcontractorPayment.id),
                func.coalesce(func.sum(SubcontractorPayment.amount), 0),
            ).where(
                SubcontractorPayment.created_at >= one_day_ago,
                SubcontractorPayment.status == SubPaymentStatus.PAID,
            )
        )
    ).first()
    payments_paid_count = int(new_payments[0] or 0)
    payments_paid_total = Decimal(new_payments[1] or 0)

    # Pending payments overall (not 24h-scoped — these are open obligations)
    pending_payments_total = (
        await db.execute(
            select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
                SubcontractorPayment.status.in_(
                    [SubPaymentStatus.PENDING, SubPaymentStatus.APPROVED]
                )
            )
        )
    ).scalar_one()

    # ---- Workforce snapshots in last 24h ----
    workforce_snaps_24h = (
        await db.execute(
            select(func.count(WorkforceSnapshot.id)).where(
                WorkforceSnapshot.created_at >= one_day_ago
            )
        )
    ).scalar_one()
    # Today's vs last week's workforce
    today_present = (
        await db.execute(
            select(func.coalesce(func.sum(WorkforceSnapshot.total_present), 0)).where(
                WorkforceSnapshot.snapshot_date >= now.date() - timedelta(days=1)
            )
        )
    ).scalar_one()
    last_week_present = (
        await db.execute(
            select(func.coalesce(func.sum(WorkforceSnapshot.total_present), 0)).where(
                and_(
                    WorkforceSnapshot.snapshot_date >= seven_days_ago.date(),
                    WorkforceSnapshot.snapshot_date < seven_days_ago.date() + timedelta(days=1),
                )
            )
        )
    ).scalar_one()

    # ---- Recently added contracts ----
    new_contracts_count = (
        await db.execute(
            select(func.count(SubcontractorContract.id)).where(
                SubcontractorContract.created_at >= one_day_ago
            )
        )
    ).scalar_one()

    # ---- Active subcontractor count ----
    active_subs = (
        await db.execute(
            select(func.count(Subcontractor.id)).where(
                Subcontractor.is_active == True  # noqa: E712
            )
        )
    ).scalar_one()

    return {
        "active_projects": int(total_active),
        "at_risk_projects": int(total_at_risk),
        "total_budget_rub": float(total_budget),
        "active_subcontractors": int(active_subs),
        "new_expenses_24h": int(new_expenses_count),
        "new_expense_total_24h": float(new_expense_total),
        "new_ledger_entries_24h": int(new_ledger_count),
        "payments_paid_count_24h": payments_paid_count,
        "payments_paid_total_24h": float(payments_paid_total),
        "pending_payments_total": float(pending_payments_total),
        "workforce_snapshots_24h": int(workforce_snaps_24h),
        "today_workforce_present": int(today_present),
        "last_week_same_day_present": int(last_week_present),
        "new_contracts_24h": int(new_contracts_count),
    }


# =============================================================================
# Rule-based fallback narrative
# =============================================================================


def _rule_briefing(facts: dict[str, Any]) -> dict[str, Any]:
    parts: list[str] = []
    highlights: list[str] = []
    decisions: list[str] = []

    active = facts["active_projects"]
    at_risk = facts["at_risk_projects"]
    pending = facts["pending_payments_total"]

    headline = (
        f"{active} aktif proje · {at_risk} risk altında · "
        f"₽{int(pending):,} bekleyen ödeme"
    )

    parts.append(
        f"Portföy: {active} aktif proje, "
        f"toplam {int(facts['total_budget_rub']):,} ₽ bütçe, "
        f"{facts['active_subcontractors']} aktif alt yüklenici."
    )

    if facts["new_expenses_24h"] > 0:
        parts.append(
            f"Son 24 saatte {facts['new_expenses_24h']} yeni harcama "
            f"({int(facts['new_expense_total_24h']):,} ₽)."
        )
        highlights.append(
            f"{facts['new_expenses_24h']} yeni harcama girişi"
        )
    if facts["new_ledger_entries_24h"] > 0:
        highlights.append(
            f"Yevmiye defterine {facts['new_ledger_entries_24h']} yeni satır"
        )
    if facts["payments_paid_count_24h"] > 0:
        highlights.append(
            f"{facts['payments_paid_count_24h']} hakediş ödendi "
            f"({int(facts['payments_paid_total_24h']):,} ₽)"
        )
    if facts["workforce_snapshots_24h"] > 0:
        highlights.append(
            f"{facts['workforce_snapshots_24h']} puantaj snapshot yüklendi"
        )

    today_w = facts["today_workforce_present"]
    last_w = facts["last_week_same_day_present"]
    if today_w and last_w:
        diff = today_w - last_w
        pct = (diff / last_w * 100) if last_w else 0
        if abs(pct) >= 10:
            highlights.append(
                f"Sahada {today_w} kişi (geçen hafta aynı günde {last_w}) → "
                f"{'%' + f'{pct:+.0f}'}"
            )

    if at_risk > 0:
        decisions.append(
            f"{at_risk} proje 'risk altında' veya 'gecikmiş' olarak işaretli — "
            "yöneticilerle hızlı bir izleme toplantısı planla."
        )
    if pending > 0:
        decisions.append(
            f"₽{int(pending):,} bekleyen alt yüklenici hakkedişi — "
            "ödeme onay kuyruğunu denetle."
        )
    if facts["new_contracts_24h"] > 0:
        decisions.append(
            f"Son 24 saatte {facts['new_contracts_24h']} yeni kontrat eklendi — "
            "imza döngüsü ve tahsisleri doğrula."
        )
    if not decisions:
        decisions.append("Acil aksiyon yok; rutin takip yeterli.")

    if not highlights:
        highlights.append("Son 24 saat sessizdi; yeni hareket kaydedilmedi.")

    summary = " ".join(parts)

    return {
        "headline": headline,
        "summary": summary,
        "highlights": highlights[:5],
        "decisions": decisions[:5],
        "source": "rule",
    }


# =============================================================================
# LLM narrative
# =============================================================================


def _llm_briefing(
    facts: dict[str, Any],
    api_key: str,
    *,
    lang: str = "EN",
) -> dict[str, Any]:
    """Send the facts to Claude and parse a structured briefing JSON."""
    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS)
        # Hard language directive so Claude doesn't auto-detect from data and
        # leak Russian/Cyrillic into an English UI (or vice versa).
        lang_name = "Turkish" if lang.upper() == "TR" else "English"
        prompt = (
            "You are an executive assistant for a large-scale construction company. "
            "Given last-24h portfolio facts, produce a concise daily briefing in JSON. "
            f"Write ALL output text in {lang_name}, regardless of the language of "
            "the underlying data. Proper nouns (company names, people, projects) "
            "may stay in their original script. Tone: factual, no marketing.\n\n"
            "Facts:\n"
            f"```json\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n```\n\n"
            "Return ONLY a JSON object, no prose:\n"
            "{\n"
            '  "headline": "1 short sentence (≤90 chars) for top-of-dashboard",\n'
            '  "summary":  "1 short paragraph (≤350 chars) executive summary",\n'
            '  "highlights": ["3-5 bullet observations from the last 24h"],\n'
            '  "decisions": ["3-5 recommended actions (imperative, concrete)"]\n'
            "}\n"
        )

        msg = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text if msg.content else "{}"
        parsed = json.loads(_extract_json_block(raw))

        return {
            "headline": str(parsed.get("headline") or "")[:200] or _rule_briefing(facts)["headline"],
            "summary": str(parsed.get("summary") or "")[:600] or _rule_briefing(facts)["summary"],
            "highlights": _clean_str_list(parsed.get("highlights"), max_items=6)
            or _rule_briefing(facts)["highlights"],
            "decisions": _clean_str_list(parsed.get("decisions"), max_items=6)
            or _rule_briefing(facts)["decisions"],
            "source": "llm",
        }
    except Exception:
        return _rule_briefing(facts)


def _clean_str_list(raw: Any, *, max_items: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        s = str(item).strip()
        if s:
            out.append(s)
        if len(out) >= max_items:
            break
    return out


def _extract_json_block(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("{"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return "{}"
