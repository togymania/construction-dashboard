"""Dashboard aggregation endpoints."""
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.models.project import Project, ProjectHealth, ProjectStatus
from app.schemas.dashboard import DashboardStats, KPIMetric

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _format_budget(total: Decimal) -> str:
    """Format a USD amount as e.g. '$1.48B' or '$245.3M'."""
    val = float(total)
    if val >= 1_000_000_000:
        return f"${val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    return f"${val:,.0f}"


@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Get dashboard KPIs",
)
async def get_dashboard_stats(
    user: CurrentUser,
    db: DBSession,
) -> DashboardStats:
    # Count active projects
    active_count_stmt = select(func.count()).where(
        Project.is_active == True,  # noqa: E712
        Project.status == ProjectStatus.ACTIVE,
    )
    active_count = (await db.execute(active_count_stmt)).scalar_one()

    # Total budget of active projects
    total_budget_stmt = select(func.coalesce(func.sum(Project.budget_usd), 0)).where(
        Project.is_active == True,  # noqa: E712
        Project.status == ProjectStatus.ACTIVE,
    )
    total_budget = (await db.execute(total_budget_stmt)).scalar_one()

    # On-track active projects
    on_track_count_stmt = select(func.count()).where(
        Project.is_active == True,  # noqa: E712
        Project.status == ProjectStatus.ACTIVE,
        Project.health == ProjectHealth.ON_TRACK,
    )
    on_track_count = (await db.execute(on_track_count_stmt)).scalar_one()

    # At-risk + delayed projects (proxy for open risks)
    risk_count_stmt = select(func.count()).where(
        Project.is_active == True,  # noqa: E712
        Project.status == ProjectStatus.ACTIVE,
        Project.health.in_([ProjectHealth.AT_RISK, ProjectHealth.DELAYED]),
    )
    risk_count = (await db.execute(risk_count_stmt)).scalar_one()

    on_track_pct = (on_track_count / active_count * 100) if active_count else 0

    return DashboardStats(
        active_projects=KPIMetric(
            label="Active Projects",
            value=str(active_count),
            change=f"{active_count} total",
            trend="neutral",
        ),
        total_budget=KPIMetric(
            label="Total Budget",
            value=_format_budget(total_budget),
            change="Live from DB",
            trend="up",
        ),
        on_track=KPIMetric(
            label="On-Track",
            value=str(on_track_count),
            change=f"{on_track_pct:.0f}% of active",
            trend="up" if on_track_pct >= 70 else "neutral",
        ),
        open_risks=KPIMetric(
            label="Open Risks",
            value=str(risk_count),
            change=f"{risk_count} need attention",
            trend="down" if risk_count == 0 else "up",
        ),
    )
