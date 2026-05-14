"""Shared FastAPI dependencies (auth, db, permissions)."""
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

# OAuth2 scheme for Swagger UI Authorize button
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

DBSession = Annotated[AsyncSession, Depends(get_db)]
Token = Annotated[str, Depends(oauth2_scheme)]


# ---------------------------------------------------------------------------
# UI language for AI-generated text
# ---------------------------------------------------------------------------
# The frontend sends X-User-Lang ("EN" | "TR") on every request reflecting
# the user's localStorage UI preference. AI prompts read this and instruct
# Claude to respond in that language regardless of the source data's
# language. Without this, Claude defaults to mirroring the data language
# (often Russian for ledger imports), which leaks Cyrillic into an English
# UI and vice versa.
UiLang = Literal["EN", "TR"]


async def get_ui_lang(
    x_user_lang: str | None = Header(default=None, alias="X-User-Lang"),
) -> UiLang:
    raw = (x_user_lang or "").strip().upper()
    if raw == "TR":
        return "TR"
    return "EN"


UserLang = Annotated[UiLang, Depends(get_ui_lang)]


async def get_current_user(db: DBSession, token: Token) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email: str | None = payload.get("sub")
    if email is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole):
    """Dependency factory that enforces role-based access.

    Usage:
        @router.post("/projects", dependencies=[Depends(require_roles(UserRole.ADMIN))])
        or inline:
        user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER))
    """

    async def checker(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(r.value for r in allowed_roles)}",
            )
        return user

    return checker
