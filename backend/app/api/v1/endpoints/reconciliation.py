"""Reconciliation review endpoints (Faz 1 — Human Review Workflow).

Lets an admin (re)generate review-tier match suggestions for a project,
list the pending queue, and approve / reject them. Approving a suggestion
applies the proposed value to the ledger row (only if that field is still
empty), so a human never overwrites data they already entered.

AUTO-tier (high-confidence) matches are handled by the
``python -m app.db.reconcile --apply`` command, not here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, DBSession, UserLang, require_roles
from app.models.budget import BudgetItem
from app.models.ledger_entry import LedgerEntry
from app.models.match_suggestion import (
    MatchSuggestion,
    SuggestionField,
    SuggestionStatus,
)
from app.models.subcontractor import Subcontractor
from app.models.user import User, UserRole
from app.schemas.match_suggestion import (
    ActionResult,
    AIBudgetSuggestRequest,
    BulkActionRequest,
    CyntekaSuggestRequest,
    CyntekaSuggestResponse,
    GenerateResponse,
    MatchSuggestionRead,
)
from app.services.ai_budget_suggester import generate_ai_budget_suggestions
from app.services.cynteka_budget import CyntekaRowIn, apply_cynteka_matches
from app.services.matching import Decision
from app.services.reconciliation import build_reconciliation_plan

router = APIRouter(tags=["Reconciliation"])

_EDITORS = (UserRole.ADMIN, UserRole.PROJECT_MANAGER)


@router.post(
    "/projects/{project_id}/reconciliation/generate",
    response_model=GenerateResponse,
    summary="(Re)generate review-tier match suggestions for a project",
)
async def generate_suggestions(
    project_id: int,
    db: DBSession,
    _user: User = Depends(require_roles(*_EDITORS)),
) -> GenerateResponse:
    plan = await build_reconciliation_plan(db, project_id)

    # Labels for the review UI.
    budget_labels = dict(
        (
            await db.execute(
                select(BudgetItem.id, BudgetItem.description).where(
                    BudgetItem.project_id == project_id
                )
            )
        ).all()
    )
    sub_labels = dict(
        (await db.execute(select(Subcontractor.id, Subcontractor.name))).all()
    )

    # Replace the existing pending queue (keep approved/rejected as history).
    await db.execute(
        delete(MatchSuggestion).where(
            MatchSuggestion.status == SuggestionStatus.PENDING
        )
    )

    persisted = 0
    for row_id, p in plan.proposals_for(Decision.REVIEW):
        if p.field == "budget_code":
            field = SuggestionField.BUDGET_CODE
            value = str(p.value)
            label = budget_labels.get(p.candidate_id)
        else:
            field = SuggestionField.SUBCONTRACTOR_ID
            value = str(p.value)
            label = sub_labels.get(p.candidate_id)
        db.add(
            MatchSuggestion(
                ledger_entry_id=row_id,
                field=field,
                proposed_value=value,
                candidate_id=p.candidate_id,
                candidate_label=label,
                score=p.score,
                reason=p.reason,
                status=SuggestionStatus.PENDING,
            )
        )
        persisted += 1

    await db.commit()
    st = plan.stats
    return GenerateResponse(
        project_id=project_id,
        auto_total=st.auto_total,
        review_persisted=persisted,
        reject_total=st.budget_reject + st.sub_reject,
        budget_review=st.budget_review,
        sub_review=st.sub_review,
    )


@router.post(
    "/projects/{project_id}/ledger/ai-suggest-budget-codes",
    response_model=list[MatchSuggestionRead],
    summary="AI-suggest budget codes for selected ledger rows (-> review queue)",
)
async def ai_suggest_budget_codes(
    project_id: int,
    payload: AIBudgetSuggestRequest,
    db: DBSession,
    lang: UserLang,
    _user: User = Depends(require_roles(*_EDITORS)),
) -> list[MatchSuggestionRead]:
    # Web research + an LLM call per row is slow; cap the batch size.
    ids = payload.entry_ids[:25]
    if not ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "entry_ids required")
    created = await generate_ai_budget_suggestions(
        db, project_id, ids, lang=lang, use_web=payload.use_web
    )
    return [MatchSuggestionRead.model_validate(m) for m in created]


@router.post(
    "/projects/{project_id}/ledger/cynteka-suggest-budget-codes",
    response_model=CyntekaSuggestResponse,
    summary="Cynteka iş-tipinden bütçe kodu ata (tek-kalem auto, çok-kalem review)",
)
async def cynteka_suggest_budget_codes(
    project_id: int,
    payload: CyntekaSuggestRequest,
    db: DBSession,
    user: User = Depends(require_roles(*_EDITORS)),
) -> CyntekaSuggestResponse:
    """Köprünün Cynteka'dan topladığı (iş tipi + içerik + firma) satırları
    bütçe kalemlerine eşler. Tek kalemli kategori netse otomatik yazar; çok
    kalemli kategori belirsizse review kuyruğuna öneri düşer."""
    if not payload.rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "rows required")
    rows = [
        CyntekaRowIn(
            entry_id=r.entry_id,
            work_type=r.work_type,
            content=r.content,
            company_name=r.company_name,
            inn=r.inn,
            invoice_number=r.invoice_number,
        )
        for r in payload.rows
    ]
    res = await apply_cynteka_matches(
        db, project_id, rows, user.id, auto_apply=payload.auto_apply
    )
    return CyntekaSuggestResponse(
        auto_applied=res.auto_applied,
        review_created=res.review_created,
        rejected=res.rejected,
        suggestions=[MatchSuggestionRead.model_validate(m) for m in res.created_suggestions],
    )


@router.get(
    "/reconciliation/suggestions",
    response_model=list[MatchSuggestionRead],
    summary="List match suggestions (review queue)",
)
async def list_suggestions(
    user: CurrentUser,
    db: DBSession,
    status_filter: SuggestionStatus = Query(
        SuggestionStatus.PENDING, alias="status"
    ),
    field: SuggestionField | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[MatchSuggestionRead]:
    stmt = (
        select(MatchSuggestion)
        .where(MatchSuggestion.status == status_filter)
        .order_by(MatchSuggestion.score.desc(), MatchSuggestion.id)
        .limit(limit)
        .offset(offset)
    )
    if field is not None:
        stmt = stmt.where(MatchSuggestion.field == field)
    rows = (await db.execute(stmt)).scalars().all()
    return [MatchSuggestionRead.model_validate(r) for r in rows]


async def _apply_to_ledger(db: DBSession, sugg: MatchSuggestion) -> bool:
    """Write the suggested value onto the ledger row if still empty.

    Returns True when a value was actually written.
    """
    entry = (
        await db.execute(
            select(LedgerEntry).where(LedgerEntry.id == sugg.ledger_entry_id)
        )
    ).scalar_one_or_none()
    if entry is None:
        return False
    if sugg.field == SuggestionField.BUDGET_CODE:
        if entry.budget_code is None:
            entry.budget_code = sugg.proposed_value
            return True
    elif sugg.field == SuggestionField.SUBCONTRACTOR_ID:
        if entry.subcontractor_id is None:
            entry.subcontractor_id = int(sugg.proposed_value)
            return True
    return False


async def _resolve(
    db: DBSession, sugg: MatchSuggestion, new_status: SuggestionStatus, user_id: int
) -> bool:
    sugg.status = new_status
    sugg.resolved_at = datetime.now(timezone.utc)
    sugg.resolved_by = user_id
    if new_status == SuggestionStatus.APPROVED:
        return await _apply_to_ledger(db, sugg)
    return False


@router.post(
    "/reconciliation/suggestions/{suggestion_id}/approve",
    response_model=MatchSuggestionRead,
    summary="Approve a suggestion and apply it to the ledger row",
)
async def approve_suggestion(
    suggestion_id: int,
    db: DBSession,
    user: User = Depends(require_roles(*_EDITORS)),
) -> MatchSuggestionRead:
    sugg = await db.get(MatchSuggestion, suggestion_id)
    if sugg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suggestion not found")
    if sugg.status != SuggestionStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Suggestion already resolved")
    await _resolve(db, sugg, SuggestionStatus.APPROVED, user.id)
    await db.commit()
    await db.refresh(sugg)
    return MatchSuggestionRead.model_validate(sugg)


@router.post(
    "/reconciliation/suggestions/{suggestion_id}/reject",
    response_model=MatchSuggestionRead,
    summary="Reject a suggestion",
)
async def reject_suggestion(
    suggestion_id: int,
    db: DBSession,
    user: User = Depends(require_roles(*_EDITORS)),
) -> MatchSuggestionRead:
    sugg = await db.get(MatchSuggestion, suggestion_id)
    if sugg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suggestion not found")
    if sugg.status != SuggestionStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Suggestion already resolved")
    await _resolve(db, sugg, SuggestionStatus.REJECTED, user.id)
    await db.commit()
    await db.refresh(sugg)
    return MatchSuggestionRead.model_validate(sugg)


@router.post(
    "/reconciliation/suggestions/bulk-approve",
    response_model=ActionResult,
    summary="Approve many suggestions at once",
)
async def bulk_approve(
    payload: BulkActionRequest,
    db: DBSession,
    user: User = Depends(require_roles(*_EDITORS)),
) -> ActionResult:
    return await _bulk(db, payload.suggestion_ids, SuggestionStatus.APPROVED, user.id)


@router.post(
    "/reconciliation/suggestions/bulk-reject",
    response_model=ActionResult,
    summary="Reject many suggestions at once",
)
async def bulk_reject(
    payload: BulkActionRequest,
    db: DBSession,
    user: User = Depends(require_roles(*_EDITORS)),
) -> ActionResult:
    return await _bulk(db, payload.suggestion_ids, SuggestionStatus.REJECTED, user.id)


async def _bulk(
    db: DBSession,
    ids: list[int],
    new_status: SuggestionStatus,
    user_id: int,
) -> ActionResult:
    rows = (
        await db.execute(
            select(MatchSuggestion).where(
                MatchSuggestion.id.in_(ids),
                MatchSuggestion.status == SuggestionStatus.PENDING,
            )
        )
    ).scalars().all()
    applied = 0
    for sugg in rows:
        if await _resolve(db, sugg, new_status, user_id):
            applied += 1
    await db.commit()
    return ActionResult(processed=len(rows), applied=applied)
