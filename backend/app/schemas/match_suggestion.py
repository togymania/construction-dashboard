"""Pydantic schemas for the reconciliation review workflow (Faz 1)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.match_suggestion import SuggestionField, SuggestionStatus


class MatchSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ledger_entry_id: int
    field: SuggestionField
    proposed_value: str
    candidate_id: int
    candidate_label: str | None
    score: Decimal
    reason: str
    rationale: str | None = None
    status: SuggestionStatus
    resolved_at: datetime | None
    resolved_by: int | None
    created_at: datetime


class GenerateResponse(BaseModel):
    """Summary returned after (re)generating suggestions for a project."""

    project_id: int
    auto_total: int          # high-confidence (apply via CLI / future endpoint)
    review_persisted: int    # PENDING suggestions written for human review
    reject_total: int
    budget_review: int
    sub_review: int


class BulkActionRequest(BaseModel):
    """Approve or reject many suggestions at once."""

    suggestion_ids: list[int]


class AIBudgetSuggestRequest(BaseModel):
    """Request AI budget-code suggestions for selected ledger rows."""

    entry_ids: list[int]
    use_web: bool = True  # research the company online via Claude web_search


class ActionResult(BaseModel):
    processed: int
    applied: int  # how many actually changed a ledger row (approve only)
