"""User ORM model."""
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, PyEnum):
    """User roles for RBAC.

    ADMIN              - full access
    PROJECT_MANAGER    - create/edit projects, tenders, subcontractors
    ENGINEER           - edit operational data (workforce, expenses)
    VIEWER             - read-only across the entire app
    WORKFORCE_EDITOR   - access ONLY to the workforce module (edit there)
    """

    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    ENGINEER = "engineer"
    VIEWER = "viewer"
    WORKFORCE_EDITOR = "workforce_editor"


class User(Base):
    """User account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.VIEWER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r}, role={self.role.value!r})>"
