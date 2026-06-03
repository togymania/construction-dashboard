"""AI Project Analysis service (v2 -- executive director).

Pipeline:
  _collect_facts  -- pull all schedule / cost / workforce / quality data
  _compute_kpis   -- compute the 8 KPIs (deterministic)
  _rule_verdict   -- baseline verdict for when Claude is unavailable
  _llm_verdict    -- decisive Claude-driven verdict using the 7-step logic
  build_ai_analysis -- the single public entry point

The KPI list is computed deterministically *regardless of Claude
availability*, so the tile grid is always trustworthy. Claude only
provides the verdict narrative (headline, drivers, actions). When the
LLM is offline or fails the rule engine fills the same verdict shape
so the UI never renders blank.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
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
    AIVerdict,
    KPIStatus,
    ProjectAIAnalysis,
)
from app.services.accruals import ContractAccrualSignal, assess_accruals
from app.services.critical_path import Activity, compute_cpm, critical_path_delayed_days
from app.services.data_reliability import (
    ReliabilityBand,
    apply_accrual_penalty,
    reliability_band,
    reliability_caveat,
    reliability_from_ledger_counts,
)
from app.services.earned_value import compute_eva
from app.services.schedule_curve import planned_s_curve_progress


# ============================================================================
# Public entry point
# ============================================================================


async def build_ai_analysis(
    db: AsyncSession,
    project_id: int,
    *,
    lang: str = "EN",
) -> ProjectAIAnalysis | None:
    """Build the v2 executive analysis for a single project."""
    project = await db.get(Project, project_id)
    if project is None:
        return None

    facts = await _collect_facts(db, project)
    kpis_dict = _compute_kpis(facts)

    api_key = (settings.ANTHROPIC_API_KEY or "").strip()
    verdict_payload: dict[str, Any] | None = None
    source = "rule"
    if api_key:
        verdict_payload = _llm_verdict(facts, kpis_dict, api_key, lang=lang)
        if verdict_payload is not None:
            source = "llm"

    if verdict_payload is None:
        verdict_payload = _rule_verdict(facts, kpis_dict, lang=lang)

    # AI Governance gate (shared with the Executive Report): the LLM path
    # is NOT otherwise reliability-gated, so an LLM "ON_TRACK" on unlinked
    # data would slip through and contradict the report. Clamp it here using
    # the SAME score both AI features share.
    dq = facts["data_quality"]
    rel_score = reliability_from_ledger_counts(
        dq["uncategorized_count"], dq["unassigned_count"], dq["total_entries"]
    )
    if (
        reliability_band(rel_score) is ReliabilityBand.LOW
        and verdict_payload.get("verdict") == "ON_TRACK"
    ):
        verdict_payload["verdict"] = "AT_RISK"
        verdict_payload["data_confidence"] = "LOW"
        if not verdict_payload.get("data_confidence_note"):
            verdict_payload["data_confidence_note"] = (
                reliability_caveat(rel_score, lang) or ""
            )

    return ProjectAIAnalysis(
        project_id=project_id,
        generated_at=datetime.now(timezone.utc),
        lang="TR" if lang.upper() == "TR" else "EN",
        source=source,  # type: ignore[arg-type]
        kpis=_kpis_to_models(kpis_dict, lang=lang),
        verdict=AIVerdict(**verdict_payload),
    )


# ============================================================================
# Fact collection
# ============================================================================


async def _collect_facts(db: AsyncSession, project: Project) -> dict[str, Any]:
    today = date.today()
    project_id = project.id

    # ---- Contracts ----------------------------------------------------------
    contracts_stmt = (
        select(SubcontractorContract, Subcontractor)
        .join(
            Subcontractor,
            Subcontractor.id == SubcontractorContract.subcontractor_id,
        )
        .where(SubcontractorContract.project_id == project_id)
    )
    contract_rows = (await db.execute(contracts_stmt)).all()

    total_contracts = len(contract_rows)
    overdue: list[dict[str, Any]] = []
    contractor_risk: dict[int, dict[str, Any]] = {}

    # Critical-path approximation: contracts whose end_date falls within
    # 30 days of the project end_date (no `is_critical_path` column
    # exists yet). Cheap heuristic -- documented here so reviewers know
    # it's intentional.
    project_end = project.end_date
    critical_window_start = (
        project_end - timedelta(days=30) if project_end else None
    )

    critical_blocked = False
    for contract, sub in contract_rows:
        is_overdue = (
            contract.status == ContractStatus.ACTIVE
            and contract.end_date < today
        )
        is_critical = (
            critical_window_start is not None
            and project_end is not None
            and critical_window_start <= contract.end_date <= project_end
        )
        if is_overdue:
            days_overdue = (today - contract.end_date).days
            overdue.append({
                "subcontractor": sub.name,
                "contract_id": contract.id,
                "days": int(days_overdue),
                "is_critical": is_critical,
            })
            bucket = contractor_risk.setdefault(
                sub.id, {"name": sub.name, "days_overdue": 0}
            )
            bucket["days_overdue"] = max(
                bucket["days_overdue"], int(days_overdue)
            )
            if is_critical:
                critical_blocked = True

    contractor_risk_top = sorted(
        contractor_risk.values(),
        key=lambda x: x["days_overdue"],
        reverse=True,
    )[:5]

    # ---- Budget / Earned-Value ---------------------------------------------
    bac = Decimal((await db.execute(
        select(func.coalesce(func.sum(BudgetItem.planned_amount), 0))
        .where(BudgetItem.project_id == project_id)
    )).scalar_one() or 0)
    if bac == 0:
        bac = Decimal(project.budget_rub or 0)

    ledger_ac = Decimal((await db.execute(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .join(
            SubcontractorContract,
            SubcontractorContract.id == LedgerEntry.contract_id,
        )
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

    # ---- Data quality ------------------------------------------------------
    # Portfolio-level (LedgerEntry has no project_id of its own); see
    # the legacy comment in the previous revision for the full reason.
    uncategorized = int((await db.execute(
        select(func.count(LedgerEntry.id)).where(
            LedgerEntry.budget_code.is_(None)
        )
    )).scalar_one() or 0)
    unassigned = int((await db.execute(
        select(func.count(LedgerEntry.id)).where(
            LedgerEntry.subcontractor_id.is_(None),
            LedgerEntry.entry_type == LedgerEntryType.EXPENSE,
        )
    )).scalar_one() or 0)
    total_entries = int((await db.execute(
        select(func.count(LedgerEntry.id))
    )).scalar_one() or 0)
    dirty_ratio = (
        (uncategorized + unassigned) / total_entries
        if total_entries > 0 else 0.0
    )
    # Reliability = 1 - dirty_ratio  (clamped to 0..1, percentage)
    reliability_pct = max(0.0, min(100.0, (1.0 - dirty_ratio) * 100.0))

    # ---- Workforce momentum ------------------------------------------------
    snapshots = (await db.execute(
        select(WorkforceSnapshot)
        .where(WorkforceSnapshot.project_id == project_id)
        .order_by(WorkforceSnapshot.snapshot_date.desc())
        .limit(30)
    )).scalars().all()

    latest_headcount = 0
    prev_headcount = 0
    momentum = "unknown"
    if snapshots:
        latest_headcount = int(snapshots[0].total_present or 0)
        # Find a snapshot ~7 days before the latest
        ref_date = snapshots[0].snapshot_date - timedelta(days=7)
        prev_snap = next(
            (s for s in snapshots[1:] if s.snapshot_date <= ref_date),
            None,
        )
        if prev_snap is not None:
            prev_headcount = int(prev_snap.total_present or 0)
            if latest_headcount > prev_headcount * 1.05:
                momentum = "growing"
            elif latest_headcount < prev_headcount * 0.95:
                momentum = "declining"
            else:
                momentum = "flat"

    # ---- S-Curve (Prompt 1) + Earned Value (Prompt 2) + CPM + Accruals ----
    planned_s_curve = planned_s_curve_progress(project.start_date, project.end_date)
    eva = compute_eva(
        bac=bac,
        physical_progress_pct=progress_pct,
        acwp=ac,
        planned_progress_pct=planned_s_curve,
    )
    # Build a CPM network from contracts (no dependency model yet → the
    # longest contract is the zero-float critical one). Critical-path delay
    # only counts slips on those zero-float activities.
    activities: list[Activity] = []
    for contract, _sub in contract_rows:
        if project.start_date and contract.end_date:
            dur = max(1, (contract.end_date - project.start_date).days)
        else:
            dur = 1
        od = 0
        if (
            contract.status == ContractStatus.ACTIVE
            and contract.end_date
            and contract.end_date < today
        ):
            od = (today - contract.end_date).days
        activities.append(
            Activity(id=str(contract.id), duration=float(dur), overdue_days=float(od))
        )
    cpm = compute_cpm(activities) if activities else None
    critical_delay = critical_path_delayed_days(activities, cpm) if activities else 0.0

    # Project-level accrual proxy: physical progress vs booked-cost rate.
    payment_rate = float(ac / bac * 100) if bac > 0 else 0.0
    accr_cvr = assess_accruals(
        [
            ContractAccrualSignal(
                contract_id=0,
                physical_progress_pct=progress_pct,
                payment_rate_pct=payment_rate,
                days_since_last_cost=(None if ac <= 0 else 0.0),
            )
        ]
    )

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "progress_pct": progress_pct,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "days_until_end": (project.end_date - today).days if project.end_date else None,
        },
        "schedule": {
            "total_contracts": total_contracts,
            "overdue_count": len(overdue),
            "overdue": overdue,
            "total_delay_days": sum(o["days"] for o in overdue),
            "max_overdue_days": max((o["days"] for o in overdue), default=0),
            "critical_blocked": critical_blocked,
            # Prompt 1: S-curve plan vs earned, and delay on the zero-float
            # critical path (not just "any contract ending soon").
            "planned_s_curve_progress_pct": planned_s_curve,
            "actual_earned_progress_pct": progress_pct,
            "critical_path_delayed_days": critical_delay,
        },
        "financial": {
            "bac": float(bac),
            "ac": float(ac),
            "budget_used_pct": float(ac / bac * 100) if bac > 0 else 0.0,
            "progress_pct": progress_pct,
            # Prompt 2: Earned Value indices.
            "cpi": eva.cpi,
            "spi": eva.spi,
            "eac": float(eva.eac) if eva.eac is not None else None,
            "vac": float(eva.vac) if eva.vac is not None else None,
            "cost_band": eva.cost_band,
            "schedule_band": eva.schedule_band,
        },
        "accruals": {
            "progress_payment_gap_pct": round(progress_pct - payment_rate, 2),
            "flagged_ratio": accr_cvr.flagged_ratio,
        },
        "data_quality": {
            "uncategorized_count": uncategorized,
            "unassigned_count": unassigned,
            "total_entries": total_entries,
            "dirty_ratio": round(dirty_ratio, 3),
            "reliability_pct": round(reliability_pct, 1),
        },
        "workforce": {
            "latest_headcount": latest_headcount,
            "prev_headcount": prev_headcount,
            "momentum": momentum,
        },
        "contractor_risk": contractor_risk_top,
    }


# ============================================================================
# KPI computation  (deterministic, no LLM)
# ============================================================================


def _compute_kpis(facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Run the 7-step logic and return raw KPI dicts keyed by stable id."""
    proj = facts["project"]
    sched = facts["schedule"]
    fin = facts["financial"]
    dq = facts["data_quality"]
    wf = facts["workforce"]
    today = date.today()

    # ----- Step 1: data confidence (driven by reliability_pct) --------------
    if dq["dirty_ratio"] >= 0.40:
        data_confidence = "LOW"
    elif dq["dirty_ratio"] >= 0.20:
        data_confidence = "MEDIUM"
    else:
        data_confidence = "HIGH"

    # ----- Step 2: schedule + projected delay -------------------------------
    start_iso = proj["start_date"]
    end_iso = proj["end_date"]
    progress_pct = float(proj["progress_pct"] or 0)

    schedule_delay_days = 0
    projected_delay_days = 0
    planned_progress = 0.0
    if start_iso and end_iso:
        start_d = date.fromisoformat(start_iso)
        end_d = date.fromisoformat(end_iso)
        span = max((end_d - start_d).days, 1)
        elapsed = max(0, min((today - start_d).days, span))
        # Prompt 1: planned progress follows the S-curve, not a straight line.
        planned_progress = sched.get("planned_s_curve_progress_pct")
        if planned_progress is None:
            planned_progress = (elapsed / span) * 100.0
        # delay in days = (planned - actual) * span / 100
        diff_pct = planned_progress - progress_pct
        schedule_delay_days = int(diff_pct / 100.0 * span)

        # projected completion delay: extrapolate from current velocity
        if elapsed > 0 and progress_pct > 0:
            velocity = progress_pct / elapsed  # %/day
            remaining = max(0.0, 100.0 - progress_pct)
            days_needed = remaining / velocity if velocity > 0 else span
            projected_end = today + timedelta(days=int(days_needed))
            projected_delay_days = (projected_end - end_d).days

    if schedule_delay_days <= 3:
        sched_status = "ok"
    elif schedule_delay_days <= 14:
        sched_status = "watch"
    else:
        sched_status = "critical"

    if projected_delay_days <= 3:
        proj_status = "ok"
    elif projected_delay_days <= 14:
        proj_status = "watch"
    else:
        proj_status = "critical"

    # ----- Step 3: critical path -------------------------------------------
    if sched["critical_blocked"]:
        critical_path_state = "blocked"
        critical_status = "critical"
    elif sched["overdue_count"] > 0:
        critical_path_state = "at_risk"
        critical_status = "watch"
    else:
        critical_path_state = "clear"
        critical_status = "ok"

    # ----- Step 4: resource efficiency -------------------------------------
    headcount = wf["latest_headcount"]
    if headcount > 0:
        # progress_pct per 1000 worker-days proxy
        efficiency_score = progress_pct / headcount * 1000.0
        eff_value = f"{efficiency_score:.1f}"
        # Heuristic threshold: under 20 means many people, little progress.
        # Combined with momentum trend per spec.
        if (
            wf["momentum"] == "growing"
            and efficiency_score < 20.0
        ):
            eff_status = "critical"
        elif efficiency_score < 15.0:
            eff_status = "watch"
        else:
            eff_status = "ok"
    else:
        eff_value = "—"
        eff_status = "unknown"

    # ----- Step 5: cost consistency — Earned Value CPI rule (Prompt 2) -----
    # CPI < 0.90 => over budget (red); CPI > 1.0 => favourable (green);
    # in between => on target (amber). Replaces the old spent-vs-progress
    # heuristic.
    cpi = fin.get("cpi")
    if cpi is None:
        cost_state = "unknown"
        cost_status = "unknown"
    elif cpi < 0.9:
        cost_state = "overrun_risk"
        cost_status = "critical"
    elif cpi > 1.0:
        cost_state = "favourable"
        cost_status = "ok"
    else:
        cost_state = "on_target"
        cost_status = "watch"

    # ----- Step 6: data reliability + accrual penalty (Prompt 3) ----------
    accr = facts.get("accruals", {})
    reliability_pct = apply_accrual_penalty(
        dq["reliability_pct"], accr.get("flagged_ratio", 0.0)
    )
    if reliability_pct >= 80:
        rel_status = "ok"
    elif reliability_pct >= 60:
        rel_status = "watch"
    else:
        rel_status = "critical"

    # ----- Contractor risk ------------------------------------------------
    risk_list = facts["contractor_risk"]
    risk_count = len(risk_list)
    if risk_count == 0:
        contractor_status = "ok"
    elif risk_count <= 2:
        contractor_status = "watch"
    else:
        contractor_status = "critical"

    # ----- Bundle ----------------------------------------------------------
    return {
        "schedule_health": {
            "value": f"{schedule_delay_days:+d} d",
            "status": sched_status,
            "raw_delay": schedule_delay_days,
            "planned_pct": planned_progress,
        },
        "projected_delay": {
            "value": f"{projected_delay_days:+d} d",
            "status": proj_status,
            "raw_delay": projected_delay_days,
        },
        "critical_path": {
            "value": critical_path_state.upper().replace("_", " "),
            "status": critical_status,
            "raw_state": critical_path_state,
        },
        "progress": {
            "value": f"{progress_pct:.0f} %",
            "status": "ok" if progress_pct > 0 else "unknown",
            "raw_progress": progress_pct,
        },
        "resource_efficiency": {
            "value": eff_value,
            "status": eff_status,
            "raw_headcount": headcount,
            "raw_momentum": wf["momentum"],
        },
        "cost_consistency": {
            "value": cost_state.upper().replace("_", " "),
            "status": cost_status,
            "raw_state": cost_state,
            "raw_used_pct": fin["budget_used_pct"],
        },
        "data_reliability": {
            "value": f"{reliability_pct:.0f} %",
            "status": rel_status,
            "raw_pct": reliability_pct,
            "raw_confidence": data_confidence,
        },
        "contractor_risk": {
            "value": str(risk_count),
            "status": contractor_status,
            "raw_top": risk_list,
        },
        "_meta": {
            "data_confidence": data_confidence,
            "project_blocked": sched["critical_blocked"],
            "projected_delay_days": projected_delay_days,
            "schedule_delay_days": schedule_delay_days,
        },
    }


def _kpis_to_models(
    kpis: dict[str, dict[str, Any]],
    *,
    lang: str,
) -> list[KPIStatus]:
    """Convert the computed dict into the fixed-order KPIStatus list.

    The frontend treats `key` as stable for i18n binding; the `label`
    is just a fallback when the frontend has no translation.
    """
    is_tr = lang.upper() == "TR"
    labels = {
        "schedule_health": ("Schedule Health", "Takvim Sağlığı"),
        "projected_delay": ("Projected Completion Delay", "Öngörülen Tamamlanma Gecikmesi"),
        "critical_path": ("Critical Path", "Kritik Yol"),
        "progress": ("Progress (Actual)", "İlerleme (Fiili)"),
        "resource_efficiency": ("Resource Efficiency", "Kaynak Verimliliği"),
        "cost_consistency": ("Cost Consistency", "Maliyet Tutarlılığı"),
        "data_reliability": ("Data Reliability", "Veri Güvenilirliği"),
        "contractor_risk": ("Contractor Risk", "Yüklenici Riski"),
    }
    order = [
        "schedule_health",
        "projected_delay",
        "critical_path",
        "progress",
        "resource_efficiency",
        "cost_consistency",
        "data_reliability",
        "contractor_risk",
    ]
    result: list[KPIStatus] = []
    for key in order:
        k = kpis[key]
        en, tr = labels[key]
        result.append(KPIStatus(
            key=key,
            value=str(k.get("value", "")),
            status=k.get("status", "unknown"),
            label=tr if is_tr else en,
            detail="",
        ))
    return result


# ============================================================================
# Rule-based verdict (LLM fallback)
# ============================================================================


def _rule_verdict(
    facts: dict[str, Any],
    kpis: dict[str, dict[str, Any]],
    *,
    lang: str,
) -> dict[str, Any]:
    is_tr = lang.upper() == "TR"
    meta = kpis["_meta"]
    blocked = meta["project_blocked"]
    proj_delay = meta["projected_delay_days"]
    confidence = meta["data_confidence"]

    # Prompt 1 #4: behind the S-curve AND the slip is on the zero-float
    # critical path → escalate.
    sched_f = facts["schedule"]
    earned = float(sched_f.get("actual_earned_progress_pct") or 0)
    planned_sc = sched_f.get("planned_s_curve_progress_pct")
    crit_delay = float(sched_f.get("critical_path_delayed_days") or 0)
    behind_curve = planned_sc is not None and earned < float(planned_sc)

    # ---- Step 7: final verdict --------------------------------------------
    if blocked:
        verdict = "CRITICAL"
    elif behind_curve and crit_delay > 14:
        verdict = "CRITICAL"
    elif proj_delay > 14:
        verdict = "AT_RISK"
    elif (
        proj_delay > 3
        or kpis["cost_consistency"]["status"] == "critical"
        or (behind_curve and crit_delay > 0)
    ):
        verdict = "AT_RISK"
    elif confidence == "LOW":
        # Cannot trust anything -> not on track
        verdict = "AT_RISK"
    else:
        verdict = "ON_TRACK"

    sched_delay = meta["schedule_delay_days"]
    overdue_count = facts["schedule"]["overdue_count"]
    cost_state = kpis["cost_consistency"]["raw_state"]
    rel_pct = kpis["data_reliability"]["raw_pct"]
    top_risk_list = facts["contractor_risk"]
    top_risk_name = top_risk_list[0]["name"] if top_risk_list else None

    # ---- Headline ---------------------------------------------------------
    if is_tr:
        headlines = {
            "CRITICAL": "Proje kritik yolda tıkanmış durumda ve hedef tarihte teslim edilemez.",
            "AT_RISK": f"Proje hedef tarihten {max(proj_delay, sched_delay)} gün geride; müdahale gerekiyor.",
            "ON_TRACK": "Proje plana uygun ilerliyor; mevcut yönetim ritmi sürdürülmelidir.",
        }
    else:
        headlines = {
            "CRITICAL": "Project is blocked on the critical path and will not deliver on time.",
            "AT_RISK": f"Project is {max(proj_delay, sched_delay)} days behind plan; intervention required.",
            "ON_TRACK": "Project is tracking the plan; current execution rhythm must hold.",
        }
    headline = headlines[verdict]

    # ---- Key drivers ------------------------------------------------------
    drivers: list[str] = []
    if is_tr:
        if blocked:
            drivers.append("Kritik yol taşeronu gecikmede")
        if sched_delay > 0:
            drivers.append(f"Takvimde {sched_delay} gün geri")
        if cost_state == "overrun_risk":
            drivers.append("Maliyet ilerlemeyi aşıyor (bütçe aşımı sinyali)")
        elif cost_state == "underreported":
            drivers.append("Harcamalar düşük raporlanıyor (eksik kayıt)")
        if rel_pct < 60:
            drivers.append(f"Veri güvenilirliği düşük (%{rel_pct:.0f})")
        if not drivers:
            drivers.append("Belirgin yapısal risk yok")
    else:
        if blocked:
            drivers.append("Critical-path contractor is overdue")
        if sched_delay > 0:
            drivers.append(f"Schedule is {sched_delay} days behind")
        if cost_state == "overrun_risk":
            drivers.append("Cost outpaces progress (overrun signal)")
        elif cost_state == "underreported":
            drivers.append("Spend underreported vs progress")
        if rel_pct < 60:
            drivers.append(f"Data reliability low ({rel_pct:.0f}%)")
        if not drivers:
            drivers.append("No structural risk detected")
    drivers = drivers[:3]

    # ---- Critical blocker -------------------------------------------------
    if blocked and top_risk_name:
        critical_blocker = (
            f"{top_risk_name} {top_risk_list[0]['days_overdue']} gün gecikmiş (kritik yol)"
            if is_tr else
            f"{top_risk_name} is {top_risk_list[0]['days_overdue']} days overdue on the critical path"
        )
    elif overdue_count > 0 and top_risk_name:
        critical_blocker = (
            f"{top_risk_name} sözleşme süresi aştı"
            if is_tr else
            f"{top_risk_name} contract is past end date"
        )
    elif cost_state == "overrun_risk":
        critical_blocker = (
            "Maliyet ilerlemeyi geçti -- bütçe aşımı sinyali"
            if is_tr else
            "Cost has overtaken progress -- budget overrun signal"
        )
    elif confidence == "LOW":
        critical_blocker = (
            "Veri kalitesi karar almak için yetersiz"
            if is_tr else
            "Data quality is insufficient for decision-making"
        )
    else:
        critical_blocker = ""

    # ---- Impact summary ---------------------------------------------------
    if verdict == "CRITICAL":
        impact_summary = "execution"
    elif cost_state == "overrun_risk":
        impact_summary = "cost"
    elif proj_delay > 3 or sched_delay > 3:
        impact_summary = "time"
    else:
        impact_summary = "execution"

    # ---- Confidence note --------------------------------------------------
    confidence_note = ""
    if confidence == "LOW":
        confidence_note = (
            f"Defteri kebir kayıtlarının %{100 - rel_pct:.0f}'i bütçe kodu veya taşeron olmadan; finansal sayılara güvenilemez."
            if is_tr else
            f"{100 - rel_pct:.0f}% of ledger entries lack budget code or subcontractor link; financial numbers cannot be trusted."
        )
    elif confidence == "MEDIUM":
        confidence_note = (
            f"Veri güvenilirliği %{rel_pct:.0f} -- temizleme önerilir."
            if is_tr else
            f"Data reliability is {rel_pct:.0f}% -- cleanup recommended."
        )

    # ---- Required actions -------------------------------------------------
    actions: list[str] = []
    if is_tr:
        if blocked and top_risk_name:
            actions.append(f"{top_risk_name} taşeronunu bugün uyar ve telafi planı iste")
        if overdue_count > 0:
            actions.append(f"{overdue_count} gecikmiş sözleşmeyi yeniden planla")
        if cost_state == "overrun_risk":
            actions.append("Bütçe aşımı doğrulaması için maliyet incelemesi yap")
        if confidence == "LOW":
            actions.append("48 saat içinde eksik defter kayıtlarını ata")
        if not actions:
            actions.append("Haftalık ilerleme ritmini koru ve verileri taze tut")
    else:
        if blocked and top_risk_name:
            actions.append(f"Escalate {top_risk_name} today and demand a recovery plan")
        if overdue_count > 0:
            actions.append(f"Re-baseline {overdue_count} overdue contracts")
        if cost_state == "overrun_risk":
            actions.append("Run a cost-variance review to confirm overrun")
        if confidence == "LOW":
            actions.append("Assign missing ledger entries within 48 hours")
        if not actions:
            actions.append("Hold weekly cadence and keep data current")
    actions = actions[:3]

    return {
        "verdict": verdict,
        "headline": headline,
        "key_drivers": drivers,
        "critical_blocker": critical_blocker,
        "impact_delay_days": int(max(proj_delay, sched_delay, 0)),
        "impact_summary": impact_summary,
        "data_confidence": confidence,
        "data_confidence_note": confidence_note,
        "required_actions": actions,
    }


# ============================================================================
# LLM verdict
# ============================================================================


_SYSTEM_PROMPT_EN = (
    "You are a senior construction project director. Your job is NOT "
    "to describe the data, but to make decisions and give clear "
    "executive-level judgment. Always think in this order: "
    "1) Can the project finish on time? "
    "2) What is blocking completion? "
    "3) Is the data reliable? "
    "4) Are resources used efficiently? "
    "5) What actions must be taken immediately? "
    "Rules: be decisive and direct; do not hedge or speculate; if data "
    "is unreliable, explicitly say so; focus on critical path and "
    "completion risk; limit output to what matters for decision-making. "
    "Use single-sentence verdict. Identify a single root cause. "
    "If data is bad, say 'Financials cannot be trusted'. Never end "
    "without actions. Use only 'will / cannot / is' -- never 'may / "
    "might / possibly'. "
    "Judge schedule against the planned S-curve (planned_s_curve_progress "
    "vs actual_earned_progress), NOT a straight line; if actual is behind "
    "the S-curve AND the slip is on the critical path "
    "(critical_path_delayed_days > 0), the status is AT_RISK or CRITICAL. "
    "Use Earned Value: CPI < 0.90 means over budget, CPI > 1.0 favourable; "
    "cite EAC. If the accrual gap is high (site progress far exceeds booked "
    "cost), warn that costs are unbooked and the profit/loss is misleading."
)


_SYSTEM_PROMPT_TR = (
    "Sen kıdemli bir inşaat proje direktörüsün. Görevin verileri "
    "tarif etmek DEĞİL; karar vermek ve net, yönetici düzeyinde "
    "yargı sunmaktır. Daima şu sırayla düşün: "
    "1) Proje zamanında bitebilir mi? "
    "2) Tamamlanmayı ne engelliyor? "
    "3) Veriye güvenilebilir mi? "
    "4) Kaynaklar verimli kullanılıyor mu? "
    "5) Derhal hangi aksiyonlar alınmalı? "
    "Kurallar: kararlı ve doğrudan ol; tereddüt etme ve spekülasyon "
    "yapma; veri güvenilmezse açıkça söyle; kritik yol ve tamamlanma "
    "riskine odaklan; yalnızca karara yarayanı yaz. "
    "Karar tek cümlede verilir. Tek bir kök neden belirt. "
    "Veri kötüyse 'Finansal verilere güvenilemez' diye yaz. Aksiyonsuz "
    "asla bitirme. Sadece 'olacak / olamaz / -dır' kullan; "
    "'olabilir / muhtemel' kullanma. "
    "Takvimi düz çizgiye göre değil planlanan S-eğrisine göre değerlendir "
    "(planned_s_curve_progress vs actual_earned_progress); fiili S-eğrisinin "
    "gerisindeyse VE gecikme kritik yoldaysa (critical_path_delayed_days > 0) "
    "durum AT_RISK veya CRITICAL'dır. Kazanılmış Değer kullan: CPI < 0,90 "
    "bütçe aşımı, CPI > 1,0 olumludur; EAC'yi belirt. Tahakkuk farkı yüksekse "
    "(saha ilerlemesi işlenen maliyeti çok aşıyorsa) maliyetlerin "
    "kaydedilmediğini ve kâr/zarar tablosunun yanıltıcı olabileceğini söyle. "
    "Tüm çıktı Türkçe olacak."
)


def _llm_verdict(
    facts: dict[str, Any],
    kpis: dict[str, dict[str, Any]],
    api_key: str,
    *,
    lang: str = "EN",
) -> dict[str, Any] | None:
    """Ask Claude for the executive verdict. Returns None on any failure."""
    try:
        import anthropic  # type: ignore

        is_tr = lang.upper() == "TR"
        system = _SYSTEM_PROMPT_TR if is_tr else _SYSTEM_PROMPT_EN

        compact = {
            "project": facts["project"],
            "schedule": facts["schedule"],
            "financial": facts["financial"],
            "accruals": facts.get("accruals", {}),
            "data_quality": facts["data_quality"],
            "workforce": facts["workforce"],
            "contractor_risk": facts["contractor_risk"],
            "kpis": {
                k: {
                    "value": v.get("value"),
                    "status": v.get("status"),
                }
                for k, v in kpis.items() if not k.startswith("_")
            },
            "meta": kpis["_meta"],
        }

        user_prompt = (
            ("Proje verisi (JSON):\n" if is_tr else "Project facts (JSON):\n")
            + "```json\n"
            + json.dumps(compact, ensure_ascii=False, indent=2, default=str)
            + "\n```\n\n"
            + (
                "Sadece JSON döndür; etrafına yazı yazma. Şu alanlar bulunmalı: "
                if is_tr else
                "Return ONLY a JSON object, no prose around it, with these fields: "
            )
            + "\n{\n"
            '  "verdict": "ON_TRACK" | "AT_RISK" | "CRITICAL",\n'
            '  "headline": "<single sentence>",\n'
            '  "key_drivers": ["<max 3 short bullets>"],\n'
            '  "critical_blocker": "<single biggest blocker>",\n'
            '  "impact_delay_days": <int>,\n'
            '  "impact_summary": "time" | "cost" | "execution",\n'
            '  "data_confidence": "HIGH" | "MEDIUM" | "LOW",\n'
            '  "data_confidence_note": "<only if not HIGH>",\n'
            '  "required_actions": ["<max 3 immediate concrete actions>"]\n'
            "}\n"
        )

        client = anthropic.Anthropic(
            api_key=api_key, timeout=settings.LLM_TIMEOUT_SECONDS
        )
        msg = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1200,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = msg.content[0].text if msg.content else "{}"
        parsed = json.loads(_extract_json_block(raw))

        # Trust deterministic numbers
        parsed["impact_delay_days"] = int(
            parsed.get("impact_delay_days") or kpis["_meta"]["projected_delay_days"] or 0
        )
        parsed.setdefault("data_confidence", kpis["_meta"]["data_confidence"])
        parsed.setdefault("verdict", "AT_RISK")
        parsed.setdefault("headline", "")
        parsed.setdefault("critical_blocker", "")
        parsed.setdefault("impact_summary", "execution")
        parsed.setdefault("data_confidence_note", "")
        parsed.setdefault("key_drivers", [])
        parsed.setdefault("required_actions", [])

        # Enforce list length caps
        parsed["key_drivers"] = list(parsed["key_drivers"])[:3]
        parsed["required_actions"] = list(parsed["required_actions"])[:3]

        # Reject pathological output
        if not parsed["required_actions"]:
            return None
        return parsed
    except Exception:
        return None


def _extract_json_block(raw: str) -> str:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL)
    if fence:
        raw = fence.group(1)
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        return raw[first : last + 1]
    return raw or "{}"
