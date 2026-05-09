"""Pydantic schemas for Dashboard aggregates."""
from datetime import datetime

from pydantic import BaseModel, Field


class KPIMetric(BaseModel):
    label: str
    value: str
    change: str
    trend: str = Field(..., description="up | down | neutral")


class DashboardStats(BaseModel):
    active_projects: KPIMetric
    total_budget: KPIMetric
    on_track: KPIMetric
    open_risks: KPIMetric


# ---------- Daily AI Briefing (Faz 4) ----------


class DailyBriefing(BaseModel):
    """The dashboard's daily AI-generated executive briefing."""

    generated_at: datetime
    headline: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    facts: dict = Field(default_factory=dict)
    source: str = "rule"  # "rule" | "llm"
