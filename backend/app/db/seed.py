"""In-memory mock data for development."""
from datetime import date

from app.schemas.project import ProjectHealth, ProjectResponse, ProjectStatus

MOCK_PROJECTS: list[ProjectResponse] = [
    ProjectResponse(id=1, name="Istanbul Havalimani Terminal B", description="Expansion of Istanbul Airport", status=ProjectStatus.ACTIVE, health=ProjectHealth.ON_TRACK, budget_usd=450_000_000, budget_spent_usd=187_000_000, start_date=date(2024, 3, 1), end_date=date(2027, 6, 30), progress_pct=41.5, location="Istanbul, Turkey"),
    ProjectResponse(id=2, name="Kanal Istanbul Etap 2", description="Second phase of Istanbul Canal", status=ProjectStatus.ACTIVE, health=ProjectHealth.AT_RISK, budget_usd=320_000_000, budget_spent_usd=95_000_000, start_date=date(2025, 1, 15), end_date=date(2028, 12, 31), progress_pct=29.7, location="Istanbul, Turkey"),
    ProjectResponse(id=3, name="Ankara-Izmir YHT", description="High-speed rail line", status=ProjectStatus.ACTIVE, health=ProjectHealth.ON_TRACK, budget_usd=280_000_000, budget_spent_usd=156_000_000, start_date=date(2023, 6, 1), end_date=date(2026, 11, 30), progress_pct=55.8, location="Ankara to Izmir, Turkey"),
    ProjectResponse(id=4, name="Marmaray Extension", description="Eastern extension of Marmaray", status=ProjectStatus.ACTIVE, health=ProjectHealth.ON_TRACK, budget_usd=150_000_000, budget_spent_usd=88_000_000, start_date=date(2024, 9, 1), end_date=date(2026, 8, 31), progress_pct=58.7, location="Istanbul, Turkey"),
    ProjectResponse(id=5, name="Galataport Phase 2", description="Waterfront development", status=ProjectStatus.ACTIVE, health=ProjectHealth.ON_TRACK, budget_usd=80_000_000, budget_spent_usd=52_000_000, start_date=date(2024, 1, 1), end_date=date(2026, 3, 31), progress_pct=65.0, location="Istanbul, Turkey"),
    ProjectResponse(id=6, name="Izmir Metro Line 5", description="New metro line", status=ProjectStatus.PLANNING, health=ProjectHealth.ON_TRACK, budget_usd=195_000_000, budget_spent_usd=8_000_000, start_date=date(2026, 6, 1), end_date=date(2030, 12, 31), progress_pct=4.1, location="Izmir, Turkey"),
]


def get_mock_dashboard_stats() -> dict:
    active = [p for p in MOCK_PROJECTS if p.status == ProjectStatus.ACTIVE]
    on_track = [p for p in active if p.health == ProjectHealth.ON_TRACK]
    total_budget = sum(p.budget_usd for p in MOCK_PROJECTS)
    return {
        "active_projects": {"label": "Active Projects", "value": str(len(active)), "change": "+2 this month", "trend": "up"},
        "total_budget": {"label": "Total Budget", "value": f"${total_budget / 1_000_000_000:.2f}B", "change": "+5.4% YoY", "trend": "up"},
        "on_track": {"label": "On-Track", "value": str(len(on_track)), "change": f"{len(on_track) * 100 // len(active)}% of active", "trend": "neutral"},
        "open_risks": {"label": "Open Risks", "value": "7", "change": "-3 from last week", "trend": "down"},
    }
