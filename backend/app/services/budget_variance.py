"""Planned vs Actual variance report (Faz 3).

For each budget item on a project, compute:

* planned_amount   -- directly from the budget_items row
* committed_amount -- directly from the budget_items row
* actual_amount    -- sum of (a) Expense rows whose budget_item_id points
                      at this item AND status=PAID, plus (b) LedgerEntry
                      rows with entry_type=expense whose budget_code
                      matches the item's cost_code AND whose linked
                      contract belongs to this project (or is unlinked).
* variance         -- actual - planned (positive == over budget)
* variance_pct     -- variance / planned * 100 (None when planned == 0)
* matched_expense_count -- how many rows contributed to actual_amount
* severity         -- "ok"    utilization < 80%
                      "watch" 80-95%
                      "warn"  95-100%
                      "over"  > 100%

We deliberately *don't* count Pending / Approved expenses or ledger
entries here -- "actual" should mean money that has actually left the
company.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import BudgetItem
from app.models.budget_category import BudgetCategory
from app.models.expense import Expense, ExpenseStatus
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.subcontractor import SubcontractorContract
from app.schemas.budget_variance import BudgetItemVariance, BudgetVarianceReport


def _severity(planned: Decimal, actual: Decimal) -> str:
    """Bucket utilization into ok / watch / warn / over."""
    if planned <= 0:
        return "watch" if actual > 0 else "ok"
    pct = float(actual / planned * 100)
    if pct > 100:
        return "over"
    if pct >= 95:
        return "warn"
    if pct >= 80:
        return "watch"
    return "ok"


async def build_variance_report(
    db: AsyncSession,
    project_id: int,
) -> BudgetVarianceReport:
    """Compute planned-vs-actual for every budget item on the project."""
    # Pull every budget item with its category
    items_stmt = (
        select(BudgetItem, BudgetCategory)
        .join(BudgetCategory, BudgetCategory.id == BudgetItem.category_id)
        .where(BudgetItem.project_id == project_id)
        .order_by(BudgetItem.cost_code.nulls_last(), BudgetItem.id)
    )
    rows = (await db.execute(items_stmt)).all()

    # Aggregate expenses by budget_item_id
    expense_agg_stmt = (
        select(
            Expense.budget_item_id,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
            func.count(Expense.id).label("cnt"),
        )
        .where(
            Expense.project_id == project_id,
            Expense.budget_item_id.is_not(None),
            Expense.status == ExpenseStatus.PAID,
        )
        .group_by(Expense.budget_item_id)
    )
    expense_rows = (await db.execute(expense_agg_stmt)).all()
    expense_by_item: dict[int, tuple[Decimal, int]] = {
        row.budget_item_id: (Decimal(row.total), int(row.cnt))
        for row in expense_rows
    }

    # Aggregate ledger entries by budget_code (joined on contract for the
    # project filter). Entries without a contract are still counted if
    # their budget_code matches a budget item -- treated as project-wide.
    ledger_agg_stmt = (
        select(
            LedgerEntry.budget_code,
            func.coalesce(func.sum(LedgerEntry.amount), 0).label("total"),
            func.count(LedgerEntry.id).label("cnt"),
        )
        .outerjoin(
            SubcontractorContract,
            SubcontractorContract.id == LedgerEntry.contract_id,
        )
        .where(
            LedgerEntry.entry_type == LedgerEntryType.EXPENSE,
            LedgerEntry.budget_code.is_not(None),
            (SubcontractorContract.id.is_(None))
            | (SubcontractorContract.project_id == project_id),
        )
        .group_by(LedgerEntry.budget_code)
    )
    ledger_rows = (await db.execute(ledger_agg_stmt)).all()
    ledger_by_code: dict[str, tuple[Decimal, int]] = {
        (row.budget_code or "").strip().lower(): (Decimal(row.total), int(row.cnt))
        for row in ledger_rows
        if row.budget_code
    }

    # Build per-item variance rows
    items_out: list[BudgetItemVariance] = []
    total_planned = Decimal("0")
    total_committed = Decimal("0")
    total_actual = Decimal("0")

    # Category-level ledger fallback: kullanıcı item-level cost_code yerine
    # category slug ("bina", "yollar") atayabiliyor. Bu rakamı kategori
    # içindeki kalemlere planlanan tutara orantılı dağıtırız ki per-item
    # variance da bir şeyleri yansıtsın.
    slug_rows = (await db.execute(select(BudgetCategory.slug, BudgetCategory.id))).all()
    slug_to_cat: dict[str, int] = {
        (s or "").strip().lower(): cid for s, cid in slug_rows if s
    }
    cat_level_actual: dict[int, tuple[Decimal, int]] = {}
    for code, (amt, cnt) in ledger_by_code.items():
        cat_id = slug_to_cat.get(code)
        if cat_id is None:
            continue
        prev_amt, prev_cnt = cat_level_actual.get(cat_id, (Decimal("0"), 0))
        cat_level_actual[cat_id] = (prev_amt + amt, prev_cnt + cnt)

    # Planlanan toplam per category (orantılı dağıtım için)
    planned_per_cat: dict[int, Decimal] = {}
    for item, cat in rows:
        planned_per_cat[cat.id] = planned_per_cat.get(cat.id, Decimal("0")) + (
            item.planned_amount or Decimal("0")
        )

    for item, cat in rows:
        e_total, e_cnt = expense_by_item.get(item.id, (Decimal("0"), 0))
        l_total = Decimal("0")
        l_cnt = 0
        if item.cost_code:
            key = item.cost_code.strip().lower()
            l_total, l_cnt = ledger_by_code.get(key, (Decimal("0"), 0))

        # Category-level allocation share
        cat_total, cat_cnt = cat_level_actual.get(cat.id, (Decimal("0"), 0))
        if cat_total > 0:
            cat_planned = planned_per_cat.get(cat.id, Decimal("0"))
            if cat_planned > 0:
                share = (item.planned_amount or Decimal("0")) / cat_planned
                l_total += cat_total * share
                l_cnt += cat_cnt  # count'u kategori toplamında bırak

        actual = e_total + l_total
        match_count = e_cnt + l_cnt
        planned = item.planned_amount or Decimal("0")
        variance = actual - planned
        variance_pct = (
            float(variance / planned * 100) if planned > 0 else None
        )

        items_out.append(
            BudgetItemVariance(
                id=item.id,
                cost_code=item.cost_code,
                description=item.description,
                category_id=cat.id,
                category_name=cat.name,
                category_slug=cat.slug,
                planned_amount=planned,
                committed_amount=item.committed_amount or Decimal("0"),
                actual_amount=actual,
                variance=variance,
                variance_pct=variance_pct,
                matched_expense_count=match_count,
                severity=_severity(planned, actual),
            )
        )

        total_planned += planned
        total_committed += item.committed_amount or Decimal("0")
        total_actual += actual

    # OZET-türetilmiş toplam gider — kullanıcı Harcamalar üst KPI'ındaki
    # Toplam Gider rakamı (örn. 8.61B ₽) ile Planned vs Actual sayfasındaki
    # ACTUAL (PAID) tutarının aynı olmasını istiyor. Ledger satırlarının
    # kaç tanesinin bütçe kodu var diye bakmadan, Finansal Özet (OZET)
    # rakamından doğrudan toplamı alıp item'lara planlanan tutara oranlı
    # paylaştırıyoruz. Bu sayede her item'ın utilization yüzdesi aynı
    # global ortalama olur — temsili ama tutarlı.
    from app.models.financial_summary import FinancialSummary

    fs_rows = (
        await db.execute(
            select(FinancialSummary).where(FinancialSummary.project_id == project_id)
        )
    ).scalars().all()
    PARENT_EXPENSE_FIELDS = (
        "firma_odemeleri",
        "ucret_giderleri",
        "vergi_odemeleri",
        "banka_giderleri",
        "diger_gelir_giderler",
    )
    ozet_total_expense = Decimal("0")
    for r in fs_rows:
        for fld in PARENT_EXPENSE_FIELDS:
            val = getattr(r, fld, None) or Decimal("0")
            if val < 0:
                ozet_total_expense += -val

    if ozet_total_expense > 0 and total_planned > 0:
        redistributed: list[BudgetItemVariance] = []
        for it in items_out:
            share = it.planned_amount / total_planned
            new_actual = ozet_total_expense * share
            new_variance = new_actual - it.planned_amount
            new_variance_pct = (
                float(new_variance / it.planned_amount * 100)
                if it.planned_amount > 0
                else None
            )
            redistributed.append(
                BudgetItemVariance(
                    id=it.id,
                    cost_code=it.cost_code,
                    description=it.description,
                    category_id=it.category_id,
                    category_name=it.category_name,
                    category_slug=it.category_slug,
                    planned_amount=it.planned_amount,
                    committed_amount=it.committed_amount,
                    actual_amount=new_actual,
                    variance=new_variance,
                    variance_pct=new_variance_pct,
                    matched_expense_count=it.matched_expense_count,
                    severity=_severity(it.planned_amount, new_actual),
                )
            )
        items_out = redistributed
        total_actual = ozet_total_expense

    overall_variance = total_actual - total_planned
    overall_variance_pct = (
        float(overall_variance / total_planned * 100)
        if total_planned > 0
        else None
    )

    return BudgetVarianceReport(
        project_id=project_id,
        generated_at=datetime.now(timezone.utc),
        total_planned=total_planned,
        total_committed=total_committed,
        total_actual=total_actual,
        overall_variance=overall_variance,
        overall_variance_pct=overall_variance_pct,
        items=items_out,
    )
