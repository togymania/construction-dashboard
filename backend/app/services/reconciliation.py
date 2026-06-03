"""Reconciliation planner (Faz 1) — the dry-run brain for fixing the
~99% of ledger rows that have no budget code or subcontractor link.

Two layers, on purpose:

* A **pure planner** (``plan_reconciliation``) that takes the unmatched
  rows plus the available candidates and returns a read-only plan: a
  per-row set of proposals (each scored + bucketed by the matching
  pipeline) and summary statistics, including the projected match-rate
  lift. No DB, fully unit-testable.
* An **async loader** (``build_reconciliation_plan``) that pulls the real
  rows / candidates out of the database and calls the pure planner.

The plan never mutates anything — applying it (auto-accepting the AUTO
tier, queueing REVIEW for a human) is a separate, reversible step that
persists suggestions (Faz 1.4).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.matching import Candidate, Decision, rank


@dataclass(frozen=True)
class UnmatchedRow:
    """A ledger row that is missing a budget code and/or a subcontractor."""

    id: int
    description: str = ""
    company_name: str = ""
    needs_budget_code: bool = False
    needs_subcontractor: bool = False


@dataclass(frozen=True)
class FieldProposal:
    """A single proposed field change for one row."""

    field: str  # "budget_code" | "subcontractor_id"
    value: object  # cost_code string or subcontractor id
    candidate_id: int
    score: float
    decision: Decision
    reason: str


@dataclass(frozen=True)
class RowPlan:
    row_id: int
    proposals: list[FieldProposal] = field(default_factory=list)


@dataclass
class ReconciliationStats:
    total_rows: int = 0
    needing_budget_code: int = 0
    needing_subcontractor: int = 0
    budget_auto: int = 0
    budget_review: int = 0
    budget_reject: int = 0
    sub_auto: int = 0
    sub_review: int = 0
    sub_reject: int = 0

    @property
    def auto_total(self) -> int:
        return self.budget_auto + self.sub_auto

    @property
    def review_total(self) -> int:
        return self.budget_review + self.sub_review


@dataclass
class ReconciliationPlan:
    rows: list[RowPlan] = field(default_factory=list)
    stats: ReconciliationStats = field(default_factory=ReconciliationStats)

    def proposals_for(self, decision: Decision) -> list[tuple[int, FieldProposal]]:
        """Flat list of ``(row_id, proposal)`` for one decision bucket."""
        return [
            (rp.row_id, p)
            for rp in self.rows
            for p in rp.proposals
            if p.decision is decision
        ]


def _tally(stats: ReconciliationStats, kind: str, decision: Decision) -> None:
    attr = f"{kind}_{decision.value}"
    setattr(stats, attr, getattr(stats, attr) + 1)


def plan_reconciliation(
    rows: list[UnmatchedRow],
    *,
    budget_candidates: list[Candidate],
    sub_candidates: list[Candidate],
) -> ReconciliationPlan:
    """Pure planner. Score every unmatched row against the candidates and
    bucket the best proposal per field. Read-only.

    * ``budget_candidates`` carry ``code`` = the budget item's cost_code;
      the proposal value for a budget match is that cost_code.
    * ``sub_candidates`` are matched on name; the proposal value is the
      subcontractor id (the candidate id).
    """
    budget_by_id = {c.id: c for c in budget_candidates}
    plan = ReconciliationPlan()
    plan.stats.total_rows = len(rows)

    for row in rows:
        proposals: list[FieldProposal] = []

        if row.needs_budget_code and budget_candidates:
            plan.stats.needing_budget_code += 1
            top = rank(row.description, budget_candidates, limit=1)
            if top:
                s = top[0]
                if s.decision is not Decision.REJECT:
                    cand = budget_by_id[s.candidate_id]
                    proposals.append(
                        FieldProposal(
                            field="budget_code",
                            value=cand.code,
                            candidate_id=s.candidate_id,
                            score=s.score,
                            decision=s.decision,
                            reason=s.reason,
                        )
                    )
                _tally(plan.stats, "budget", s.decision)

        if row.needs_subcontractor and sub_candidates:
            plan.stats.needing_subcontractor += 1
            top = rank(row.company_name, sub_candidates, limit=1)
            if top:
                s = top[0]
                if s.decision is not Decision.REJECT:
                    proposals.append(
                        FieldProposal(
                            field="subcontractor_id",
                            value=s.candidate_id,
                            candidate_id=s.candidate_id,
                            score=s.score,
                            decision=s.decision,
                            reason=s.reason,
                        )
                    )
                _tally(plan.stats, "sub", s.decision)

        if proposals:
            plan.rows.append(RowPlan(row_id=row.id, proposals=proposals))

    return plan


def match_rate(matched: int, total: int) -> float | None:
    """Percentage of rows that are matched, or ``None`` when there are none."""
    if total <= 0:
        return None
    return round(matched / total * 100, 2)


# ---------------------------------------------------------------------------
# Async DB loader
# ---------------------------------------------------------------------------


async def build_reconciliation_plan(db, project_id: int) -> ReconciliationPlan:
    """Load unmatched ledger rows + candidates for a project and plan.

    Read-only: this only *reads* the DB and returns a dry-run plan.
    """
    from sqlalchemy import or_, select

    from app.models.budget import BudgetItem
    from app.models.ledger_entry import LedgerEntry, LedgerEntryType
    from app.models.subcontractor import Subcontractor, SubcontractorStatus

    # Unmatched ledger rows: missing a budget code, or an EXPENSE missing a sub.
    ledger_stmt = select(LedgerEntry).where(
        or_(
            LedgerEntry.budget_code.is_(None),
            (LedgerEntry.subcontractor_id.is_(None))
            & (LedgerEntry.entry_type == LedgerEntryType.EXPENSE),
        )
    )
    ledger_rows = (await db.execute(ledger_stmt)).scalars().all()
    rows = [
        UnmatchedRow(
            id=e.id,
            description=e.description or "",
            company_name=e.company_name or "",
            needs_budget_code=e.budget_code is None,
            needs_subcontractor=(
                e.subcontractor_id is None
                and e.entry_type == LedgerEntryType.EXPENSE
            ),
        )
        for e in ledger_rows
    ]

    budget_items = (
        await db.execute(
            select(BudgetItem).where(BudgetItem.project_id == project_id)
        )
    ).scalars().all()
    budget_candidates = [
        Candidate(id=b.id, text=b.description or "", code=b.cost_code)
        for b in budget_items
        if b.cost_code
    ]

    subs = (
        await db.execute(
            select(Subcontractor).where(
                Subcontractor.is_active.is_(True),
                Subcontractor.status == SubcontractorStatus.ACTIVE,
            )
        )
    ).scalars().all()
    sub_candidates = [Candidate(id=s.id, text=s.name or "") for s in subs]

    return plan_reconciliation(
        rows,
        budget_candidates=budget_candidates,
        sub_candidates=sub_candidates,
    )
