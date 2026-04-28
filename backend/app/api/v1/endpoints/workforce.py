"""Workforce management endpoints (positions, daily snapshots, KPIs, Excel import)."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_roles
from app.core.config import settings
from app.models.project import Project
from app.models.user import User, UserRole
from app.services.workforce_excel import parse_workforce_excel
from app.models.workforce import (
    WorkforceCategory,
    WorkforceCount,
    WorkforcePosition,
    WorkforceSnapshot,
)
from app.schemas.workforce import (
    WorkforceCategory as WorkforceCategorySchema,
    WorkforceCountInput,
    WorkforceImportResponse,
    WorkforceImportWarning,
    WorkforceMultiImportResponse,
    WorkforceKPIBundle,
    WorkforceKPICategoryToday,
    WorkforceKPICompanyToday,
    WorkforceKPIDailyPoint,
    WorkforceKPITopPosition,
    WorkforceKPIWeeklyBucket,
    WorkforcePositionCreate,
    WorkforcePositionResponse,
    WorkforcePositionUpdate,
    WorkforceSnapshotCreate,
    WorkforceSnapshotListItem,
    WorkforceSnapshotResponse,
    CreatorSummary,
    PositionSummary,
    WorkforceCountResponse,
)


router = APIRouter(tags=["Workforce"])


# ============================================================================
# Helpers
# ============================================================================

_DIACRITIC_MAP = str.maketrans({
    "\u0130": "I", "\u0131": "i", "\u015e": "S", "\u015f": "s",
    "\u011e": "G", "\u011f": "g", "\u00dc": "U", "\u00fc": "u",
    "\u00d6": "O", "\u00f6": "o", "\u00c7": "C", "\u00e7": "c",
})


def normalize_position_name(name: str) -> str:
    """Normalize position name for matching: uppercase, no diacritics, single spaces."""
    if not name:
        return ""
    # Turkish-aware fold
    folded = name.translate(_DIACRITIC_MAP)
    # Remove other accents
    folded = "".join(c for c in unicodedata.normalize("NFD", folded) if unicodedata.category(c) != "Mn")
    folded = folded.upper()
    folded = re.sub(r"\s+", " ", folded).strip()
    return folded


async def _ensure_project(db, project_id: int) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


async def _ensure_position(db, position_id: int) -> WorkforcePosition:
    pos = await db.get(WorkforcePosition, position_id)
    if pos is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")
    return pos


async def _ensure_snapshot(db, project_id: int, snapshot_date: date) -> WorkforceSnapshot:
    stmt = (
        select(WorkforceSnapshot)
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date == snapshot_date,
        )
        .options(selectinload(WorkforceSnapshot.counts).selectinload(WorkforceCount.position))
    )
    snap = (await db.execute(stmt)).scalar_one_or_none()
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found for that date")
    return snap


async def _resolve_or_create_position(
    db, position_id: int | None, position_name: str | None, category: WorkforceCategory | None
) -> tuple[WorkforcePosition, bool]:
    """Resolve a count input to a position. Returns (position, was_created)."""
    if position_id is not None:
        pos = await db.get(WorkforcePosition, position_id)
        if pos is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Position id={position_id} does not exist",
            )
        return pos, False

    # Auto-create path: position_name + category required (validator enforced)
    assert position_name and category
    normalized = normalize_position_name(position_name)
    stmt = select(WorkforcePosition).where(
        WorkforcePosition.category == category,
        WorkforcePosition.name_normalized == normalized,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False

    new_pos = WorkforcePosition(
        category=category,
        name=position_name.strip(),
        name_normalized=normalized,
        display_order=999,
        is_active=True,
    )
    db.add(new_pos)
    await db.flush()
    return new_pos, True


async def _recompute_snapshot_aggregates(db, snapshot: WorkforceSnapshot) -> None:
    """Recompute denormalized aggregates from current counts on the snapshot.

    Async because we may need to fetch position categories for counts whose
    relationship was not eagerly loaded in this session (avoids greenlet error
    on lazy-load through async sessions).
    """
    counts = snapshot.counts or []
    snapshot.total_general_staff = sum(c.general_staff for c in counts)
    snapshot.total_absent = sum(c.absent for c in counts)
    snapshot.total_leave_sick = sum(c.leave_sick for c in counts)
    snapshot.total_present = sum(c.present for c in counts)

    # Build a position_id -> category map without triggering lazy-loads
    pos_ids = {c.position_id for c in counts}
    if pos_ids:
        rows = (await db.execute(
            select(WorkforcePosition.id, WorkforcePosition.category).where(
                WorkforcePosition.id.in_(pos_ids)
            )
        )).all()
        cat_by_pos = {pid: cat for pid, cat in rows}
    else:
        cat_by_pos = {}

    snapshot.direct_present = sum(
        c.present for c in counts if cat_by_pos.get(c.position_id) == WorkforceCategory.DIRECT
    )
    snapshot.indirect_present = sum(
        c.present for c in counts if cat_by_pos.get(c.position_id) == WorkforceCategory.INDIRECT
    )
    snapshot.subcontractor_present = sum(
        c.present for c in counts if cat_by_pos.get(c.position_id) == WorkforceCategory.SUBCONTRACTOR
    )


# ============================================================================
# POSITIONS - admin CRUD
# ============================================================================

@router.get(
    "/workforce/positions",
    response_model=list[WorkforcePositionResponse],
    summary="List workforce positions",
)
async def list_positions(
    db: DBSession,
    _user: CurrentUser,
    category: WorkforceCategorySchema | None = Query(None),
    is_active: bool | None = Query(None),
):
    stmt = select(WorkforcePosition)
    if category is not None:
        stmt = stmt.where(WorkforcePosition.category == category)
    if is_active is not None:
        stmt = stmt.where(WorkforcePosition.is_active == is_active)
    stmt = stmt.order_by(WorkforcePosition.category, WorkforcePosition.display_order, WorkforcePosition.name)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.post(
    "/workforce/positions",
    response_model=WorkforcePositionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workforce position (admin)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def create_position(payload: WorkforcePositionCreate, db: DBSession, _user: CurrentUser):
    normalized = normalize_position_name(payload.name)
    pos = WorkforcePosition(
        category=payload.category,
        name=payload.name.strip(),
        name_normalized=normalized,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    db.add(pos)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Position {payload.name!r} already exists in category {payload.category.value}",
        )
    await db.refresh(pos)
    return pos


@router.patch(
    "/workforce/positions/{position_id}",
    response_model=WorkforcePositionResponse,
    summary="Update a workforce position (admin)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def update_position(position_id: int, payload: WorkforcePositionUpdate, db: DBSession, _user: CurrentUser):
    pos = await _ensure_position(db, position_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        pos.name = data["name"].strip()
        pos.name_normalized = normalize_position_name(data["name"])
    for k in ("category", "display_order", "is_active"):
        if k in data:
            setattr(pos, k, data[k])
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Position with same name already exists in this category")
    await db.refresh(pos)
    return pos


@router.delete(
    "/workforce/positions/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a position (admin) - sets is_active=false",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def delete_position(position_id: int, db: DBSession, _user: CurrentUser):
    pos = await _ensure_position(db, position_id)
    pos.is_active = False
    await db.commit()


# ============================================================================
# PROJECT-SCOPED SNAPSHOTS
# ============================================================================

@router.get(
    "/projects/{project_id}/workforce",
    response_model=list[WorkforceSnapshotListItem],
    summary="List daily workforce snapshots for a project",
)
async def list_snapshots(
    project_id: int,
    db: DBSession,
    _user: CurrentUser,
    limit: int = Query(60, ge=1, le=365),
    offset: int = Query(0, ge=0),
):
    await _ensure_project(db, project_id)
    stmt = (
        select(WorkforceSnapshot)
        .where(WorkforceSnapshot.project_id == project_id)
        .order_by(WorkforceSnapshot.snapshot_date.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.get(
    "/projects/{project_id}/workforce/kpis",
    response_model=WorkforceKPIBundle,
    summary="Workforce KPI bundle for the dashboard",
)
async def workforce_kpis(project_id: int, db: DBSession, _user: CurrentUser):
    """Return aggregated KPI bundle for the project workforce dashboard.

    Multi-company aware: when several snapshots exist for the same date (one per
    company), they are summed for project-wide totals and broken out per company.
    """
    await _ensure_project(db, project_id)

    # Total snapshot count
    snapshot_count = (await db.execute(
        select(func.count(WorkforceSnapshot.id)).where(WorkforceSnapshot.project_id == project_id)
    )).scalar_one()

    if snapshot_count == 0:
        return WorkforceKPIBundle(
            project_id=project_id,
            as_of_date=None,
            snapshot_count=0,
        )

    # Most recent snapshot_date in the project (across all companies)
    latest_date = (await db.execute(
        select(func.max(WorkforceSnapshot.snapshot_date)).where(WorkforceSnapshot.project_id == project_id)
    )).scalar_one()

    # All snapshots for that date (one row per company)
    today_stmt = (
        select(WorkforceSnapshot)
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date == latest_date,
        )
        .options(selectinload(WorkforceSnapshot.counts).selectinload(WorkforceCount.position))
    )
    today_snaps = (await db.execute(today_stmt)).scalars().all()

    # Sum across companies for "today" totals
    today_direct = sum(s.direct_present for s in today_snaps)
    today_indirect = sum(s.indirect_present for s in today_snaps)
    today_subcont = sum(s.subcontractor_present for s in today_snaps)

    # Yesterday = the next-most-recent date (could be 1+ days back)
    prior_date = (await db.execute(
        select(func.max(WorkforceSnapshot.snapshot_date))
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date < latest_date,
        )
    )).scalar_one_or_none()

    prior_direct = prior_indirect = prior_subcont = 0
    if prior_date is not None:
        prior_rows = (await db.execute(
            select(
                func.sum(WorkforceSnapshot.direct_present),
                func.sum(WorkforceSnapshot.indirect_present),
                func.sum(WorkforceSnapshot.subcontractor_present),
            ).where(
                WorkforceSnapshot.project_id == project_id,
                WorkforceSnapshot.snapshot_date == prior_date,
            )
        )).one()
        prior_direct = int(prior_rows[0] or 0)
        prior_indirect = int(prior_rows[1] or 0)
        prior_subcont = int(prior_rows[2] or 0)

    def _delta(today_val: int, prior_val: int) -> tuple[int, float | None]:
        d = today_val - prior_val
        pct = (d / prior_val * 100.0) if prior_val > 0 else None
        return d, pct

    # Per-position counts across all companies for "today"
    pos_count_by_cat = {
        WorkforceCategory.DIRECT: 0,
        WorkforceCategory.INDIRECT: 0,
        WorkforceCategory.SUBCONTRACTOR: 0,
    }
    for s in today_snaps:
        for c in s.counts:
            pos_count_by_cat[c.position.category] += 1

    by_cat: list[WorkforceKPICategoryToday] = []
    for cat, today_val, prior_val in (
        (WorkforceCategory.DIRECT, today_direct, prior_direct),
        (WorkforceCategory.INDIRECT, today_indirect, prior_indirect),
        (WorkforceCategory.SUBCONTRACTOR, today_subcont, prior_subcont),
    ):
        d, pct = _delta(today_val, prior_val)
        by_cat.append(WorkforceKPICategoryToday(
            category=cat,
            present_today=today_val,
            delta_vs_yesterday=d,
            delta_pct=pct,
            position_count=pos_count_by_cat[cat],
        ))

    # Per-company breakdown for "today"
    by_company: list[WorkforceKPICompanyToday] = []
    # Maintain a stable order: Monotekstroy then Monart, then anything else alphabetical
    company_order = {"Monotekstroy": 0, "Monart": 1}
    for s in sorted(today_snaps, key=lambda x: (company_order.get(x.company_label, 99), x.company_label)):
        by_company.append(WorkforceKPICompanyToday(
            company_label=s.company_label,
            snapshot_date=s.snapshot_date,
            direct_present=s.direct_present,
            indirect_present=s.indirect_present,
            subcontractor_present=s.subcontractor_present,
            total_present=s.total_present,
        ))

    # 30-day daily trend - sum companies per date
    cutoff_30 = latest_date - timedelta(days=29)
    trend_rows = (await db.execute(
        select(
            WorkforceSnapshot.snapshot_date,
            func.sum(WorkforceSnapshot.direct_present),
            func.sum(WorkforceSnapshot.indirect_present),
            func.sum(WorkforceSnapshot.subcontractor_present),
            func.sum(WorkforceSnapshot.total_present),
        )
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date >= cutoff_30,
        )
        .group_by(WorkforceSnapshot.snapshot_date)
        .order_by(WorkforceSnapshot.snapshot_date.asc())
    )).all()

    daily_trend = [
        WorkforceKPIDailyPoint(
            snapshot_date=row[0],
            direct_present=int(row[1] or 0),
            indirect_present=int(row[2] or 0),
            subcontractor_present=int(row[3] or 0),
            total_present=int(row[4] or 0),
        )
        for row in trend_rows
    ]

    # "This week vs last week" - simple Monday-anchored buckets, last 2 weeks only
    this_monday = latest_date - timedelta(days=latest_date.weekday())
    last_monday = this_monday - timedelta(days=7)

    week_rows = (await db.execute(
        select(
            WorkforceSnapshot.snapshot_date,
            func.sum(WorkforceSnapshot.direct_present),
            func.sum(WorkforceSnapshot.indirect_present),
            func.sum(WorkforceSnapshot.subcontractor_present),
            func.sum(WorkforceSnapshot.total_present),
        )
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date >= last_monday,
        )
        .group_by(WorkforceSnapshot.snapshot_date)
        .order_by(WorkforceSnapshot.snapshot_date.asc())
    )).all()

    week_buckets: dict[date, list[tuple]] = {last_monday: [], this_monday: []}
    for row in week_rows:
        d = row[0]
        monday = d - timedelta(days=d.weekday())
        if monday in week_buckets:
            week_buckets[monday].append(row)

    weekly: list[WorkforceKPIWeeklyBucket] = []
    for monday in sorted(week_buckets.keys()):
        snaps = week_buckets[monday]
        n = len(snaps)
        if n == 0:
            continue
        weekly.append(WorkforceKPIWeeklyBucket(
            week_start=monday,
            avg_total_present=sum(int(r[4] or 0) for r in snaps) / n,
            avg_direct=sum(int(r[1] or 0) for r in snaps) / n,
            avg_indirect=sum(int(r[2] or 0) for r in snaps) / n,
            avg_subcontractor=sum(int(r[3] or 0) for r in snaps) / n,
            days_recorded=n,
        ))

    # Top positions today (across all companies)
    all_today_counts: list[WorkforceCount] = []
    for s in today_snaps:
        all_today_counts.extend(s.counts)

    # Combine same-position counts across companies
    pos_totals: dict[int, dict] = {}
    for c in all_today_counts:
        pid = c.position_id
        if pid not in pos_totals:
            pos_totals[pid] = {
                "position_id": pid,
                "position_name": c.position.name,
                "category": c.position.category,
                "present": 0,
            }
        pos_totals[pid]["present"] += c.present

    top_positions = sorted(
        [WorkforceKPITopPosition(**v) for v in pos_totals.values()],
        key=lambda x: x.present,
        reverse=True,
    )[:8]

    return WorkforceKPIBundle(
        project_id=project_id,
        as_of_date=latest_date,
        snapshot_count=snapshot_count,
        by_category_today=by_cat,
        by_company_today=by_company,
        daily_trend=daily_trend,
        weekly_buckets=weekly,
        top_positions=top_positions,
    )
    yesterday = (await db.execute(yest_stmt)).scalar_one_or_none()

    def _delta(today_val: int, yest_val: int) -> tuple[int, float | None]:
        d = today_val - yest_val
        pct = (d / yest_val * 100.0) if yest_val > 0 else None
        return d, pct

    # Position counts per category (today)
    pos_count_by_cat = {WorkforceCategory.DIRECT: 0, WorkforceCategory.INDIRECT: 0, WorkforceCategory.SUBCONTRACTOR: 0}
    for c in latest.counts:
        pos_count_by_cat[c.position.category] += 1

    by_cat: list[WorkforceKPICategoryToday] = []
    for cat, today_present, yest_present in (
        (WorkforceCategory.DIRECT, latest.direct_present, yesterday.direct_present if yesterday else 0),
        (WorkforceCategory.INDIRECT, latest.indirect_present, yesterday.indirect_present if yesterday else 0),
        (WorkforceCategory.SUBCONTRACTOR, latest.subcontractor_present, yesterday.subcontractor_present if yesterday else 0),
    ):
        d, pct = _delta(today_present, yest_present)
        by_cat.append(WorkforceKPICategoryToday(
            category=cat,
            present_today=today_present,
            delta_vs_yesterday=d,
            delta_pct=pct,
            position_count=pos_count_by_cat[cat],
        ))

    # 30-day trend
    cutoff_30 = today_date - timedelta(days=29)
    trend_stmt = (
        select(WorkforceSnapshot)
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date >= cutoff_30,
        )
        .order_by(WorkforceSnapshot.snapshot_date.asc())
    )
    trend_rows = (await db.execute(trend_stmt)).scalars().all()
    daily_trend = [
        WorkforceKPIDailyPoint(
            snapshot_date=s.snapshot_date,
            direct_present=s.direct_present,
            indirect_present=s.indirect_present,
            subcontractor_present=s.subcontractor_present,
            total_present=s.total_present,
        )
        for s in trend_rows
    ]

    # 8-week buckets
    cutoff_56 = today_date - timedelta(weeks=8) + timedelta(days=1)
    week_stmt = (
        select(WorkforceSnapshot)
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date >= cutoff_56,
        )
        .order_by(WorkforceSnapshot.snapshot_date.asc())
    )
    week_rows = (await db.execute(week_stmt)).scalars().all()

    # Group by Monday-anchored week
    buckets: dict[date, list[WorkforceSnapshot]] = {}
    for s in week_rows:
        # Monday of that week
        monday = s.snapshot_date - timedelta(days=s.snapshot_date.weekday())
        buckets.setdefault(monday, []).append(s)

    weekly: list[WorkforceKPIWeeklyBucket] = []
    for monday in sorted(buckets.keys()):
        snaps = buckets[monday]
        n = len(snaps)
        weekly.append(WorkforceKPIWeeklyBucket(
            week_start=monday,
            avg_total_present=sum(s.total_present for s in snaps) / n,
            avg_direct=sum(s.direct_present for s in snaps) / n,
            avg_indirect=sum(s.indirect_present for s in snaps) / n,
            avg_subcontractor=sum(s.subcontractor_present for s in snaps) / n,
            days_recorded=n,
        ))

    # Top positions today
    top_positions = sorted(
        [
            WorkforceKPITopPosition(
                position_id=c.position.id,
                position_name=c.position.name,
                category=c.position.category,
                present=c.present,
            )
            for c in latest.counts
        ],
        key=lambda x: x.present,
        reverse=True,
    )[:8]

    return WorkforceKPIBundle(
        project_id=project_id,
        as_of_date=today_date,
        snapshot_count=snapshot_count,
        by_category_today=by_cat,
        daily_trend=daily_trend,
        weekly_buckets=weekly,
        top_positions=top_positions,
    )


@router.get(
    "/projects/{project_id}/workforce/{snapshot_date}",
    response_model=WorkforceSnapshotResponse,
    summary="Get a single daily workforce snapshot with all counts",
)
async def get_snapshot(project_id: int, snapshot_date: date, db: DBSession, _user: CurrentUser):
    await _ensure_project(db, project_id)
    snap = await _ensure_snapshot(db, project_id, snapshot_date)
    return snap


@router.post(
    "/projects/{project_id}/workforce",
    response_model=WorkforceSnapshotResponse,
    summary="Create or replace a workforce snapshot for a date (idempotent upsert)",
)
async def upsert_snapshot(
    project_id: int,
    payload: WorkforceSnapshotCreate,
    db: DBSession,
    user: CurrentUser,
):
    await _ensure_project(db, project_id)

    # Look for existing snapshot on that date
    existing_stmt = (
        select(WorkforceSnapshot)
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date == payload.snapshot_date,
        )
        .options(selectinload(WorkforceSnapshot.counts))
    )
    snap = (await db.execute(existing_stmt)).scalar_one_or_none()

    if snap is None:
        snap = WorkforceSnapshot(
            project_id=project_id,
            snapshot_date=payload.snapshot_date,
            uploaded_by=user.id,
            source=payload.source,
            source_filename=payload.source_filename,
            notes=payload.notes,
        )
        db.add(snap)
        await db.flush()
    else:
        # Wipe existing counts (replace semantics)
        for c in list(snap.counts):
            await db.delete(c)
        await db.flush()
        snap.uploaded_by = user.id
        snap.source = payload.source
        snap.source_filename = payload.source_filename
        snap.notes = payload.notes

    # Add new counts
    for ci in payload.counts:
        pos, _ = await _resolve_or_create_position(db, ci.position_id, ci.position_name, ci.category)
        count = WorkforceCount(
            snapshot_id=snap.id,
            position_id=pos.id,
            general_staff=ci.general_staff,
            absent=ci.absent,
            leave_sick=ci.leave_sick,
            present=ci.present if ci.present is not None else max(0, ci.general_staff - ci.absent - ci.leave_sick),
        )
        db.add(count)

    await db.flush()

    # Reload with counts for aggregate computation
    await db.refresh(snap, attribute_names=["counts"])
    # Need positions on counts for category-aware aggregation
    reload_stmt = (
        select(WorkforceSnapshot)
        .where(WorkforceSnapshot.id == snap.id)
        .options(selectinload(WorkforceSnapshot.counts).selectinload(WorkforceCount.position))
    )
    snap = (await db.execute(reload_stmt)).scalar_one()

    await _recompute_snapshot_aggregates(db, snap)
    await db.commit()
    await db.refresh(snap)

    # Re-fetch with eager loads for response
    final_stmt = (
        select(WorkforceSnapshot)
        .where(WorkforceSnapshot.id == snap.id)
        .options(selectinload(WorkforceSnapshot.counts).selectinload(WorkforceCount.position))
    )
    return (await db.execute(final_stmt)).scalar_one()


@router.delete(
    "/projects/{project_id}/workforce/{snapshot_date}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workforce snapshot for a date",
)
async def delete_snapshot(project_id: int, snapshot_date: date, db: DBSession, _user: CurrentUser):
    await _ensure_project(db, project_id)
    snap = await _ensure_snapshot(db, project_id, snapshot_date)
    await db.delete(snap)
    await db.commit()


# ============================================================================
# EXCEL IMPORT - placeholder (will be implemented in Phase 2.5)
# ============================================================================

async def _import_single_file(
    db,
    project_id: int,
    user,
    file: UploadFile,
) -> WorkforceImportResponse:
    """Process a single Excel file and upsert its snapshot.

    Returns a per-file WorkforceImportResponse. On failure (parse error, missing
    company, etc.) returns success=False with error message; does NOT raise so
    the multi-file endpoint can continue with the remaining files.
    """
    filename = (file.filename or "")[:255]

    # Validate extension
    if not filename.lower().endswith(".xlsx"):
        return WorkforceImportResponse(
            project_id=project_id,
            snapshot_date=None,
            company_label=None,
            source_filename=filename or None,
            success=False,
            error="Only .xlsx files are accepted",
            rows_imported=0, rows_skipped=0, positions_created=0,
        )

    # Validate size
    max_bytes = settings.MAX_IMPORT_FILE_SIZE_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        return WorkforceImportResponse(
            project_id=project_id,
            snapshot_date=None,
            company_label=None,
            source_filename=filename,
            success=False,
            error=f"File exceeds {settings.MAX_IMPORT_FILE_SIZE_MB} MB limit",
            rows_imported=0, rows_skipped=0, positions_created=0,
        )

    # Parse Excel
    try:
        parsed = parse_workforce_excel(contents)
    except Exception as e:
        return WorkforceImportResponse(
            project_id=project_id,
            snapshot_date=None,
            company_label=None,
            source_filename=filename,
            success=False,
            error=f"Could not parse Excel: {e}",
            rows_imported=0, rows_skipped=0, positions_created=0,
        )

    # Validate detected fields
    if parsed.snapshot_date is None:
        return WorkforceImportResponse(
            project_id=project_id,
            snapshot_date=None,
            company_label=parsed.company_label,
            source_filename=filename,
            success=False,
            error="Could not determine snapshot date from Excel header",
            rows_imported=0, rows_skipped=0, positions_created=0,
        )

    if parsed.company_label is None:
        return WorkforceImportResponse(
            project_id=project_id,
            snapshot_date=parsed.snapshot_date,
            company_label=None,
            source_filename=filename,
            success=False,
            error=f"Could not detect company from Excel - expected Monotekstroy or Monart in header. project_label={parsed.project_label!r}",
            rows_imported=0, rows_skipped=0, positions_created=0,
        )

    if not parsed.rows:
        return WorkforceImportResponse(
            project_id=project_id,
            snapshot_date=parsed.snapshot_date,
            company_label=parsed.company_label,
            source_filename=filename,
            success=False,
            error="No data rows extracted from cover page - is this a valid puantaj file?",
            rows_imported=0, rows_skipped=0, positions_created=0,
        )

    warnings: list[WorkforceImportWarning] = []

    # Upsert: find existing snapshot or create new (now keyed by project + date + company)
    existing_stmt = (
        select(WorkforceSnapshot)
        .where(
            WorkforceSnapshot.project_id == project_id,
            WorkforceSnapshot.snapshot_date == parsed.snapshot_date,
            WorkforceSnapshot.company_label == parsed.company_label,
        )
        .options(selectinload(WorkforceSnapshot.counts))
    )
    snap = (await db.execute(existing_stmt)).scalar_one_or_none()

    if snap is None:
        snap = WorkforceSnapshot(
            project_id=project_id,
            snapshot_date=parsed.snapshot_date,
            company_label=parsed.company_label,
            uploaded_by=user.id,
            source="excel",
            source_filename=filename,
            notes=f"Project label: {parsed.project_label}" if parsed.project_label else None,
        )
        db.add(snap)
        await db.flush()
    else:
        warnings.append(WorkforceImportWarning(
            code="SNAPSHOT_REPLACED",
            message=f"Existing {parsed.company_label} snapshot for {parsed.snapshot_date} was replaced",
        ))
        for c in list(snap.counts):
            await db.delete(c)
        await db.flush()
        snap.uploaded_by = user.id
        snap.source = "excel"
        snap.source_filename = filename
        snap.notes = f"Project label: {parsed.project_label}" if parsed.project_label else None

    rows_imported = 0
    rows_skipped = 0
    positions_created = 0

    for prow in parsed.rows:
        category = WorkforceCategory(prow.category)
        try:
            pos, was_created = await _resolve_or_create_position(
                db, position_id=None, position_name=prow.position_name, category=category
            )
        except HTTPException as e:
            warnings.append(WorkforceImportWarning(
                code="POSITION_RESOLVE_FAILED",
                message=f"Skipped {prow.position_name!r}: {e.detail}",
            ))
            rows_skipped += 1
            continue

        if was_created:
            positions_created += 1
            warnings.append(WorkforceImportWarning(
                code="UNKNOWN_POSITION_CREATED",
                message=f"Auto-created position {pos.name!r} ({category.value})",
                detail={"position_id": pos.id, "name": pos.name, "category": category.value},
            ))

        count = WorkforceCount(
            snapshot_id=snap.id,
            position_id=pos.id,
            general_staff=prow.general_staff,
            absent=prow.absent,
            leave_sick=prow.leave_sick,
            present=prow.present,
        )
        db.add(count)
        rows_imported += 1

    await db.flush()

    # Reload + recompute aggregates
    reload_stmt = (
        select(WorkforceSnapshot)
        .where(WorkforceSnapshot.id == snap.id)
        .options(selectinload(WorkforceSnapshot.counts).selectinload(WorkforceCount.position))
    )
    snap = (await db.execute(reload_stmt)).scalar_one()
    await _recompute_snapshot_aggregates(db, snap)

    # GRAND TOTAL validation
    if parsed.grand_total is not None:
        gt = parsed.grand_total
        if (gt.general_staff != snap.total_general_staff
                or gt.absent != snap.total_absent
                or gt.leave_sick != snap.total_leave_sick
                or gt.present != snap.total_present):
            warnings.append(WorkforceImportWarning(
                code="GRAND_TOTAL_MISMATCH",
                message=(
                    f"Excel GRAND TOTAL (g={gt.general_staff}, a={gt.absent}, "
                    f"l={gt.leave_sick}, p={gt.present}) does not match summed rows "
                    f"(g={snap.total_general_staff}, a={snap.total_absent}, "
                    f"l={snap.total_leave_sick}, p={snap.total_present})"
                ),
            ))

    for pw in parsed.parse_warnings:
        warnings.append(WorkforceImportWarning(code="PARSER_WARNING", message=pw))

    # Build response (manual to avoid lazy-load greenlet issues)
    snap_row = (await db.execute(
        select(WorkforceSnapshot).where(WorkforceSnapshot.id == snap.id)
    )).scalar_one()

    uploader_summary = None
    if snap_row.uploaded_by:
        uploader = (await db.execute(
            select(User).where(User.id == snap_row.uploaded_by)
        )).scalar_one_or_none()
        if uploader:
            uploader_summary = CreatorSummary(
                id=uploader.id, email=uploader.email, full_name=uploader.full_name,
            )

    count_rows = (await db.execute(
        select(WorkforceCount).where(WorkforceCount.snapshot_id == snap_row.id)
    )).scalars().all()

    pos_ids = list({c.position_id for c in count_rows})
    pos_map: dict[int, WorkforcePosition] = {}
    if pos_ids:
        pos_rows = (await db.execute(
            select(WorkforcePosition).where(WorkforcePosition.id.in_(pos_ids))
        )).scalars().all()
        pos_map = {p.id: p for p in pos_rows}

    count_responses = []
    for c in count_rows:
        p = pos_map.get(c.position_id)
        if p is None:
            continue
        count_responses.append(WorkforceCountResponse(
            id=c.id,
            general_staff=c.general_staff, absent=c.absent,
            leave_sick=c.leave_sick, present=c.present,
            position=PositionSummary(
                id=p.id, category=p.category, name=p.name,
                display_order=p.display_order,
            ),
        ))

    snap_response = WorkforceSnapshotResponse(
        id=snap_row.id,
        project_id=snap_row.project_id,
        snapshot_date=snap_row.snapshot_date,
        company_label=snap_row.company_label,
        source=snap_row.source,
        source_filename=snap_row.source_filename,
        notes=snap_row.notes,
        total_general_staff=snap_row.total_general_staff,
        total_absent=snap_row.total_absent,
        total_leave_sick=snap_row.total_leave_sick,
        total_present=snap_row.total_present,
        direct_present=snap_row.direct_present,
        indirect_present=snap_row.indirect_present,
        subcontractor_present=snap_row.subcontractor_present,
        uploaded_by_user=uploader_summary,
        created_at=snap_row.created_at,
        updated_at=snap_row.updated_at,
        counts=count_responses,
    )

    return WorkforceImportResponse(
        project_id=project_id,
        snapshot_date=parsed.snapshot_date,
        company_label=parsed.company_label,
        source_filename=filename,
        success=True,
        error=None,
        rows_imported=rows_imported,
        rows_skipped=rows_skipped,
        positions_created=positions_created,
        warnings=warnings,
        snapshot=snap_response,
    )


@router.post(
    "/projects/{project_id}/workforce/import",
    response_model=WorkforceMultiImportResponse,
    summary="Bulk import multiple daily snapshots from Excel cover-page format",
)
async def import_workforce_from_excel(
    project_id: int,
    db: DBSession,
    user: CurrentUser,
    files: list[UploadFile] = File(...),
):
    """Parse one or more cover-page-format Excels and upsert each snapshot.

    Behavior:
    - 1-10 files per request
    - Each file MUST contain Monotekstroy or Monart in the header (B2 area)
    - One snapshot per (project, date, company) - same date for both companies coexists
    - Files that fail (parse error, missing company, etc.) are reported per-file
      with success=False; the rest still succeed
    """
    await _ensure_project(db, project_id)

    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one file is required")
    if len(files) > 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum 10 files per import")

    results: list[WorkforceImportResponse] = []
    for file in files:
        try:
            r = await _import_single_file(db, project_id, user, file)
        except Exception as e:
            r = WorkforceImportResponse(
                project_id=project_id,
                snapshot_date=None,
                company_label=None,
                source_filename=(file.filename or "")[:255] or None,
                success=False,
                error=f"Unexpected error: {e}",
                rows_imported=0, rows_skipped=0, positions_created=0,
            )
            await db.rollback()
        results.append(r)

    # Commit ONCE at the end - per-file flushes are already done inside helper
    await db.commit()

    return WorkforceMultiImportResponse(
        project_id=project_id,
        files_total=len(files),
        files_succeeded=sum(1 for r in results if r.success),
        files_failed=sum(1 for r in results if not r.success),
        results=results,
    )

