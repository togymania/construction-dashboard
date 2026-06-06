"""Cynteka faturalarından bütçe kodu atama orchestrator'ü.

Köprü (tarayıcı/Claude-in-Chrome) Cynteka'dan her ödeme için iş tipi
(Вид работ), içerik ve firma bilgisini toplayıp bu servise gönderir. Servis
saf `budget_code_matcher` motorunu çalıştırır ve:

    * decision == "auto"   -> ledger satırına cost_code yazılır (boşsa) +
                              denetim için APPROVED MatchSuggestion kaydı.
    * decision == "review" -> PENDING MatchSuggestion (mevcut review modalında
                              çıkar, kullanıcı onaylar/seçer).
    * decision == "reject" -> hiçbir şey yapılmaz (kodsuz kalır).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import BudgetItem
from app.models.budget_category import BudgetCategory
from app.models.ledger_entry import LedgerEntry
from app.models.match_suggestion import (
    MatchSuggestion,
    SuggestionField,
    SuggestionStatus,
)
from app.services.budget_code_matcher import (
    BudgetItemRef,
    InvoiceSignal,
    match_budget_code,
)


@dataclass(frozen=True)
class CyntekaRowIn:
    entry_id: int
    work_type: str = ""
    content: str = ""
    company_name: str = ""
    inn: str = ""
    invoice_number: str = ""


@dataclass
class CyntekaResult:
    auto_applied: int = 0
    review_created: int = 0
    rejected: int = 0
    created_suggestions: list = None  # PENDING + APPROVED MatchSuggestion

    def __post_init__(self):
        if self.created_suggestions is None:
            self.created_suggestions = []


async def _load_item_refs(db: AsyncSession, project_id: int) -> tuple[list[BudgetItemRef], dict[str, int]]:
    """Projenin bütçe kalemlerini kategori bilgisiyle yükle.

    Döner: (BudgetItemRef listesi, cost_code -> BudgetItem.id eşlemesi)
    """
    rows = (
        await db.execute(
            select(BudgetItem, BudgetCategory)
            .join(BudgetCategory, BudgetCategory.id == BudgetItem.category_id)
            .where(BudgetItem.project_id == project_id)
        )
    ).all()
    refs: list[BudgetItemRef] = []
    code_to_id: dict[str, int] = {}
    for item, cat in rows:
        if not item.cost_code:
            continue
        refs.append(
            BudgetItemRef(
                cost_code=item.cost_code,
                description=item.description or "",
                category_slug=cat.slug or "",
                category_name=cat.name or "",
            )
        )
        code_to_id[item.cost_code] = item.id
    return refs, code_to_id


async def apply_cynteka_matches(
    db: AsyncSession,
    project_id: int,
    rows: list[CyntekaRowIn],
    user_id: int,
    *,
    auto_apply: bool = True,
) -> CyntekaResult:
    refs, code_to_id = await _load_item_refs(db, project_id)
    result = CyntekaResult()

    entry_ids = [r.entry_id for r in rows][:500]
    entries = {
        e.id: e
        for e in (
            await db.execute(
                select(LedgerEntry).where(LedgerEntry.id.in_(entry_ids))
            )
        ).scalars().all()
    }

    now = datetime.now(timezone.utc)

    for r in rows:
        entry = entries.get(r.entry_id)
        if entry is None:
            continue

        signal = InvoiceSignal(
            work_type=r.work_type,
            content=r.content,
            company_name=r.company_name or (entry.company_name or ""),
            inn=r.inn,
            invoice_number=r.invoice_number,
        )
        m = match_budget_code(signal, refs)

        if m.decision == "reject" or not m.cost_code:
            result.rejected += 1
            continue

        # Önceki PENDING bütçe-kodu önerisini temizle (tek öneri olsun)
        await db.execute(
            delete(MatchSuggestion).where(
                MatchSuggestion.ledger_entry_id == entry.id,
                MatchSuggestion.field == SuggestionField.BUDGET_CODE,
                MatchSuggestion.status == SuggestionStatus.PENDING,
            )
        )

        cand_id = code_to_id.get(m.cost_code, 0)
        base = dict(
            ledger_entry_id=entry.id,
            field=SuggestionField.BUDGET_CODE,
            proposed_value=str(m.cost_code),
            candidate_id=cand_id,
            candidate_label=m.candidate_description,
            score=Decimal(str(round(m.confidence, 2))),
            reason="cynteka",
            rationale=m.rationale,
        )

        if m.decision == "auto" and auto_apply:
            # Doğrudan ledger'a yaz (boşsa) ve denetim kaydı bırak.
            applied = False
            if entry.budget_code is None:
                entry.budget_code = m.cost_code
                applied = True
            ms = MatchSuggestion(
                status=SuggestionStatus.APPROVED,
                resolved_at=now,
                resolved_by=user_id,
                **base,
            )
            db.add(ms)
            result.created_suggestions.append(ms)
            if applied:
                result.auto_applied += 1
            else:
                # zaten koduydu; yine de denetim kaydı kaldı
                result.auto_applied += 1
        else:
            ms = MatchSuggestion(status=SuggestionStatus.PENDING, **base)
            db.add(ms)
            result.created_suggestions.append(ms)
            result.review_created += 1

    await db.commit()
    for ms in result.created_suggestions:
        await db.refresh(ms)
    return result
