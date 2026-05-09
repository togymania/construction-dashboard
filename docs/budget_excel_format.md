# Budget Excel Format

ConstructHub's budget import accepts a generic, header-driven `.xlsx` file.
The first row must be a header; data rows follow. Header matching is
**case-insensitive** and supports aliases in English, Turkish and Russian
(see the alias table below).

## Required columns

| Field | Aliases (any of) |
|---|---|
| **Description** | item, item name, description, desc, kalem, kalem adı, açıklama, наименование, описание |
| **Category** | category, kategori, категория, budget category, bütçe kategorisi |
| **Amount** *(planned)* | amount, budget, total, planned, planned amount, tutar, bütçe, miktar, planlanan, сумма, бюджет, плановая |

If any of these is missing the import is rejected with a 400. If a category
doesn't exist yet, it is **auto-created** and a single warning is raised.

## Optional columns

| Field | Aliases (any of) |
|---|---|
| **Cost code** *(WBS)* | code, cost code, wbs, wbs code, item code, kod, kalem kodu, iş kalemi kodu, код, шифр |
| **Committed amount** | committed, committed amount, commitment, po, po amount, taahhüt, taahhüt edilen, kontrat tutarı, обязательство, законтрактовано |
| **Notes** | notes, note, not, açıklama 2, комментарий, примечание |

`cost_code` is what powers the **Planned vs Actual** matching layer (Faz 3) —
expense / ledger entries with the same code are aggregated against the line.

## Example (English)

| Cost Code | Description | Category | Planned Amount | Committed Amount | Notes |
|---|---|---|---|---|---|
| 1.1 | Site preparation | Earthworks | 1,500,000 | 1,200,000 | Excludes utility relocation |
| 1.2.1 | Concrete foundation | Structural | 8,400,000 | 8,400,000 | |
| 1.2.2 | Steel rebar | Structural | 2,300,000 | 1,750,000 | |
| 2.1 | Electrical rough-in | MEP | 4,800,000 | 0 | Sub still being selected |

## Example (Turkish)

| Kod | Kalem Adı | Kategori | Planlanan Tutar | Taahhüt | Notlar |
|---|---|---|---|---|---|
| 1.1 | Saha hazırlığı | Hafriyat | 1,500,000 | 1,200,000 | |
| 1.2.1 | Betonarme temel | Yapısal | 8,400,000 | 8,400,000 | |

## Behaviour

- **Append mode** *(default)*: existing rows are kept, duplicates skipped
  by `(category, lower(description))` pair.
- **Replace mode**: every existing budget item for the project is deleted
  first, then all rows from the file are inserted.
- **Negative amounts** are rejected on `planned_amount`; treated as 0 on
  `committed_amount` with a warning.
- **Empty rows** are skipped silently.
- **File limit**: `MAX_IMPORT_FILE_SIZE_MB` (default 5 MB).

## What we don't yet support (future work)

- Multi-sheet workbooks with cross-sheet references — only the active
  sheet is read.
- Currency columns — every amount is assumed RUB. Multi-currency budgets
  would require a `currency` column + per-row FX.
- Quantity × unit price decomposition — only totals are stored. If your
  source file has `qty * unit_price`, pre-compute it before importing or
  hand us a sample and we'll add a column alias.

## When the user shares a real template

Open the file, check:

1. Which **alias** the headers map to. If a header doesn't match any of the
   aliases above, add it to `_BUDGET_COLUMN_ALIASES` in
   `backend/app/api/v1/endpoints/budget_items.py`.
2. Whether the file is **structured** (single header row, flat rows) or
   **hierarchical** (parent rows for groups, child rows for sub-items). The
   current parser assumes flat. Hierarchical files need a pre-processing
   pass that flattens parent → child by repeating the parent's category /
   cost-code prefix on each child row.
3. Whether **amount cells contain formulas** — `data_only=True` is set on
   `load_workbook` so cached values are returned, but a workbook saved
   without recalculation will have empty cells. Tell the user to "Save
   As → Recalculate before save" if numbers are blank.
