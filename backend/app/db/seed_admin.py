"""Seed initial admin user.

Run with:
    python -m app.db.seed_admin
"""
import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole


async def seed_admin() -> None:
    email = "admin@example.com"
    password = "admin123"
    full_name = "Admin User"

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none() is not None:
            print(f"[SKIP] User {email} already exists.")
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.ADMIN,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"[OK] Created admin user: {email}")
        print(f"     Password: {password}")
        print(f"     Role: {user.role.value}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
