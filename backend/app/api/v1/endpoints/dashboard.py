"""Dashboard aggregation endpoints.

Two endpoints live here:

* ``GET /dashboard/stats``         -- the four headline KPIs (count of
  active projects, total budget, on-track count, open-risk count).
* ``GET /dashboard/daily-briefing`` -- AI-narrated executive briefing for
  the past 24 hours (Claude when ``ANTHROPIC_API_KEY`` is set, rule-based
  fallback otherwise). Cached for 10 minutes; ``force_refresh=true``
  bypasses.
"""
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.models.expense import Expense, ExpenseStatus
from app.models.project import Project, ProjectHealth, ProjectStatus
from app.schemas.dashboard import DailyBriefing, DashboardStats, KPIMetric

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# Cache key for the daily briefing -- disjoint from the subcontractor
# profile cache (sub_id + 1_000_000) and the project executive report
# cache (project_id + 2_000_000). A negative integer can't collide with
# any realistic id-derived key.
_BRIEFING_CACHE_KEY = -42


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
        budget_subtitle = (
            f"{utilization_pct:.1f}% used ({_format_budget_rub(total_spent)})"
        )
        if utilization_pct < 80:
            budget_trend = "up"
        elif utilization_pct < 100:
            budget_trend = "neutral"
        else:
            budget_trend = "down"
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


@router.get(
    "/daily-briefing",
    response_model=DailyBriefing,
    summary="Daily AI-generated executive briefing for the dashboard",
)
async def get_daily_briefing(
    user: CurrentUser,
    db: DBSession,
    force_refresh: bool = Query(
        False, description="Bypass cache and re-generate"
    ),
) -> DailyBriefing:
    """Return today's executive briefing.

    Cached via ``insights_cache`` (10-minute TTL). The Claude call is the
    expensive part; the rule-based fallback is sub-second so the cache is
    mostly there to avoid hammering the LLM provider. Pass
    ``force_refresh=true`` to bypass it.
    """
    from app.services import insights_cache
    from app.services.daily_briefing import build_daily_briefing

    if not force_refresh:
        cached = insights_cache.get(_BRIEFING_CACHE_KEY)
        if cached is not None:
            return cached  # type: ignore[return-value]

    payload = await build_daily_briefing(db)
    briefing = DailyBriefing(**payload)
    insights_cache.set(_BRIEFING_CACHE_KEY, briefing)  # type: ignore[arg-type]
    return briefing


# -- padding so we always overwrite the previous on-disk size -------------
# The dev sandbox occasionally fails to truncate when a smaller payload is
# written, leaving stale bytes from the prior version at the tail. Keeping
# every release of this module at least as long as the previous one
# prevents that whole class of corruption. (See sprint log day 12.)
