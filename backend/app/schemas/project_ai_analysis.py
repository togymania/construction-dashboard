"""Pydantic schemas for the AI Project Analysis endpoint.

A single AI-generated report that synthesizes all project signals
(schedule, data quality, financial, productivity, risk) into a
structured executive briefing. Mirrors the 6-section prompt template
the user gave us; each section is a small object so the frontend can
render colored cards cleanly without re-parsing free-form text.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 🔴  Section 1 — Subcontractor & Schedule
# ---------------------------------------------------------------------------


class CriticalDelay(BaseModel):
    """A single overdue / critical contract line for the schedule card."""

    subcontractor: str
    contract_id: int | None = None
    days: int = Field(0, description="Days overdue (positive = late)")
    reason: str = ""


class DisciplineDelay(BaseModel):
    discipline: str
    delayed_count: int = 0
    delay_days: int = 0


class ScheduleSection(BaseModel):
    delayed_contracts: int = 0
    total_contracts: int = 0
    critical_delays: list[CriticalDelay] = []
    discipline_delays: list[DisciplineDelay] = []
    total_delay_days: int = 0


# ---------------------------------------------------------------------------
# 🟠  Section 2 — Data Quality
# ---------------------------------------------------------------------------


class SuggestedMatch(BaseModel):
    """A proposed link for an unassigned/uncategorized record."""

    entry_id: int | None = None
    description: str = ""
    suggested_target: str = ""  # e.g. subcontractor name or category
    confidence: float = Field(0.0, ge=0.0, le=1.0)


DataQualityRisk = Literal["LOW", "MEDIUM", "HIGH"]


class DataQualitySection(BaseModel):
    uncategorized_count: int = 0
    unassigned_count: int = 0
    suggested_matches: list[SuggestedMatch] = []
    risk_level: DataQualityRisk = "LOW"


# ---------------------------------------------------------------------------
# 🟡  Section 3 — Financial (EAC)
# ---------------------------------------------------------------------------


FinancialStatus = Literal["OVER_BUDGET", "ON_TRACK", "UNDER_BUDGET", "UNKNOWN"]


class FinancialSection(BaseModel):
    progress_pct: float = 0.0
    budget_used_pct: float = 0.0
    bac: Decimal = Decimal("0")  # Budget at completion
    ac: Decimal = Decimal("0")  # Actual cost to date
    eac: Decimal = Decimal("0")  # Estimate at completion
    variance: Decimal = Decimal("0")  # BAC - EAC (positive = under budget)
    status: FinancialStatus = "UNKNOWN"


# ---------------------------------------------------------------------------
# 🟢  Section 4 — Workforce / Productivity
# ---------------------------------------------------------------------------


ProductivityStatus = Literal["GOOD", "AVERAGE", "LOW", "UNKNOWN"]


class ProductivitySection(BaseModel):
    headcount: int = 0
    man_hours: float = 0.0
    # Productivity is "output / man-hour". We don't yet track production
    # units (m²/m³) so this is often estimated by the LLM. The number
    # field stays optional so the card can render either the value or
    # an "—" placeholder cleanly.
    productivity: float | None = None
    deviation_pct: float | None = None
    status: ProductivityStatus = "UNKNOWN"


# ---------------------------------------------------------------------------
# 🔵  Section 5 — Risk Analysis & Forecast
# ---------------------------------------------------------------------------


RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class TopRisk(BaseModel):
    title: str
    impact: str = ""
    cause: str = ""


class RiskSection(BaseModel):
    overall_risk: RiskLevel = "LOW"
    predicted_delay_days: int = 0
    top_risks: list[TopRisk] = []


# ---------------------------------------------------------------------------
# 🧠  Section 6 — Executive Summary
# ---------------------------------------------------------------------------


ProjectStatus = Literal["GOOD", "WARNING", "CRITICAL"]


class ExecutiveSection(BaseModel):
    project_status: ProjectStatus = "GOOD"
    biggest_problem: str = ""
    financial_status: str = ""
    schedule_status: str = ""
    urgent_action: str = ""
    summary: str = Field("", description="≤4 sentence top-line for an executive")


# ---------------------------------------------------------------------------
# Full payload
# ---------------------------------------------------------------------------


class ProjectAIAnalysis(BaseModel):
    """The full 6-section AI analysis returned to the frontend."""

    project_id: int
    generated_at: datetime
    lang: Literal["EN", "TR"] = "EN"
    source: Literal["llm", "rule"] = "rule"

    schedule: ScheduleSection
    data_quality: DataQualitySection
    financial: FinancialSection
    productivity: ProductivitySection
    risk: RiskSection
    executive: ExecutiveSection
