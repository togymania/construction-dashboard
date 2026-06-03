"""MatchSuggestion ORM model (Faz 1 — Human Review Workflow).

A persisted, human-reviewable proposal to fill in a missing field on a
``LedgerEntry`` (its ``budget_code`` or ``subcontractor_id``). The
reconciliation engine writes REVIEW-tier proposals here as PENDING; a
reviewer then approves (which applies the change to the ledger row) or
rejects them. AUTO-tier proposals are applied directly by the
``app.db.reconcile`` command and are not stored here.

``created_at`` / ``updated_at`` come from ``Base``.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class SuggestionField(str, PyEnum):
    """Which ledger field this suggestion would fill."""

    BUDGET_CODE = "budget_code"
    SUBCONTRACTOR_ID = "subcontractor_id"


class SuggestionStatus(str, PyEnum):
    """Lifecycle of a suggestion."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MatchSuggestion(Base):
    """One proposed fill for a ledger row's missing budget code / sub link."""

    __tablename__ = "match_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    ledger_entry_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    field: Mapped[SuggestionField] = mapped_column(
        Enum(SuggestionField, name="suggestion_field", values_callable=_enum_values),
        nullable=False,
        index=True,
    )
    # The value to write onto the ledger row (cost_code string, or a
    # subcontractor id rendered as text). Kept as text so one column serves
    # both field kinds; the apply step casts as needed.
    proposed_value: Mapped[str] = mapped_column(String(100), nullable=False)
    # The matched candidate (budget item id or subcontractor id) + a label
    # for display in the review UI.
    candidate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_label: Mapped[str | None] = mapped_column(String(500), nullable=True)

    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    # Free-text explanation (used by AI budget suggestions to show why the
    # code was proposed, incl. any web-research finding).
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[SuggestionStatus] = mapped_column(
        Enum(SuggestionStatus, name="suggestion_status", values_callable=_enum_values),
        nullable=False,
        default=SuggestionStatus.PENDING,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    ledger_entry = relationship("LedgerEntry", lazy="selectin")

    __table_args__ = (
        Index("ix_match_suggestions_entry_field", "ledger_entry_id", "field"),
    )

    def __repr__(self) -> str:
        return (
            f"<MatchSuggestion(id={self.id}, entry={self.ledger_entry_id}, "
            f"field={self.field.value!r}, status={self.status.value!r}, "
            f"score={self.score})>"
        )
