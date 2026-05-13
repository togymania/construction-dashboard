"""Tender → TDF Excel (КП Форма) export.

Şirketin resmî 'Форма КП' şablonunu (`templates/tdf_template.xlsx`)
açar, bilinen hücrelere ihale verilerini yazar ve sonucu byte stream
olarak döner. Şablonun görselini (logo, kenarlık, renkler, sütun
genişlikleri, format) değiştirmiyoruz — sadece hücre değerlerini.

Şablon layout (analyze_tdf.py çıktısından):

    Row 7   : Тема (A7 label) | tender adı (B7:G7 merged)
              + bidder 1 toplam (I7:J7 merged)
              + bidder 2 toplam (L7:M7 merged)
    Row 8   : Sütun başlıkları (şablonda hazır)
    Row 9-15: Line items
              A: №           B: Наименование
              C: Изображение  D: План
              E: Тип пирога   F: Ед. изм.
              G: Кол-во
              I/J: Bidder 1 (cena / стоимость)
              L/M: Bidder 2 (cena / стоимость)
    Row 5   : Bidder isimleri (I5:J5, L5:M5 merged)
    Row 18  : Контактное лицо (I18:M18 merged) — her bidder ortak
    Row 22  : В стоимость входит (I22:M22)
    Row 23  : В стоимость НЕ входит (I23:M23)
    Row 27  : Условия оплаты (I27:M27)
    Row 28  : Сроки выполнения работ (I28:M28)
    Row 29  : Объект (I29:M29)

Sınırlamalar (şablon ile aynı):
    - Maks 2 bidder yan yana (variant'lar dahil; 3+ → ilk 2 alınır)
    - Maks 7 line item (8+ → ilk 7 alınır + uyarı)

Daha fazlası için şablonu Excel'de bir kez genişletmek lazım.
"""
from __future__ import annotations

import shutil
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Sequence

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.models.tender import (
    Bid,
    BidLineItem,
    BidPriceType,
    BidStatus,
    Tender,
    TenderLineItem,
)


TEMPLATE_PATH = Path(__file__).parent / "templates" / "tdf_template.xlsx"

# Bidder kolon haritası — şablona göre
BIDDER_SLOTS = [
    {  # Bidder 1
        "name_cell": "I5",
        "total_cell": "I7",
        "unit_col": 9,    # I
        "total_col": 10,  # J
        "contact_cell": "I18",
        "comments_cell": "I21",
        "included_cell": "I22",
        "not_included_cell": "I23",
        "payment_cell": "I27",
        "delivery_cell": "I28",
        "object_cell": "I29",
    },
    {  # Bidder 2
        "name_cell": "L5",
        "total_cell": "L7",
        "unit_col": 12,  # L
        "total_col": 13,  # M
        "contact_cell": "L18",
        "comments_cell": "L21",
        "included_cell": "L22",
        "not_included_cell": "L23",
        "payment_cell": "L27",
        "delivery_cell": "L28",
        "object_cell": "L29",
    },
]
MAX_BIDDERS = len(BIDDER_SLOTS)
MAX_LINE_ITEMS = 7
LINE_ITEM_START_ROW = 9


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_tdf_workbook(tender: Tender) -> bytes:
    """Tender'ı TDF formatlı .xlsx olarak üret, byte stream döndür."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"TDF şablonu bulunamadı: {TEMPLATE_PATH}. "
            "backend/app/services/templates/tdf_template.xlsx'i kopyalayın."
        )

    # Şablonu in-memory olarak yükle (orijinal dosyayı değiştirmemek için)
    wb = load_workbook(TEMPLATE_PATH)

    # SUPERSEDED bid'leri dahil etme; max 2 alınır
    bidders: list[Bid] = sorted(
        [b for b in tender.bids if b.status != BidStatus.SUPERSEDED],
        key=lambda b: (b.company_name, b.variant_label or ""),
    )
    line_items: list[TenderLineItem] = sorted(
        tender.line_items, key=lambda li: li.order_num
    )

    # Tek sheet bırak (ilki) — diğerlerini sil
    sheet_names = wb.sheetnames
    primary_name = sheet_names[0] if sheet_names else "КП Форма"
    for name in sheet_names[1:]:
        del wb[name]

    ws: Worksheet = wb[primary_name]

    # Sheet adını tender başlığına çevir (max 31 karakter, geçersiz karakterleri at)
    safe_title = (tender.title or "КП Форма")[:31]
    for bad in "[]:*?/\\":
        safe_title = safe_title.replace(bad, " ")
    ws.title = safe_title or "КП Форма"

    # Şablonda footer satırları (R18, R21, R22, R23, R27, R28, R29) her biri
    # tek bir merged blok (I18:M18) olarak gelir — yani sadece 1 bidder için
    # alan ayrılmış. Bunları parçalayıp her bidder için ayrı slot açıyoruz:
    #     I-J → Bidder 1
    #     L-M → Bidder 2
    _split_footer_merges(ws, rows=[18, 21, 22, 23, 27, 28, 29])

    # Header
    ws["B7"] = tender.title or ""

    # Bidder isimleri + toplamlar
    for idx, b in enumerate(bidders[:MAX_BIDDERS]):
        slot = BIDDER_SLOTS[idx]
        label = b.company_name
        if b.variant_label:
            label += f"\n{b.variant_label}"
        ws[slot["name_cell"]] = label
        total = Decimal(b.total_amount or 0)
        ws[slot["total_cell"]] = float(total) if total > 0 else 0

    # Line items
    for idx, li in enumerate(line_items[:MAX_LINE_ITEMS]):
        r = LINE_ITEM_START_ROW + idx
        # Şablondaki order_num üzerine yazma — kendi mevcut
        # değerleri (1..7) ile aynı kalsın. Sadece description vs.
        # üzerine yazıyoruz.
        ws.cell(row=r, column=1, value=li.display_label or li.order_num)
        ws.cell(row=r, column=2, value=li.description or "")
        ws.cell(row=r, column=5, value=_line_type_label(li))
        ws.cell(row=r, column=6, value=li.unit or "")
        ws.cell(row=r, column=7, value=float(li.quantity or 0) if li.quantity else 0)

        qty = Decimal(li.quantity or 0)
        for b_idx, b in enumerate(bidders[:MAX_BIDDERS]):
            slot = BIDDER_SLOTS[b_idx]
            cell_data = _find_bid_line(b, li.id)
            if cell_data is None:
                ws.cell(row=r, column=slot["unit_col"], value=None)
                ws.cell(row=r, column=slot["total_col"], value=None)
                continue
            if cell_data.price_type != BidPriceType.FIXED:
                # "Договорная" / "не включена"
                text = cell_data.raw_text_price or cell_data.price_type.value
                ws.cell(row=r, column=slot["unit_col"], value=text)
                ws.cell(row=r, column=slot["total_col"], value=text)
                continue
            unit_price = Decimal(cell_data.unit_price_total or 0)
            ws.cell(
                row=r, column=slot["unit_col"],
                value=float(unit_price) if unit_price > 0 else 0,
            )
            ws.cell(
                row=r, column=slot["total_col"],
                value=float(qty * unit_price) if (qty and unit_price) else 0,
            )

    # Boş kalan line item satırlarını temizle (şablon 7 satır içeriyor; eğer
    # bizim line item'larımız 4 ise kalan 3 satırı silmek lazım — yoksa
    # şablonda preset değerler kalır). Ama description'ları silersek
    # row'lar boş gözükür, görsel olarak temiz.
    for idx in range(len(line_items), MAX_LINE_ITEMS):
        r = LINE_ITEM_START_ROW + idx
        ws.cell(row=r, column=2, value="")
        ws.cell(row=r, column=5, value="")
        ws.cell(row=r, column=6, value="")
        ws.cell(row=r, column=7, value=None)
        for b_idx in range(MAX_BIDDERS):
            slot = BIDDER_SLOTS[b_idx]
            ws.cell(row=r, column=slot["unit_col"], value=None)
            ws.cell(row=r, column=slot["total_col"], value=None)

    # Footer alanları — her bidder için
    for idx, b in enumerate(bidders[:MAX_BIDDERS]):
        slot = BIDDER_SLOTS[idx]
        ws[slot["contact_cell"]] = _contact_block(b)
        ws[slot["comments_cell"]] = b.notes or ""
        ws[slot["included_cell"]] = b.included_in_price or ""
        ws[slot["not_included_cell"]] = b.not_included_in_price or ""
        ws[slot["payment_cell"]] = b.payment_terms or ""
        ws[slot["delivery_cell"]] = (
            f"{b.delivery_days} дней" if b.delivery_days else ""
        )
        ws[slot["object_cell"]] = tender.object_name or ""

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_footer_merges(ws: Worksheet, rows: list[int]) -> None:
    """Şablondaki I:M merged footer bloklarını I:J ve L:M olarak ikiye böl.

    Şablon sadece 1 bidder için footer alanı bırakmış; biz 2 bidder için
    iki ayrı slot lazım. Merged range'leri unmerge edip yeni iki merged
    blok oluşturuyoruz. K sütunu (separator) merged dışında kalır.
    """
    for row in rows:
        # Aynı satırı kaplayan tüm merged range'leri bul (ranges set'i
        # üzerinde iterate ederken modifiye etmemek için kopyala).
        to_unmerge: list[str] = []
        for mr in list(ws.merged_cells.ranges):
            if mr.min_row == row and mr.max_row == row:
                # I:M aralığını içeren herhangi bir merge
                if mr.min_col <= 9 and mr.max_col >= 13:
                    to_unmerge.append(str(mr))
        for ref in to_unmerge:
            try:
                ws.unmerge_cells(ref)
            except Exception:
                pass
        # Yeni iki slot
        try:
            ws.merge_cells(start_row=row, start_column=9, end_row=row, end_column=10)
        except Exception:
            pass
        try:
            ws.merge_cells(start_row=row, start_column=12, end_row=row, end_column=13)
        except Exception:
            pass


def _find_bid_line(bid: Bid, line_id: int) -> BidLineItem | None:
    for bl in bid.line_items:
        if bl.tender_line_item_id == line_id:
            return bl
    return None


def _line_type_label(li: TenderLineItem) -> str:
    if li.line_type == "work":
        return "Работы"
    if li.line_type == "material":
        return "Материал"
    return ""


def _contact_block(bid: Bid) -> str:
    parts = []
    if bid.contact_name:
        parts.append(bid.contact_name)
    if bid.contact_phone:
        parts.append(bid.contact_phone)
    if bid.contact_email:
        parts.append(bid.contact_email)
    return ", ".join(parts)
