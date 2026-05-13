"""Seed / reset the two demo users for the live presentation.

Idempotent — çalıştırınca:

  • admin@example.com   / admin123  → role = VIEWER  (read-only, tüm sayfaları görür)
  • admin1@example.com  / admin456  → role = WORKFORCE_EDITOR (sadece İşgücü)

İlk çalıştırmada kullanıcı yoksa oluşturur, varsa role + parolayı
istenen değerlere zorlar.

Kullanım (Render shell veya local):
    python -m app.db.seed_demo_users
"""
import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole


DEMO_USERS = [
    {
        "email":     "admin@example.com",
        "password":  "admin123",
        "full_name": "Demo Read-Only",
        "role":      UserRole.VIEWER,
    },
    {
        "email":     "admin1@example.com",
        "password":  "admin456",
        "full_name": "Demo Workforce Editor",
        "role":      UserRole.WORKFORCE_EDITOR,
    },
]


async def seed_demo_users() -> None:
    async with AsyncSessionLocal() as db:
        for spec in DEMO_USERS:
            existing = (
                await db.execute(select(User).where(User.email == spec["email"]))
            ).scalar_one_or_none()
            if existing is None:
                user = User(
                    email=spec["email"],
                    hashed_password=hash_password(spec["password"]),
                    full_name=spec["full_name"],
                    role=spec["role"],
                    is_active=True,
                )
                db.add(user)
                print(f"[OK] Created {spec['email']:25s}  role={spec['role'].value}")
            else:
                existing.hashed_password = hash_password(spec["password"])
                existing.full_name = spec["full_name"]
                existing.role = spec["role"]
                existing.is_active = True
                print(f"[OK] Updated {spec['email']:25s}  role={spec['role'].value}")
        await db.commit()
    print()
    print("Demo logins:")
    print("  admin@example.com   / admin123    — VIEWER (read-only)")
    print("  admin1@example.com  / admin456    — WORKFORCE_EDITOR")


if __name__ == "__main__":
    asyncio.run(seed_demo_users())
