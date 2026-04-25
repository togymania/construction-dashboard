"""Budget item CRUD endpoints + per-project budget summary aggregation."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.budget import BudgetItem
from app.models.budget_category import BudgetCategory
from app.models.expense import Expense, ExpenseStatus
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.budget import (
    BudgetCategoryBreakdown,
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
    await _ensure_category_exists(db, payload.category_id)

    item = BudgetItem(
        project_id=project_id,
        category_id=payload.category_id,
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
    "/budget-items/{item_id}",
    response_model=BudgetItemResponse,
    summary="Update a budget item",
)
async def update_budget_item(
    item_id: int,
    payload: BudgetItemUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BudgetItem:
    item = await _get_budget_item_with_category(db, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget item not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # If category is being changed, validate it
    if "category_id" in update_data:
        await _ensure_category_exists(db, update_data["category_id"])

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
    "/budget-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a budget item",
)
async def delete_budget_item(
    item_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> None:
    item = await db.get(BudgetItem, item_id)
    if item is None:
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
