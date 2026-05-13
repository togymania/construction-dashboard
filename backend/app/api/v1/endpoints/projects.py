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

router = APIRouter(prefix="/projects", tags=["Projects"])


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
