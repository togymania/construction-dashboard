"""Dashboard aggregation endpoints."""
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.models.expense import Expense, ExpenseStatus
from app.models.project import Project, ProjectHealth, ProjectStatus
from app.schemas.dashboard import DashboardStats, KPIMetric

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _format_budget_rub(total: Decimal) -> str:
    """Format a RUB amount as full number with thousands separator."""
    return f"{int(total):,} RUB"


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

    # Total budget of active projects (RUB)
    total_budget_stmt = select(func.coalesce(func.sum(Project.budget_rub), 0)).where(
        Project.is_active == True,  # noqa: E712
        Project.status == ProjectStatus.ACTIVE,
    )
    total_budget: Decimal = (await db.execute(total_budget_stmt)).scalar_one()

    # Total spent across active projects (paid expenses only)
    total_spent_stmt = (
        select(func.coalesce(func.sum(Expense.amount), 0))
        .join(Project, Expense.project_id == Project.id)
        .where(
            Project.is_active == True,  # noqa: E712
            Project.status == ProjectStatus.ACTIVE,
            Expense.status == ExpenseStatus.PAID,
        )
    )
    total_spent: Decimal = (await db.execute(total_spent_stmt)).scalar_one()

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

    # Budget utilization across portfolio
    if total_budget > 0:
        utilization_pct = float(total_spent / total_budget * 100)
        budget_subtitle = f"{utilization_pct:.1f}% used ({_format_budget_rub(total_spent)})"
        budget_trend = "up" if utilization_pct < 80 else ("neutral" if utilization_pct < 100 else "down")
    else:
        budget_subtitle = "No active budget"
        budget_trend = "neutral"

    return DashboardStats(
        active_projects=KPIMetric(
            label="Active Projects",
            value=str(active_count),
            change=f"{active_count} total",
            trend="neutral",
        ),
        total_budget=KPIMetric(
            label="Total Budget",
            value=_format_budget_rub(total_budget),
            change=budget_subtitle,
            trend=budget_trend,
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
