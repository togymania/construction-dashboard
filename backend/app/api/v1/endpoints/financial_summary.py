"""Financial Summary (OZET) endpoints — list + upload.

URL layout::

    GET  /projects/{project_id}/financial-summary
        → her şirket için 1 row, max 2 row (Monotek + Monart)

    POST /projects/{project_id}/financial-summary/upload
        Form-data: file (.xlsx), optional company_label override
        → dosyanın OZET sayfasını parse eder, upsert eder, döner

Yetkilendirme: list herkese açık (authenticated), upload sadece ADMIN
veya PROJECT_MANAGER. Aynı (proje, şirket) için upload yapıldığında
mevcut kayıt üzerine yazılır.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, require_roles
from app.models.financial_summary import FinancialSummary
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.financial_summary import FinancialSummaryRead

router = APIRouter(tags=["Financial Summary"])


@router.get(
    "/projects/{project_id}/financial-summary",
    response_model=list[FinancialSummaryRead],
    summary="List financial OZET summaries for the project (max 2 — Monotek + Monart)",
)
async def list_financial_summaries(
    project_id: int,
    user: CurrentUser,
    db: DBSession,
) -> list[FinancialSummaryRead]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    rows = (
        await db.execute(
            select(FinancialSummary)
            .where(FinancialSummary.project_id == project_id)
            .order_by(FinancialSummary.company_label.asc())
        )
    ).scalars().all()
    return [FinancialSummaryRead.model_validate(r) for r in rows]


@router.post(
    "/projects/{project_id}/financial-summary/upload",
    response_model=FinancialSummaryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a 'Harcama Takip' Excel and persist the OZET sheet",
)
async def upload_financial_summary(
    project_id: int,
    db: DBSession,
    file: UploadFile = File(...),
    company_label: str | None = Form(default=None),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROJECT_MANAGER)),
) -> FinancialSummaryRead:
    from app.services.financial_summary_parser import (
        OzetParseError,
        detect_company_label,
        parse_ozet,
    )

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing filename")

    raw = await file.read()
    try:
        data = parse_ozet(raw)
    except OzetParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # Company label — kullanıcı override etmediyse dosya adından çıkar
    label = (company_label or detect_company_label(file.filename) or "Unknown").strip()
    if label == "Unknown":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Dosya adından şirket etiketi tespit edilemedi. "
            "company_label=Monotek veya company_label=Monart geçin.",
        )

    # Upsert
    existing = (
        await db.execute(
            select(FinancialSummary).where(
                FinancialSummary.project_id == project_id,
                FinancialSummary.company_label == label,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        row = FinancialSummary(
            project_id=project_id,
            company_label=label,
            as_of_date=data["as_of_date"],
            isveren_tahsilatlari=data["isveren_tahsilatlari"],
            firma_odemeleri=data["firma_odemeleri"],
            ucret_giderleri=data["ucret_giderleri"],
            vergi_odemeleri=data["vergi_odemeleri"],
            gelir_vergisi=data["gelir_vergisi"],
            kdv=data["kdv"],
            faiz_gelirleri=data["faiz_gelirleri"],
            banka_giderleri=data["banka_giderleri"],
            diger_gelir_giderler=data["diger_gelir_giderler"],
            toplam=data["toplam"],
            source_filename=file.filename,
            uploaded_by=user.id,
        )
        db.add(row)
    else:
        row = existing
        row.as_of_date = data["as_of_date"]
        row.isveren_tahsilatlari = data["isveren_tahsilatlari"]
        row.firma_odemeleri = data["firma_odemeleri"]
        row.ucret_giderleri = data["ucret_giderleri"]
        row.vergi_odemeleri = data["vergi_odemeleri"]
        row.gelir_vergisi = data["gelir_vergisi"]
        row.kdv = data["kdv"]
        row.faiz_gelirleri = data["faiz_gelirleri"]
        row.banka_giderleri = data["banka_giderleri"]
        row.diger_gelir_giderler = data["diger_gelir_giderler"]
        row.toplam = data["toplam"]
        row.source_filename = file.filename
        row.uploaded_by = user.id

    await db.commit()
    await db.refresh(row)
    return FinancialSummaryRead.model_validate(row)
