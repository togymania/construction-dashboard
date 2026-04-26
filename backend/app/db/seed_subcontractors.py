"""Seed subcontractors, contracts, and payments for the demo project.

Run with:
    python -m app.db.seed_subcontractors

Idempotent: if any subcontractor with the seeded names already exists,
the script skips and reports.
"""
import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.subcontractor import (
    ContractStatus,
    PaymentStatus,
    Subcontractor,
    SubcontractorContract,
    SubcontractorPayment,
    SubcontractorStatus,
)
from app.models.user import User


# ------------------------------------------------------------------------
# Subcontractor companies
# ------------------------------------------------------------------------

SUBCONTRACTORS_SEED = [
    {
        "name": "Yilmaz Elektrik San. ve Tic. A.S.",
        "tax_id": "1234567890",
        "contact_person": "Mehmet Yilmaz",
        "phone": "+90 212 555 0101",
        "email": "info@yilmazelektrik.com.tr",
        "address": "Ikitelli OSB, Istanbul, Turkey",
        "specialization": "Elektrik",
        "status": SubcontractorStatus.ACTIVE,
        "rating": Decimal("4.5"),
        "notes": "Long-term partner, reliable on schedule.",
    },
    {
        "name": "Demir Yapi Insaat Ltd.",
        "tax_id": "2345678901",
        "contact_person": "Ayse Demir",
        "phone": "+90 216 555 0202",
        "email": "kontak@demiryapi.com.tr",
        "address": "Umraniye, Istanbul, Turkey",
        "specialization": "Yapi",
        "status": SubcontractorStatus.ACTIVE,
        "rating": Decimal("4.2"),
        "notes": None,
    },
    {
        "name": "Atlas Beton A.S.",
        "tax_id": "3456789012",
        "contact_person": "Ali Atlas",
        "phone": "+90 232 555 0303",
        "email": "satis@atlasbeton.com.tr",
        "address": "Cigli, Izmir, Turkey",
        "specialization": "Beton",
        "status": SubcontractorStatus.ACTIVE,
        "rating": Decimal("4.8"),
        "notes": "Top-tier concrete supplier; consistently delivers ahead of schedule.",
    },
    {
        "name": "Kuzey Mekanik Muhendislik",
        "tax_id": "4567890123",
        "contact_person": "Hasan Kuzey",
        "phone": "+90 312 555 0404",
        "email": "info@kuzeymekanik.com.tr",
        "address": "Cankaya, Ankara, Turkey",
        "specialization": "Mekanik",
        "status": SubcontractorStatus.SUSPENDED,
        "rating": Decimal("3.5"),
        "notes": "Suspended due to delayed delivery on previous project.",
    },
]


# ------------------------------------------------------------------------
# Contracts on the demo project (Istanbul Havalimani Terminal B, id=1)
# Indexed by subcontractor name -> list of contract dicts
# Each contract has a "payments" list (created after contract insert)
# ------------------------------------------------------------------------

CONTRACTS_SEED = {
    "Yilmaz Elektrik San. ve Tic. A.S.": [
        {
            "contract_number": "YE-2024-001",
            "description": "Terminal B electrical infrastructure",
            "contract_amount": Decimal("850000000"),
            "start_date": date(2024, 4, 1),
            "end_date": date(2026, 12, 31),
            "status": ContractStatus.ACTIVE,
            "scope_of_work": (
                "MV/LV distribution panels, cable trays, lighting, "
                "emergency systems and grounding for Terminal B."
            ),
            "payments": [
                {
                    "payment_number": 1,
                    "description": "Mobilization and initial materials",
                    "amount": Decimal("200000000"),
                    "payment_date": date(2024, 5, 15),
                    "status": PaymentStatus.PAID,
                    "invoice_number": "FT-2024-0512",
                },
                {
                    "payment_number": 2,
                    "description": "Q3 2024 progress payment",
                    "amount": Decimal("200000000"),
                    "payment_date": date(2024, 10, 5),
                    "status": PaymentStatus.PAID,
                    "invoice_number": "FT-2024-0987",
                },
                {
                    "payment_number": 3,
                    "description": "Q1 2025 progress payment - awaiting approval",
                    "amount": Decimal("150000000"),
                    "payment_date": date(2025, 3, 30),
                    "due_date": date(2025, 4, 30),
                    "status": PaymentStatus.PENDING,
                    "invoice_number": "FT-2025-0231",
                },
            ],
        },
    ],
    "Demir Yapi Insaat Ltd.": [
        {
            "contract_number": "DY-2024-007",
            "description": "Terminal B structural steel works",
            "contract_amount": Decimal("1200000000"),
            "start_date": date(2024, 5, 10),
            "end_date": date(2027, 3, 31),
            "status": ContractStatus.ACTIVE,
            "scope_of_work": (
                "Roof truss, secondary steel framing and cladding "
                "supports for Terminal B main hall."
            ),
            "payments": [
                {
                    "payment_number": 1,
                    "description": "Down payment - 33% of contract",
                    "amount": Decimal("400000000"),
                    "payment_date": date(2024, 6, 20),
                    "status": PaymentStatus.PAID,
                    "invoice_number": "DY-INV-2024-001",
                },
                {
                    "payment_number": 2,
                    "description": "Foundation steel completion milestone",
                    "amount": Decimal("300000000"),
                    "payment_date": date(2024, 12, 1),
                    "due_date": date(2025, 1, 15),
                    "status": PaymentStatus.APPROVED,
                    "invoice_number": "DY-INV-2024-002",
                },
            ],
        },
    ],
    "Atlas Beton A.S.": [
        {
            "contract_number": "AB-2024-003",
            "description": "Ready-mix concrete supply (Terminal B foundation)",
            "contract_amount": Decimal("650000000"),
            "start_date": date(2024, 3, 20),
            "end_date": date(2025, 9, 30),
            "status": ContractStatus.COMPLETED,
            "scope_of_work": (
                "C40 ready-mix concrete supply for Terminal B "
                "foundation and lower-floor slab pours."
            ),
            "payments": [
                {
                    "payment_number": 1,
                    "description": "Foundation pour batch 1",
                    "amount": Decimal("220000000"),
                    "payment_date": date(2024, 5, 30),
                    "status": PaymentStatus.PAID,
                    "invoice_number": "AB-2024-F001",
                },
                {
                    "payment_number": 2,
                    "description": "Foundation pour batch 2 + slab works",
                    "amount": Decimal("250000000"),
                    "payment_date": date(2024, 11, 15),
                    "status": PaymentStatus.PAID,
                    "invoice_number": "AB-2024-F045",
                },
                {
                    "payment_number": 3,
                    "description": "Final delivery + retention release",
                    "amount": Decimal("180000000"),
                    "payment_date": date(2025, 9, 25),
                    "status": PaymentStatus.PAID,
                    "invoice_number": "AB-2025-FINAL",
                },
            ],
        },
    ],
}


async def seed_subcontractors() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Find admin user
        admin = (await db.execute(
            select(User).where(User.email == "admin@example.com")
        )).scalar_one_or_none()
        if admin is None:
            print("[ERR] Admin user not found. Run seed_admin first.")
            return

        # 2. Find demo project
        project = (await db.execute(
            select(Project).where(Project.name == "Istanbul Havalimani Terminal B")
        )).scalar_one_or_none()
        if project is None:
            print("[ERR] Project 'Istanbul Havalimani Terminal B' not found. "
                  "Run seed_projects first.")
            return

        # 3. Idempotency check: if ANY of the seeded subcontractors exist, skip
        existing_count = (await db.execute(
            select(func.count(Subcontractor.id))
        )).scalar_one()
        if existing_count > 0:
            print(f"[SKIP] Subcontractors table already has {existing_count} rows.")
            return

        # 4. Insert subcontractors
        sub_by_name: dict[str, Subcontractor] = {}
        for spec in SUBCONTRACTORS_SEED:
            sub = Subcontractor(
                **spec,
                is_active=True,
                created_by=admin.id,
            )
            db.add(sub)
            sub_by_name[spec["name"]] = sub
        await db.flush()
        print(f"[OK] Inserted {len(sub_by_name)} subcontractors")

        # 5. Insert contracts + payments
        contract_count = 0
        payment_count = 0
        for sub_name, contracts in CONTRACTS_SEED.items():
            sub = sub_by_name[sub_name]
            for c_spec in contracts:
                payments = c_spec.pop("payments", [])
                contract = SubcontractorContract(
                    subcontractor_id=sub.id,
                    project_id=project.id,
                    created_by=admin.id,
                    **c_spec,
                )
                db.add(contract)
                await db.flush()
                contract_count += 1

                for p_spec in payments:
                    # If status is PAID/APPROVED, set approved_by/at to admin/today
                    extra = {}
                    if p_spec.get("status") in (PaymentStatus.PAID, PaymentStatus.APPROVED):
                        from datetime import datetime, timezone as _tz
                        extra["approved_by"] = admin.id
                        extra["approved_at"] = datetime.now(_tz.utc)

                    payment = SubcontractorPayment(
                        contract_id=contract.id,
                        created_by=admin.id,
                        **p_spec,
                        **extra,
                    )
                    db.add(payment)
                    payment_count += 1

        await db.commit()
        print(f"[OK] Inserted {contract_count} contracts and {payment_count} payments")
        print()
        print("Demo data summary:")
        print(f"  - 4 subcontractors (3 ACTIVE, 1 SUSPENDED)")
        print(f"  - 3 contracts on Istanbul Havalimani Terminal B")
        print(f"  - Total contract value: 2,700,000,000 RUB")
        print(f"  - Paid so far:          1,450,000,000 RUB")
        print(f"  - Pending/approved:       450,000,000 RUB")


if __name__ == "__main__":
    asyncio.run(seed_subcontractors())
