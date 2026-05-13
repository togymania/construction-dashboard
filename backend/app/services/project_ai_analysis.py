"""AI Project Analysis service.

Wraps a single project's data (schedule, finance, workforce, ledger
quality) into structured facts and asks Claude to produce a 6-section
executive briefing. When Claude is unavailable, a rule-based fallback
produces a parallel structure so the page never renders empty.

The 6 sections mirror the prompt template the product owner supplied:

  🔴 Subcontractor & Schedule
  🟠 Data Quality
  🟡 Financial (EAC)
  🟢 Workforce / Productivity
  🔵 Risk Analysis & Forecast
  🧠 Executive Summary

The LLM is instructed to write all output in the requested UI language
(EN or TR) regardless of the language of the underlying records;
proper nouns (company names, people) may stay in their original script.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.budget import BudgetItem
from app.models.expense import Expense
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.project import Project
from app.models.subcontractor import (
    ContractStatus,
    Subcontractor,
    SubcontractorContract,
)
from app.models.workforce import WorkforceSnapshot
from app.schemas.project_ai_analysis import (
    CriticalDelay,
    DataQualitySection,
    DisciplineDelay,
    ExecutiveSection,
    FinancialSection,
    ProductivitySection,
    ProjectAIAnalysis,
    RiskSection,
    ScheduleSection,
    SuggestedMatch,
    TopRisk,
)


# =============================================================================
# Public entry point
# =============================================================================


async def build_ai_analysis(
    db: AsyncSession,
    project_id: int,
    *,
    lang: str = "EN",
) -> ProjectAIAnalysis | None:
    """Build the full 6-section analysis for a project.

    Returns None when the project doesn't exist. Otherwise returns the
    populated analysis -- LLM-narrated when ANTHROPIC_API_KEY is set,
    rule-based otherwise.
    """
    project = await db.get(Project, project_id)
    if project is None:
        return None

    facts = await _collect_facts(db, project)
    api_key = (settings.ANTHROPIC_API_KEY or "").strip()

    if api_key:
        narrative = _llm_analysis(facts, api_key, lang=lang)
        if narrative is not None:
            narrative["source"] = "llm"
            return _assemble(project_id, lang, narrative)

    # Rule fallback
    narrative = _rule_analysis(facts)
    narrative["source"] = "rule"
    return _assemble(project_id, lang, narrative)


def _assemble(
    project_id: int,
    lang: str,
    narrative: dict[str, Any],
) -> ProjectAIAnalysis:
    """Validate the narrative dict into the response model."""
    return ProjectAIAnalysis(
        project_id=project_id,
        generated_at=datetime.now(timezone.utc),
        lang="TR" if lang.upper() == "TR" else "EN",
        source=narrative.get("source", "rule"),  # type: ignore[arg-type]
        schedule=ScheduleSection(**narrative["schedule"]),
        data_quality=DataQualitySection(**narrative["data_quality"]),
        financial=FinancialSection(**narrative["financial"]),
        productivity=ProductivitySection(**narrative["productivity"]),
        risk=RiskSection(**narrative["risk"]),
        executive=ExecutiveSection(**narrative["executive"]),
    )


# =============================================================================
# Fact collection -- pull everything once, hand off to LLM or rule engine
# =============================================================================


async def _collect_facts(db: AsyncSession, project: Project) -> dict[str, Any]:
    today = date.today()
    project_id = project.id

    # ---- Contracts (with subcontractor join) ----
    contracts_stmt = (
        select(SubcontractorContract, Subcontractor)
        .join(Subcontractor, Subcontractor.id == SubcontractorContract.subcontractor_id)
        .where(SubcontractorContract.project_id == project_id)
    )
    contract_rows = (await db.execute(contracts_stmt)).all()

    total_contracts = len(contract_rows)
    overdue: list[dict[str, Any]] = []
    by_discipline: dict[str, dict[str, int]] = {}

    for contract, sub in contract_rows:
        if contract.status == ContractStatus.ACTIVE and contract.end_date < today:
            days_overdue = (today - contract.end_date).days
            overdue.append({
                "subcontractor": sub.name,
                "contract_id": contract.id,
                "days": int(days_overdue),
                "reason": f"End date {contract.end_date.isoformat()} passed",
            })
            disc = (sub.specialization or "Unknown").strip() or "Unknown"
            bucket = by_discipline.setdefault(disc, {"delayed_count": 0, "delay_days": 0})
            bucket["delayed_count"] += 1
            bucket["delay_days"] += int(days_overdue)

    # ---- Budget items (Budget at Completion) ----
    bac = Decimal((await db.execute(
        select(func.coalesce(func.sum(BudgetItem.planned_amount), 0))
        .where(BudgetItem.project_id == project_id)
    )).scalar_one() or 0)

    # If no budget_items defined, fall back to project.budget_rub so
    # EAC math doesn't divide by zero on a partially-set-up project.
    if bac == 0:
        bac = Decimal(project.budget_rub or 0)

    # ---- Actual cost (AC): ledger EXPENSE + classic expenses table ----
    # LedgerEntry has no project_id of its own; it's tied to a contract,
    # which carries the project_id. Join through the contract to scope
    # spend per project.
    ledger_ac = Decimal((await db.execute(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .join(SubcontractorContract, SubcontractorContract.id == LedgerEntry.contract_id)
        .where(
            SubcontractorContract.project_id == project_id,
            LedgerEntry.entry_type == LedgerEntryType.EXPENSE,
        )
    )).scalar_one() or 0)

    expense_ac = Decimal((await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.project_id == project_id)
    )).scalar_one() or 0)
    ac = ledger_ac + expense_ac

    progress_pct = float(project.progress_pct or 0)
    ev = bac * Decimal(progress_pct / 100.0) if bac > 0 else Decimal(0)
    cpi = float(ev / ac) if ac > 0 else 1.0
    eac = ac + (bac - ev) / Decimal(cpi if cpi > 0 else 1.0)
    variance = bac - eac
    budget_used_pct = float(ac / bac * 100) if bac > 0 else 0.0

    if bac == 0:
        fin_status = "UNKNOWN"
    elif eac > bac * Decimal("1.05"):
        fin_status = "OVER_BUDGET"
    elif eac < bac * Decimal("0.95"):
        fin_status = "UNDER_BUDGET"
    else:
        fin_status = "ON_TRACK"

    # ---- Data quality (portfolio-wide for now) ----
    # LedgerEntry isn't project-scoped at the row level. Unassigned rows
    # by definition have no project context. We report portfolio totals
    # so the user can see the cleanup queue from any project's analysis.
    uncategorized = int((await db.execute(
        select(func.count(LedgerEntry.id)).where(LedgerEntry.budget_code.is_(None))
    )).scalar_one() or 0)
    unassigned = int((await db.execute(
        select(func.count(LedgerEntry.id)).where(
            LedgerEntry.subcontractor_id.is_(None),
            LedgerEntry.entry_type == LedgerEntryType.EXPENSE,
        )
    )).scalar_one() or 0)

    # Risk level based on combined ratio of dirty rows
    total_entries = int((await db.execute(
        select(func.count(LedgerEntry.id))
    )).scalar_one() or 0)
    dirty_ratio = ((uncategorized + unassigned) / total_entries) if total_entries > 0 else 0.0
    if dirty_ratio >= 0.4:
        dq_risk = "HIGH"
    elif dirty_ratio >= 0.15:
        dq_risk = "MEDIUM"
    else:
        dq_risk = "LOW"

    # ---- Suggested matches (top 10 unassigned + fuzzy match to subs) ----
    # Lightweight rapidfuzz-based suggestion. Skip if the optional dep
    # isn't installed so the service stays resilient.
    suggested_matches: list[dict[str, Any]] = []
    try:
        from rapidfuzz import fuzz, process  # type: ignore

        sub_names = [(sub.id, sub.name) for _, sub in contract_rows]
        # Dedupe sub names
        seen = set()
        deduped_subs = []
        for sid, name in sub_names:
            if sid not in seen:
                seen.add(sid)
                deduped_subs.append((sid, name))

        if deduped_subs:
            sample = (await db.execute(
                select(LedgerEntry.id, LedgerEntry.description)
                .where(
                    LedgerEntry.subcontractor_id.is_(None),
                    LedgerEntry.entry_type == LedgerEntryType.EXPENSE,
                )
                .limit(50)
            )).all()
            for entry_id, desc in sample:
                if not desc:
                    continue
                best = process.extractOne(
                    desc,
                    [name for _, name in deduped_subs],
                    scorer=fuzz.partial_ratio,
                )
                if best and best[1] >= 70:
                    suggested_matches.append({
                        "entry_id": int(entry_id),
                        "description": desc[:120],
                        "suggested_target": str(best[0]),
                        "confidence": round(best[1] / 100.0, 2),
                    })
                if len(suggested_matches) >= 5:
                    break
    except ImportError:
        pass

    # ---- Workforce ----
    latest_snapshot = (await db.execute(
        select(WorkforceSnapshot)
        .where(WorkforceSnapshot.project_id == project_id)
        .order_by(WorkforceSnapshot.snapshot_date.desc())
        .limit(1)
    )).scalar_one_or_none()

    headcount = 0
    man_hours = 0.0
    if latest_snapshot is not None:
        # Snapshot already holds denormalized total_present (headcount).
        # man-hours are not tracked separately yet -- estimate as
        # headcount * 10h (standard inşaat shift) so the productivity
        # card has *some* number for Claude to reason about. Marked
        # explicitly as an estimate downstream.
        headcount = int(latest_snapshot.total_present or 0)
        man_hours = float(headcount * 10)

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "budget_rub": float(project.budget_rub or 0),
            "progress_pct": progress_pct,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "days_until_end": (project.end_date - today).days if project.end_date else None,
        },
        "schedule": {
            "total_contracts": total_contracts,
            "overdue": overdue,
            "by_discipline": by_discipline,
            "total_delay_days": sum(o["days"] for o in overdue),
        },
        "data_quality": {
            "uncategorized_count": uncategorized,
            "unassigned_count": unassigned,
            "total_entries": total_entries,
            "dirty_ratio": round(dirty_ratio, 3),
            "risk_level": dq_risk,
            "suggested_matches": suggested_matches,
        },
        "financial": {
            "bac": float(bac),
            "ac": float(ac),
            "ev": float(ev),
            "cpi": round(cpi, 3),
            "eac": float(eac),
            "variance": float(variance),
            "progress_pct": progress_pct,
            "budget_used_pct": round(budget_used_pct, 2),
            "status": fin_status,
        },
        "productivity": {
            "headcount": headcount,
            "man_hours": man_hours,
            "snapshot_date": latest_snapshot.snapshot_date.isoformat() if latest_snapshot else None,
        },
    }


# =============================================================================
# LLM narrative
# =============================================================================


def _llm_analysis(
    facts: dict[str, Any],
    api_key: str,
    *,
    lang: str = "EN",
) -> dict[str, Any] | None:
    """Send the facts to Claude and parse a 6-section structured response.

    Returns None on any failure so the caller can fall back to the rule
    engine instead of leaking a half-broken response to the client.
    """
    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS)
        lang_name = "Turkish" if lang.upper() == "TR" else "English"
        prompt = _build_prompt(facts, lang_name)
        msg = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text if msg.content else "{}"
        parsed = json.loads(_extract_json_block(raw))

        # Validate the shape minimally -- presence of all 6 sections
        required = {"schedule", "data_quality", "financial", "productivity", "risk", "executive"}
        if not required.issubset(parsed.keys()):
            return None

        # Merge with raw facts so deterministic numbers stay correct
        # even if Claude reformats them: numeric fields trust the facts,
        # text fields trust Claude. This avoids hallucinated EAC numbers
        # while keeping the AI's qualitative judgement.
        parsed["financial"] = {**parsed.get("financial", {}), **facts["financial"]}
        # Keep the deterministic counts in data_quality, allow Claude to
        # add the risk_level narrative and suggested_matches enrichment
        dq = parsed.get("data_quality", {})
        dq["uncategorized_count"] = facts["data_quality"]["uncategorized_count"]
        dq["unassigned_count"] = facts["data_quality"]["unassigned_count"]
        if not dq.get("suggested_matches"):
            dq["suggested_matches"] = facts["data_quality"]["suggested_matches"]
        parsed["data_quality"] = dq

        # Schedule: trust the contract list we collected, let Claude
        # synthesize the discipline_delays narrative if it provided one
        parsed["schedule"]["delayed_contracts"] = len(facts["schedule"]["overdue"])
        parsed["schedule"]["total_contracts"] = facts["schedule"]["total_contracts"]
        parsed["schedule"]["total_delay_days"] = facts["schedule"]["total_delay_days"]
        # Map the overdue list to the CriticalDelay shape if Claude
        # didn't already produce it
        if not parsed["schedule"].get("critical_delays"):
            parsed["schedule"]["critical_delays"] = facts["schedule"]["overdue"][:5]
        # discipline_delays
        if not parsed["schedule"].get("discipline_delays"):
            parsed["schedule"]["discipline_delays"] = [
                {"discipline": k, **v}
                for k, v in facts["schedule"]["by_discipline"].items()
            ]

        # Productivity: bring back the headcount/man_hours from facts
        prod = parsed.get("productivity", {})
        prod["headcount"] = facts["productivity"]["headcount"]
        prod["man_hours"] = facts["productivity"]["man_hours"]
        parsed["productivity"] = prod

        return parsed
    except Exception:
        # Logging is the caller's responsibility; we never raise so the
        # rule fallback can still serve the page.
        return None


def _build_prompt(facts: dict[str, Any], lang_name: str) -> str:
    """Compose the system+user prompt for Claude.

    The output schema mirrors the 6 sections defined by the product
    owner. We force Claude into a JSON envelope so the parser stays
    deterministic.
    """
    return (
        "You are an advanced project-control, finance and risk-analysis "
        "AI for large-scale construction projects.\n"
        "Your goal: analyse the supplied project data and help managers "
        "make fast, accurate decisions. Back claims with the supplied "
        f"numbers. Write ALL output text in {lang_name} regardless of "
        "the language of the data. Proper nouns (company names, people, "
        "project names) may stay in their original script.\n\n"
        "Facts:\n"
        f"```json\n{json.dumps(facts, ensure_ascii=False, indent=2, default=str)}\n```\n\n"
        "Return ONLY a JSON object matching this exact shape, no prose around it:\n"
        "{\n"
        '  "schedule": {\n'
        '    "delayed_contracts": <int>,\n'
        '    "total_contracts": <int>,\n'
        '    "critical_delays": [ { "subcontractor":"...", "contract_id":<int>, "days":<int>, "reason":"..." } ],\n'
        '    "discipline_delays": [ { "discipline":"...", "delayed_count":<int>, "delay_days":<int> } ],\n'
        '    "total_delay_days": <int>\n'
        '  },\n'
        '  "data_quality": {\n'
        '    "uncategorized_count": <int>,\n'
        '    "unassigned_count": <int>,\n'
        '    "suggested_matches": [ { "entry_id":<int|null>, "description":"...", "suggested_target":"...", "confidence":<0..1> } ],\n'
        '    "risk_level": "LOW" | "MEDIUM" | "HIGH"\n'
        '  },\n'
        '  "financial": {\n'
        '    "progress_pct": <float>, "budget_used_pct": <float>,\n'
        '    "bac": <float>, "ac": <float>, "eac": <float>, "variance": <float>,\n'
        '    "status": "OVER_BUDGET" | "ON_TRACK" | "UNDER_BUDGET" | "UNKNOWN"\n'
        '  },\n'
        '  "productivity": {\n'
        '    "headcount": <int>, "man_hours": <float>,\n'
        '    "productivity": <float|null>, "deviation_pct": <float|null>,\n'
        '    "status": "GOOD" | "AVERAGE" | "LOW" | "UNKNOWN"\n'
        '  },\n'
        '  "risk": {\n'
        '    "overall_risk": "LOW" | "MEDIUM" | "HIGH",\n'
        '    "predicted_delay_days": <int>,\n'
        '    "top_risks": [ { "title":"...", "impact":"...", "cause":"..." } ]\n'
        '  },\n'
        '  "executive": {\n'
        '    "project_status": "GOOD" | "WARNING" | "CRITICAL",\n'
        '    "biggest_problem": "...",\n'
        '    "financial_status": "...",\n'
        '    "schedule_status": "...",\n'
        '    "urgent_action": "...",\n'
        '    "summary": "≤4 sentences, factual"\n'
        '  }\n'
        "}\n"
        "When a metric cannot be computed from the data, set its numeric "
        "value to 0 (or null where the schema allows) and mention the "
        "estimation status in the narrative fields. Do not invent "
        "subcontractor names or contract numbers.\n"
    )


def _extract_json_block(raw: str) -> str:
    """Strip markdown fences and grab the first JSON object."""
    raw = raw.strip()
    # ```json ... ``` fence
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL)
    if fence:
        raw = fence.group(1)
    # find the first { and matching last }
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        return raw[first : last + 1]
    return raw or "{}"


# =============================================================================
# Rule-based fallback (no LLM)
# =============================================================================


def _rule_analysis(facts: dict[str, Any]) -> dict[str, Any]:
    """Produce a serviceable analysis without calling Claude.

    The number-only fields come straight from facts. Narrative fields
    use small phrase templates so the page still feels populated.
    """
    sched = facts["schedule"]
    dq = facts["data_quality"]
    fin = facts["financial"]
    prod = facts["productivity"]

    # ---- Risk synthesis ----
    score = 0
    if sched["total_delay_days"] > 30:
        score += 2
    elif sched["total_delay_days"] > 0:
        score += 1
    if fin["status"] == "OVER_BUDGET":
        score += 2
    elif fin["budget_used_pct"] > 90:
        score += 1
    if dq["risk_level"] == "HIGH":
        score += 1

    if score >= 3:
        overall_risk = "HIGH"
        project_status = "CRITICAL"
    elif score >= 1:
        overall_risk = "MEDIUM"
        project_status = "WARNING"
    else:
        overall_risk = "LOW"
        project_status = "GOOD"

    top_risks: list[dict[str, str]] = []
    if sched["total_delay_days"] > 0:
        top_risks.append({
            "title": f"Schedule slip ({sched['total_delay_days']} days)",
            "impact": f"{len(sched['overdue'])} contracts past due",
            "cause": "Overdue subcontractor deliveries",
        })
    if fin["status"] == "OVER_BUDGET":
        top_risks.append({
            "title": "Budget overrun trending",
            "impact": f"EAC {fin['eac']:,.0f} vs BAC {fin['bac']:,.0f}",
            "cause": f"CPI {fin['cpi']:.2f} below 1.0",
        })
    if dq["risk_level"] in ("MEDIUM", "HIGH"):
        top_risks.append({
            "title": "Data quality gaps",
            "impact": f"{dq['uncategorized_count']} uncategorized, {dq['unassigned_count']} unassigned",
            "cause": "Imported ledger entries missing budget code / subcontractor link",
        })

    # ---- Productivity stub ----
    prod_status = "UNKNOWN"
    if prod["headcount"] > 0 and prod["man_hours"] > 0:
        prod_status = "AVERAGE"

    # ---- Executive summary text ----
    summary_lines = []
    summary_lines.append(
        f"Project is at {fin['progress_pct']:.0f}% completion with "
        f"{fin['budget_used_pct']:.0f}% of budget consumed."
    )
    if sched["total_delay_days"] > 0:
        summary_lines.append(
            f"{len(sched['overdue'])} contracts are overdue by a combined "
            f"{sched['total_delay_days']} days."
        )
    if fin["status"] == "OVER_BUDGET":
        summary_lines.append("Forecast indicates a budget overrun.")
    elif fin["status"] == "ON_TRACK":
        summary_lines.append("Spend is tracking the plan within ±5%.")
    if dq["risk_level"] != "LOW":
        summary_lines.append(
            f"{dq['uncategorized_count'] + dq['unassigned_count']} ledger rows need cleanup."
        )

    biggest_problem = "No critical issues detected."
    urgent_action = "Continue monitoring."
    if top_risks:
        biggest_problem = top_risks[0]["title"]
        urgent_action = (
            "Review overdue contracts and re-baseline schedule"
            if "Schedule" in top_risks[0]["title"]
            else "Investigate cost-performance gap"
            if "Budget" in top_risks[0]["title"]
            else "Assign uncategorized ledger rows"
        )

    return {
        "schedule": {
            "delayed_contracts": len(sched["overdue"]),
            "total_contracts": sched["total_contracts"],
            "critical_delays": sched["overdue"][:5],
            "discipline_delays": [
                {"discipline": k, **v} for k, v in sched["by_discipline"].items()
            ],
            "total_delay_days": int(sched["total_delay_days"]),
        },
        "data_quality": {
            "uncategorized_count": int(dq["uncategorized_count"]),
            "unassigned_count": int(dq["unassigned_count"]),
            "suggested_matches": dq["suggested_matches"],
            "risk_level": dq["risk_level"],
        },
        "financial": {
            "progress_pct": fin["progress_pct"],
            "budget_used_pct": fin["budget_used_pct"],
            "bac": fin["bac"],
            "ac": fin["ac"],
            "eac": fin["eac"],
            "variance": fin["variance"],
            "status": fin["status"],
        },
        "productivity": {
            "headcount": int(prod["headcount"]),
            "man_hours": float(prod["man_hours"]),
            "productivity": None,
            "deviation_pct": None,
            "status": prod_status,
        },
        "risk": {
            "overall_risk": overall_risk,
            "predicted_delay_days": int(sched["total_delay_days"] * 1.2),
            "top_risks": top_risks[:3],
        },
        "executive": {
            "project_status": project_status,
            "biggest_problem": biggest_problem,
            "financial_status": fin["status"].replace("_", " ").title(),
            "schedule_status": (
                f"{len(sched['overdue'])} contracts late"
                if sched["overdue"]
                else "All contracts on schedule"
            ),
            "urgent_action": urgent_action,
            "summary": " ".join(summary_lines),
        },
    }
