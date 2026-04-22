"""Pydantic schemas for Dashboard aggregates."""
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
