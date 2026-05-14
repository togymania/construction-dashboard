"""Pydantic schemas for the AI Project Analysis endpoint (v2).

The v2 framework replaces the descriptive 6-section dashboard with an
executive director model: 8 compact KPIs + a single decisive verdict
that tells the PM (a) can the project finish on time, (b) what is
blocking it, (c) is the data trustworthy, (d) what actions are
required RIGHT NOW.

The endpoint URL and response_model name (``ProjectAIAnalysis``) stay
the same so the frontend client stays small; the *shape* is what
changed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


KPIStatusLevel = Literal["ok", "watch", "critical", "unknown"]


class KPIStatus(BaseModel):
    """One of the 8 compact KPI tiles rendered in the frontend grid."""

    key: str = Field(
        ...,
        description=(
            "Stable identifier (schedule_health, projected_delay, ...). "
            "Frontend uses this to bind a stable i18n label and icon."
        ),
    )
    value: str = Field(
        "",
        description="Display-ready value (already formatted: '14 d', '78 %').",
    )
    status: KPIStatusLevel = "unknown"
    label: str = ""  # English source label; frontend can override via i18n
    detail: str = ""  # one short sentence explaining the value


VerdictLevel = Literal["ON_TRACK", "AT_RISK", "CRITICAL", "UNKNOWN"]
DataConfidence = Literal["HIGH", "MEDIUM", "LOW"]


class AIVerdict(BaseModel):
    """The executive verdict block rendered above the KPI grid."""

    verdict: VerdictLevel = "UNKNOWN"
    headline: str = ""
    key_drivers: list[str] = Field(default_factory=list, max_length=3)
    critical_blocker: str = ""
    impact_delay_days: int = 0
    impact_summary: str = ""
    data_confidence: DataConfidence = "MEDIUM"
    data_confidence_note: str = ""
    required_actions: list[str] = Field(default_factory=list, max_length=3)


class ProjectAIAnalysis(BaseModel):
    """v2 executive AI director payload."""

    project_id: int
    generated_at: datetime
    lang: Literal["EN", "TR"] = "EN"
    source: Literal["llm", "rule"] = "rule"

    kpis: list[KPIStatus] = Field(default_factory=list)
    verdict: AIVerdict


ProjectAIAnalysisV2 = ProjectAIAnalysis
