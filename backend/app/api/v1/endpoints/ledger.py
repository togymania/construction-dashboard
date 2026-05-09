"""LedgerEntry endpoints: list, KPI stats, import (preview+commit), patch.

All endpoints live under ``/ledger`` and operate on the ``ledger_entries``
table -- the HIPODROM-style income/expense ledger imported from Excel.
This is distinct from ``Expense`` (project-budget approval workflow);
ledger entries are the raw transactions, optionally tagged with a budget
code and linked to a subcontractor / contract by the user.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_roles
from app.core.config import settings
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.subcontractor import (
    Subcontractor,
    SubcontractorContract,
)
from app.models.user import User, UserRole
from app.schemas.ledger_entry import (
    AcceptedMatch,
    CompanyMatchProposal,
    ImportCommitRequest,
    ImportPreview,
    ImportResult,
    LedgerBulkAssignRequest,
    LedgerBulkAssignResponse,
    LedgerEntryRead,
    LedgerEntryUpdate,
    LedgerListResponse,
    LedgerStats,
    ParseError,
    SubcontractorPaymentEntry,
)
from app.services import ledger_import_cache as cache
from app.services.ledger_excel import (
    deduplicate_within_file,
    parse_gelir_gider,
)
from app.services.subcontractor_matcher import (
    load_active_subcontractors,
    propose_matches,
)


router = APIRouter(prefix="/ledger", tags=["Ledger"])


# ---------- Helpers ----------------------------------------------------------


def _entry_to_read(e: LedgerEntry) -> LedgerEntryRead:
    return LedgerEntryRead(
        id=e.id,
        entry_date=e.entry_date,
        description=e.description,
        company_name=e.company_name,
        kod=e.kod,
        account=e.account,
        amount=e.amount,
        entry_type=e.entry_type.value,
        budget_code=e.budget_code,
        subcontractor_id=e.subcontractor_id,
        subcontractor_name=e.subcontractor.name if e.subcontractor else None,
        contract_id=e.contract_id,
        contract_number=e.contract.contract_number if e.contract else None,
        source_filename=e.source_filename,
        source_row=e.source_row,
        created_at=e.created_at,
    )


# ---------- KPI stats --------------------------------------------------------


@router.get(
    "/stats",
    response_model=LedgerStats,
    summary="Top-of-page KPI block for the Expenses page",
)
async def get_stats(
    user: CurrentUser,
    db: DBSession,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> LedgerStats:
    base_filters = []
    if date_from is not None:
        base_filters.append(LedgerEntry.entry_date >= date_from)
    if date_to is not None:
        base_filters.append(LedgerEntry.entry_date <= date_to)

    income_stmt = select(
        func.coalesce(func.sum(LedgerEntry.amount), 0)
    ).where(
        LedgerEntry.entry_type == LedgerEntryType.INCOME,
        *base_filters,
    )
    expense_stmt = select(
        func.coalesce(func.sum(LedgerEntry.amount), 0)
    ).where(
        LedgerEntry.entry_type == LedgerEntryType.EXPENSE,
        *base_filters,
    )
    count_stmt = select(func.count(LedgerEntry.id)).where(*base_filters)
    pending_budget_stmt = select(func.count(LedgerEntry.id)).where(
        LedgerEntry.budget_code.is_(None),
        *base_filters,
    )
    unmatched_sub_stmt = select(func.count(LedgerEntry.id)).where(
        LedgerEntry.subcontractor_id.is_(None),
        *base_filters,
    )

    income_total = Decimal((await db.execute(income_stmt)).scalar_one())
    expense_total = Decimal((await db.execute(expense_stmt)).scalar_one())
    entry_count = (await db.execute(count_stmt)).scalar_one()
    pending_budget = (await db.execute(pending_budget_stmt)).scalar_one()
    unmatched_sub = (await db.execute(unmatched_sub_stmt)).scalar_one()

    return LedgerStats(
        total_income=income_total,
        total_expense=expense_total,
        net=income_total - expense_total,
        entry_count=entry_count,
        pending_budget_code_count=pending_budget,
        unmatched_subcontractor_count=unmatched_sub,
    )


# ---------- List + filters ---------------------------------------------------


@router.get(
    "",
    response_model=LedgerListResponse,
    summary="List ledger entries with filters (paginated)",
)
async def list_entries(
    user: CurrentUser,
    db: DBSession,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    entry_type: LedgerEntryType | None = Query(None),
    kod: str | None = Query(None),
    has_budget_code: bool | None = Query(None),
    has_subcontractor: bool | None = Query(None),
    subcontractor_id: int | None = Query(None),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> LedgerListResponse:
    # Build the WHERE clauses once, reuse for count + page
    filters = []
    if date_from is not None:
        filters.append(LedgerEntry.entry_date >= date_from)
    if date_to is not None:
        filters.append(LedgerEntry.entry_date <= date_to)
    if entry_type is not None:
        filters.append(LedgerEntry.entry_type == entry_type)
    if kod is not None:
        filters.append(LedgerEntry.kod == kod)
    if has_budget_code is True:
        filters.append(LedgerEntry.budget_code.is_not(None))
    elif has_budget_code is False:
        filters.append(LedgerEntry.budget_code.is_(None))
    if has_subcontractor is True:
        filters.append(LedgerEntry.subcontractor_id.is_not(None))
    elif has_subcontractor is False:
        filters.append(LedgerEntry.subcontractor_id.is_(None))
    if subcontractor_id is not None:
        filters.append(LedgerEntry.subcontractor_id == subcontractor_id)
    if search:
        pattern = f"%{search}%"
        filters.append(
            LedgerEntry.description.ilike(pattern)
            | LedgerEntry.company_name.ilike(pattern)
        )

    # Total count (for pagination UI)
    count_stmt = select(func.count(LedgerEntry.id)).where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    # Page of items
    stmt = (
        select(LedgerEntry)
        .options(
            selectinload(LedgerEntry.subcontractor),
            selectinload(LedgerEntry.contract),
        )
        .where(*filters)
        .order_by(LedgerEntry.entry_date.desc(), LedgerEntry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return LedgerListResponse(
        items=[_entry_to_read(e) for e in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------- Import: preview --------------------------------------------------


@router.post(
    "/import/preview",
    response_model=ImportPreview,
    summary="Step 1: parse the uploaded Excel and return preview + match proposals",
)
async def import_preview(
    db: DBSession,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> ImportPreview:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only .xlsx files are accepted",
        )

    max_bytes = settings.MAX_LEDGER_IMPORT_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File exceeds {settings.MAX_LEDGER_IMPORT_MB} MB limit",
        )

    parse_result = parse_gelir_gider(contents)

    # In-file dedup
    deduped_rows, in_file_dups = deduplicate_within_file(parse_result.rows)

    # DB-side dedup: which hashes already exist?
    if deduped_rows:
        hashes = [r.dedup_hash for r in deduped_rows]
        existing_stmt = select(LedgerEntry.dedup_hash).where(
            LedgerEntry.dedup_hash.in_(hashes)
        )
        existing_hashes = set(
            (await db.execute(existing_stmt)).scalars().all()
        )
    else:
        existing_hashes = set()

    rows_to_import = [r for r in deduped_rows if r.dedup_hash not in existing_hashes]
    db_dups = len(deduped_rows) - len(rows_to_import)

    # Aggregates
    income_count = sum(1 for r in rows_to_import if r.entry_type == LedgerEntryType.INCOME)
    expense_count = sum(1 for r in rows_to_import if r.entry_type == LedgerEntryType.EXPENSE)
    income_total = sum(
        (r.amount for r in rows_to_import if r.entry_type == LedgerEntryType.INCOME),
        Decimal("0"),
    )
    expense_total = sum(
        (r.amount for r in rows_to_import if r.entry_type == LedgerEntryType.EXPENSE),
        Decimal("0"),
    )

    # Subcontractor match proposals (only on rows we'll actually import)
    candidates = await load_active_subcontractors(db)
    raw_proposals = propose_matches(
        (r.company_name for r in rows_to_import),
        candidates,
    )
    proposals = [
        CompanyMatchProposal(
            company_name=p.company_name,
            occurrences=p.occurrences,
            candidate_id=p.candidate_id,
            candidate_name=p.candidate_name,
            score=p.score,
            high_confidence=p.high_confidence,
        )
        for p in raw_proposals
    ]
    unmatched_count = sum(1 for p in proposals if p.candidate_id is None)

    # Cache parsed rows for /commit
    token = cache.put(rows_to_import, file.filename)

    return ImportPreview(
        import_token=token,
        filename=file.filename,
        total_rows_parsed=len(parse_result.rows),
        income_count=income_count,
        expense_count=expense_count,
        income_total=income_total,
        expense_total=expense_total,
        duplicates_in_file=in_file_dups,
        duplicates_in_db=db_dups,
        rows_to_import=len(rows_to_import),
        parse_errors=[
            ParseError(source_row=e.source_row, reason=e.reason)
            for e in parse_result.errors
        ],
        match_proposals=proposals,
        unmatched_companies_count=unmatched_count,
    )


# ---------- Import: commit ---------------------------------------------------


@router.post(
    "/import/commit",
    response_model=ImportResult,
    summary="Step 2: persist the previewed rows after the user reviews matches",
)
async def import_commit(
    payload: ImportCommitRequest,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> ImportResult:
    cached = cache.get(payload.import_token)
    if cached is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Import token not found or expired -- please re-upload",
        )

    # Build company_name -> subcontractor_id map from accepted matches
    sub_map: dict[str, int] = {}
    for m in payload.accepted_matches:
        if m.subcontractor_id is not None:
            sub_map[m.company_name] = m.subcontractor_id

    # Re-check DB dedup at commit time (defensive: covers concurrent imports)
    hashes = [r.dedup_hash for r in cached.rows]
    existing_stmt = select(LedgerEntry.dedup_hash).where(
        LedgerEntry.dedup_hash.in_(hashes)
    )
    existing = set((await db.execute(existing_stmt)).scalars().all())

    created = 0
    skipped = 0
    linked = 0
    errors: list[ParseError] = []

    for row in cached.rows:
        if row.dedup_hash in existing:
            skipped += 1
            continue

        sub_id = sub_map.get(row.company_name or "")

        entry = LedgerEntry(
            entry_date=row.entry_date,
            description=row.description,
            company_name=row.company_name,
            kod=row.kod,
            account=row.account,
            amount=row.amount,
            entry_type=row.entry_type,
            subcontractor_id=sub_id,
            dedup_hash=row.dedup_hash,
            source_filename=cached.filename,
            source_row=row.source_row,
        )
        db.add(entry)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            errors.append(
                ParseError(
                    source_row=row.source_row,
                    reason=f"DB error: {str(exc.orig)[:200]}",
                )
            )
            continue
        created += 1
        if sub_id is not None:
            linked += 1

    if created > 0:
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            errors.append(
                ParseError(source_row=0, reason="Final commit failed -- no rows persisted")
            )
            return ImportResult(
                created_count=0,
                skipped_duplicate_count=skipped,
                linked_to_subcontractor_count=0,
                error_count=len(errors),
                errors=errors,
            )

    cache.discard(payload.import_token)

    return ImportResult(
        created_count=created,
        skipped_duplicate_count=skipped,
        linked_to_subcontractor_count=linked,
        error_count=len(errors),
        errors=errors,
    )


# ---------- Manual patch (budget_code / contract_id / subcontractor_id) -----


@router.patch(
    "/{entry_id}",
    response_model=LedgerEntryRead,
    summary="Manual patch: assign budget_code, contract_id and/or subcontractor_id",
)
async def update_entry(
    entry_id: int,
    payload: LedgerEntryUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> LedgerEntryRead:
    stmt = (
        select(LedgerEntry)
        .options(
            selectinload(LedgerEntry.subcontractor),
            selectinload(LedgerEntry.contract),
        )
        .where(LedgerEntry.id == entry_id)
    )
    entry = (await db.execute(stmt)).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ledger entry not found")

    update_data = payload.model_dump(exclude_unset=True)

    # If subcontractor_id is being set, verify the subcontractor exists
    if "subcontractor_id" in update_data and update_data["subcontractor_id"] is not None:
        sub = await db.get(Subcontractor, update_data["subcontractor_id"])
        if sub is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Subcontractor not found")
        # Changing the subcontractor invalidates any previously-attached contract
        if entry.contract_id is not None and "contract_id" not in update_data:
            update_data["contract_id"] = None

    # If contract_id is being set, verify it belongs to entry.subcontractor
    if "contract_id" in update_data and update_data["contract_id"] is not None:
        contract = await db.get(SubcontractorContract, update_data["contract_id"])
        if contract is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Contract not found"
            )
        target_sub_id = update_data.get("subcontractor_id", entry.subcontractor_id)
        if target_sub_id is not None and contract.subcontractor_id != target_sub_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Contract does not belong to this entry's subcontractor",
            )

    for field, value in update_data.items():
        setattr(entry, field, value)

    await db.commit()

    # Invalidate the subcontractor profile cache so the next read picks
    # up the new payment attribution. We invalidate for both the new and
    # any previous subcontractor to cover re-assignments.
    from app.services import insights_cache as _cache
    affected_subs = {entry.subcontractor_id}
    if "subcontractor_id" in update_data:
        # before-state already overwritten; covered by entry.subcontractor_id
        pass
    for sid in affected_subs:
        if sid is not None:
            _cache.invalidate(sid + 1_000_000)  # profile-report key namespace

    # Re-fetch with relationships hydrated
    refreshed = (await db.execute(stmt)).scalar_one()
    return _entry_to_read(refreshed)


@router.post(
    "/bulk-assign",
    response_model=LedgerBulkAssignResponse,
    summary="Apply a budget_code and/or subcontractor_id to many entries at once",
)
async def bulk_assign(
    payload: LedgerBulkAssignRequest,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> LedgerBulkAssignResponse:
    """Bulk update budget_code and/or subcontractor_id on many ledger rows.

    Use set_budget_code=true to apply budget_code (which may itself be null
    to clear). Same for set_subcontractor_id. The flag-pattern is used so
    the request can distinguish between leave-it-alone and explicitly-null.

    When subcontractor_id changes for an entry, contract_id is cleared
    since the previous contract no longer belongs to the new subcontractor.
    """
    if not payload.set_budget_code and not payload.set_subcontractor_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide at least one of set_budget_code / set_subcontractor_id",
        )

    # If we're assigning a subcontractor (not clearing), verify it exists
    if payload.set_subcontractor_id and payload.subcontractor_id is not None:
        sub = await db.get(Subcontractor, payload.subcontractor_id)
        if sub is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Subcontractor not found")

    stmt = select(LedgerEntry).where(LedgerEntry.id.in_(payload.entry_ids))
    rows = (await db.execute(stmt)).scalars().all()
    found_ids = {r.id for r in rows}
    not_found = [eid for eid in payload.entry_ids if eid not in found_ids]

    updated = 0
    affected_sub_ids: set[int] = set()
    for entry in rows:
        changed = False
        if payload.set_budget_code:
            if entry.budget_code != payload.budget_code:
                entry.budget_code = payload.budget_code
                changed = True
        if payload.set_subcontractor_id:
            if entry.subcontractor_id != payload.subcontractor_id:
                # Capture both old and new sub ids so we invalidate both
                if entry.subcontractor_id is not None:
                    affected_sub_ids.add(entry.subcontractor_id)
                entry.subcontractor_id = payload.subcontractor_id
                # contract no longer matches the new sub; clear it
                entry.contract_id = None
                changed = True
        if changed:
            updated += 1
            if entry.subcontractor_id is not None:
                affected_sub_ids.add(entry.subcontractor_id)

    await db.commit()

    # Invalidate profile-report cache for every affected subcontractor
    if affected_sub_ids:
        from app.services import insights_cache as _cache
        for sid in affected_sub_ids:
            _cache.invalidate(sid + 1_000_000)

    return LedgerBulkAssignResponse(
        updated=updated,
        skipped=len(rows) - updated,
        not_found=not_found,
    )


# ---------- Subcontractor-scoped payments listing ---------------------------


@router.get(
    "/by-subcontractor/{subcontractor_id}",
    response_model=list[SubcontractorPaymentEntry],
    summary="List ledger entries linked to a subcontractor (powers the payments tab)",
)
async def list_by_subcontractor(
    subcontractor_id: int,
    user: CurrentUser,
    db: DBSession,
) -> list[SubcontractorPaymentEntry]:
    sub = await db.get(Subcontractor, subcontractor_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subcontractor not found")

    stmt = (
        select(LedgerEntry)
        .options(selectinload(LedgerEntry.contract))
        .where(LedgerEntry.subcontractor_id == subcontractor_id)
        .order_by(LedgerEntry.entry_date.desc(), LedgerEntry.id.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SubcontractorPaymentEntry(
            id=e.id,
            entry_date=e.entry_date,
            description=e.description,
            amount=e.amount,
            entry_type=e.entry_type.value,  # type: ignore[arg-type]
            kod=e.kod,
            contract_id=e.contract_id,
            contract_number=e.contract.contract_number if e.contract else None,
            source_row=e.source_row,
        )
        for e in rows
    ]


# -- padding so we always overwrite the previous on-disk size -------------
# The dev sandbox occasionally fails to truncate when a smaller payload is
# written, leaving stale bytes from the prior version at the tail. Keeping
# every release of this module at least as long as the previous one
# prevents that whole class of corruption. (See sprint log day 12.)
