"""Tender (ihale) CRUD + AI extraction + AI analysis endpoints.

URL layout:

    GET  /projects/{project_id}/tenders                List tenders on project
    POST /projects/{project_id}/tenders                Create (with line items)
    POST /projects/{project_id}/tenders/extract        Upload a file -> draft
    GET  /tenders/{tender_id}                          Full tender + bids
    PATCH /tenders/{tender_id}                         Update meta / status
    DELETE /tenders/{tender_id}                        Drop tender + cascades
    POST /tenders/{tender_id}/line-items               Append a line item
    PATCH /tender-line-items/{lid}                     Edit a line item
    DELETE /tender-line-items/{lid}                    Drop a line item
    POST /tenders/{tender_id}/bids                     Create a bid (with prices)
    PATCH /bids/{bid_id}                               Update bid + lines
    DELETE /bids/{bid_id}                              Drop a bid
    POST /tenders/{tender_id}/award                    Mark a bid as selected
    GET  /tenders/{tender_id}/ai-analysis              6-section AI recommendation
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, UserLang, require_roles
from app.models.project import Project
from app.models.tender import (
    Bid,
    BidLineItem,
    BidPriceType,
    BidStatus,
    LineType,
    Tender,
    TenderLineItem,
    TenderStatus,
)
from app.models.user import User, UserRole
from app.schemas.tender import (
    BidCreate,
    BidLineItemUpsert,
    BidRead,
    BidUpdate,
    ExtractedBid,
    TenderAIAnalysis,
    TenderCreate,
    TenderExtraction,
    TenderLineItemCreate,
    TenderLineItemRead,
    TenderLineItemUpdate,
    TenderListItem,
    TenderMarketPrices,
    TenderRead,
    TenderUpdate,
)

router = APIRouter(tags=["Tenders"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _qty_for_line(line_items: list[TenderLineItem], line_id: int) -> Decimal:
    for li in line_items:
        if li.id == line_id:
            return Decimal(li.quantity or 0)
    return Decimal(0)


async def _recompute_bid_totals(
    db,
    bid: Bid,
    qty_by_line_id: dict[int, Decimal] | None = None,
) -> None:
    """Refresh cached totals on a bid from its persisted line items.

    Reads bid_line_items via an explicit SELECT instead of the ORM
    relationship (which would lazy-load under async and crash).
    """
    # Pull the bid's lines via an explicit query — never touching the
    # relationship attribute. Safe under async.
    bls = (
        (
            await db.execute(
                select(BidLineItem).where(BidLineItem.bid_id == bid.id)
            )
        )
        .scalars()
        .all()
    )

    if qty_by_line_id is None:
        if bls:
            line_ids = [bl.tender_line_item_id for bl in bls]
            rows = (
                await db.execute(
                    select(TenderLineItem.id, TenderLineItem.quantity)
                    .where(TenderLineItem.id.in_(line_ids))
                )
            ).all()
            qty_by_line_id = {int(r[0]): Decimal(r[1] or 0) for r in rows}
        else:
            qty_by_line_id = {}

    tot_labor = Decimal(0)
    tot_material = Decimal(0)
    tot_amount = Decimal(0)
    for bl in bls:
        # Non-fixed rows (Договорная / не включена / on_request) don't
        # contribute to numeric totals. Their line_total stays 0 and the
        # raw_text_price is preserved for display.
        if bl.price_type != BidPriceType.FIXED:
            bl.line_total = Decimal("0.00")
            continue
        qty = qty_by_line_id.get(bl.tender_line_item_id, Decimal(0))
        bl.line_total = (qty * Decimal(bl.unit_price_total or 0)).quantize(
            Decimal("0.01")
        )
        if bl.unit_price_labor is not None:
            tot_labor += qty * Decimal(bl.unit_price_labor)
        if bl.unit_price_material is not None:
            tot_material += qty * Decimal(bl.unit_price_material)
        tot_amount += bl.line_total
    bid.total_labor = tot_labor.quantize(Decimal("0.01"))
    bid.total_material = tot_material.quantize(Decimal("0.01"))
    bid.total_amount = tot_amount.quantize(Decimal("0.01"))
    # Net (без НДС) is the gross divided by (1 + vat_rate/100). We keep
    # both figures so the UI can flip between them without re-querying.
    vat = Decimal(bid.vat_rate or 0)
    if vat > 0:
        bid.total_without_vat = (
            bid.total_amount / (Decimal("1") + vat / Decimal("100"))
        ).quantize(Decimal("0.01"))
    else:
        bid.total_without_vat = bid.total_amount


def _normalize_split(
    labor: Decimal | None, material: Decimal | None, total: Decimal | None
) -> tuple[Decimal | None, Decimal | None, Decimal]:
    """Apply the labor/material/total split rules consistently.

    * If labor and material both present → total = labor + material
      (override whatever the caller passed)
    * If only one of (labor, material) present → that one is used as
      the total; the other stays NULL
    * If only total present → labor and material stay NULL
    """
    lab = Decimal(labor) if labor is not None else None
    mat = Decimal(material) if material is not None else None
    tot = Decimal(total or 0)

    if lab is not None and mat is not None:
        tot = lab + mat
    elif lab is not None and mat is None:
        tot = max(tot, lab)
    elif mat is not None and lab is None:
        tot = max(tot, mat)
    return lab, mat, tot


# ---------------------------------------------------------------------------
# Tender CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/tenders",
    response_model=list[TenderListItem],
    summary="List tenders for a project",
)
async def list_project_tenders(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
) -> list[TenderListItem]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    tenders = (
        (
            await db.execute(
                select(Tender)
                .where(Tender.project_id == project_id)
                .options(
                    selectinload(Tender.line_items),
                    selectinload(Tender.bids),
                )
                .order_by(Tender.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    out: list[TenderListItem] = []
    for t in tenders:
        # Lowest bid (only count received/selected bids, ignore invited-no-price)
        live_bids = [
            b for b in t.bids
            if b.status in (BidStatus.RECEIVED, BidStatus.SELECTED)
            and Decimal(b.total_amount or 0) > 0
        ]
        # bid_count = unique active bidders (variants count, but old
        # revisions of the same chain do NOT — we count only non-superseded).
        active_bids = [
            b for b in t.bids if b.status != BidStatus.SUPERSEDED
        ]
        lowest = min(live_bids, key=lambda b: Decimal(b.total_amount), default=None)
        out.append(
            TenderListItem(
                id=t.id,
                project_id=t.project_id,
                title=t.title,
                status=t.status.value,  # type: ignore[arg-type]
                currency=t.currency,
                line_item_count=len(t.line_items),
                bid_count=len(active_bids),
                lowest_bid_amount=Decimal(lowest.total_amount) if lowest else None,
                lowest_bid_company=lowest.company_name if lowest else None,
                awarded_bid_id=t.awarded_bid_id,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return out


@router.post(
    "/projects/{project_id}/tenders",
    response_model=TenderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tender (optionally pre-filled with line items)",
)
async def create_tender(
    project_id: int,
    payload: TenderCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> TenderRead:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    tender = Tender(
        project_id=project_id,
        title=payload.title,
        object_name=payload.object_name,
        description=payload.description,
        currency=payload.currency or "RUB",
        payment_terms_expected=payload.payment_terms_expected,
        delivery_terms_expected=payload.delivery_terms_expected,
        notes=payload.notes,
        status=TenderStatus.DRAFT,
    )
    db.add(tender)
    await db.flush()

    # Two-pass insert so we can link parents <- children: pass 1 creates
    # every line and remembers (order_num -> id); pass 2 sets parent_id
    # on rows whose payload specified a parent_order_num.
    id_by_order: dict[int, int] = {}
    parent_pending: list[tuple[int, int]] = []  # (child_order, parent_order)
    for li in payload.line_items:
        row = TenderLineItem(
            tender_id=tender.id,
            order_num=li.order_num,
            description=li.description,
            unit=li.unit,
            quantity=Decimal(li.quantity or 0),
            notes=li.notes,
            display_label=li.display_label,
            line_type=LineType(li.line_type) if li.line_type else LineType.MISC,
        )
        db.add(row)
        await db.flush()  # so row.id is materialised
        id_by_order[li.order_num] = row.id
        if li.parent_order_num is not None:
            parent_pending.append((li.order_num, li.parent_order_num))
    for child_order, parent_order in parent_pending:
        parent_id = id_by_order.get(parent_order)
        child_id = id_by_order.get(child_order)
        if parent_id and child_id:
            row = await db.get(TenderLineItem, child_id)
            if row is not None:
                row.parent_id = parent_id
    await db.commit()
    await db.refresh(tender)
    # Re-load with relationships
    return await _load_tender_read(db, tender.id)


@router.get(
    "/tenders/{tender_id}",
    response_model=TenderRead,
    summary="Get a tender with line items + all bids (comparison grid data)",
)
async def get_tender(
    tender_id: int,
    user: CurrentUser,
    db: DBSession,
) -> TenderRead:
    return await _load_tender_read(db, tender_id)


@router.patch(
    "/tenders/{tender_id}",
    response_model=TenderRead,
    summary="Update tender meta or status",
)
async def update_tender(
    tender_id: int,
    payload: TenderUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> TenderRead:
    tender = await db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        try:
            tender.status = TenderStatus(data.pop("status"))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid status")
    for k, v in data.items():
        setattr(tender, k, v)
    await db.commit()
    return await _load_tender_read(db, tender_id)


@router.delete(
    "/tenders/{tender_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tender (cascades to line items and bids)",
)
async def delete_tender(
    tender_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> None:
    tender = await db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    await db.delete(tender)
    await db.commit()


# ---------------------------------------------------------------------------
# Tender line items
# ---------------------------------------------------------------------------


@router.post(
    "/tenders/{tender_id}/line-items",
    response_model=TenderLineItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Append a line item to a tender",
)
async def add_line_item(
    tender_id: int,
    payload: TenderLineItemCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> TenderLineItemRead:
    tender = await db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    parent_id: int | None = None
    if payload.parent_order_num is not None:
        parent = (
            await db.execute(
                select(TenderLineItem).where(
                    TenderLineItem.tender_id == tender_id,
                    TenderLineItem.order_num == payload.parent_order_num,
                )
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"parent_order_num {payload.parent_order_num} does not exist in this tender",
            )
        parent_id = parent.id
    li = TenderLineItem(
        tender_id=tender_id,
        order_num=payload.order_num,
        description=payload.description,
        unit=payload.unit,
        quantity=Decimal(payload.quantity or 0),
        notes=payload.notes,
        parent_id=parent_id,
        display_label=payload.display_label,
        line_type=LineType(payload.line_type) if payload.line_type else LineType.MISC,
    )
    db.add(li)
    await db.commit()
    await db.refresh(li)
    return TenderLineItemRead.model_validate(li)


@router.patch(
    "/tender-line-items/{line_id}",
    response_model=TenderLineItemRead,
    summary="Edit a tender line item (changes propagate to bid line totals)",
)
async def update_line_item(
    line_id: int,
    payload: TenderLineItemUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> TenderLineItemRead:
    li = await db.get(TenderLineItem, line_id)
    if li is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Line item not found")
    data = payload.model_dump(exclude_unset=True)
    # parent_order_num and line_type need translation before we set
    # them on the ORM row.
    if "parent_order_num" in data:
        parent_order = data.pop("parent_order_num")
        if parent_order is None:
            li.parent_id = None
        else:
            parent = (
                await db.execute(
                    select(TenderLineItem).where(
                        TenderLineItem.tender_id == li.tender_id,
                        TenderLineItem.order_num == parent_order,
                    )
                )
            ).scalar_one_or_none()
            if parent is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"parent_order_num {parent_order} does not exist in this tender",
                )
            li.parent_id = parent.id
    if "line_type" in data:
        lt = data.pop("line_type")
        li.line_type = LineType(lt) if lt else LineType.MISC
    for k, v in data.items():
        setattr(li, k, v)
    await db.flush()
    # If quantity changed, recompute bid line_totals for any bid touching this line
    if "quantity" in data:
        bids = (
            (
                await db.execute(
                    select(Bid)
                    .join(BidLineItem, BidLineItem.bid_id == Bid.id)
                    .where(BidLineItem.tender_line_item_id == line_id)
                    .options(
                        selectinload(Bid.line_items).selectinload(BidLineItem.tender_line_item)
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for b in bids:
            await _recompute_bid_totals(db, b)
    await db.commit()
    await db.refresh(li)
    return TenderLineItemRead.model_validate(li)


@router.delete(
    "/tender-line-items/{line_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Drop a tender line item (cascades to all bids' price rows)",
)
async def delete_line_item(
    line_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> None:
    li = await db.get(TenderLineItem, line_id)
    if li is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Line item not found")
    tender_id = li.tender_id
    await db.delete(li)
    await db.flush()
    # Recompute bids on this tender (we lost cells)
    bids = (
        (
            await db.execute(
                select(Bid)
                .where(Bid.tender_id == tender_id)
                .options(
                    selectinload(Bid.line_items).selectinload(BidLineItem.tender_line_item)
                )
            )
        )
        .scalars()
        .all()
    )
    for b in bids:
        await _recompute_bid_totals(db, b)
    await db.commit()


# ---------------------------------------------------------------------------
# Bids
# ---------------------------------------------------------------------------


@router.post(
    "/tenders/{tender_id}/bids",
    response_model=BidRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a bid for a tender",
)
async def create_bid(
    tender_id: int,
    payload: BidCreate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BidRead:
    tender = (
        await db.execute(
            select(Tender)
            .where(Tender.id == tender_id)
            .options(selectinload(Tender.line_items))
        )
    ).scalar_one_or_none()
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")

    if payload.subcontractor_id is not None:
        from app.models.subcontractor import Subcontractor

        if await db.get(Subcontractor, payload.subcontractor_id) is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "subcontractor_id does not exist"
            )

    # Revision detection: if a non-superseded bid already exists on this
    # tender for the same (company_name, variant_label) pair, treat the
    # incoming bid as a revision — point parent_bid_id at the latest
    # predecessor, bump revision_no, and flip prior live bids to
    # SUPERSEDED so the comparison grid only shows the newest.
    company = payload.company_name.strip()
    variant = (payload.variant_label or None)
    predecessors = (
        (
            await db.execute(
                select(Bid).where(
                    Bid.tender_id == tender_id,
                    Bid.company_name == company,
                    (Bid.variant_label.is_(None) if variant is None
                     else Bid.variant_label == variant),
                    Bid.status != BidStatus.SUPERSEDED,
                )
                .order_by(Bid.revision_no.desc(), Bid.id.desc())
            )
        )
        .scalars()
        .all()
    )
    parent_id: int | None = None
    next_revision = 1
    if predecessors:
        latest = predecessors[0]
        parent_id = latest.id
        next_revision = (latest.revision_no or 1) + 1
        for old in predecessors:
            old.status = BidStatus.SUPERSEDED
            # If a previous awarded bid is now superseded, also clear
            # the tender's awarded pointer so the user can re-pick the
            # winner from the new revision once it lands.
            if tender.awarded_bid_id == old.id:
                tender.awarded_bid_id = None
                if tender.status == TenderStatus.AWARDED:
                    tender.status = TenderStatus.OPEN

    bid = Bid(
        tender_id=tender_id,
        subcontractor_id=payload.subcontractor_id,
        company_name=company,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        included_in_price=payload.included_in_price,
        not_included_in_price=payload.not_included_in_price,
        payment_terms=payload.payment_terms,
        delivery_days=payload.delivery_days,
        notes=payload.notes,
        variant_label=variant,
        quote_date=payload.quote_date,
        vat_rate=Decimal(payload.vat_rate) if payload.vat_rate is not None else Decimal("20"),
        revision_no=next_revision,
        parent_bid_id=parent_id,
        status=BidStatus.RECEIVED if payload.line_items else BidStatus.INVITED,
        received_at=datetime.now(timezone.utc) if payload.line_items else None,
    )
    db.add(bid)
    await db.flush()

    await _apply_bid_lines(db, bid, payload.line_items, tender.line_items)

    if tender.status == TenderStatus.DRAFT:
        tender.status = TenderStatus.OPEN
    await db.commit()
    return await _load_bid_read(db, bid.id)


@router.patch(
    "/bids/{bid_id}",
    response_model=BidRead,
    summary="Update a bid (meta or replace line prices)",
)
async def update_bid(
    bid_id: int,
    payload: BidUpdate,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> BidRead:
    bid = (
        await db.execute(
            select(Bid)
            .where(Bid.id == bid_id)
            .options(
                selectinload(Bid.line_items).selectinload(BidLineItem.tender_line_item),
                selectinload(Bid.tender).selectinload(Tender.line_items),
            )
        )
    ).scalar_one_or_none()
    if bid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bid not found")

    data = payload.model_dump(exclude_unset=True)
    line_items_payload = data.pop("line_items", None)
    if "status" in data:
        try:
            bid.status = BidStatus(data.pop("status"))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid status")
    for k, v in data.items():
        setattr(bid, k, v)

    if line_items_payload is not None:
        # Wipe and re-create -- the simpler, predictable path. We use a
        # bulk DELETE statement instead of iterating bid.line_items to
        # avoid touching the relationship (which lazy-loads under
        # async).
        from sqlalchemy import delete as sa_delete

        await db.execute(
            sa_delete(BidLineItem).where(BidLineItem.bid_id == bid.id)
        )
        await db.flush()
        await _apply_bid_lines(
            db,
            bid,
            [BidLineItemUpsert(**li) for li in line_items_payload],
            bid.tender.line_items,
        )
        if bid.status == BidStatus.INVITED and line_items_payload:
            bid.status = BidStatus.RECEIVED
            bid.received_at = datetime.now(timezone.utc)

    await db.commit()
    return await _load_bid_read(db, bid_id)


@router.delete(
    "/bids/{bid_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Drop a bid (cascades to line prices)",
)
async def delete_bid(
    bid_id: int,
    db: DBSession,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> None:
    bid = await db.get(Bid, bid_id)
    if bid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bid not found")
    # If this was the awarded bid, clear the pointer first
    tender = await db.get(Tender, bid.tender_id)
    if tender is not None and tender.awarded_bid_id == bid.id:
        tender.awarded_bid_id = None
        tender.status = TenderStatus.OPEN
    await db.delete(bid)
    await db.commit()


@router.post(
    "/tenders/{tender_id}/award",
    response_model=TenderRead,
    summary="Mark a bid as the awarded one",
)
async def award_bid(
    tender_id: int,
    db: DBSession,
    bid_id: int = Query(..., description="bid_id to award"),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> TenderRead:
    tender = await db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    bid = await db.get(Bid, bid_id)
    if bid is None or bid.tender_id != tender_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bid does not belong to this tender")

    # Reset previously selected bids
    others = (
        (
            await db.execute(
                select(Bid).where(Bid.tender_id == tender_id, Bid.status == BidStatus.SELECTED)
            )
        )
        .scalars()
        .all()
    )
    for o in others:
        o.status = BidStatus.RECEIVED

    bid.status = BidStatus.SELECTED
    tender.awarded_bid_id = bid.id
    tender.status = TenderStatus.AWARDED
    await db.commit()
    return await _load_tender_read(db, tender_id)


# ---------------------------------------------------------------------------
# AI extraction (Excel/PDF upload -> structured draft)
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/tenders/extract",
    response_model=TenderExtraction,
    summary="Upload an Excel/PDF tender quotation file and return an editable draft",
)
async def extract_tender(
    project_id: int,
    db: DBSession,
    lang: UserLang,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> TenderExtraction:
    """Parse an arbitrary tender quotation file and return a draft.

    The draft is *not* persisted — the frontend lets the user edit it
    before posting back to ``POST /projects/{project_id}/tenders`` (with
    line_items + bids assembled from the draft).
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if file.filename is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    raw = await file.read()
    from app.services.tender_extraction import extract_tender_from_file

    draft = extract_tender_from_file(
        raw_bytes=raw,
        filename=file.filename,
        lang=lang,
    )
    return draft


@router.post(
    "/tenders/{tender_id}/bids/extract",
    response_model=ExtractedBid,
    summary="Upload one company's quote file and match it to this tender's line items",
)
async def extract_single_bid(
    tender_id: int,
    db: DBSession,
    lang: UserLang,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> ExtractedBid:
    """Parse a single bidder's quotation against an existing tender.

    The returned ``ExtractedBid`` carries the company info plus a list of
    line prices keyed by ``order_num`` — the frontend maps those to real
    line_item IDs at save time. Nothing is persisted; the user reviews
    and edits before submitting via ``POST /tenders/{tid}/bids``.
    """
    tender = (
        await db.execute(
            select(Tender)
            .where(Tender.id == tender_id)
            .options(selectinload(Tender.line_items))
        )
    ).scalar_one_or_none()
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    if file.filename is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    raw = await file.read()
    from app.services.tender_extraction import extract_bid_from_file

    return extract_bid_from_file(
        raw_bytes=raw,
        filename=file.filename,
        line_items=tender.line_items,
        lang=lang,
    )


# ---------------------------------------------------------------------------
# AI Analysis (6-section recommendation)
# ---------------------------------------------------------------------------


@router.get(
    "/tenders/{tender_id}/ai-analysis",
    response_model=TenderAIAnalysis,
    summary="Six-section AI analysis comparing all bids on a tender",
)
async def get_tender_ai_analysis(
    tender_id: int,
    user: CurrentUser,
    db: DBSession,
    lang: UserLang,
    force_refresh: bool = Query(False),
) -> TenderAIAnalysis:
    from app.services import insights_cache
    from app.services.tender_ai_analysis import build_tender_ai_analysis

    cache_key = (tender_id + 4_000_000) * 10 + (1 if lang == "TR" else 0)
    if not force_refresh:
        cached = insights_cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

    result = await build_tender_ai_analysis(db, tender_id, lang=lang)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    insights_cache.set(cache_key, result)  # type: ignore[arg-type]
    return result


# ---------------------------------------------------------------------------
# Market price help-box (Seviye 1 — Claude'un training data'sından)
# ---------------------------------------------------------------------------


@router.get(
    "/tenders/{tender_id}/market-prices",
    response_model=TenderMarketPrices,
    summary="Per-line market price band (Seviye 1: Claude training knowledge)",
)
async def get_tender_market_prices(
    tender_id: int,
    user: CurrentUser,
    db: DBSession,
    lang: UserLang,
    force_refresh: bool = Query(False),
) -> TenderMarketPrices:
    """Look up a rough market band for each tender line item.

    Seviye 1 = no live web search, just what Claude already knows. The
    response is cached so reopening the comparison grid doesn't burn
    tokens. Set ``force_refresh=true`` to bypass the cache.
    """
    from app.services import insights_cache
    from app.services.tender_market_prices import build_tender_market_prices

    cache_key = (tender_id + 9_000_000) * 10 + (1 if lang == "TR" else 0)
    if not force_refresh:
        cached = insights_cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

    result = await build_tender_market_prices(db, tender_id, lang=lang)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    insights_cache.set(cache_key, result)  # type: ignore[arg-type]
    return result


# ---------------------------------------------------------------------------
# TDF Excel export (КП Форма)
# ---------------------------------------------------------------------------


@router.get(
    "/tenders/{tender_id}/export-tdf",
    summary="Download tender as TDF (КП Форма) Excel file",
    response_class=StreamingResponse,
)
async def export_tender_tdf(
    tender_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Generate the standardized TDF (Teklif Değerlendirme Formu / КП Форма)
    Excel workbook for this tender. Columns include each non-superseded
    bidder (each variant as its own pair of columns), all line items, totals,
    contact info, included/not-included clauses, payment terms.
    """
    from io import BytesIO
    from app.services.tender_export import build_tdf_workbook

    tender = (
        await db.execute(
            select(Tender)
            .where(Tender.id == tender_id)
            .options(
                selectinload(Tender.line_items),
                selectinload(Tender.bids).selectinload(Bid.line_items),
            )
        )
    ).scalar_one_or_none()
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")

    data = build_tdf_workbook(tender)
    # ASCII-safe filename for Content-Disposition; rich UTF-8 filename
    # goes into filename* per RFC 5987 so Cyrillic stays intact for
    # browsers that respect it.
    import urllib.parse
    safe = f"tender-{tender_id}-tdf.xlsx"
    rich = urllib.parse.quote(f"{tender.title or 'tender'}-tdf.xlsx")
    headers = {
        "Content-Disposition": (
            f'attachment; filename="{safe}"; '
            f"filename*=UTF-8''{rich}"
        )
    }
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Internal: shared loaders
# ---------------------------------------------------------------------------


async def _load_tender_read(db, tender_id: int) -> TenderRead:
    tender = (
        await db.execute(
            select(Tender)
            .where(Tender.id == tender_id)
            .options(
                selectinload(Tender.line_items),
                selectinload(Tender.bids).selectinload(Bid.line_items),
            )
        )
    ).scalar_one_or_none()
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tender not found")
    return TenderRead.model_validate(tender)


async def _load_bid_read(db, bid_id: int) -> BidRead:
    bid = (
        await db.execute(
            select(Bid)
            .where(Bid.id == bid_id)
            .options(selectinload(Bid.line_items))
        )
    ).scalar_one_or_none()
    if bid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bid not found")
    return BidRead.model_validate(bid)


async def _apply_bid_lines(
    db,
    bid: Bid,
    lines: list[BidLineItemUpsert],
    tender_line_items: list[TenderLineItem],
) -> None:
    """Insert new bid_line_items rows for the given upsert payload.

    Avoids touching ``bid.line_items`` (the ORM relationship) on the
    write path because async sessions can't lazy-load it. Each row is
    added directly to the session via the FK column; the comparison
    grid eager-loads when it actually needs the list.
    """
    line_by_id = {li.id: li for li in tender_line_items}
    qty_by_id = {li.id: Decimal(li.quantity or 0) for li in tender_line_items}
    for upsert in lines:
        if upsert.tender_line_item_id not in line_by_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"tender_line_item_id {upsert.tender_line_item_id} does not belong to this tender",
            )
        try:
            pt = BidPriceType(upsert.price_type)
        except ValueError:
            pt = BidPriceType.FIXED
        # For non-fixed prices (Договорная etc.) we don't carry numeric
        # unit prices — null out the columns and let the raw_text_price
        # speak for itself in the UI.
        if pt != BidPriceType.FIXED:
            lab, mat, tot = None, None, Decimal(0)
        else:
            lab, mat, tot = _normalize_split(
                upsert.unit_price_labor,
                upsert.unit_price_material,
                upsert.unit_price_total,
            )
        bl = BidLineItem(
            bid_id=bid.id,
            tender_line_item_id=upsert.tender_line_item_id,
            unit_price_labor=lab,
            unit_price_material=mat,
            unit_price_total=tot,
            price_type=pt,
            raw_text_price=(upsert.raw_text_price or None),
            notes=upsert.notes,
        )
        db.add(bl)
    await db.flush()
    await _recompute_bid_totals(db, bid, qty_by_id)
