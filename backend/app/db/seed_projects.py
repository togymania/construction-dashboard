"""Seed initial projects (admin-owned Turkish mega projects).

Run with:
    python -m app.db.seed_projects
"""
import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.project import Project, ProjectHealth, ProjectStatus
from app.models.user import User


PROJECTS_SEED = [
    {
        "name": "Istanbul Havalimani Terminal B",
        "description": "Second terminal expansion with international gates and cargo facilities.",
        "status": ProjectStatus.ACTIVE,
        "health": ProjectHealth.ON_TRACK,
        "budget_rub": Decimal("42750000000"),
        "start_date": date(2024, 3, 15),
        "end_date": date(2027, 12, 30),
        "progress_pct": Decimal("41.5"),
        "location": "Istanbul, Turkey",
    },
    {
        "name": "Kanal Istanbul Etap 2",
        "description": "Second phase of the Istanbul Canal project - dredging and lock systems.",
        "status": ProjectStatus.ACTIVE,
        "health": ProjectHealth.AT_RISK,
        "budget_rub": Decimal("30400000000"),
        "start_date": date(2024, 6, 1),
        "end_date": date(2028, 8, 30),
        "progress_pct": Decimal("29.7"),
        "location": "Istanbul, Turkey",
    },
    {
        "name": "Ankara-Izmir YHT",
        "description": "High-speed rail link between Ankara and Izmir, 624 km alignment.",
        "status": ProjectStatus.ACTIVE,
        "health": ProjectHealth.ON_TRACK,
        "budget_rub": Decimal("26600000000"),
        "start_date": date(2023, 9, 1),
        "end_date": date(2026, 11, 30),
        "progress_pct": Decimal("55.8"),
        "location": "Ankara to Izmir, Turkey",
    },
    {
        "name": "Marmaray Extension",
        "description": "Marmaray suburban rail extension to Gebze and beyond.",
        "status": ProjectStatus.ACTIVE,
        "health": ProjectHealth.ON_TRACK,
        "budget_rub": Decimal("14250000000"),
        "start_date": date(2024, 1, 10),
        "end_date": date(2026, 6, 30),
        "progress_pct": Decimal("58.7"),
        "location": "Istanbul, Turkey",
    },
    {
        "name": "Galataport Phase 2",
        "description": "Continued development of Galataport cruise terminal and retail complex.",
        "status": ProjectStatus.PLANNING,
        "health": ProjectHealth.ON_TRACK,
        "budget_rub": Decimal("7600000000"),
        "start_date": date(2025, 9, 1),
        "end_date": date(2028, 3, 30),
        "progress_pct": Decimal("4.0"),
        "location": "Istanbul, Turkey",
    },
    {
        "name": "Izmir Metro Line 5",
        "description": "New metro line connecting Uckuyular to Karsiyaka, 14 stations.",
        "status": ProjectStatus.ACTIVE,
        "health": ProjectHealth.ON_TRACK,
        "budget_rub": Decimal("18525000000"),
        "start_date": date(2024, 4, 20),
        "end_date": date(2027, 10, 30),
        "progress_pct": Decimal("40.5"),
        "location": "Izmir, Turkey",
    },
]


async def seed_projects() -> None:
    async with AsyncSessionLocal() as db:
        admin_stmt = select(User).where(User.email == "admin@example.com")
        admin = (await db.execute(admin_stmt)).scalar_one_or_none()

        if admin is None:
            print("[ERR] Admin user not found. Run seed_admin first.")
            return

        existing_stmt = select(Project)
        existing_count = len((await db.execute(existing_stmt)).scalars().all())

        if existing_count > 0:
            print(f"[SKIP] Projects table already has {existing_count} rows.")
            return

        created = 0
        for p in PROJECTS_SEED:
            project = Project(owner_id=admin.id, **p)
            db.add(project)
            created += 1

        await db.commit()
        print(f"[OK] Seeded {created} projects owned by {admin.email}")


if __name__ == "__main__":
    asyncio.run(seed_projects())
