"""Budget category CRUD endpoints (admin/manager managed)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, exists, func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.budget import BudgetItem
from app.models.budget_category import BudgetCategory
from app.models.expense import Expense
from app.models.user import User, UserRole
from app.schemas.budget_category import (
    BudgetCategoryCreate,
    BudgetCategoryReorder,
    BudgetCategoryResponse,
    BudgetCategoryUpdate,
)

router = APIRouter(prefix="/budget-categories", tags=["Budget Categories"])


@router.get(
    "",
    response_model=list[BudgetCategoryResponse],
    summary="List budget categories",
)
async def list_categories(
    user: CurrentUser,
    db: DBSession,
    include_inactive: bool = Query(False),
) -> list[BudgetCategory]:
    stmt = select(BudgetCategory).order_by(
        BudgetCategory.display_order, BudgetCategory.id
    )
    if not include_inactive:
        stmt = stmt.where(BudgetCategory.is_active == True)  # noqa: E712

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=BudgetCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new budget category",
)
async def create_category(
    payload: BudgetCategoryCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BudgetCategory:
    category = BudgetCategory(
        name=payload.name,
        slug=payload.slug,
        display_order=payload.display_order,
        is_active=payload.is_active,
        is_system=False,  # User-created categories are never system
    )
    db.add(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name or slug already exists",
        )
    await db.refresh(category)
    return category


@router.put(
    "/{category_id}",
    response_model=BudgetCategoryResponse,
    summary="Update a budget category",
)
async def update_category(
    category_id: int,
    payload: BudgetCategoryUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BudgetCategory:
    category = await db.get(BudgetCategory, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # System categories: only display_order and is_active can be changed
    update_data = payload.model_dump(exclude_unset=True)
    if category.is_system:
        forbidden = set(update_data.keys()) - {"display_order", "is_active"}
        if forbidden:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"System categories cannot have these fields modified: {sorted(forbidden)}",
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name or slug already exists",
        )
    await db.refresh(category)
    return category


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a budget category (admin only). Blocked if in use or system.",
)
async def delete_category(
    category_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN)),
) -> None:
    category = await db.get(BudgetCategory, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    if category.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System categories cannot be deleted. Deactivate them instead.",
        )

    # Check usage in budget_items or expenses (RESTRICT enforcement at app level too)
    in_use_stmt = select(
        case(
            (
                exists().where(BudgetItem.category_id == category_id),
                True,
            ),
            else_=False,
        ).label("used_in_items"),
        case(
            (
                exists().where(Expense.category_id == category_id),
                True,
            ),
            else_=False,
        ).label("used_in_expenses"),
    )
    result = (await db.execute(in_use_stmt)).one()
    if result.used_in_items or result.used_in_expenses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Category is in use. Reassign or delete the related budget items "
                "and expenses first, or deactivate the category instead."
            ),
        )

    await db.delete(category)
    await db.commit()


@router.patch(
    "/reorder",
    response_model=list[BudgetCategoryResponse],
    summary="Bulk reorder categories by ID list",
)
async def reorder_categories(
    payload: BudgetCategoryReorder,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> list[BudgetCategory]:
    # Validate all IDs exist
    stmt = select(BudgetCategory).where(BudgetCategory.id.in_(payload.order))
    result = await db.execute(stmt)
    categories = {c.id: c for c in result.scalars().all()}

    missing = set(payload.order) - set(categories.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category IDs not found: {sorted(missing)}",
        )

    # Apply new order: 10, 20, 30, ... so users can insert categories in between later
    for position, cat_id in enumerate(payload.order, start=1):
        categories[cat_id].display_order = position * 10

    await db.commit()

    # Return all categories in new order
    stmt = select(BudgetCategory).order_by(
        BudgetCategory.display_order, BudgetCategory.id
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
