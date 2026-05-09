"""BudgetItem ORM model.

The BudgetItem table is the planned side of the planned-vs-actual report.
Each row is a single budget line for a project, optionally tagged with a
WBS-style cost code so the variance service can match expenses and
ledger entries to it.

Field notes
-----------
* ``cost_code``       -- optional, indexed; used by Faz 3 matching.
* ``committed_amount`` -- money already promised via signed contracts/POs
                          but not yet paid. Sits between planned and actual.
* ``planned_amount``  -- the line item budget number (always present).
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BudgetItem(Base):
    """Planned budget line item for a project."""

    __tablename__ = "budget_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("budget_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # WBS / cost code (e.g. "1.2.1.3"). Optional; used for Excel imports
    # plus the planned-vs-actual matching layer (Faz 3) to link expenses
    # by string equality on cost_code <-> ledger.budget_code.
    cost_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    planned_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )

    # Committed = signed contracts / purchase orders for this line. Falls
    # between planned and actual on the spend continuum. Defaults to 0
    # for backwards-compat with rows imported before the column existed.
    committed_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", backref="budget_items", lazy="selectin")
    category = relationship("BudgetCategory", lazy="selectin")
    expenses = relationship(
        "Expense",
        back_populates="budget_item",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<BudgetItem(id={self.id}, project_id={self.project_id}, "
            f"category_id={self.category_id}, planned={self.planned_amount})>"
        )


# -- padding so we always overwrite the previous on-disk size --------------
# The dev sandbox occasionally fails to truncate when a smaller payload is
# written, leaving stale bytes from the prior version at the tail. Keeping
# every release of this module at least as long as the previous one
# prevents that whole class of corruption.
