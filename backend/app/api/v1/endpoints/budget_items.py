"""Budget item CRUD endpoints + per-project budget summary aggregation."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

import io
from decimal import Decimal as _Decimal
from decimal import InvalidOperation as _InvalidOperation
from typing import Literal

from fastapi import File, Form, UploadFile
from openpyxl import load_workbook

from app.api.deps import CurrentUser, DBSession, require_roles
from app.core.config import settings
from app.services.category_service import get_or_create_category, resolve_category
from app.models.budget import BudgetItem
from app.models.budget_category import BudgetCategory
from app.models.expense import Expense, ExpenseStatus
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.budget import (
    BudgetCategoryBreakdown,
    BudgetImportResult,
    BudgetImportRowError,
    BudgetImportRowWarning,
    BudgetItemCreate,
    BudgetItemResponse,
    BudgetItemUpdate,
    BudgetSummary,
)

router = APIRouter(tags=["Budget Items"])


# ---------- Helpers ----------

async def _ensure_project_exists(db, project_id: int) -> Project:
    project = await db.get(Project, project_id)
    if project is None or not project.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


async def _ensure_category_exists(db, category_id: int) -> BudgetCategory:
    cat = await db.get(BudgetCategory, category_id)
    if cat is None or not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category id={category_id} does not exist or is inactive",
        )
    return cat


async def _get_budget_item_with_category(db, item_id: int) -> BudgetItem | None:
    """Fetch a budget item with its category eagerly loaded."""
    stmt = (
        select(BudgetItem)
        .options(selectinload(BudgetItem.category))
        .where(BudgetItem.id == item_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------- BudgetItem CRUD (nested under projects) ----------

@router.get(
    "/projects/{project_id}/budget-items",
    response_model=list[BudgetItemResponse],
    summary="List budget items for a project",
)
async def list_budget_items(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
) -> list[BudgetItem]:
    await _ensure_project_exists(db, project_id)

    stmt = (
        select(BudgetItem)
        .options(selectinload(BudgetItem.category))
        .join(BudgetCategory, BudgetItem.category_id == BudgetCategory.id)
        .where(BudgetItem.project_id == project_id)
        .order_by(BudgetCategory.display_order, BudgetItem.id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/projects/{project_id}/budget-items",
    response_model=BudgetItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new budget item under a project",
)
async def create_budget_item(
    project_id: int,
    payload: BudgetItemCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BudgetItem:
    await _ensure_project_exists(db, project_id)

    # Resolve category: existing id OR free-text auto-create
    try:
        category = await resolve_category(
            db,
            category_id=payload.category_id,
            category_name_new=payload.category_name_new,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    item = BudgetItem(
        project_id=project_id,
        category_id=category.id,
        description=payload.description,
        planned_amount=payload.planned_amount,
        notes=payload.notes,
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create budget item (constraint violation)",
        )
    await db.refresh(item, attribute_names=["category"])
    return item


@router.put(
    "/projects/{project_id}/budget-items/{item_id}",
    response_model=BudgetItemResponse,
    summary="Update a budget item (scoped under project)",
)
async def update_budget_item(
    project_id: int,
    item_id: int,
    payload: BudgetItemUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BudgetItem:
    await _ensure_project_exists(db, project_id)
    item = await _get_budget_item_with_category(db, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget item not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Category change: existing id OR free-text auto-create (mutually exclusive)
    if "category_id" in update_data or "category_name_new" in update_data:
        try:
            category = await resolve_category(
                db,
                category_id=update_data.get("category_id"),
                category_name_new=update_data.get("category_name_new"),
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        update_data["category_id"] = category.id
        update_data.pop("category_name_new", None)  # not a real ORM field

    for field, value in update_data.items():
        setattr(item, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update budget item (constraint violation)",
        )
    await db.refresh(item, attribute_names=["category"])
    return item


@router.delete(
    "/projects/{project_id}/budget-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a budget item (scoped under project)",
)
async def delete_budget_item(
    project_id: int,
    item_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> None:
    await _ensure_project_exists(db, project_id)
    item = await db.get(BudgetItem, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget item not found",
        )

    # Note: expenses with budget_item_id pointing here will have it set to NULL
    # (per ondelete='SET NULL' on Expense.budget_item_id)
    await db.delete(item)
    await db.commit()


# ---------- Budget Summary (aggregation) ----------

@router.get(
    "/projects/{project_id}/budget-summary",
    response_model=BudgetSummary,
    summary="Get budget summary for a project (planned vs spent, by category)",
)
async def get_budget_summary(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
) -> BudgetSummary:
    project = await _ensure_project_exists(db, project_id)

    # Total planned (sum of all budget items)
    total_planned_stmt = select(func.coalesce(func.sum(BudgetItem.planned_amount), 0)).where(
        BudgetItem.project_id == project_id
    )
    total_planned: Decimal = (await db.execute(total_planned_stmt)).scalar_one()

    # Total spent (paid expenses only)
    total_spent_stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.project_id == project_id,
        Expense.status == ExpenseStatus.PAID,
    )
    total_spent: Decimal = (await db.execute(total_spent_stmt)).scalar_one()

    # Total pending (PENDING + APPROVED, not yet paid)
    total_pending_stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.project_id == project_id,
        Expense.status.in_([ExpenseStatus.PENDING, ExpenseStatus.APPROVED]),
    )
    total_pending: Decimal = (await db.execute(total_pending_stmt)).scalar_one()

    remaining = total_planned - total_spent
    utilization_pct = float(total_spent / total_planned * 100) if total_planned > 0 else 0.0

    # Per-category breakdown
    planned_per_cat_stmt = (
        select(
            BudgetItem.category_id,
            func.coalesce(func.sum(BudgetItem.planned_amount), 0).label("planned"),
        )
        .where(BudgetItem.project_id == project_id)
        .group_by(BudgetItem.category_id)
    )
    planned_rows = (await db.execute(planned_per_cat_stmt)).all()
    planned_by_cat: dict[int, Decimal] = {row[0]: row[1] for row in planned_rows}

    spent_per_cat_stmt = (
        select(
            Expense.category_id,
            func.coalesce(func.sum(Expense.amount), 0).label("spent"),
        )
        .where(
            Expense.project_id == project_id,
            Expense.status == ExpenseStatus.PAID,
        )
        .group_by(Expense.category_id)
    )
    spent_rows = (await db.execute(spent_per_cat_stmt)).all()
    spent_by_cat: dict[int, Decimal] = {row[0]: row[1] for row in spent_rows}

    relevant_cat_ids = set(planned_by_cat.keys()) | set(spent_by_cat.keys())
    if relevant_cat_ids:
        cat_stmt = (
            select(BudgetCategory)
            .where(BudgetCategory.id.in_(relevant_cat_ids))
            .order_by(BudgetCategory.display_order, BudgetCategory.id)
        )
        cats = list((await db.execute(cat_stmt)).scalars().all())
    else:
        cats = []

    by_category: list[BudgetCategoryBreakdown] = []
    for cat in cats:
        planned = planned_by_cat.get(cat.id, Decimal("0"))
        spent = spent_by_cat.get(cat.id, Decimal("0"))
        cat_remaining = planned - spent
        cat_util = float(spent / planned * 100) if planned > 0 else 0.0
        by_category.append(
            BudgetCategoryBreakdown(
                category_id=cat.id,
                category_name=cat.name,
                category_slug=cat.slug,
                planned_amount=planned,
                spent_amount=spent,
                remaining_amount=cat_remaining,
                utilization_pct=cat_util,
            )
        )

    return BudgetSummary(
        project_id=project_id,
        project_budget_rub=project.budget_rub,
        total_planned=total_planned,
        total_spent=total_spent,
        total_pending=total_pending,
        remaining=remaining,
        utilization_pct=utilization_pct,
        by_category=by_category,
    )


# ---------- Budget Item Excel Import ----------

# Header aliases (TR / EN / RU). All compared case-insensitively after .lower().
_BUDGET_COLUMN_ALIASES: dict[str, list[str]] = {
    "category": [
        "category", "kategori",
        "категория",  # Cyrillic
        "budget category", "bütçe kategorisi",
    ],
    "description": [
        "item", "item name", "description", "desc",
        "kalem", "kalem adı", "açıklama",
        "наименование", "описание",
    ],
    "amount": [
        "amount", "budget", "total", "planned",
        "tutar", "bütçe", "miktar", "planlanan",
        "сумма", "бюджет",
    ],
    "notes": [
        "notes", "note",
        "not", "açıklama 2",
        "комментарий", "примечание",
    ],
    # Ignored on purpose (brief mentions Code/Cost Code/Kod as optional;
    # we don't have a column for it yet, so any header alias matching
    # this group is silently skipped).
    "_ignored_code": ["code", "cost code", "kod", "код"],
}


def _build_budget_header_map(headers: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(headers):
        if raw is None:
            continue
        normalised = str(raw).strip().lower()
        for field, aliases in _BUDGET_COLUMN_ALIASES.items():
            if field.startswith("_"):  # ignored fields like cost code
                continue
            if normalised in aliases and field not in mapping:
                mapping[field] = idx
                break
    return mapping


@router.post(
    "/projects/{project_id}/budget-items/import",
    response_model=BudgetImportResult,
    summary="Bulk-import budget items from an Excel (.xlsx) file",
)
async def import_budget_items_from_excel(
    project_id: int,
    db: DBSession,
    file: UploadFile = File(...),
    overwrite_mode: Literal["append", "replace"] = Form("append"),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BudgetImportResult:
    """
    Bulk-create budget items from an Excel sheet.

    Modes:
      * append  : insert rows, skip duplicates
                  ((project_id, category_id, lower(description)) match)
      * replace : DELETE every existing budget item for the project first,
                  then insert all rows from the Excel.
                  WARNING: destructive. Caller must confirm in UI.

    Categories:
      * If the row's "Category" cell matches an existing budget category
        (case-insensitive, trim/normalised), that category is used.
      * Otherwise a new category is auto-created (is_system=False).
        Each newly-created category produces a single warning, not one per row.
    """
    await _ensure_project_exists(db, project_id)

    if overwrite_mode not in ("append", "replace"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="overwrite_mode must be 'append' or 'replace'",
        )

    # File extension check
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are accepted",
        )

    max_bytes = settings.MAX_IMPORT_FILE_SIZE_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds {settings.MAX_IMPORT_FILE_SIZE_MB} MB limit",
        )

    # Parse Excel
    try:
        wb = load_workbook(filename=io.BytesIO(contents), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read Excel file",
        )

    ws = wb.active
    if ws is None:
        wb.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active sheet in workbook",
        )

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a header row and at least one data row",
        )

    header_row = rows[0]
    header_map = _build_budget_header_map([str(h) if h else "" for h in header_row])

    # Required columns
    if "amount" not in header_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Could not find an 'amount' / 'tutar' / 'сумма' column. "
                f"Headers found: {[str(h) for h in header_row if h]}"
            ),
        )
    if "description" not in header_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Could not find a description column "
                "(item / kalem / описание / etc)."
            ),
        )

    # Replace mode: wipe existing items first.
    deleted_count = 0
    if overwrite_mode == "replace":
        existing = (await db.execute(
            select(BudgetItem).where(BudgetItem.project_id == project_id)
        )).scalars().all()
        deleted_count = len(existing)
        for item in existing:
            await db.delete(item)
        await db.flush()

    # Pre-load known category IDs (to announce auto-created ones once)
    known_category_ids: set[int] = {
        cat_id for cat_id in (
            await db.execute(select(BudgetCategory.id))
        ).scalars().all()
    }

    # Pre-load existing (category_id, lower(description)) pairs for dup detection.
    # In replace mode we just deleted everything, so this is empty.
    existing_pairs: set[tuple[int, str]] = set()
    if overwrite_mode == "append":
        rows_check = (await db.execute(
            select(BudgetItem.category_id, BudgetItem.description).where(
                BudgetItem.project_id == project_id
            )
        )).all()
        existing_pairs = {(c, (d or "").lower()) for c, d in rows_check}

    # Track in-file duplicates too
    seen_in_file: set[tuple[int, str]] = set()

    imported = 0
    errors: list[BudgetImportRowError] = []
    warnings: list[BudgetImportRowWarning] = []

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            # ---- Description (required) ----
            raw_desc = row[header_map["description"]]
            description = str(raw_desc).strip() if raw_desc else ""
            if not description:
                errors.append(BudgetImportRowError(
                    row=row_idx, reason="Missing description"
                ))
                continue
            description = description[:500]

            # ---- Amount (required) ----
            raw_amount = row[header_map["amount"]]
            if raw_amount is None or str(raw_amount).strip() == "":
                errors.append(BudgetImportRowError(
                    row=row_idx, reason="Missing amount"
                ))
                continue
            try:
                amount = _Decimal(
                    str(raw_amount).replace(",", "").replace(" ", "").strip()
                )
            except (_InvalidOperation, ValueError):
                errors.append(BudgetImportRowError(
                    row=row_idx, reason=f"Invalid amount: {raw_amount}"
                ))
                continue
            if amount < 0:
                errors.append(BudgetImportRowError(
                    row=row_idx, reason=f"Amount cannot be negative: {raw_amount}"
                ))
                continue

            # ---- Category (optional - auto-create) ----
            cat_id: int
            if "category" in header_map:
                raw_cat = row[header_map["category"]]
                if raw_cat and str(raw_cat).strip():
                    try:
                        cat = await get_or_create_category(db, str(raw_cat).strip())
                    except ValueError:
                        errors.append(BudgetImportRowError(
                            row=row_idx, reason="Invalid category name"
                        ))
                        continue
                    cat_id = cat.id
                    if cat.id not in known_category_ids:
                        warnings.append(BudgetImportRowWarning(
                            row=row_idx,
                            reason=f"Auto-created new category '{cat.name}'",
                        ))
                        known_category_ids.add(cat.id)
                else:
                    errors.append(BudgetImportRowError(
                        row=row_idx, reason="Category cell is empty"
                    ))
                    continue
            else:
                errors.append(BudgetImportRowError(
                    row=row_idx,
                    reason="No category column in file (Category / Kategori / Категория required)",
                ))
                continue

            # ---- Notes (optional) ----
            notes_val: str | None = None
            if "notes" in header_map:
                raw_notes = row[header_map["notes"]]
                if raw_notes and str(raw_notes).strip():
                    notes_val = str(raw_notes).strip()

            # ---- Duplicate detection ----
            dup_key = (cat_id, description.lower())
            if dup_key in existing_pairs:
                warnings.append(BudgetImportRowWarning(
                    row=row_idx,
                    reason=f"Skipped: duplicate of existing item ({description})",
                ))
                continue
            if dup_key in seen_in_file:
                warnings.append(BudgetImportRowWarning(
                    row=row_idx,
                    reason=f"Skipped: duplicate within file ({description})",
                ))
                continue
            seen_in_file.add(dup_key)

            # ---- Insert ----
            bi = BudgetItem(
                project_id=project_id,
                category_id=cat_id,
                description=description,
                planned_amount=amount,
                notes=notes_val,
            )
            db.add(bi)
            try:
                await db.flush()
            except IntegrityError as ie:
                await db.rollback()
                errors.append(BudgetImportRowError(
                    row=row_idx,
                    reason=f"DB error: {str(ie.orig)[:200]}",
                ))
                continue

            imported += 1

        except Exception as exc:
            errors.append(BudgetImportRowError(row=row_idx, reason=str(exc)))

    # Final commit
    if imported > 0 or deleted_count > 0:
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return BudgetImportResult(
                imported_count=0,
                skipped_count=len(errors) + len(warnings) + imported,
                deleted_count=0,
                errors=errors + [BudgetImportRowError(
                    row=0, reason="Final commit failed - no rows imported"
                )],
                warnings=warnings,
            )

    return BudgetImportResult(
        imported_count=imported,
        skipped_count=len(errors) + len(warnings),
        deleted_count=deleted_count,
        errors=errors,
        warnings=warnings,
    )
