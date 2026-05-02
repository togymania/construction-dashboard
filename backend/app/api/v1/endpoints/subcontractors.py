"""Subcontractor management endpoints (companies, contracts, payments)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.project import Project
from app.models.subcontractor import (
    ContractDocument,
    ContractStatus,
    PaymentStatus,
    Subcontractor,
    SubcontractorContract,
    SubcontractorPayment,
    SubcontractorStatus,
)
from app.models.user import User, UserRole
from app.schemas.subcontractor import (
    AIInsight,
    ContractAlert,
    ContractCreate,
    ContractDocumentResponse,
    ContractForecast,
    ContractResponse,
    ContractUpdate,
    MonthlyCashFlowPoint,
    MonthlyPaymentPoint,
    PaymentCreate,
    PaymentDiscipline,
    PaymentResponse,
    PaymentUpdate,
    RiskScore,
    SubcontractorCreate,
    SubcontractorInsights,
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


# ============================================================================
# Cross-cut: contracts under a specific project
# ============================================================================

@router.get(
    "/projects/{project_id}/subcontractor-contracts",
    response_model=list[ContractResponse],
    summary="List all subcontractor contracts on a specific project",
    tags=["Subcontractors"],
)
async def list_contracts_for_project(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
    status_filter: ContractStatus | None = Query(None, alias="status"),
) -> list[ContractResponse]:
    # Verify project exists (and is active)
    project = await db.get(Project, project_id)
    if project is None or not project.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    conditions = [SubcontractorContract.project_id == project_id]
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


# ============================================================================
# Phase 1: Financial Intelligence
# ============================================================================

@router.get(
    "/subcontractors/{sub_id}/contracts/{contract_id}/forecast",
    response_model=ContractForecast,
    summary="Financial forecast for a contract",
)
async def get_contract_forecast(
    sub_id: int, contract_id: int, user: CurrentUser, db: DBSession,
) -> ContractForecast:
    await _ensure_subcontractor(db, sub_id)
    contract = await _ensure_contract_under_sub(db, sub_id, contract_id)
    today = _today()

    total_paid = Decimal((await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
            SubcontractorPayment.contract_id == contract_id,
            SubcontractorPayment.status == PaymentStatus.PAID,
        )
    )).scalar_one())

    remaining = contract.contract_amount - total_paid
    progress = float(total_paid / contract.contract_amount * 100) if contract.contract_amount > 0 else 0.0

    days_elapsed = max((today - contract.start_date).days, 1)
    days_remaining = max((contract.end_date - today).days, 0)

    burn_rate = total_paid / days_elapsed if days_elapsed > 0 else Decimal("0")

    # Last 30 days paid
    from datetime import timedelta
    cutoff = today - timedelta(days=30)
    paid_30d = Decimal((await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
            SubcontractorPayment.contract_id == contract_id,
            SubcontractorPayment.status == PaymentStatus.PAID,
            SubcontractorPayment.payment_date >= cutoff,
        )
    )).scalar_one())

    avg_daily = paid_30d / 30 if paid_30d > 0 else Decimal("0")
    est_date = None
    if avg_daily > 0 and remaining > 0:
        est_days = int(remaining / avg_daily)
        est_date = (today + timedelta(days=est_days)).isoformat()

    next_30 = avg_daily * 30

    return ContractForecast(
        contract_id=contract_id,
        contract_amount=contract.contract_amount,
        total_paid=total_paid,
        remaining_amount=remaining,
        payment_progress_pct=round(progress, 2),
        burn_rate_per_day=round(burn_rate, 2),
        avg_daily_payment=round(avg_daily, 2),
        estimated_completion_date=est_date,
        next_30_days_projected=round(next_30, 2),
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
    )


@router.get(
    "/subcontractors/{sub_id}/payment-discipline",
    response_model=PaymentDiscipline,
    summary="Payment discipline score for a subcontractor",
)
async def get_payment_discipline(
    sub_id: int, user: CurrentUser, db: DBSession,
) -> PaymentDiscipline:
    await _ensure_subcontractor(db, sub_id)
    today = _today()

    # Get all payments for this subcontractor's contracts
    contract_ids_stmt = select(SubcontractorContract.id).where(
        SubcontractorContract.subcontractor_id == sub_id
    )
    payments = list((await db.execute(
        select(SubcontractorPayment).where(
            SubcontractorPayment.contract_id.in_(contract_ids_stmt)
        )
    )).scalars().all())

    total = len(payments)
    if total == 0:
        return PaymentDiscipline(
            subcontractor_id=sub_id, score=100, grade="A",
            overdue_payment_pct=0.0, rejected_payment_pct=0.0,
            avg_approval_days=0.0, total_payments_evaluated=0,
        )

    # Overdue: due_date < today AND status != PAID
    overdue = sum(
        1 for p in payments
        if p.due_date and p.due_date < today and p.status != PaymentStatus.PAID
    )
    overdue_pct = (overdue / total) * 100

    # Rejected
    rejected = sum(1 for p in payments if p.status == PaymentStatus.REJECTED)
    rejected_pct = (rejected / total) * 100

    # Average approval time
    approval_times = []
    for p in payments:
        if p.approved_at and p.created_at:
            delta = (p.approved_at - p.created_at).total_seconds() / 86400
            approval_times.append(delta)
    avg_approval = sum(approval_times) / len(approval_times) if approval_times else 0.0

    # Score: 100 minus penalties
    penalty_overdue = min(40, overdue_pct * 0.4)
    penalty_rejected = min(30, rejected_pct * 0.3)
    penalty_slow = min(30, max(0, (avg_approval - 3) * 5))  # 3 days baseline
    score = max(0, int(100 - penalty_overdue - penalty_rejected - penalty_slow))

    grades = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]
    grade = next(g for threshold, g in grades if score >= threshold)

    return PaymentDiscipline(
        subcontractor_id=sub_id,
        score=score,
        grade=grade,
        overdue_payment_pct=round(overdue_pct, 1),
        rejected_payment_pct=round(rejected_pct, 1),
        avg_approval_days=round(avg_approval, 1),
        total_payments_evaluated=total,
    )


@router.get(
    "/subcontractors/{sub_id}/cashflow",
    response_model=list[MonthlyCashFlowPoint],
    summary="Monthly cash flow breakdown for a subcontractor",
)
async def get_cashflow(
    sub_id: int, user: CurrentUser, db: DBSession,
) -> list[MonthlyCashFlowPoint]:
    await _ensure_subcontractor(db, sub_id)

    contract_ids_stmt = select(SubcontractorContract.id).where(
        SubcontractorContract.subcontractor_id == sub_id
    )

    # Paid by month
    paid_rows = (await db.execute(
        select(
            func.to_char(func.date_trunc("month", SubcontractorPayment.payment_date), "YYYY-MM").label("month"),
            func.coalesce(func.sum(SubcontractorPayment.amount), 0).label("amount"),
        )
        .where(
            SubcontractorPayment.contract_id.in_(contract_ids_stmt),
            SubcontractorPayment.status == PaymentStatus.PAID,
        )
        .group_by("month").order_by("month")
    )).all()

    approved_rows = (await db.execute(
        select(
            func.to_char(func.date_trunc("month", SubcontractorPayment.payment_date), "YYYY-MM").label("month"),
            func.coalesce(func.sum(SubcontractorPayment.amount), 0).label("amount"),
        )
        .where(
            SubcontractorPayment.contract_id.in_(contract_ids_stmt),
            SubcontractorPayment.status == PaymentStatus.APPROVED,
        )
        .group_by("month").order_by("month")
    )).all()

    pending_rows = (await db.execute(
        select(
            func.to_char(func.date_trunc("month", SubcontractorPayment.payment_date), "YYYY-MM").label("month"),
            func.coalesce(func.sum(SubcontractorPayment.amount), 0).label("amount"),
        )
        .where(
            SubcontractorPayment.contract_id.in_(contract_ids_stmt),
            SubcontractorPayment.status == PaymentStatus.PENDING,
        )
        .group_by("month").order_by("month")
    )).all()

    # Merge into single dict
    months: dict[str, dict[str, Decimal]] = {}
    for m, amt in paid_rows:
        months.setdefault(str(m), {"paid": Decimal("0"), "approved": Decimal("0"), "pending": Decimal("0")})
        months[str(m)]["paid"] = Decimal(amt or 0)
    for m, amt in approved_rows:
        months.setdefault(str(m), {"paid": Decimal("0"), "approved": Decimal("0"), "pending": Decimal("0")})
        months[str(m)]["approved"] = Decimal(amt or 0)
    for m, amt in pending_rows:
        months.setdefault(str(m), {"paid": Decimal("0"), "approved": Decimal("0"), "pending": Decimal("0")})
        months[str(m)]["pending"] = Decimal(amt or 0)

    result = sorted(months.items())[-12:]  # last 12 months
    return [
        MonthlyCashFlowPoint(
            month=m,
            paid_amount=d["paid"],
            approved_amount=d["approved"],
            pending_amount=d["pending"],
        )
        for m, d in result
    ]


# ============================================================================
# Phase 2: Risk & Alert System
# ============================================================================

@router.get(
    "/subcontractors/{sub_id}/contracts/{contract_id}/alerts",
    response_model=list[ContractAlert],
    summary="Risk alerts for a specific contract",
)
async def get_contract_alerts(
    sub_id: int, contract_id: int, user: CurrentUser, db: DBSession,
) -> list[ContractAlert]:
    await _ensure_subcontractor(db, sub_id)
    contract = await _ensure_contract_under_sub(db, sub_id, contract_id)
    today = _today()

    alerts: list[ContractAlert] = []

    # Calculate paid
    total_paid = Decimal((await db.execute(
        select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
            SubcontractorPayment.contract_id == contract_id,
            SubcontractorPayment.status == PaymentStatus.PAID,
        )
    )).scalar_one())

    # 1. Over-budget
    if total_paid > contract.contract_amount:
        over = total_paid - contract.contract_amount
        alerts.append(ContractAlert(
            level="critical", category="budget",
            message=f"Over-budget by {over:,.0f} ₽ (paid {total_paid:,.0f} vs contract {contract.contract_amount:,.0f})",
        ))

    # 2. Overdue payments
    overdue_count = (await db.execute(
        select(func.count(SubcontractorPayment.id)).where(
            SubcontractorPayment.contract_id == contract_id,
            SubcontractorPayment.due_date < today,
            SubcontractorPayment.status.in_([PaymentStatus.PENDING, PaymentStatus.APPROVED]),
        )
    )).scalar_one()
    if overdue_count > 0:
        alerts.append(ContractAlert(
            level="critical", category="payment",
            message=f"{overdue_count} overdue payment{'s' if overdue_count > 1 else ''}",
        ))

    # 3. Low progress + high payment
    if contract.contract_amount > 0:
        paid_pct = float(total_paid / contract.contract_amount * 100)
        duration = max((contract.end_date - contract.start_date).days, 1)
        elapsed_pct = float((today - contract.start_date).days / duration * 100)
        if paid_pct > 70 and elapsed_pct < 50:
            alerts.append(ContractAlert(
                level="warning", category="budget",
                message=f"High payment ({paid_pct:.0f}%) but only {elapsed_pct:.0f}% of time elapsed",
            ))

    # 4. Nearing end date
    days_until_end = (contract.end_date - today).days
    if 0 < days_until_end < 14 and contract.status == ContractStatus.ACTIVE:
        alerts.append(ContractAlert(
            level="warning", category="timeline",
            message=f"Contract ends in {days_until_end} day{'s' if days_until_end > 1 else ''}",
        ))

    # 5. Already overdue
    if contract.status == ContractStatus.ACTIVE and contract.end_date < today:
        overdue_days = (today - contract.end_date).days
        alerts.append(ContractAlert(
            level="critical", category="timeline",
            message=f"Contract is {overdue_days} day{'s' if overdue_days > 1 else ''} overdue",
        ))

    return alerts


@router.get(
    "/subcontractors/{sub_id}/risk-score",
    response_model=RiskScore,
    summary="Aggregate risk score for a subcontractor",
)
async def get_risk_score(
    sub_id: int, user: CurrentUser, db: DBSession,
) -> RiskScore:
    sub = await _ensure_subcontractor(db, sub_id)
    today = _today()

    contracts = list((await db.execute(
        select(SubcontractorContract).where(
            SubcontractorContract.subcontractor_id == sub_id,
            SubcontractorContract.status == ContractStatus.ACTIVE,
        )
    )).scalars().all())

    all_alerts: list[ContractAlert] = []
    contract_scores: list[int] = []

    for c in contracts:
        score = 0
        total_paid = Decimal((await db.execute(
            select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
                SubcontractorPayment.contract_id == c.id,
                SubcontractorPayment.status == PaymentStatus.PAID,
            )
        )).scalar_one())

        # Over-budget: +30
        if total_paid > c.contract_amount:
            score += 30
            all_alerts.append(ContractAlert(
                level="critical", category="budget",
                message=f"Contract #{c.id}: Over-budget",
            ))

        # Overdue payments: +20
        overdue_count = (await db.execute(
            select(func.count(SubcontractorPayment.id)).where(
                SubcontractorPayment.contract_id == c.id,
                SubcontractorPayment.due_date < today,
                SubcontractorPayment.status.in_([PaymentStatus.PENDING, PaymentStatus.APPROVED]),
            )
        )).scalar_one()
        if overdue_count > 0:
            score += min(20, overdue_count * 7)
            all_alerts.append(ContractAlert(
                level="critical", category="payment",
                message=f"Contract #{c.id}: {overdue_count} overdue payment{'s' if overdue_count > 1 else ''}",
            ))

        # Nearing end
        days_until = (c.end_date - today).days
        if 0 < days_until < 14:
            score += 15
            all_alerts.append(ContractAlert(
                level="warning", category="timeline",
                message=f"Contract #{c.id} ends in {days_until} days",
            ))
        elif days_until <= 0:
            score += 25
            all_alerts.append(ContractAlert(
                level="critical", category="timeline",
                message=f"Contract #{c.id} is overdue by {abs(days_until)} days",
            ))

        # High spend ratio
        if c.contract_amount > 0:
            paid_pct = float(total_paid / c.contract_amount * 100)
            duration = max((c.end_date - c.start_date).days, 1)
            elapsed_pct = float((today - c.start_date).days / duration * 100)
            if paid_pct > 70 and elapsed_pct < 50:
                score += 10
                all_alerts.append(ContractAlert(
                    level="warning", category="budget",
                    message=f"Contract #{c.id}: High spend ({paid_pct:.0f}%) vs time ({elapsed_pct:.0f}%)",
                ))

        contract_scores.append(min(100, score))

    agg_score = int(sum(contract_scores) / len(contract_scores)) if contract_scores else 0
    agg_score = min(100, agg_score)

    level = "critical" if agg_score >= 60 else "warning" if agg_score >= 30 else "healthy"
    summary = (
        f"{sub.name}: {len(contracts)} active contracts, "
        f"risk score {agg_score}/100 ({level}), "
        f"{len(all_alerts)} alert{'s' if len(all_alerts) != 1 else ''}"
    )

    return RiskScore(
        subcontractor_id=sub_id,
        score=agg_score,
        level=level,
        alerts=all_alerts[:20],
        summary=summary,
    )


# ============================================================================
# Phase 3: Document Intelligence
# ============================================================================

@router.post(
    "/subcontractors/{sub_id}/contracts/{contract_id}/documents",
    response_model=ContractDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document for a contract",
)
async def upload_document(
    sub_id: int,
    contract_id: int,
    file: UploadFile,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
    file_type: str = Query("CONTRACT", description="CONTRACT|INVOICE|ADDENDUM|REPORT"),
):
    from app.models.subcontractor import DocumentType as DocTypeModel
    import json as _json

    await _ensure_subcontractor(db, sub_id)
    await _ensure_contract_under_sub(db, sub_id, contract_id)

    # Validate file_type
    try:
        doc_type = DocTypeModel(file_type.upper())
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid file_type: {file_type}")

    # Determine version
    max_version = (await db.execute(
        select(func.coalesce(func.max(ContractDocument.version), 0)).where(
            ContractDocument.contract_id == contract_id,
            ContractDocument.file_type == doc_type,
        )
    )).scalar_one()
    version = int(max_version) + 1

    # Save file
    import os
    upload_dir = os.path.join("uploads", "contracts", str(contract_id))
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = f"{doc_type.value.lower()}_v{version}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Try to extract data from text-based files
    extracted = None
    if file.content_type and "text" in file.content_type:
        try:
            from app.services.contract_parser import parse_contract_text
            text = content.decode("utf-8", errors="ignore")
            extracted = _json.dumps(parse_contract_text(text))
        except Exception:
            pass

    doc = ContractDocument(
        contract_id=contract_id,
        file_name=file.filename or safe_name,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        file_type=doc_type,
        version=version,
        extracted_data=extracted,
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    resp = ContractDocumentResponse.model_validate(doc)
    if doc.extracted_data:
        resp.extracted_data = _json.loads(doc.extracted_data)
    return resp


@router.get(
    "/subcontractors/{sub_id}/contracts/{contract_id}/documents",
    response_model=list[ContractDocumentResponse],
    summary="List documents for a contract",
)
async def list_documents(
    sub_id: int, contract_id: int, user: CurrentUser, db: DBSession,
) -> list[ContractDocumentResponse]:
    import json as _json

    await _ensure_subcontractor(db, sub_id)
    await _ensure_contract_under_sub(db, sub_id, contract_id)

    docs = list((await db.execute(
        select(ContractDocument).where(
            ContractDocument.contract_id == contract_id
        ).order_by(ContractDocument.created_at.desc())
    )).scalars().all())

    result = []
    for doc in docs:
        resp = ContractDocumentResponse.model_validate(doc)
        if doc.extracted_data:
            try:
                resp.extracted_data = _json.loads(doc.extracted_data)
            except Exception:
                pass
        result.append(resp)
    return result


@router.get(
    "/documents/{doc_id}/download",
    summary="Download a document by ID",
)
async def download_document(
    doc_id: int, user: CurrentUser, db: DBSession,
):
    from fastapi.responses import FileResponse
    import os

    doc = await db.get(ContractDocument, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found on disk")

    return FileResponse(
        path=doc.file_path,
        filename=doc.file_name,
        media_type=doc.mime_type,
    )


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    doc_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
):
    import os

    doc = await db.get(ContractDocument, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    # Remove file from disk
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.commit()


# ============================================================================
# Phase 4: AI Insights
# ============================================================================

@router.get(
    "/subcontractors/{sub_id}/ai-insights",
    response_model=SubcontractorInsights,
    summary="AI-generated insights for a subcontractor",
)
async def get_ai_insights(
    sub_id: int, user: CurrentUser, db: DBSession,
) -> SubcontractorInsights:
    sub = await _ensure_subcontractor(db, sub_id)

    # Get active contracts with paid amounts
    contracts_raw = list((await db.execute(
        select(SubcontractorContract).where(
            SubcontractorContract.subcontractor_id == sub_id,
        )
    )).scalars().all())

    contract_dicts = []
    for c in contracts_raw:
        total_paid = Decimal((await db.execute(
            select(func.coalesce(func.sum(SubcontractorPayment.amount), 0)).where(
                SubcontractorPayment.contract_id == c.id,
                SubcontractorPayment.status == PaymentStatus.PAID,
            )
        )).scalar_one())
        contract_dicts.append({
            "id": c.id,
            "contract_amount": str(c.contract_amount),
            "total_paid": str(total_paid),
            "start_date": c.start_date.isoformat(),
            "end_date": c.end_date.isoformat(),
            "status": c.status.value,
        })

    # Get all payments
    contract_ids = [c.id for c in contracts_raw]
    payments_raw = []
    if contract_ids:
        payments_raw = list((await db.execute(
            select(SubcontractorPayment).where(
                SubcontractorPayment.contract_id.in_(contract_ids)
            )
        )).scalars().all())

    payment_dicts = [
        {
            "amount": str(p.amount),
            "payment_date": p.payment_date.isoformat(),
            "due_date": p.due_date.isoformat() if p.due_date else None,
            "status": p.status.value,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments_raw
    ]

    # Get risk score
    risk_resp = await get_risk_score(sub_id, user, db)

    # Generate insights
    from app.services.insight_generator import generate_insights, determine_overall_health

    insights = generate_insights(
        subcontractor_name=sub.name,
        contracts=contract_dicts,
        payments=payment_dicts,
        risk_score=risk_resp.score,
    )

    return SubcontractorInsights(
        subcontractor_id=sub_id,
        insights=insights,
        overall_health=determine_overall_health(risk_resp.score),
    )
