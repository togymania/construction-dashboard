"""Project Executive Report (Faz 5) — 1-2 page AI-narrated digest.

Pulls everything we have on a project (budget, variance, subcontractors,
workforce, contracts, risks) and asks Claude to produce a narrative report
that an executive can read in 5 minutes and walk into a meeting prepared.

When no API key is set, a rule-based fallback produces a slightly drier
version of the same report — same shape, different prose.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.budget import BudgetItem
from app.models.budget_category import BudgetCategory
from app.models.expense import Expense, ExpenseStatus
from app.models.project import Project, ProjectHealth, ProjectStatus
from app.models.subcontractor import (
    PaymentStatus as SubPaymentStatus,
    Subcontractor,
    SubcontractorContract,
    SubcontractorPayment,
)
from app.models.workforce import WorkforceSnapshot
from app.services.budget_variance import build_variance_report


async def build_executive_report(
    db: AsyncSession,
    project_id: int,
) -> dict[str, Any] | None:
    """Build the executive report payload for a single project.

    Returns None if the project doesn't exist. Otherwise returns a dict
    shaped per the schema (see ProjectExecutiveReport).
    """
    project = await db.get(Project, project_id)
    if project is None:
        return None

    facts = await _collect_project_facts(db, project)
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()

    if api_key:
        narrative = _llm_report(facts, api_key)
    else:
        narrative = _rule_report(facts)

    return {
        "project_id": project.id,
        "project_name": project.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **narrative,
        "facts": facts,
    }


# =============================================================================
# Fact collection
# =============================================================================


async def _collect_project_facts(
    db: AsyncSession,
    project: Project,
) -> dict[str, Any]:
    """Gather every signal we have on this project."""
    now = datetime.now(timezone.utc)

    # ---- Budget variance (heavyweight call — but fact-rich) ----
    variance = await build_variance_report(db, project.id)

    # ---- Subcontractor + contract aggregates for this project ----
    contracts_stmt = (
        select(SubcontractorContract)
        .where(SubcontractorContract.project_id == project.id)
        .options(selectinload(SubcontractorContract.subcontractor))
    )
    contracts = list((await db.execute(contracts_stmt)).scalars().all())

    contract_ids = [c.id for c in contracts]
    paid_total = Decimal("0")
    pending_total = Decimal("0")
    delay_samples: list[int] = []
    if contract_ids:
        paid_stmt = select(
            func.coalesce(func.sum(SubcontractorPayment.amount), 0)
        ).where(
            SubcontractorPayment.contract_id.in_(contract_ids),
            SubcontractorPayment.status == SubPaymentStatus.PAID,
        )
        paid_total = Decimal((await db.execute(paid_stmt)).scalar_one())

        pending_stmt = select(
            func.coalesce(func.sum(SubcontractorPayment.amount), 0)
        ).where(
            SubcontractorPayment.contract_id.in_(contract_ids),
            SubcontractorPayment.status.in_(
                [SubPaymentStatus.PENDING, SubPaymentStatus.APPROVED]
            ),
        )
        pending_total = Decimal((await db.execute(pending_stmt)).scalar_one())

        # Avg delay
        delay_rows = (
            await db.execute(
                select(
                    SubcontractorPayment.payment_date,
                    SubcontractorPayment.due_date,
                ).where(
                    SubcontractorPayment.contract_id.in_(contract_ids),
                    SubcontractorPayment.status == SubPaymentStatus.PAID,
                    SubcontractorPayment.due_date.is_not(None),
                )
            )
        ).all()
        for pd, dd in delay_rows:
            if pd and dd:
                delay_samples.append((pd - dd).days)

    avg_delay = (
        round(sum(delay_samples) / len(delay_samples), 1) if delay_samples else None
    )

    # ---- Subcontractor leaderboard (top 5 by contract value) ----
    sub_value: dict[int, dict[str, Any]] = {}
    for c in contracts:
        sid = c.subcontractor_id
        slot = sub_value.setdefault(
            sid,
            {
                "subcontractor_id": sid,
                "name": c.subcontractor.name if c.subcontractor else "?",
                "total_value": Decimal("0"),
                "active_contracts": 0,
            },
        )
        slot["total_value"] += c.contract_amount or Decimal("0")
        if c.status.value == "active":
            slot["active_contracts"] += 1
    top_subs = sorted(
        sub_value.values(), key=lambda x: x["total_value"], reverse=True
    )[:5]

    # ---- Workforce trend (last 7 days vs prior 7) ----
    seven = now.date() - timedelta(days=7)
    fourteen = now.date() - timedelta(days=14)
    last_week_present = (
        await db.execute(
            select(func.coalesce(func.sum(WorkforceSnapshot.total_present), 0)).where(
                WorkforceSnapshot.project_id == project.id,
                WorkforceSnapshot.snapshot_date >= seven,
            )
        )
    ).scalar_one()
    prior_week_present = (
        await db.execute(
            select(func.coalesce(func.sum(WorkforceSnapshot.total_present), 0)).where(
                WorkforceSnapshot.project_id == project.id,
                WorkforceSnapshot.snapshot_date >= fourteen,
                WorkforceSnapshot.snapshot_date < seven,
            )
        )
    ).scalar_one()

    # ---- Top variance offenders (over budget) ----
    over_items = [
        {
            "cost_code": it.cost_code,
            "description": it.description,
            "planned": float(it.planned_amount),
            "actual": float(it.actual_amount),
            "variance": float(it.variance),
            "variance_pct": it.variance_pct,
        }
        for it in variance.items
        if it.severity == "over"
    ][:6]

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "location": project.location,
            "status": project.status.value,
            "health": project.health.value,
            "progress_pct": float(project.progress_pct),
            "budget_rub": float(project.budget_rub),
            "start_date": project.start_date.isoformat(),
            "end_date": project.end_date.isoformat(),
            "description": project.description,
        },
        "budget": {
            "total_planned": float(variance.total_planned),
            "total_committed": float(variance.total_committed),
            "total_actual": float(variance.total_actual),
            "overall_variance": float(variance.overall_variance),
            "overall_variance_pct": variance.overall_variance_pct,
            "over_budget_items": over_items,
            "items_count": len(variance.items),
        },
        "subcontractors": {
            "active_count": len({c.subcontractor_id for c in contracts}),
            "contract_count": len(contracts),
            "total_paid": float(paid_total),
            "total_pending": float(pending_total),
            "avg_payment_delay_days": avg_delay,
            "top_5": [
                {
                    **s,
                    "total_value": float(s["total_value"]),
                }
                for s in top_subs
            ],
        },
        "workforce": {
            "last_7_days_total": int(last_week_present),
            "prior_7_days_total": int(prior_week_present),
            "delta_pct": (
                float((last_week_present - prior_week_present) / prior_week_present * 100)
                if prior_week_present
                else None
            ),
        },
    }


# =============================================================================
# Rule-based narrative
# =============================================================================


def _rule_report(facts: dict[str, Any]) -> dict[str, Any]:
    proj = facts["project"]
    budget = facts["budget"]
    subs = facts["subcontractors"]
    wf = facts["workforce"]

    headline = (
        f"{proj['name']} · {proj['health']} · "
        f"%{proj['progress_pct']:.0f} ilerleme · "
        f"%{budget['overall_variance_pct']:.0f} bütçe sapması"
        if budget.get("overall_variance_pct") is not None
        else f"{proj['name']} · {proj['health']} · %{proj['progress_pct']:.0f}"
    )

    summary_parts: list[str] = [
        f"{proj['name']} ({proj['location']}) {proj['status']} durumda, "
        f"%{proj['progress_pct']:.0f} tamamlandı.",
    ]
    if budget["total_planned"] > 0:
        summary_parts.append(
            f"Planlanan ₽{int(budget['total_planned']):,}, "
            f"gerçekleşen ₽{int(budget['total_actual']):,}; "
            f"sapma ₽{int(budget['overall_variance']):,}"
            + (
                f" (%{budget['overall_variance_pct']:.1f})"
                if budget["overall_variance_pct"] is not None
                else ""
            )
            + "."
        )
    if subs["contract_count"] > 0:
        summary_parts.append(
            f"{subs['active_count']} alt yüklenici ile {subs['contract_count']} "
            f"kontrat aktif. ₽{int(subs['total_paid']):,} ödendi, "
            f"₽{int(subs['total_pending']):,} bekliyor."
        )
    if wf["last_7_days_total"]:
        summary_parts.append(
            f"Son 7 günde sahada {wf['last_7_days_total']} kişi-gün."
        )

    sections = {
        "executive_summary": " ".join(summary_parts),
        "financial_status": (
            f"Bütçe sapması "
            + (
                f"%{budget['overall_variance_pct']:+.1f}"
                if budget["overall_variance_pct"] is not None
                else "n/a"
            )
            + ". "
            + (
                f"{len(budget['over_budget_items'])} kalem bütçeyi aşmış durumda — "
                "denetim önerilir."
                if budget["over_budget_items"]
                else "Bütçe sınırları içinde, kritik aşım yok."
            )
        ),
        "critical_risks": _format_risks(budget, subs, wf),
        "subcontractor_performance": _format_sub_perf(subs),
        "workforce_health": _format_workforce(wf),
        "next_30_days": _format_outlook(proj, budget, subs),
    }

    actions: list[str] = []
    if budget["over_budget_items"]:
        actions.append(
            f"{len(budget['over_budget_items'])} bütçe aşımını yönetim ile değerlendir."
        )
    if subs["avg_payment_delay_days"] and subs["avg_payment_delay_days"] > 18:
        actions.append(
            f"Hakkediş gecikmesi ortalama {subs['avg_payment_delay_days']:.0f} gün — "
            "treasury ile gözden geçir."
        )
    if subs["total_pending"] > 0:
        actions.append(
            f"₽{int(subs['total_pending']):,} bekleyen ödemeyi takipte tut."
        )
    if proj["health"] in ("at_risk", "delayed"):
        actions.append("Proje sağlığı kötüleşmiş — hızlı durum toplantısı planla.")
    if not actions:
        actions.append("Acil aksiyon yok; rutin takip yeterli.")

    return {
        "headline": headline,
        "sections": sections,
        "recommended_actions": actions[:6],
        "source": "rule",
    }


def _format_risks(budget: dict, subs: dict, wf: dict) -> str:
    bullets: list[str] = []
    for item in budget.get("over_budget_items", [])[:3]:
        bullets.append(
            f"{item['description']}: planlanan ₽{int(item['planned']):,}, "
            f"gerçekleşen ₽{int(item['actual']):,}"
        )
    if subs.get("avg_payment_delay_days") and subs["avg_payment_delay_days"] > 18:
        bullets.append(
            f"Ortalama hakediş gecikmesi {subs['avg_payment_delay_days']:.0f} gün."
        )
    delta = wf.get("delta_pct")
    if delta is not None and delta < -15:
        bullets.append(
            f"İşgücü %{abs(delta):.0f} düşmüş — verimlilik etkisi kontrol edilmeli."
        )
    if not bullets:
        return "Kritik risk işareti yok; mevcut göstergeler normal aralıkta."
    return " · ".join(bullets)


def _format_sub_perf(subs: dict) -> str:
    if subs["contract_count"] == 0:
        return "Bu projede aktif alt yüklenici yok."
    leaders = subs.get("top_5", [])
    if not leaders:
        return f"{subs['active_count']} alt yüklenici aktif."
    top_line = ", ".join(
        f"{s['name']} (₽{int(s['total_value']):,})" for s in leaders[:3]
    )
    return (
        f"{subs['active_count']} aktif alt yüklenici, "
        f"toplam ₽{int(subs['total_paid']):,} ödendi. "
        f"En büyük sözleşmeler: {top_line}."
    )


def _format_workforce(wf: dict) -> str:
    if not wf["last_7_days_total"]:
        return "Son 7 gün için işgücü kaydı yok."
    delta = wf.get("delta_pct")
    if delta is None:
        return f"Son 7 günde sahada {wf['last_7_days_total']} kişi-gün."
    direction = "arttı" if delta >= 0 else "düştü"
    return (
        f"Son 7 günde sahada {wf['last_7_days_total']} kişi-gün — "
        f"önceki haftaya göre %{abs(delta):.0f} {direction}."
    )


def _format_outlook(proj: dict, budget: dict, subs: dict) -> str:
    bits: list[str] = []
    bits.append(
        f"Proje bitiş tarihi {proj['end_date']}; mevcut tempoda hedeflere ulaşma "
        + (
            "ihtimali yüksek."
            if proj["health"] == "on_track"
            else "ihtimali kritik gözden geçirme gerektirir."
        )
    )
    if budget["overall_variance_pct"] is not None and budget["overall_variance_pct"] > 5:
        bits.append("Bütçe baskısı önümüzdeki 30 günde artabilir.")
    if subs["total_pending"] > 0:
        bits.append(
            f"₽{int(subs['total_pending']):,} bekleyen ödemenin %30+'ı ay sonu "
            "yaklaşırken kapatılmalı."
        )
    return " ".join(bits)


# =============================================================================
# LLM narrative
# =============================================================================


def _llm_report(facts: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Send the facts to Claude and parse a structured executive report."""
    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS)
        prompt = (
            "You are an executive assistant for a large-scale construction company. "
            "Given the project facts below, produce a 1-2 page executive report in JSON. "
            "Tone: factual, decisive, NO marketing language. Match the team's "
            "language (Turkish if data feels Turkish/Russian, otherwise English). "
            "Each section is 1-3 sentences.\n\n"
            "Facts:\n"
            f"```json\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n```\n\n"
            "Return ONLY a JSON object with this exact shape, no prose around it:\n"
            "{\n"
            '  "headline": "1 sentence (≤120 chars) for the report cover",\n'
            '  "sections": {\n'
            '    "executive_summary":         "1 paragraph",\n'
            '    "financial_status":          "1-3 sentences",\n'
            '    "critical_risks":            "1-3 sentences (or bullet-style joined w/ ; )",\n'
            '    "subcontractor_performance": "1-3 sentences",\n'
            '    "workforce_health":          "1-2 sentences",\n'
            '    "next_30_days":              "1-3 sentences forward-looking"\n'
            "  },\n"
            '  "recommended_actions": ["3-6 imperative bullets"]\n'
            "}\n"
        )

        msg = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text if msg.content else "{}"
        parsed = json.loads(_extract_json_block(raw))

        rule_fallback = _rule_report(facts)
        sections_in = parsed.get("sections") or {}
        sections = {}
        for key in (
            "executive_summary",
            "financial_status",
            "critical_risks",
            "subcontractor_performance",
            "workforce_health",
            "next_30_days",
        ):
            val = str(sections_in.get(key) or "").strip()
            sections[key] = val or rule_fallback["sections"].get(key, "")

        actions_raw = parsed.get("recommended_actions") or []
        actions = [str(a).strip() for a in actions_raw if str(a).strip()][:6]
        if not actions:
            actions = rule_fallback["recommended_actions"]

        return {
            "headline": str(parsed.get("headline") or "").strip() or rule_fallback["headline"],
            "sections": sections,
            "recommended_actions": actions,
            "source": "llm",
        }
    except Exception:
        return _rule_report(facts)


def _extract_json_block(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("{"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return "{}"
