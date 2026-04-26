"""Category resolution service.

Provides helpers for resolving (and auto-creating) budget categories
from free-text input. Used by:
  * Manual expense create/update endpoints
  * Excel expense import
  * Excel budget item import (day 7+)

Naming rules:
  * Whitespace is trimmed and collapsed (multiple spaces -> single space).
  * Lookup is case-insensitive ("Materials" == "materials" == "  MATERIALS  ").
  * Original casing as typed by the user is preserved in the new row.
  * Slug is generated from the normalised name; collisions are avoided
    by appending an integer suffix.
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget_category import BudgetCategory


# ---- Public helpers ----


def normalize_category_name(name: str) -> str:
    """Trim and collapse whitespace. Returns empty string for None/empty input."""
    if not name:
        return ""
    return " ".join(name.split())


def slugify(name: str) -> str:
    """Convert a category name to a URL-safe slug.

    Examples:
        "HVAC Works"         -> "hvac-works"
        "Beton & Çimento"    -> "beton-cimento"
        "Электрика"          -> "elektrika"  (best-effort transliteration)
    """
    if not name:
        return ""
    # Turkish: explicit handling of dotted/dotless I before lowercasing.
    # str.lower() on "İ" produces "i" + combining dot above (U+0307),
    # which would survive the regex strip and pollute the slug.
    name = name.replace("İ", "I").replace("ı", "i")
    # Lowercase
    s = name.lower()
    # Cyrillic -> Latin (basic table covering common Russian letters)
    cyr_map = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
        "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
        "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
        "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    })
    s = s.translate(cyr_map)
    # Turkish diacritics
    tr_map = str.maketrans({
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    })
    s = s.translate(tr_map)
    # Replace anything not [a-z0-9] with hyphen, collapse runs
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "category"


async def find_category_by_name(
    db: AsyncSession, name: str
) -> BudgetCategory | None:
    """Case-insensitive lookup by display name. Returns None if not found."""
    clean = normalize_category_name(name)
    if not clean:
        return None
    stmt = select(BudgetCategory).where(
        func.lower(BudgetCategory.name) == clean.lower()
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_category(
    db: AsyncSession,
    name: str,
) -> BudgetCategory:
    """Find an existing category (case-insensitive) or create a new
    custom one (is_system=False, is_active=True).

    The caller is responsible for committing the transaction. This
    function flushes so that the new row gets an id, but does NOT commit.

    Raises:
        ValueError: if `name` is empty after normalisation.
    """
    clean = normalize_category_name(name)
    if not clean:
        raise ValueError("Category name cannot be empty")

    # 1. Look up by case-insensitive name
    existing = await find_category_by_name(db, clean)
    if existing is not None:
        return existing

    # 2. Compute next display_order (max + 10)
    max_order = (
        await db.execute(
            select(func.coalesce(func.max(BudgetCategory.display_order), 0))
        )
    ).scalar() or 0

    # 3. Generate a unique slug (handle collisions with integer suffix)
    base_slug = slugify(clean)
    slug = base_slug
    suffix = 2
    while True:
        existing_slug = (
            await db.execute(
                select(BudgetCategory).where(BudgetCategory.slug == slug)
            )
        ).scalar_one_or_none()
        if existing_slug is None:
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    # 4. Insert
    new_cat = BudgetCategory(
        name=clean,
        slug=slug,
        display_order=int(max_order) + 10,
        is_system=False,
        is_active=True,
    )
    db.add(new_cat)
    await db.flush()
    return new_cat


async def resolve_category(
    db: AsyncSession,
    *,
    category_id: int | None,
    category_name_new: str | None,
) -> BudgetCategory:
    """High-level helper for endpoints that accept either an existing
    category id or a free-text name (mutually exclusive).

    Used by:
        POST /projects/{id}/expenses
        PUT  /projects/{id}/expenses/{eid}
        POST /projects/{id}/budget-items
        PUT  /budget-items/{id}

    Raises:
        ValueError: when both or neither is supplied, when the id is
                    unknown/inactive, or when the name is empty.
    """
    if (category_id is None) == (category_name_new is None):
        raise ValueError(
            "Provide exactly one of category_id or category_name_new"
        )

    if category_id is not None:
        cat = await db.get(BudgetCategory, category_id)
        if cat is None or not cat.is_active:
            raise ValueError(f"Category id={category_id} not found or inactive")
        return cat

    return await get_or_create_category(db, category_name_new)
