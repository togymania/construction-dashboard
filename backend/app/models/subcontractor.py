"""Subcontractor ORM models: companies, contracts, and payments."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


# ---------- Enums ----------

class SubcontractorStatus(str, PyEnum):
    """Subcontractor company lifecycle status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLACKLISTED = "blacklisted"


class ContractStatus(str, PyEnum):
    """Contract lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class PaymentStatus(str, PyEnum):
    """Subcontractor payment (hakediş) status."""

    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


# ---------- Subcontractor ----------

class Subcontractor(Base):
    """Subcontractor company card."""

    __tablename__ = "subcontractors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[SubcontractorStatus] = mapped_column(
        Enum(
            SubcontractorStatus,
            name="subcontractor_status",
            values_callable=_enum_values,
        ),
        default=SubcontractorStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    contracts = relationship(
        "SubcontractorContract",
        back_populates="subcontractor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        # Case-insensitive UNIQUE on tax_id (NULLs allowed; partial index)
        Index(
            "ix_subcontractors_tax_id_lower",
            func.lower(tax_id),
            unique=True,
            postgresql_where=text("tax_id IS NOT NULL"),
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_subcontractors_rating_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Subcontractor(id={self.id}, name={self.name!r}, "
            f"status={self.status.value!r})>"
        )


# ---------- Contract ----------

class SubcontractorContract(Base):
    """Contract between a subcontractor and a project."""

    __tablename__ = "subcontractor_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subcontractor_id: Mapped[int] = mapped_column(
        ForeignKey("subcontractors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        Enum(
            ContractStatus,
            name="contract_status",
            values_callable=_enum_values,
        ),
        default=ContractStatus.DRAFT,
        nullable=False,
        index=True,
    )
    scope_of_work: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subcontractor = relationship(
        "Subcontractor", back_populates="contracts", lazy="selectin"
    )
    project = relationship("Project", lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    payments = relationship(
        "SubcontractorPayment",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        # Case-insensitive UNIQUE on contract_number (NULLs allowed; partial index)
        Index(
            "ix_subcontractor_contracts_number_lower",
            func.lower(contract_number),
            unique=True,
            postgresql_where=text("contract_number IS NOT NULL"),
        ),
        CheckConstraint(
            "end_date >= start_date",
            name="ck_subcontractor_contracts_date_range",
        ),
        CheckConstraint(
            "contract_amount >= 0",
            name="ck_subcontractor_contracts_amount_nonneg",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SubcontractorContract(id={self.id}, sub_id={self.subcontractor_id}, "
            f"project_id={self.project_id}, amount={self.contract_amount}, "
            f"status={self.status.value!r})>"
        )


# ---------- Payment ----------

class SubcontractorPayment(Base):
    """Subcontractor payment (hakediş) tied to a contract."""

    __tablename__ = "subcontractor_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("subcontractor_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="subcontractor_payment_status",
            values_callable=_enum_values,
        ),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contract = relationship(
        "SubcontractorContract", back_populates="payments", lazy="selectin"
    )
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    approver = relationship("User", foreign_keys=[approved_by], lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "payment_number",
            name="uq_subcontractor_payments_contract_paynum",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_subcontractor_payments_amount_positive",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SubcontractorPayment(id={self.id}, contract_id={self.contract_id}, "
            f"num={self.payment_number}, amount={self.amount}, "
            f"status={self.status.value!r})>"
        )


# ---------- Document Type ----------

class DocumentType(str, PyEnum):
    """Type of contract document."""

    CONTRACT = "CONTRACT"
    INVOICE = "INVOICE"
    ADDENDUM = "ADDENDUM"
    REPORT = "REPORT"


# ---------- Contract Document ----------

class ContractDocument(Base):
    """Document attached to a subcontractor contract."""

    __tablename__ = "contract_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("subcontractor_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            name="document_type",
            values_callable=_enum_values,
        ),
        default=DocumentType.CONTRACT,
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    extracted_data: Mapped[str | None] = mapped_column(
        Text, nullable=True  # JSON stored as text
    )
    # Raw file bytes persisted in DB (Render disk is ephemeral). Only stored
    # for files up to settings.DOC_DB_STORE_MAX_MB; larger files stay disk-only.
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Extracted plain text (PDF text layer or decoded md/txt). Used by the
    # AI assistant to answer questions about the document.
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contract = relationship("SubcontractorContract", lazy="selectin")
    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ContractDocument(id={self.id}, contract_id={self.contract_id}, "
            f"file_name={self.file_name!r}, type={self.file_type.value!r})>"
        )
