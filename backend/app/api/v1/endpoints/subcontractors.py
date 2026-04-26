"""Subcontractor management endpoints (companies, contracts, payments)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.project import Project
from app.models.subcontractor import (
    ContractStatus,
    PaymentStatus,
    Subcontractor,
    SubcontractorContract,
    SubcontractorPayment,
    SubcontractorStatus,
)
from app.models.user import User, UserRole
from app.schemas.subcontractor import (
    ContractCreate,
    ContractResponse,
    ContractUpdate,
    MonthlyPaymentPoint,
    PaymentCreate,
    PaymentResponse,
    PaymentUpdate,
    SubcontractorCreate,
    SubcontractorKPIs,
    SubcontractorListItem,
    SubcontractorResponse,
    SubcontractorUpdate,
    TopSubcontractor,
)

router = APIRouter(tags=["Subcontractors"])


# ============================================================================
# Helpers
# ============================================================================

def _today() -> date:
    return date.today()


async def _ensure_subcontractor(db, sub_id: int) -> Subcontractor:
    sub = await db.get(Subcontractor, sub_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subcontractor not found")
    return sub


async def _ensure_contract_under_sub(db, sub_id: int, contract_id: int) -> SubcontractorContract:
    contract = await db.get(SubcontractorContract, contract_id)
    if contract is None or contract.subcontractor_id != sub_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    return contract


async def _ensure_payment_under_contract(db, contract_id: int, payment_id: int) -> SubcontractorPayment:
    payment = await db.get(SubcontractorPayment, payment_id)
    if payment is None or payment.contract_id != contract_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return payment


async def _compute_subcontractor_aggregates(db, sub_id: int) -> tuple[int, Decimal]:
    stmt = select(
        func.count(SubcontractorContract.id).filter(
            SubcontractorContract.status == ContractStatus.ACTIVE
        ),
        func.coalesce(func.sum(SubcontractorContract.contract_amount), 0),
    ).where(SubcontractorContract.subcontractor_id == sub_id)
    row = (await db.execute(stmt)).one()
    return int(row[0] or 0), Decimal(row[1] or 0)


async def _compute_contract_aggregates(db, contract: SubcontractorContract) -> dict:
    paid = (await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
            SubcontractorPayment.contract_id == contract.id,
            SubcontractorPayment.status == PaymentStatus.PAID,
        )
    )).scalar_one()
    pending = (await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
            SubcontractorPayment.contract_id == contract.id,
            SubcontractorPayment.status.in_([PaymentStatus.PENDING, PaymentStatus.APPROVED]),
        )
    )).scalar_one()
    count = (await db.execute(
        select(func.count(SubcontractorPayment.id)).where(
            SubcontractorPayment.contract_id == contract.id
        )
    )).scalar_one()
    is_overdue = (
        contract.status == ContractStatus.ACTIVE and contract.end_date < _today()
    )
    return {
        "paid_amount": Decimal(paid),
        "pending_amount": Decimal(pending),
        "payment_count": int(count),
        "is_overdue": is_overdue,
    }


def _sub_to_response(sub: Subcontractor, active_cnt: int, total_val: Decimal) -> SubcontractorResponse:
    return SubcontractorResponse(
        id=sub.id,
        name=sub.name,
        tax_id=sub.tax_id,
        contact_person=sub.contact_person,
        phone=sub.phone,
        email=sub.email,
        address=sub.address,
        specialization=sub.specialization,
        status=SubcontractorStatus(sub.status.value),
        rating=sub.rating,
        notes=sub.notes,
        is_active=sub.is_active,
        created_by=sub.created_by,
        creator=sub.creator,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        active_contract_count=active_cnt,
        total_contract_value=total_val,
    )


def _contract_to_response(c: SubcontractorContract, aggs: dict) -> ContractResponse:
    return ContractResponse(
        id=c.id,
        subcontractor_id=c.subcontractor_id,
        project_id=c.project_id,
        contract_number=c.contract_number,
        description=c.description,
        contract_amount=c.contract_amount,
        start_date=c.start_date,
        end_date=c.end_date,
        status=ContractStatus(c.status.value),
        scope_of_work=c.scope_of_work,
        notes=c.notes,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
        subcontractor=c.subcontractor,
        project=c.project,
        paid_amount=aggs["paid_amount"],
        pending_amount=aggs["pending_amount"],
        payment_count=aggs["payment_count"],
        is_overdue=aggs["is_overdue"],
    )


# ============================================================================
# Subcontractor list / create / detail / update / delete + meta routes
# ============================================================================

@router.get(
    "/subcontractors/stats/kpis",
    response_model=SubcontractorKPIs,
    summary="Aggregated KPIs for the subcontractor dashboard",
)
async def get_subcontractor_kpis(user: CurrentUser, db: DBSession) -> SubcontractorKPIs:
    today = _today()

    total_subs = (await db.execute(
        select(func.count(Subcontractor.id)).where(Subcontractor.is_active.is_(True))
    )).scalar_one()
    active_contracts = (await db.execute(
        select(func.count(SubcontractorContract.id)).where(
            SubcontractorContract.status == ContractStatus.ACTIVE
        )
    )).scalar_one()
    overdue_contracts = (await db.execute(
        select(func.count(SubcontractorContract.id)).where(
            SubcontractorContract.status == ContractStatus.ACTIVE,
            SubcontractorContract.end_date < today,
        )
    )).scalar_one()
    total_value = (await db.execute(
        select(func.coalesce(func.sum(SubcontractorContract.contract_amount), 0))
    )).scalar_one()
    total_paid = (await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
            SubcontractorPayment.status == PaymentStatus.PAID
        )
    )).scalar_one()
    total_pending = (await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
            SubcontractorPayment.status.in_([PaymentStatus.PENDING, PaymentStatus.APPROVED])
        )
    )).scalar_one()

    completion_pct = float(total_paid / total_value * 100) if total_value > 0 else 0.0

    top_stmt = (
        select(
            Subcontractor.id,
            Subcontractor.name,
            func.coalesce(func.sum(SubcontractorContract.contract_amount), 0).label("total"),
            func.count(SubcontractorContract.id).label("cnt"),
        )
        .join(SubcontractorContract, SubcontractorContract.subcontractor_id == Subcontractor.id)
        .group_by(Subcontractor.id, Subcontractor.name)
        .order_by(func.coalesce(func.sum(SubcontractorContract.contract_amount), 0).desc())
        .limit(5)
    )
    top_subs = [
        TopSubcontractor(
            id=r[0], name=r[1],
            total_value=Decimal(r[2] or 0), contract_count=int(r[3] or 0),
        )
        for r in (await db.execute(top_stmt)).all()
    ]

    contracts_by_status: dict[str, int] = {s.value: 0 for s in ContractStatus}
    for st, cnt in (await db.execute(
        select(SubcontractorContract.status, func.count(SubcontractorContract.id))
        .group_by(SubcontractorContract.status)
    )).all():
        contracts_by_status[st.value] = int(cnt)

    payments_by_status: dict[str, Decimal] = {s.value: Decimal("0") for s in PaymentStatus}
    for st, amt in (await db.execute(
        select(
            SubcontractorPayment.status,
            func.coalesce(func.sum(SubcontractorPayment.amount), 0),
        ).group_by(SubcontractorPayment.status)
    )).all():
        payments_by_status[st.value] = Decimal(amt or 0)

    monthly_rows = (await db.execute(
        select(
            func.to_char(func.date_trunc("month", SubcontractorPayment.payment_date), "YYYY-MM").label("month"),
            func.coalesce(func.sum(SubcontractorPayment.amount), 0).label("amount"),
            func.count(SubcontractorPayment.id).label("cnt"),
        )
        .where(SubcontractorPayment.status == PaymentStatus.PAID)
        .group_by("month").order_by("month")
    )).all()
    monthly = [
        MonthlyPaymentPoint(month=str(r[0]), amount=Decimal(r[1] or 0), count=int(r[2] or 0))
        for r in monthly_rows[-6:]
    ]

    return SubcontractorKPIs(
        total_subcontractors=int(total_subs),
        active_contracts=int(active_contracts),
        overdue_contracts=int(overdue_contracts),
        total_contract_value=Decimal(total_value),
        total_paid=Decimal(total_paid),
        total_pending=Decimal(total_pending),
        payment_completion_pct=round(completion_pct, 2),
        top_subcontractors=top_subs,
        contracts_by_status=contracts_by_status,
        payments_by_status=payments_by_status,
        monthly_payments=monthly,
    )


@router.get(
    "/subcontractors/specializations",
    response_model=list[str],
    summary="Distinct specialization values (for typeahead)",
)
async def list_specializations(user: CurrentUser, db: DBSession) -> list[str]:
    rows = (await db.execute(
        select(Subcontractor.specialization)
        .where(
            Subcontractor.specialization.is_not(None),
            Subcontractor.specialization != "",
        )
        .distinct().order_by(Subcontractor.specialization)
    )).scalars().all()
    return [r for r in rows if r]


@router.get(
    "/subcontractors",
    response_model=list[SubcontractorListItem],
    summary="List subcontractors (with filters)",
)
async def list_subcontractors(
    user: CurrentUser,
    db: DBSession,
    status_filter: SubcontractorStatus | None = Query(None, alias="status"),
    specialization: str | None = Query(None, max_length=255),
    search: str | None = Query(None, max_length=255),
    include_inactive: bool = Query(False),
) -> list[SubcontractorListItem]:
    conditions = []
    if not include_inactive:
        conditions.append(Subcontractor.is_active.is_(True))
    if status_filter is not None:
        conditions.append(Subcontractor.status == status_filter)
    if specialization:
        conditions.append(
            func.lower(Subcontractor.specialization) == specialization.strip().lower()
        )
    if search:
        like = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Subcontractor.name).like(like),
                func.lower(func.coalesce(Subcontractor.tax_id, "")).like(like),
                func.lower(func.coalesce(Subcontractor.contact_person, "")).like(like),
            )
        )

    stmt = (
        select(Subcontractor)
        .where(and_(*conditions) if conditions else True)
        .order_by(Subcontractor.name)
    )
    subs = list((await db.execute(stmt)).scalars().all())
    if not subs:
        return []

    sub_ids = [s.id for s in subs]
    agg_map: dict[int, tuple[int, Decimal]] = {}
    for sid, active_cnt, total in (await db.execute(
        select(
            SubcontractorContract.subcontractor_id,
            func.count(SubcontractorContract.id).filter(
                SubcontractorContract.status == ContractStatus.ACTIVE
            ).label("active_cnt"),
            func.coalesce(func.sum(SubcontractorContract.contract_amount), 0).label("total"),
        )
        .where(SubcontractorContract.subcontractor_id.in_(sub_ids))
        .group_by(SubcontractorContract.subcontractor_id)
    )).all():
        agg_map[sid] = (int(active_cnt or 0), Decimal(total or 0))

    return [
        SubcontractorListItem(
            id=s.id, name=s.name, tax_id=s.tax_id,
            specialization=s.specialization,
            status=SubcontractorStatus(s.status.value),
            rating=s.rating, is_active=s.is_active,
            active_contract_count=agg_map.get(s.id, (0, Decimal("0")))[0],
            total_contract_value=agg_map.get(s.id, (0, Decimal("0")))[1],
            created_at=s.created_at,
        )
        for s in subs
    ]


@router.post(
    "/subcontractors",
    response_model=SubcontractorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subcontractor",
)
async def create_subcontractor(
    payload: SubcontractorCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> SubcontractorResponse:
    sub = Subcontractor(
        name=payload.name, tax_id=payload.tax_id,
        contact_person=payload.contact_person, phone=payload.phone,
        email=payload.email, address=payload.address,
        specialization=payload.specialization, status=payload.status,
        rating=payload.rating, notes=payload.notes,
        is_active=True, created_by=user.id,
    )
    db.add(sub)
    try:
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        msg = str(ie.orig)[:200]
        if "tax_id" in msg.lower():
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                "A subcontractor with this tax_id already exists")
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"Could not create subcontractor: {msg}")

    await db.refresh(sub, attribute_names=["creator"])
    return _sub_to_response(sub, 0, Decimal("0"))


@router.get(
    "/subcontractors/{sub_id}",
    response_model=SubcontractorResponse,
    summary="Get subcontractor detail",
)
async def get_subcontractor(sub_id: int, user: CurrentUser, db: DBSession) -> SubcontractorResponse:
    sub = await _ensure_subcontractor(db, sub_id)
    await db.refresh(sub, attribute_names=["creator"])
    active_cnt, total_val = await _compute_subcontractor_aggregates(db, sub.id)
    return _sub_to_response(sub, active_cnt, total_val)


@router.patch(
    "/subcontractors/{sub_id}",
    response_model=SubcontractorResponse,
    summary="Update a subcontractor (partial)",
)
async def update_subcontractor(
    sub_id: int,
    payload: SubcontractorUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> SubcontractorResponse:
    sub = await _ensure_subcontractor(db, sub_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sub, field, value)
    try:
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        msg = str(ie.orig)[:200]
        if "tax_id" in msg.lower():
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                "A subcontractor with this tax_id already exists")
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"Could not update subcontractor: {msg}")

    await db.refresh(sub, attribute_names=["creator"])
    active_cnt, total_val = await _compute_subcontractor_aggregates(db, sub.id)
    return _sub_to_response(sub, active_cnt, total_val)


@router.delete(
    "/subcontractors/{sub_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a subcontractor (only if no contracts exist)",
)
async def delete_subcontractor(
    sub_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    sub = await _ensure_subcontractor(db, sub_id)
    contract_count = (await db.execute(
        select(func.count(SubcontractorContract.id)).where(
            SubcontractorContract.subcontractor_id == sub_id
        )
    )).scalar_one()
    if contract_count > 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot delete: subcontractor has {contract_count} contract(s). "
            "Suspend the subcontractor instead.",
        )
    sub.is_active = False
    sub.status = SubcontractorStatus.SUSPENDED
    await db.commit()


# ============================================================================
# Contract list / create / detail / update / delete
# ============================================================================

@router.get(
    "/subcontractors/{sub_id}/contracts",
    response_model=list[ContractResponse],
    summary="List contracts for a subcontractor",
)
async def list_contracts(
    sub_id: int,
    user: CurrentUser,
    db: DBSession,
    status_filter: ContractStatus | None = Query(None, alias="status"),
) -> list[ContractResponse]:
    await _ensure_subcontractor(db, sub_id)
    conditions = [SubcontractorContract.subcontractor_id == sub_id]
    if status_filter is not None:
        conditions.append(SubcontractorContract.status == status_filter)

    stmt = (
        select(SubcontractorContract)
        .options(
            selectinload(SubcontractorContract.subcontractor),
            selectinload(SubcontractorContract.project),
        )
        .where(and_(*conditions))
        .order_by(SubcontractorContract.start_date.desc(), SubcontractorContract.id.desc())
    )
    contracts = list((await db.execute(stmt)).scalars().all())
    if not contracts:
        return []

    contract_ids = [c.id for c in contracts]
    today = _today()

    paid_map: dict[int, Decimal] = {
        cid: Decimal(amt or 0) for cid, amt in (await db.execute(
            select(
                SubcontractorPayment.contract_id,
                func.coalesce(func.sum(SubcontractorPayment.amount), 0),
            ).where(
                SubcontractorPayment.contract_id.in_(contract_ids),
                SubcontractorPayment.status == PaymentStatus.PAID,
            ).group_by(SubcontractorPayment.contract_id)
        )).all()
    }
    pending_map: dict[int, Decimal] = {
        cid: Decimal(amt or 0) for cid, amt in (await db.execute(
            select(
                SubcontractorPayment.contract_id,
                func.coalesce(func.sum(SubcontractorPayment.amount), 0),
            ).where(
                SubcontractorPayment.contract_id.in_(contract_ids),
                SubcontractorPayment.status.in_([PaymentStatus.PENDING, PaymentStatus.APPROVED]),
            ).group_by(SubcontractorPayment.contract_id)
        )).all()
    }
    count_map: dict[int, int] = {
        cid: int(cnt or 0) for cid, cnt in (await db.execute(
            select(SubcontractorPayment.contract_id, func.count(SubcontractorPayment.id))
            .where(SubcontractorPayment.contract_id.in_(contract_ids))
            .group_by(SubcontractorPayment.contract_id)
        )).all()
    }

    return [
        _contract_to_response(c, {
            "paid_amount": paid_map.get(c.id, Decimal("0")),
            "pending_amount": pending_map.get(c.id, Decimal("0")),
            "payment_count": count_map.get(c.id, 0),
            "is_overdue": (c.status == ContractStatus.ACTIVE and c.end_date < today),
        })
        for c in contracts
    ]


@router.post(
    "/subcontractors/{sub_id}/contracts",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a contract under a subcontractor",
)
async def create_contract(
    sub_id: int,
    payload: ContractCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> ContractResponse:
    await _ensure_subcontractor(db, sub_id)
    project = await db.get(Project, payload.project_id)
    if project is None or not project.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"Project id={payload.project_id} does not exist")

    contract = SubcontractorContract(
        subcontractor_id=sub_id,
        project_id=payload.project_id,
        contract_number=payload.contract_number,
        description=payload.description,
        contract_amount=payload.contract_amount,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status,
        scope_of_work=payload.scope_of_work,
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(contract)
    try:
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        msg = str(ie.orig)[:200]
        if "contract_number" in msg.lower():
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                "A contract with this contract_number already exists")
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"Could not create contract: {msg}")

    await db.refresh(contract, attribute_names=["subcontractor", "project"])
    aggs = await _compute_contract_aggregates(db, contract)
    return _contract_to_response(contract, aggs)


@router.get(
    "/subcontractors/{sub_id}/contracts/{contract_id}",
    response_model=ContractResponse,
    summary="Get contract detail",
)
async def get_contract(
    sub_id: int, contract_id: int, user: CurrentUser, db: DBSession,
) -> ContractResponse:
    await _ensure_subcontractor(db, sub_id)
    contract = await _ensure_contract_under_sub(db, sub_id, contract_id)
    await db.refresh(contract, attribute_names=["subcontractor", "project"])
    aggs = await _compute_contract_aggregates(db, contract)
    return _contract_to_response(contract, aggs)


@router.patch(
    "/subcontractors/{sub_id}/contracts/{contract_id}",
    response_model=ContractResponse,
    summary="Update a contract (partial)",
)
async def update_contract(
    sub_id: int,
    contract_id: int,
    payload: ContractUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> ContractResponse:
    await _ensure_subcontractor(db, sub_id)
    contract = await _ensure_contract_under_sub(db, sub_id, contract_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "project_id" in update_data and update_data["project_id"] is not None:
        project = await db.get(Project, update_data["project_id"])
        if project is None or not project.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                f"Project id={update_data['project_id']} does not exist")

    for field, value in update_data.items():
        setattr(contract, field, value)

    try:
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        msg = str(ie.orig)[:200]
        if "contract_number" in msg.lower():
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                "A contract with this contract_number already exists")
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"Could not update contract: {msg}")

    await db.refresh(contract, attribute_names=["subcontractor", "project"])
    aggs = await _compute_contract_aggregates(db, contract)
    return _contract_to_response(contract, aggs)


@router.delete(
    "/subcontractors/{sub_id}/contracts/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a contract (only when status=DRAFT)",
)
async def delete_contract(
    sub_id: int,
    contract_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
):
    await _ensure_subcontractor(db, sub_id)
    contract = await _ensure_contract_under_sub(db, sub_id, contract_id)
    if contract.status != ContractStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot delete contract with status={contract.status.value}. "
            "Only DRAFT contracts can be deleted.",
        )
    await db.delete(contract)
    await db.commit()


# ============================================================================
# Payment list / create / update / delete
# ============================================================================

@router.get(
    "/subcontractors/{sub_id}/contracts/{contract_id}/payments",
    response_model=list[PaymentResponse],
    summary="List payments (hakedis) for a contract",
)
async def list_payments(
    sub_id: int,
    contract_id: int,
    user: CurrentUser,
    db: DBSession,
) -> list[PaymentResponse]:
    await _ensure_subcontractor(db, sub_id)
    await _ensure_contract_under_sub(db, sub_id, contract_id)

    rows = list((await db.execute(
        select(SubcontractorPayment)
        .where(SubcontractorPayment.contract_id == contract_id)
        .order_by(SubcontractorPayment.payment_number)
    )).scalars().all())
    return [PaymentResponse.model_validate(p) for p in rows]


@router.post(
    "/subcontractors/{sub_id}/contracts/{contract_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment (auto-numbers if payment_number not given)",
)
async def create_payment(
    sub_id: int,
    contract_id: int,
    payload: PaymentCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> PaymentResponse:
    await _ensure_subcontractor(db, sub_id)
    contract = await _ensure_contract_under_sub(db, sub_id, contract_id)

    # Auto-assign payment_number if not provided
    payment_number = payload.payment_number
    if payment_number is None:
        max_num = (await db.execute(
            select(func.coalesce(func.max(SubcontractorPayment.payment_number), 0))
            .where(SubcontractorPayment.contract_id == contract_id)
        )).scalar_one()
        payment_number = int(max_num) + 1

    # Build payment
    payment = SubcontractorPayment(
        contract_id=contract_id,
        payment_number=payment_number,
        description=payload.description,
        amount=payload.amount,
        payment_date=payload.payment_date,
        due_date=payload.due_date,
        status=payload.status,
        invoice_number=payload.invoice_number,
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(payment)
    try:
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        msg = str(ie.orig)[:200]
        if "payment_number" in msg.lower() or "uq_subcontractor_payments" in msg.lower():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Payment number {payment_number} already exists for this contract",
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"Could not create payment: {msg}")

    await db.refresh(payment)

    # Soft over-payment warning (after commit, in response)
    total_for_contract = (await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0))
        .where(SubcontractorPayment.contract_id == contract_id)
    )).scalar_one()
    warning = None
    if Decimal(total_for_contract) > contract.contract_amount:
        warning = (
            f"Total payments ({total_for_contract}) exceed contract amount "
            f"({contract.contract_amount}). Over-payment: "
            f"{Decimal(total_for_contract) - contract.contract_amount}"
        )

    response = PaymentResponse.model_validate(payment)
    response.over_payment_warning = warning
    return response


@router.patch(
    "/subcontractors/{sub_id}/contracts/{contract_id}/payments/{payment_id}",
    response_model=PaymentResponse,
    summary="Update a payment (partial)",
)
async def update_payment(
    sub_id: int,
    contract_id: int,
    payment_id: int,
    payload: PaymentUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> PaymentResponse:
    await _ensure_subcontractor(db, sub_id)
    contract = await _ensure_contract_under_sub(db, sub_id, contract_id)
    payment = await _ensure_payment_under_contract(db, contract_id, payment_id)

    update_data = payload.model_dump(exclude_unset=True)

    # Track approved_at when transitioning to APPROVED
    from datetime import datetime, timezone as _tz
    if (
        "status" in update_data
        and update_data["status"] == PaymentStatus.APPROVED
        and payment.status != PaymentStatus.APPROVED
    ):
        payment.approved_by = user.id
        payment.approved_at = datetime.now(_tz.utc)

    for field, value in update_data.items():
        setattr(payment, field, value)

    try:
        await db.commit()
    except IntegrityError as ie:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
            f"Could not update payment: {str(ie.orig)[:200]}")

    await db.refresh(payment)

    # Recompute over-payment warning
    total_for_contract = (await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0))
        .where(SubcontractorPayment.contract_id == contract_id)
    )).scalar_one()
    warning = None
    if Decimal(total_for_contract) > contract.contract_amount:
        warning = (
            f"Total payments ({total_for_contract}) exceed contract amount "
            f"({contract.contract_amount})."
        )

    response = PaymentResponse.model_validate(payment)
    response.over_payment_warning = warning
    return response


@router.delete(
    "/subcontractors/{sub_id}/contracts/{contract_id}/payments/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment (only if status != PAID)",
)
async def delete_payment(
    sub_id: int,
    contract_id: int,
    payment_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
):
    await _ensure_subcontractor(db, sub_id)
    await _ensure_contract_under_sub(db, sub_id, contract_id)
    payment = await _ensure_payment_under_contract(db, contract_id, payment_id)

    if payment.status == PaymentStatus.PAID:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot delete a PAID payment. Reverse the status first if you must.",
        )
    await db.delete(payment)
    await db.commit()
