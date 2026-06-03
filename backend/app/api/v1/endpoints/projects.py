"""Project CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, UserLang, require_roles
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.project import (
    ProjectCreate,
    ProjectExecutiveReport,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.financials import ProjectFinancialsRead
from app.schemas.project_ai_analysis import ProjectAIAnalysis
from app.services.metrics import compute_project_financials

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get(
    "/{project_id}/financials",
    response_model=ProjectFinancialsRead,
    summary="Canonical project financial metrics (Single Source of Truth)",
)
async def get_project_financials(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
) -> ProjectFinancialsRead:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    fin = await compute_project_financials(db, project_id)
    return ProjectFinancialsRead(
        project_id=fin.project_id,
        budget_total=fin.budget_total,
        planned_total=fin.planned_total,
        committed_total=fin.committed_total,
        spent_total=fin.spent_total,
        remaining=fin.remaining,
        utilization_pct=fin.utilization_pct,
        budget_consumed_pct=fin.budget_consumed_pct,
    )


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List all projects",
)
async def list_projects(
    user: CurrentUser,
    db: DBSession,
    status_filter: str | None = Query(None, alias="status"),
    health_filter: str | None = Query(None, alias="health"),
    search: str | None = Query(None),
    include_inactive: bool = Query(False),
) -> list[Project]:
    stmt = select(Project).options(selectinload(Project.owner))

    if not include_inactive:
        stmt = stmt.where(Project.is_active == True)  # noqa: E712

    if status_filter:
        stmt = stmt.where(Project.status == status_filter)

    if health_filter:
        stmt = stmt.where(Project.health == health_filter)

    if search:
        stmt = stmt.where(Project.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(Project.created_at.desc())

    result = await db.execute(stmt)
    projects = result.scalars().all()
    return list(projects)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project by ID",
)
async def get_project(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
) -> Project:
    stmt = (
        select(Project)
        .options(selectinload(Project.owner))
        .where(Project.id == project_id, Project.is_active == True)  # noqa: E712
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    payload: ProjectCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> Project:
    project = Project(
        name=payload.name,
        description=payload.description,
        status=payload.status,
        health=payload.health,
        budget_rub=payload.budget_rub,
        start_date=payload.start_date,
        end_date=payload.end_date,
        progress_pct=payload.progress_pct,
        location=payload.location,
        owner_id=user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project, attribute_names=["owner"])
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user: CurrentUser,
    db: DBSession,
) -> Project:
    stmt = (
        select(Project)
        .options(selectinload(Project.owner))
        .where(Project.id == project_id, Project.is_active == True)  # noqa: E712
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    is_admin = user.role == UserRole.ADMIN
    is_pm = user.role == UserRole.PROJECT_MANAGER
    is_owner = project.owner_id == user.id

    if not (is_admin or is_pm or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this project",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project, attribute_names=["owner"])
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project (soft delete, admin only)",
)
async def delete_project(
    project_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> None:
    stmt = select(Project).where(Project.id == project_id, Project.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project.is_active = False
    await db.commit()


# ---------- EAC (Earned Value Management) ----------


@router.get(
    "/{project_id}/eac",
    summary="Project Earned-Value metrics (BAC/AC/EV/CPI/EAC/VAC)",
)
async def get_eac(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Compute Earned Value Management figures for a project.

    Returns a dict with:
      bac  -- Budget at Completion (sum of budget_items.planned_amount,
              falling back to project.budget_rub when items are absent)
      ac   -- Actual Cost: ledger EXPENSE + Expense rows for this project
      ev   -- Earned Value = progress_pct * BAC
      cpi  -- Cost Performance Index = EV / AC (1.0 when AC==0)
      eac  -- Estimate at Completion = AC + (BAC - EV) / CPI
      vac  -- Variance at Completion = BAC - EAC (positive = under budget)
      status -- categorical UNDER_BUDGET / ON_TRACK / OVER_BUDGET / UNKNOWN
    """
    from decimal import Decimal
    from sqlalchemy import func
    from app.models.budget import BudgetItem
    from app.models.expense import Expense
    from app.models.financial_summary import FinancialSummary
    from app.models.ledger_entry import LedgerEntry, LedgerEntryType
    from app.models.subcontractor import SubcontractorContract

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    bac = Decimal((await db.execute(
        select(func.coalesce(func.sum(BudgetItem.planned_amount), 0))
        .where(BudgetItem.project_id == project_id)
    )).scalar_one() or 0)
    if bac == 0:
        bac = Decimal(project.budget_rub or 0)

    # AC (Actual Cost) — Finansal Özet (OZET) Toplam Gider'inden çekilir.
    # OZET satırları varsa: her şirket için negatif kalemleri topla
    # (firma_odemeleri, ucret_giderleri, vergi_odemeleri, banka_giderleri,
    # diger_gelir_giderler eğer negatifse). gelir_vergisi + kdv sub-item'lar
    # vergi_odemeleri içinde zaten — çift sayma yok. toplam roll-up'tır,
    # dahil edilmez.
    # OZET yoksa eski mantığa düş: ledger EXPENSE + Expense tablosu.
    fs_rows = (
        await db.execute(
            select(FinancialSummary).where(FinancialSummary.project_id == project_id)
        )
    ).scalars().all()

    if fs_rows:
        PARENT_EXPENSE_FIELDS = (
            "firma_odemeleri",
            "ucret_giderleri",
            "vergi_odemeleri",
            "banka_giderleri",
            "diger_gelir_giderler",
        )
        ac = Decimal(0)
        for row in fs_rows:
            for field in PARENT_EXPENSE_FIELDS:
                val = getattr(row, field, None) or Decimal(0)
                if val < 0:
                    ac += -val  # absolute value
    else:
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

    progress = float(project.progress_pct or 0)
    ev = bac * Decimal(progress / 100.0) if bac > 0 else Decimal(0)
    cpi = float(ev / ac) if ac > 0 else 1.0
    eac = ac + (bac - ev) / Decimal(cpi if cpi > 0 else 1.0)
    vac = bac - eac

    if bac == 0:
        eac_status = "UNKNOWN"
    elif eac > bac * Decimal("1.05"):
        eac_status = "OVER_BUDGET"
    elif eac < bac * Decimal("0.95"):
        eac_status = "UNDER_BUDGET"
    else:
        eac_status = "ON_TRACK"

    return {
        "bac": float(bac),
        "ac": float(ac),
        "ev": float(ev),
        "cpi": round(cpi, 3),
        "eac": float(eac),
        "vac": float(vac),
        "progress_pct": progress,
        "status": eac_status,
    }


# ---------- Executive Report (Faz 5) ----------


# Cache key offset for executive report — disjoint from sub profile (>1M)
# and dashboard briefing (-42).
_EXEC_REPORT_KEY_OFFSET = 2_000_000


@router.get(
    "/{project_id}/executive-report",
    response_model=ProjectExecutiveReport,
    summary="AI-narrated 1-2 page executive report for the project",
)
async def get_executive_report(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
    lang: UserLang,
    force_refresh: bool = Query(False, description="Bypass cache and re-generate"),
) -> ProjectExecutiveReport:
    """Build the executive digest for a project.

    Cached via ``insights_cache`` (10-min TTL, keyed per UI language so EN
    and TR variants don't shadow each other). The Claude path is the
    expensive one; rule-based fallback is sub-second.
    """
    from app.services import insights_cache
    from app.services.project_executive_report import build_executive_report

    # Multiply by 10 then add lang flag so EN/TR have separate cache slots.
    cache_key = (project_id + _EXEC_REPORT_KEY_OFFSET) * 10 + (
        1 if lang == "TR" else 0
    )
    if not force_refresh:
        cached = insights_cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

    payload = await build_executive_report(db, project_id, lang=lang)
    if payload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    report = ProjectExecutiveReport(**payload)
    insights_cache.set(cache_key, report)  # type: ignore[arg-type]
    return report


# Cache key offset for AI analysis — disjoint from the others.
_AI_ANALYSIS_KEY_OFFSET = 3_000_000


@router.get(
    "/{project_id}/ai-analysis",
    response_model=ProjectAIAnalysis,
    summary="Six-section AI project control & risk analysis",
)
async def get_ai_analysis(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
    lang: UserLang,
    force_refresh: bool = Query(False, description="Bypass cache and re-generate"),
) -> ProjectAIAnalysis:
    """Run the full schedule + data quality + finance + productivity +
    risk + executive analysis for a project.

    Cached for 15 minutes per (project, language) so demo refreshes feel
    instant while the underlying Claude call is gated. Pass
    ``force_refresh=true`` to re-run.
    """
    from app.services import insights_cache
    from app.services.project_ai_analysis import build_ai_analysis

    cache_key = (project_id + _AI_ANALYSIS_KEY_OFFSET) * 10 + (
        1 if lang == "TR" else 0
    )
    if not force_refresh:
        cached = insights_cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

    analysis = await build_ai_analysis(db, project_id, lang=lang)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    insights_cache.set(cache_key, analysis)  # type: ignore[arg-type]
    return analysis
