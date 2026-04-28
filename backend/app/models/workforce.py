"""Workforce ORM models: positions, daily snapshots, and per-position counts."""
from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ---------- Enums ----------

class WorkforceCategory(str, PyEnum):
    """Top-level workforce classification mirroring the daily-puantaj cover page.

    - DIRECT: productive personnel (rabotchie / iscilik) - field workers building
    - INDIRECT: unproductive personnel (ITR / ofis) - engineers, managers, support
    - SUBCONTRACTOR: subcontractor productive personnel - third-party crews
    """

    DIRECT = "direct"
    INDIRECT = "indirect"
    SUBCONTRACTOR = "subcontractor"


# Sabit firma listesi - parse sirasinda Excel B2'sinden okunan deger
# bu listeyle normalize edilmek zorunda. Yeni firma eklemek icin bu tuple'i guncelle.
COMPANY_LABELS = ("Monotekstroy", "Monart")


# ---------- Models ----------

class WorkforcePosition(Base):
    """A position / role used inside daily workforce snapshots.

    Catalog is project-agnostic; the same row (e.g. ELECTRICIAN under direct)
    appears across all projects. Names are normalized for matching during
    Excel import (uppercase, single space, no diacritics).

    For the construction industry, INCE ISLER (finishing-works crews led by
    different foremen) collapses into a single position by user decision -
    foreman name is dropped and counts are summed.
    """

    __tablename__ = "workforce_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[WorkforceCategory] = mapped_column(
        Enum(WorkforceCategory, name="workforce_category", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=999)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    counts: Mapped[list["WorkforceCount"]] = relationship(back_populates="position", cascade="all, delete-orphan")

    __table_args__ = (
        # one row per (category, normalized name) - so DIRECT/MASON and INDIRECT/MASON can coexist
        UniqueConstraint("category", "name_normalized", name="uq_workforce_position_category_name"),
        Index("ix_workforce_position_active", "category", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<WorkforcePosition id={self.id} {self.category.value}/{self.name!r}>"


class WorkforceSnapshot(Base):
    """One row per project per day - the daily puantaj cover-page summary.

    Aggregates are denormalized for fast KPI reads (no JOIN needed for the
    dashboard top-line numbers). Service layer keeps them in sync whenever
    counts are written.
    """

    __tablename__ = "workforce_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Hangi taseron firma ile ilgili - sabit liste: Monotekstroy / Monart
    # Tarih + firma birlikte UNIQUE -> ayni gun iki firma snapshot olabilir.
    company_label: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Monotekstroy", server_default=text("'Monotekstroy'"), index=True
    )

    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", server_default=text("\'manual\'"))
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Denormalized aggregates (kept in sync by service layer)
    total_general_staff: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_absent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_leave_sick: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    total_present: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    direct_present: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    indirect_present: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    subcontractor_present: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    counts: Mapped[list["WorkforceCount"]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # one snapshot per project per day - re-import for same date upserts
        UniqueConstraint("project_id", "snapshot_date", "company_label", name="uq_workforce_snapshot_project_date_company"),
        CheckConstraint("total_general_staff >= 0", name="ck_workforce_snapshot_general_nonneg"),
        CheckConstraint("total_absent >= 0", name="ck_workforce_snapshot_absent_nonneg"),
        CheckConstraint("total_leave_sick >= 0", name="ck_workforce_snapshot_leave_nonneg"),
        CheckConstraint("total_present >= 0", name="ck_workforce_snapshot_present_nonneg"),
        Index("ix_workforce_snapshot_project_date_desc", "project_id", "snapshot_date"),
    )

    def __repr__(self) -> str:
        return f"<WorkforceSnapshot id={self.id} project={self.project_id} date={self.snapshot_date}>"


class WorkforceCount(Base):
    """One row per snapshot per position - the atomic detail line.

    Mirrors a single row from the cover-page section: position name with its
    four columns (general staff, absent, leave/sick, present).

    Validation: present = general - absent - leave (computed but not enforced
    in DB, since Excel sometimes ships rounding/manual-edit mismatches).
    """

    __tablename__ = "workforce_counts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("workforce_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_id: Mapped[int] = mapped_column(
        ForeignKey("workforce_positions.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    general_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    absent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    leave_sick: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    present: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    snapshot: Mapped["WorkforceSnapshot"] = relationship(back_populates="counts")
    position: Mapped["WorkforcePosition"] = relationship(back_populates="counts")

    __table_args__ = (
        UniqueConstraint("snapshot_id", "position_id", name="uq_workforce_count_snapshot_position"),
        CheckConstraint("general_staff >= 0", name="ck_workforce_count_general_nonneg"),
        CheckConstraint("absent >= 0", name="ck_workforce_count_absent_nonneg"),
        CheckConstraint("leave_sick >= 0", name="ck_workforce_count_leave_nonneg"),
        CheckConstraint("present >= 0", name="ck_workforce_count_present_nonneg"),
    )

    def __repr__(self) -> str:
        return f"<WorkforceCount snap={self.snapshot_id} pos={self.position_id} present={self.present}>"
