"""Tender → TDF Excel (КП Форма) export.

Şirket içinde standart olan "КП Форма (2)" şablonunu birebir üretir.
Yapı, ``samples/tenders/50. Lastik Kaplama/20260429_TDF_IP__r00.xlsx``
dosyasındaki orijinal şablondan kopyalanmıştır:

    Row 7 : Тема: <tender title>
    Row 8 : Sütun başlıkları (#, Наименование, Ед. изм., Кол-во,
            ardından her bidder için "Цена мат. за ед.,  руб. с НДС" +
            "Общая стоимость, руб. с НДС")
    Row 9+: Line items
    Row 23: Контактное лицо, ФИО, телефон, e-mail
    Row 26: Комментарии (her bidder için)
    Row 27: В стоимость входит:
    Row 28: В стоимость НЕ входит:
    Row 32: Условия оплаты:
    Row 33: Сроки выполнения работ:
    Row 34: Объект:

Bidder'lar (variant'lar dahil; eski revisionlar dahil edilmez) yan
yana iki sütun olarak sıralanır. Her bidder iki sütun kaplar: birim
fiyat + toplam.
"""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models.tender import (
    Bid,
    BidLineItem,
    BidPriceType,
    BidStatus,
    Tender,
    TenderLineItem,
)


# ---------------------------------------------------------------------------
# Stilleri tek bir yerde tutalım — şablonu yeniden marka ile düzenlemek
# istersek tek kaynaktan değiştiririz.
# ---------------------------------------------------------------------------

THIN_BORDER = Border(
    left=Side(style="thin", color="999999"),
    right=Side(style="thin", color="999999"),
    top=Side(style="thin", color="999999"),
    bottom=Side(style="thin", color="999999"),
)
MEDIUM_BORDER = Border(
    left=Side(style="medium", color="143C73"),
    right=Side(style="medium", color="143C73"),
    top=Side(style="medium", color="143C73"),
    bottom=Side(style="medium", color="143C73"),
)

FILL_HEADER = PatternFill("solid", fgColor="143C73")      # koyu lacivert
FILL_SUBHEADER = PatternFill("solid", fgColor="1FA3DA")   # açık mavi
FILL_LABEL = PatternFill("solid", fgColor="E8F1FB")       # buz mavisi
FILL_ALT = PatternFill("solid", fgColor="F7FAFD")         # alternating row

FONT_HEADER = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
FONT_SUBHEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FONT_LABEL = Font(name="Calibri", size=11, bold=True, color="143C73")
FONT_BODY = Font(name="Calibri", size=11, color="1E293B")
FONT_BIDDER = Font(name="Calibri", size=11, bold=True, color="143C73")

ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_tdf_workbook(tender: Tender) -> bytes:
    """Tender'ı TDF formatlı bir .xlsx olarak üret, byte stream döndür.

    `tender` mutlaka şu yolla yüklenmiş olmalı:
        selectinload(Tender.line_items)
        selectinload(Tender.bids).selectinload(Bid.line_items)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "КП Форма"

    # SUPERSEDED bid'leri dahil etme — sadece aktif teklifler.
    bidders: list[Bid] = sorted(
        [b for b in tender.bids if b.status != BidStatus.SUPERSEDED],
        key=lambda b: (b.company_name, b.variant_label or ""),
    )

    line_items: list[TenderLineItem] = sorted(
        tender.line_items, key=lambda li: li.order_num
    )

    _write_header(ws, tender)
    _write_table(ws, tender, line_items, bidders)
    _write_footer(ws, tender, bidders)
    _set_column_widths(ws, bidders)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Section: header (rows 1-7)
# ---------------------------------------------------------------------------


def _write_header(ws, tender: Tender) -> None:
    # Row 1: kurumsal başlık (Monotekstroy — tdf banner)
    ws.cell(row=1, column=1, value="MONOTEKSTROY · КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ").font = Font(
        name="Calibri", size=14, bold=True, color="143C73"
    )
    ws.row_dimensions[1].height = 24
    ws.cell(row=1, column=1).alignment = ALIGN_LEFT

    # Row 3 - 4: kim için / kimden / tarih (manuel doldurulabilir)
    ws.cell(row=3, column=1, value="Кому:").font = FONT_LABEL
    ws.cell(row=3, column=2, value="").alignment = ALIGN_LEFT
    ws.cell(row=4, column=1, value="От кого:").font = FONT_LABEL
    ws.cell(row=4, column=2, value="").alignment = ALIGN_LEFT
    ws.cell(row=5, column=1, value="Дата:").font = FONT_LABEL
    ws.cell(row=5, column=2, value=tender.created_at.strftime("%d.%m.%Y")).alignment = ALIGN_LEFT

    # Row 7: Тема
    ws.cell(row=7, column=1, value="Тема:").font = FONT_LABEL
    cell = ws.cell(row=7, column=2, value=tender.title)
    cell.font = Font(name="Calibri", size=12, bold=True, color="143C73")
    cell.alignment = ALIGN_LEFT
    ws.row_dimensions[7].height = 22


# ---------------------------------------------------------------------------
# Section: ana tablo (row 8 header + N satır body)
# ---------------------------------------------------------------------------


# Sabit sol sütunlar
FIXED_COLS = [
    ("№", 5),
    ("Наименование", 38),
    ("Ед. изм.", 10),
    ("Кол-во", 10),
]
PER_BIDDER_COLS = [
    ("Цена мат.\nза ед.,\nруб. с НДС", 14),
    ("Общая\nстоимость,\nруб. с НДС", 16),
]


def _write_table(
    ws,
    tender: Tender,
    line_items: Sequence[TenderLineItem],
    bidders: Sequence[Bid],
) -> None:
    header_row = 8

    # Üst bantta bidder adları — her bidder iki sütun (birim + toplam) kaplar.
    bidder_band_row = 8
    body_header_row = 9

    # 1) Sabit sütun başlıkları (Row 8-9 birleştirilmiş)
    for ci, (label, _w) in enumerate(FIXED_COLS, start=1):
        for r in (bidder_band_row, body_header_row):
            c = ws.cell(row=r, column=ci, value=label if r == bidder_band_row else "")
            c.fill = FILL_HEADER
            c.font = FONT_HEADER
            c.alignment = ALIGN_CENTER
            c.border = THIN_BORDER
        ws.merge_cells(
            start_row=bidder_band_row, start_column=ci,
            end_row=body_header_row, end_column=ci,
        )

    # 2) Her bidder için iki sütun
    col_cursor = len(FIXED_COLS) + 1
    for b in bidders:
        bidder_label = b.company_name + (f" · {b.variant_label}" if b.variant_label else "")
        # Üst bant: bidder adı (iki sütun merged)
        top = ws.cell(row=bidder_band_row, column=col_cursor, value=bidder_label)
        top.fill = FILL_SUBHEADER
        top.font = FONT_SUBHEADER
        top.alignment = ALIGN_CENTER
        top.border = THIN_BORDER
        ws.merge_cells(
            start_row=bidder_band_row, start_column=col_cursor,
            end_row=bidder_band_row, end_column=col_cursor + 1,
        )
        # 2. satırda sütun başlıkları
        for k, (sub_label, _w) in enumerate(PER_BIDDER_COLS):
            c = ws.cell(row=body_header_row, column=col_cursor + k, value=sub_label)
            c.fill = FILL_SUBHEADER
            c.font = FONT_SUBHEADER
            c.alignment = ALIGN_CENTER
            c.border = THIN_BORDER
        col_cursor += 2

    # 3) Line items (Row 10..)
    body_row = body_header_row + 1
    for idx, li in enumerate(line_items):
        r = body_row + idx
        zebra = FILL_ALT if idx % 2 == 1 else None

        # # / Описание / Ед. / Кол-во
        cells = [
            (1, li.display_label or li.order_num),
            (2, li.description),
            (3, li.unit or ""),
            (4, float(li.quantity or 0)),
        ]
        for ci, val in cells:
            c = ws.cell(row=r, column=ci, value=val)
            c.font = FONT_BODY
            c.border = THIN_BORDER
            c.alignment = ALIGN_LEFT if ci == 2 else ALIGN_CENTER
            if zebra:
                c.fill = zebra
        # Paket satırları daha kalın
        if li.line_type == "package":
            for ci in range(1, 5):
                ws.cell(row=r, column=ci).font = Font(
                    name="Calibri", size=11, bold=True, color="143C73"
                )

        # Her bidder için fiyat hücreleri
        col_cursor = len(FIXED_COLS) + 1
        for b in bidders:
            cell_data = _find_bid_line(b, li.id)
            qty = Decimal(li.quantity or 0)
            if cell_data is None:
                _put_currency(ws, r, col_cursor, None, zebra)
                _put_currency(ws, r, col_cursor + 1, None, zebra)
            elif cell_data.price_type != BidPriceType.FIXED:
                # Договорная / не включена → birim hücresine kelime,
                # toplam hücresine de aynısı.
                txt = cell_data.raw_text_price or cell_data.price_type.value
                _put_text(ws, r, col_cursor, txt, zebra, italic=True)
                _put_text(ws, r, col_cursor + 1, txt, zebra, italic=True)
            else:
                unit = Decimal(cell_data.unit_price_total or 0)
                total = qty * unit
                _put_currency(ws, r, col_cursor, unit, zebra)
                _put_currency(ws, r, col_cursor + 1, total, zebra)
            col_cursor += 2

    # 4) TOPLAM satırı
    total_row = body_row + len(line_items)
    ws.cell(row=total_row, column=1, value="").border = THIN_BORDER
    label = ws.cell(row=total_row, column=2, value="ИТОГО с НДС")
    label.font = Font(name="Calibri", size=12, bold=True, color="143C73")
    label.fill = FILL_LABEL
    label.alignment = ALIGN_RIGHT
    label.border = THIN_BORDER
    for ci in (1, 3, 4):
        ws.cell(row=total_row, column=ci).fill = FILL_LABEL
        ws.cell(row=total_row, column=ci).border = THIN_BORDER

    col_cursor = len(FIXED_COLS) + 1
    for b in bidders:
        _put_currency(ws, total_row, col_cursor, None, FILL_LABEL)  # birim sütun boş
        c = _put_currency(ws, total_row, col_cursor + 1, Decimal(b.total_amount or 0), FILL_LABEL)
        c.font = Font(name="Calibri", size=12, bold=True, color="143C73")
        col_cursor += 2

    # 5) KDV hariç satırı
    net_row = total_row + 1
    ws.cell(row=net_row, column=2, value="без НДС").font = Font(
        name="Calibri", size=10, italic=True, color="64748B"
    )
    ws.cell(row=net_row, column=2).alignment = ALIGN_RIGHT
    col_cursor = len(FIXED_COLS) + 1
    for b in bidders:
        _put_currency(ws, net_row, col_cursor + 1, Decimal(b.total_without_vat or 0), None,
                      italic=True, muted=True)
        col_cursor += 2


def _find_bid_line(bid: Bid, line_id: int) -> BidLineItem | None:
    for bl in bid.line_items:
        if bl.tender_line_item_id == line_id:
            return bl
    return None


def _put_currency(ws, r, c, value, fill, *, italic=False, muted=False):
    cell = ws.cell(row=r, column=c, value=float(value) if value is not None else None)
    cell.number_format = '#,##0.00 " ₽";-#,##0.00 " ₽";""'
    cell.font = Font(
        name="Calibri", size=11,
        color="94A3B8" if muted else "1E293B",
        italic=italic,
    )
    cell.alignment = ALIGN_RIGHT
    cell.border = THIN_BORDER
    if fill is not None:
        cell.fill = fill
    return cell


def _put_text(ws, r, c, text, fill, *, italic=False):
    cell = ws.cell(row=r, column=c, value=text)
    cell.font = Font(name="Calibri", size=10, italic=italic, color="C2410C")
    cell.alignment = ALIGN_CENTER
    cell.border = THIN_BORDER
    if fill is not None:
        cell.fill = fill
    return cell


# ---------------------------------------------------------------------------
# Section: footer (contact / commentary / payment / delivery / object)
# ---------------------------------------------------------------------------


def _write_footer(ws, tender: Tender, bidders: Sequence[Bid]) -> None:
    # Tablo bittikten sonra başla — body line item sayısına göre dinamik.
    base = 10 + max(len(tender.line_items), 12) + 4  # toplam satır + 2 spacer

    rows = [
        ("Контактное лицо, ФИО, телефон, e-mail:",
         lambda b: _contact_block(b)),
        ("Комментарии:", lambda b: b.notes or ""),
        ("В стоимость входит:", lambda b: b.included_in_price or ""),
        ("В стоимость НЕ входит:", lambda b: b.not_included_in_price or ""),
        ("Условия оплаты:", lambda b: b.payment_terms or ""),
        ("Сроки выполнения работ:",
         lambda b: (f"{b.delivery_days} дней" if b.delivery_days else "")),
    ]
    for offset, (label, getter) in enumerate(rows):
        r = base + offset * 2
        lc = ws.cell(row=r, column=1, value=label)
        lc.font = FONT_LABEL
        lc.alignment = ALIGN_LEFT
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)

        col_cursor = len(FIXED_COLS) + 1
        for b in bidders:
            value = getter(b)
            c = ws.cell(row=r, column=col_cursor, value=value)
            c.font = FONT_BODY
            c.alignment = ALIGN_LEFT
            c.border = THIN_BORDER
            ws.merge_cells(
                start_row=r, start_column=col_cursor,
                end_row=r, end_column=col_cursor + 1,
            )
            ws.row_dimensions[r].height = 40
            col_cursor += 2

    # Objet satırı (tender meta)
    obj_row = base + len(rows) * 2 + 1
    ws.cell(row=obj_row, column=1, value="Объект:").font = FONT_LABEL
    obj_cell = ws.cell(row=obj_row, column=2, value=tender.object_name or "")
    obj_cell.font = FONT_BODY
    obj_cell.alignment = ALIGN_LEFT
    ws.merge_cells(start_row=obj_row, start_column=2, end_row=obj_row, end_column=4)


def _contact_block(bid: Bid) -> str:
    parts = []
    if bid.contact_name:
        parts.append(bid.contact_name)
    if bid.contact_phone:
        parts.append(bid.contact_phone)
    if bid.contact_email:
        parts.append(bid.contact_email)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Sütun genişlikleri
# ---------------------------------------------------------------------------


def _set_column_widths(ws, bidders: Sequence[Bid]) -> None:
    for ci, (_label, width) in enumerate(FIXED_COLS, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = width
    col_cursor = len(FIXED_COLS) + 1
    for _ in bidders:
        for k, (_label, width) in enumerate(PER_BIDDER_COLS):
            ws.column_dimensions[get_column_letter(col_cursor + k)].width = width
        col_cursor += 2
