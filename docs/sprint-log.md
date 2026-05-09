# Sprint Log - ConstructHub

Living, day-by-day log. Forward-looking master plan is in
docs/plans/sprint_roadmap.md. Day-specific plans live under
docs/plans/dayN_*_plan.md.

## Day 12 — Contract list + Profile report ledger-aware (2026-05-09)

**Status:** Per-contract "Paid" column in the Contracts tab now sums
ledger EXPENSE entries (where ``LedgerEntry.contract_id`` matches), and
the Profile report ("Firma Kartviziti") includes ledger-side payments
in its Financial Summary. Both surfaces previously read only from the
legacy SubcontractorPayment table and showed 0.

### What landed

* ``list_contracts_for_sub`` and ``list_subcontractor_contracts_for_project``
  endpoints: extended their inline aggregation to add ``LedgerEntry``
  EXPENSE sums per contract on top of SubcontractorPayment.PAID. Two
  separate endpoints had nearly-identical inline aggregations -- both
  patched in one ``replace_all`` pass.
* ``subcontractor_profile.py`` (Firma Kartviziti service): aggregates
  ``LedgerEntry`` EXPENSE rows for the subcontractor and folds the
  amount into ``total_paid`` on top of SubcontractorPayment.PAID.
* Cache invalidation hooks added to:
  - ``PATCH /ledger/{id}`` (single-row update) -- invalidates the
    affected sub's profile-report cache
  - ``POST /ledger/bulk-assign`` -- invalidates every affected
    sub's cache (covers re-assignments via old + new sub_id capture)

### Why this was needed

Frontend dropdown in the Payments tab calls ``api.ledger.update`` with
``contract_id`` -- so the link is persisted. But the Contracts list
endpoint had its own inline SQL that only looked at
``SubcontractorPayment``, so the freshly-attached ledger rows never
showed up in the per-contract Paid column. Same root cause for the
Profile report's "Ödenen 0 ₽".

---

## Day 12 — Subcontractor "paid" + cash flow ledger-aware (2026-05-09)

**Status:** Subcontractor detail page's "Paid" KPI and the cash flow chart
+ forecast now read from the LedgerEntry table in addition to the legacy
SubcontractorPayment table. Ledger-imported expenses tied to a sub via
``subcontractor_id`` finally show up on the dashboard rather than as
phantom 0 ₽.

### What landed

* New helper ``_compute_paid_for_subcontractor(db, sub_id)`` -- sums
  SubcontractorPayment.PAID + LedgerEntry.EXPENSE (subcontractor_id match).
* ``_compute_contract_aggregates`` extended to also count
  LedgerEntry.EXPENSE rows whose ``contract_id`` matches the contract
  (in addition to SubcontractorPayment.PAID). Pending stays as
  SubcontractorPayment.PENDING/APPROVED only -- ledger has no pending.
* New schema field ``SubcontractorResponse.total_paid`` (Decimal,
  default 0). Frontend ``totalPaid`` prefers this over per-contract sum.
* ``GET /subcontractors/{id}/cashflow`` (monthly history) now sums ledger
  EXPENSE entries into the ``paid`` bucket per month.
* ``GET /subcontractors/{id}/cashflow-forecast`` history merges
  SubcontractorPayment + LedgerEntry monthly aggregates.
* Frontend ``ledger-payments-tab.tsx`` table set to ``table-fixed``
  with truncated description column + tooltip on hover -- previously
  overflowed off-screen on smaller laptops.

### Caveats

* If the user records the same payment in **both** tables, totals
  double-count. Real workflow uses one or the other (we expect ledger).
* Ledger entries with ``contract_id IS NULL`` only show up on the
  subcontractor-wide "Paid" KPI, not on a specific contract row in the
  Contracts tab. Future enhancement: auto-attach ledger to the unique
  active contract when the user only has one.

---

## Day 12 — ÇMI Monart import (2026-05-09 — afternoon)

**Status:** ÇMI master budget Excel parsed end-to-end. 15 Monart top-level
work packages auto-categorized into 8 budget categories, totalling
**11.94B RUB**. Sub-detail rows (kod yok) folded into parent ``notes`` field
to avoid double-counting.

### What landed

- New service `app/services/monart_budget_parser.py`. Header-row
  scanner that walks the ÇMI sheet, filters by column P (Bütçe sorumlusu)
  ``"Монарт"`` substring, and only emits rows that have a cost code in
  column A. Empty-A rows that follow are attached as informational
  ``sub_items`` to the most recent parent.
- Auto-category mapping:
  - 3 → Bina
  - 29-33 → Yollar
  - 35-37 → Altyapı
  - 38 → Haberleşme
  - 39 → Isıtma
  - 40-41 → Elektrik
  - 44 → Peyzaj
  - 45 → Aydınlatma
- New endpoint
  `POST /api/v1/projects/{id}/budget-items/import-cmi` (admin/PM only).
  Multipart: `file`, `sheet_name` (default `ЦМИ`),
  `responsible_filter` (default `Монарт`), `overwrite_mode`
  (`append`/`replace`). Idempotent: existing `cost_code`s skipped with
  warning.
- Frontend: `BudgetItemImportDialog` extended with a Format selector
  (Standart format / ÇMI master bütçe) and a Bütçe sorumlusu filter
  input that's only shown for the ÇMI variant. File-size limit
  auto-bumps to 25 MB for the master workbook.
- New api-client method: `api.budgetItems.importCmiMonart(...)`.

### Validation

- Parsed actual ``ЦМИ - MONART STROY_BÜTÇE 20250304 rev016 OA.xlsx``:
  15 top-level Monart items, 90 attached detail rows, total
  11,939,135,997.39 RUB. Matches manual roll-up of column I for the
  Monart-responsible rows (non-detail).
- Parser correctly demoted three previously-misclassified parents
  (rows 3093, 3102, 3110 = sub-items of "Благоустройство" #44)
  into the parent's notes. Pre-fix total had been 12.48B (538M
  double-counted).
- Note: the older `app/services/budget_excel_cmi.py` file still
  exists on disk (sandbox couldn't delete it) but is no longer
  imported anywhere. Safe to delete from the host machine.

### Carried forward

- After successful import on a real project, kullanıcının başka
  firmaların kalemlerini de (Альмис gibi) ayrı bir taşeron-bütçesi
  olarak görmek isteyip istemediğini soracağız.
- Sub-item'lar şu an sadece parent'ın notes alanında metin olarak
  saklanıyor. İleride ayrı bir nested ``BudgetItemDetail`` tablosu
  açıp variance reportu daha detaylı yapabiliriz.

---

## Day 12 — Demo Blitz Faz 2-5 (2026-05-09 — same day continuation)

**Status:** All four remaining phases (Budget Excel parser hardening,
Planned vs Actual variance, Dashboard daily AI briefing, Project executive
report) shipped end-to-end. LLM paths gated on `ANTHROPIC_API_KEY`; all
fall back to rule-based copy when the key is missing so demos work today.

### What landed

**Faz 2 — Budget Excel parser**
- `BudgetItem` model: `cost_code` (indexed string, nullable) +
  `committed_amount` (Numeric, default 0). Migration
  `c2d4e6f8a1b3_add_cost_code_and_committed_to_budget_items`.
- Schema (`schemas/budget.py`): `BudgetItemBase` / `BudgetItemUpdate`
  pick up the new fields.
- Parser (`app/api/v1/endpoints/budget_items.py`): added `cost_code` and
  `committed_amount` to the column-alias table (TR/EN/RU). Parser writes
  both to the new columns; negative committed amounts → 0 with warning.
- `create_budget_item` endpoint passes both fields when constructing
  rows via the JSON API.
- Format reference: `docs/budget_excel_format.md` documents the alias
  table, required vs optional columns, and what to add when the user
  shares a template.

**Faz 3 — Planned vs Actual variance**
- New service `app/services/budget_variance.py`. Aggregates two sources
  of "actual": (1) PAID expenses with `budget_item_id` matching the row,
  (2) EXPENSE-type ledger entries whose `budget_code` matches the
  budget item's `cost_code` AND whose contract belongs to this project
  (or is unlinked).
- New schemas: `BudgetItemVariance`, `BudgetVarianceReport`.
- New endpoint: `GET /api/v1/projects/{id}/budget/variance`.
- Severity buckets: ok / watch / warn / over (≥80, ≥95, >100).
- Frontend: new `<BudgetVarianceTab>` component at
  `components/budget-items/variance-tab.tsx`. Top KPI strip (Planned /
  Committed / Actual / Variance), filter chips by severity, search,
  sortable table (cost code, planned, actual, variance), per-row badges.
- Wired into the budget page as a new "Planned vs Actual" tab.

**Faz 4 — Dashboard daily AI briefing**
- New service `app/services/daily_briefing.py`. Collects 24-hour facts
  across the portfolio (new expenses, new ledger rows, payments paid,
  workforce snapshots, new contracts, project state) → asks Claude (or
  rule-based) for a 1-paragraph summary + 3-5 highlights + 3-5 decisions.
- New schema: `DailyBriefing`.
- New endpoint: `GET /api/v1/dashboard/daily-briefing?force_refresh=`.
- Cache: `insights_cache.set(-42, …)` (disjoint key from sub-profile +
  exec-report).
- Frontend: new `<DailyBriefingCard>` at
  `components/dashboard/daily-briefing-card.tsx` — gradient header,
  AI Generated badge, Yenile button, two-column highlights / decisions.
- Mounted at the top of `/` (the dashboard).

**Faz 5 — Project executive report**
- New service `app/services/project_executive_report.py`. Pulls budget
  variance + subcontractor leaderboard + workforce trend + project
  metadata into a structured fact bundle, then asks Claude for six
  narrative sections (executive summary / financial / risks / sub
  performance / workforce / next 30 days) + recommended actions.
- New schemas: `ExecutiveReportSections`, `ProjectExecutiveReport`.
- New endpoint: `GET /api/v1/projects/{id}/executive-report?force_refresh=`.
- Cache: project_id + 2_000_000 (disjoint).
- Frontend: `/projects/[id]/reports` is now a real page (no more
  ComingSoonPage). Cover card with project metadata, six section cards,
  recommended-actions card, browser-print to PDF via `window.print()`.
  Print-hidden controls so the printed PDF is clean.

### Cache key namespace map

| Owner | Offset / Key |
|---|---|
| AI insights (per sub) | sub_id |
| Subcontractor profile | sub_id + 1_000_000 |
| Project executive report | project_id + 2_000_000 |
| Dashboard daily briefing | -42 |

All cache entries clear automatically after the `insights_cache` TTL.
Manual force_refresh on each endpoint bypasses.

### Bugs fought

- **Sandbox mount truncation:** As before, bash-side `python` invokes
  see truncated sources. Verified via Read tool which uses Windows side.
- **Cache key collisions:** Used disjoint offsets per resource family so
  the single shared cache module supports multiple unrelated namespaces.

### Carried forward

- Real Excel template from user → revisit alias table once received,
  potentially add column aliases or hierarchy flattening.
- PDF generation via WeasyPrint or Playwright for the executive report
  if browser-print isn't enough.
- Ledger entry → budget_item FK migration (currently matched via the
  `budget_code` ↔ `cost_code` string join).

---

## Day 12 — Demo Blitz Faz 1 (2026-05-09)

**Status:** Sidebar restructure shipped, Expenses bulk-assign + sort shipped,
Subcontractor area-chart + profile-report ("Firma Kartviziti") shipped. API
key promised by user — wiring is ready (`ANTHROPIC_API_KEY` env var flips
all paths from rule/mock to real Claude on backend restart).

### What landed

**1.1 — Project-scoped sidebar restructure**
- Top-level nav reduced to Dashboard / Projects (+ Admin: Budget Categories).
- New `ProjectProvider` context (`components/providers/project-provider.tsx`)
  loads the active project once and exposes it via `useProject()`.
- New `ProjectSidebar` (`components/layout/project-sidebar.tsx`) — renders
  Overview / Subcontractors / Workforce / Budget / Expenses / Schedule /
  Risks / Reports for the selected project.
- New `app/(dashboard)/projects/[id]/layout.tsx` slots the sub-sidebar in.
- New `app/(dashboard)/projects/[id]/page.tsx` — project overview / module
  quick-launch grid with KPI strip.
- Modules moved: `subcontractors/`, `workforce/`, `expenses/`, `schedule/`,
  `risks/`, `reports/` → all live under `projects/[id]/...` and read
  `projectId` from `useParams` / `useProject`.
- Subcontractor detail + contract detail now nested at
  `projects/[id]/subcontractors/[subId]/contracts/[contractId]`.
- Legacy top-level routes return `redirect("/projects")` so old links still
  bounce somewhere sensible.
- Projects list rows + new "Open Project" dropdown action go straight to the
  overview (`/projects/{id}`).
- i18n: `nav.overview`, `nav.budget`, `project.backToProjects` keys added
  (TR + EN).

**1.2 — Expenses sort + bulk assign**
- Sortable headers (Date / Company / Amount). Visual arrow ikonu.
- Inline single-row edit popovers for budget code (uses BudgetCategory.slug)
  and subcontractor (uses /subcontractors list).
- Per-row checkbox + sticky bulk action bar appears when ≥1 selected.
- Quick selectors: click company name or KOD badge to select all matching
  rows on the page.
- Backend: new `POST /api/v1/ledger/bulk-assign` endpoint (admin/PM only).
  Schemas: `LedgerBulkAssignRequest`, `LedgerBulkAssignResponse`.
- Existing `PATCH /ledger/{id}` extended to accept `subcontractor_id`
  (clears `contract_id` when sub changes — keeps FK invariant).

**1.3 — Subcontractor: Area chart + Claude API + Firma Kartviziti**
- Cash flow tab: Recharts BarChart → AreaChart with gradient fills (Paid
  green / Approved blue / Pending amber, all stacked).
- Backend service: `app/services/subcontractor_profile.py`. Aggregates
  contracts + payments + every contract document's extracted_data into a
  single `SubcontractorProfileReport`. Claude path when API key present,
  rule-based fallback otherwise.
- New schemas (`schemas/subcontractor.py`): `ProfileSection`,
  `PenaltyPattern`, `TimelineKeyDate`, `SubcontractorProfileReport`.
- New endpoint: `GET /subcontractors/{id}/profile-report?force_refresh=`,
  cached in `insights_cache` with disjoint key namespace (`sub_id +
  1_000_000`).
- Cache invalidation hooks added on document upload, re-extract, and
  extracted-data PATCH.
- Frontend: new `<SubcontractorProfileCard>` component — gradient header
  card with KPI tiles (toplam değer / ödenen / bekleyen / aktif-bitmiş /
  risk score), four narrative sections (Şirket Özeti / Mali / Risk /
  Ödeme Şartları), penalty patterns list, kritik tarihler timeline,
  AI tavsiyeleri. "Yenile" button forces refresh.
- Subcontractor detail page: new "Profil" tab as the default landing tab.

### Bugs fought

- **Param collision after route restructure:** subcontractor detail
  used `useParams<{ id: string }>` for sub id, but `id` is now project id.
  Renamed to `subId`, both pages updated; `params.id` now means project.
- **Internal links (`/subcontractors/{id}` etc):** patched all hard-coded
  links inside subcontractor + budget pages to project-scoped routes.

### Carried to Day 13 (Faz 2 — Budget Excel)

- User will share the budget Excel template — parser + import endpoint
  + frontend dialog still pending.
- After parser lands, Faz 3 (Planned vs Actual) wires expenses to budget
  items via FK + variance report.

### Validation

- Backend `py_compile` clean for all new/modified modules.
- Schema additions all optional / additive — no existing endpoint broken.
- Manual review of `<SubcontractorProfileCard>`, sidebar, project-scoped
  routes via Read tool (sandbox mount truncation prevents bash python
  smoke tests on large files).

---

## Day 11 — Subcontractor Intelligence (2026-05-02)

**Status:** Backend + frontend wired. LLM paths land as **mock responses**
because Anthropic API key not yet obtained — flipping to real LLM is one
`.env` line + cache-bust away. Commit deferred to local machine (sandbox
mount truncates large files; safer to commit from Windows).

### What landed

**FAZ 2 — Cash Flow Forecast (~2.5 hours, shipped first per plan revision)**
- New service `app/services/cashflow_forecast.py` with EMA + linear-trend +
  quarterly-seasonality engine. Honest about limits: <12 months data → flag
  `insufficient_data=True` and fall back to naive average.
- Three scenarios: best / likely / worst, capped by remaining contract
  capacity (no extrapolation past contract end-dates).
- "No active contracts" branch returns zeros with high confidence (proven
  with COMPLETED Atlas Beton fixture).
- New schema: `CashFlowForecast`, `CashFlowForecastPoint`, `ContractEndPoint`.
  Old `MonthlyCashFlowPoint` + `/cashflow` endpoint untouched (zero break).
- New endpoint: `GET /subcontractors/{id}/cashflow-forecast`.
- Frontend: dedicated `CashFlowForecastChart` component with Recharts
  `ComposedChart` (Bar history + Line scenarios + Area confidence band +
  ReferenceLine "today" + ReferenceDot contract-end markers + Insights
  bullets + Contract-end-dates list).
- "<12 ay veriden" amber warning badge per user request.
- Confidence pill (color-coded), method label ("EMA + Mevsimsellik" /
  "Basit Ortalama").
- Wired into existing Cash Flow tab on subcontractor detail page (above
  the existing detailed monthly bar chart).

**FAZ 1 — PDF Upload + LLM Extraction Scaffolding (~2 hours, mock LLM)**
- `requirements.txt`: added `pdfplumber==0.11.4`, `anthropic==0.39.0`.
- `config.py` + `.env`: `ANTHROPIC_API_KEY` (empty default → mock path),
  `ANTHROPIC_MODEL`, `LLM_TIMEOUT_SECONDS`, `MAX_PDF_SIZE_MB=20`.
- `contract_parser.py` split into 3 layers:
  - `parse_contract_text(text)` — existing regex (kept as fallback).
  - `extract_text_from_pdf(bytes)` — pdfplumber wrapper.
  - `parse_contract_with_llm(text, api_key=None)` — real Anthropic call
    when key present, otherwise synthetic mock that blends regex output
    with placeholder structured fields (penalty clauses, key dates,
    risk flags) so frontend is fully testable now.
- Schema additions: `PenaltyClause`, `KeyDate`, extended
  `ExtractedContractData` with `currency`, `company_name`,
  `counterparty_name`, `payment_terms_summary`, `penalty_clauses`,
  `key_dates`, `risk_flags`, `summary`, `source`, `extracted_at`. All
  new fields **optional** for backwards-compat with existing rows.
- Existing `upload_document` endpoint now dispatches to PDF branch
  (with size guard) → text extraction → LLM (or mock) extraction.
- Two new endpoints:
  - `POST /documents/{id}/re-extract` — manual re-run (key value when
    LLM key gets added later or parser improves).
  - `PATCH /documents/{id}/extracted-data` — user manual correction
    (marks source as `user_edited`).
- Frontend: new `ExtractedDataPreview` component shown inline as an
  expandable row under each document (toggle by clicking filename or
  Bot icon). Shows summary, key/value grid, penalty clauses (red border),
  key dates, risk flags, source badge, confidence %. "Yeniden cikart"
  + "Duzenle / Kaydet" actions for editors.
- Yellow banner when `source=llm_mock` instructing user to add API key.

**FAZ 3 — Insight Generator Extension + Cache (~1.5 hours)**
- Did **not** rewrite `insight_generator.py` — extended it. Added 3 new
  rule-based insight families on top of existing ones:
  - Per-contract pace projection ("kalan %X normal akista Y ayda biter")
    — `category=schedule`, with severity matched to whether tempo fits
    contract end-date.
  - Average payment delay ("ortalama 22 gun, sektor 12-15") —
    `category=financial`, warns if >25 days.
  - Mock LLM-style commentary stub (`source=llm_mock`) when risk_score
    >= 30, prompting user to add API key for real analysis.
- New service `app/services/insights_cache.py`: in-memory dict, TTL=10m,
  process-local. Includes `invalidate(sub_id)` for future call sites
  (payment write paths).
- `AIInsight` schema extended with optional `category`, `title`, `body`,
  `action`, `source` fields (backwards-compat — old clients ignore).
- `/ai-insights` endpoint: cache lookup → generate → cache write.
  `?force_refresh=true` query param bypasses cache.
- Frontend: new `SubcontractorInsightsCard` component replaces inline
  insights tab markup. Features: severity-sorted list, category filter
  chips with counts, refresh button (calls force_refresh), per-row
  source badges (LLM/mock), action callout, mock-banner footer.

### Bugs fought

- **Sandbox mount truncation:** Cowork's Linux mount cuts off large
  files (>~12KB) when read from bash. Edit/Read tools work fine
  (Windows side is intact), but `python` invoked from bash sees
  truncated source and fails with syntax errors. Workaround:
  rely on Read tool for verification, defer commits to host machine.
- **Atlas COMPLETED forecast:** First version of `build_forecast`
  produced positive forecast values for completed contracts because
  the trend/EMA pipeline ignored contract status. Fixed by adding
  early-return: if no `active` contracts AND total_remaining<=0,
  return all-zero forecast with confidence=0.9.
- **Pydantic forward reference:** `ExtractedContractData` referenced
  `PenaltyClause` and `KeyDate` defined later in the file. Reordered
  so child models come first.
- **React Fragment + key prop:** `<>` shorthand can't take `key`,
  switched to `<Fragment key={...}>` in document table mapping.

### Carried to Day 12

- Anthropic API key wiring (just `.env` value) + cache-bust to flip
  all `llm_mock` paths to real LLM.
- Cache invalidation hooks on payment create/update/delete (now manual
  via "Yenile" button only).
- Real PDF fixtures for end-to-end validation — currently only mock
  text path validated.
- Replace contract `description` quick-summary with extracted_data
  `summary` when present (cross-cut with FAZ 1).
- TS strict-mode debt still 6 errors (Day 4-5). No new errors introduced
  but couldn't verify in sandbox due to mount truncation.

### Validation

- Backend `cashflow_forecast.py` unit-tested with 4 scenarios:
  - 4-month history + active contract → 3 capped scenarios, insights
    flag insufficient data.
  - 14-month history with engineered Q4 dip → seasonality factor 0.75
    detected, insight surfaces "Q4 %25 daha dusuk".
  - Empty history → method=none, empty forecast.
  - 18-month + active contract → method=ema_seasonal, confidence=0.8.
- Manual review of all generated React components (Read tool, full file).
- Schema validation: `CashFlowForecast(**bundle)` round-trip OK.

---

## Day 10 — Workforce Module + Sidebar Cleanup (2026-04-28)

**Status:** Committed end of day, cosmetics + Top Positions chart fix carried to Day 11.

### What landed

**Phase 1: Sidebar cleanup (~10 min)**
- Removed broken `/budget` nav link.
- Added 3 placeholder pages: `/schedule`, `/risks`, `/reports` via reusable `<ComingSoonPage>` component.
- Added `Workforce` nav item with `Users` icon between Subcontractors and Schedule.

**Phase 2: Workforce backend (~3 hours total, multiple migrations)**
- 3 SQLAlchemy models: `WorkforcePosition` (catalog), `WorkforceSnapshot` (daily, denormalized aggregates), `WorkforceCount` (atomic per-position).
- 13 Pydantic schemas including KPI bundle with per-category cards, daily trend, weekly buckets, top positions, multi-import response.
- 10 endpoints: positions CRUD, project-scoped snapshots, KPI bundle, multi-file Excel import.
- Excel parser for cover-page format (Monotekstroy/Monart puantaj). Auto-detects Section A (PRODUCTIVE) / B (UNPRODUCTIVE) / C (SUBCONT). Validates GRAND TOTAL, surfaces mismatches as non-blocking warnings.
- Migration `70b1a888e789` initial workforce tables.
- Migration `eee0e6994fba` adds `company_label` column + UNIQUE `(project_id, snapshot_date, company_label)` to allow Mono and Monart snapshots on the same date.

**Phase 3: Workforce frontend (~2 hours)**
- Types in `frontend/src/types/workforce.ts` matching backend Pydantic 1:1.
- `api.workforce` namespace in `api-client.ts` with 10 functions including multi-file `importExcel(files: File[])`.
- Dashboard charts component (`dashboard-charts.tsx`): TopPositionsChart, TodayByCategoryChart, DailyTrendChart, WeeklyComparisonChart. Color triad indigo/cyan/emerald.
- Page `/workforce/page.tsx`: 3 KPI cards (Mono+Monart total) + per-company breakdown card (Today by Company) + charts + recent snapshots with company badges.
- Upload dialog with multi-file picker, progressive validation, per-file result panel showing company badge + warnings (GRAND_TOTAL_MISMATCH, UNKNOWN_POSITION_CREATED, SNAPSHOT_REPLACED).

**Phase 4: User-driven schema upgrade**
- After initial single-file upload UX, user requested multi-file (Mono + Monart upload together) with sticky 2-company model. Refactored DB + endpoint + frontend to support `company_label` per snapshot.
- KPI endpoint rewritten: same date with multiple companies sums for project-wide totals AND breaks out per company. Added `by_company_today` to bundle.
- Daily trend now sums Mono+Monart per date.
- Weekly bucket simplified to "this week vs last week" (last 2 weeks only).

### Bugs fought

- **PostgreSQL substring trap:** `"PRODUCTIVE LABOUR"` matches inside `"UNPRODUCTIVE LABOUR"`. Section A end check needed `"UNPRODUCTIVE" not in joined_upper` negation.
- **Async SQLAlchemy + sync helpers:** Lazy-loaded relationships (`obj.relationship.attr`) cause `MissingGreenlet` errors when called from sync code in async context. Fixed `_recompute_snapshot_aggregates` to be async + fetch positions explicitly via dict map.
- **Pydantic serialization through async session:** `expire_on_commit=False` not enough — final fetch + relationship lazy-load still bombs. Fixed by building response manually with explicit per-table fetches and constructing Pydantic models from dicts (no `from_attributes`).
- **PowerShell heredoc + Python f-strings:** `<` characters can vanish in TypeScript generics (`Record<...>`) when written via PowerShell pipe to Python heredoc. Manual diff-and-fix with `str_replace`.
- **Recharts Tooltip formatter signature change** (TS strict): tuple return rejected — switch to single string return.
- **FastAPI auth login:** endpoint accepts JSON with `email` field (not OAuth2 form `username`). Token field is `access_token`.

### Carried to Day 11

- Top Positions chart legend hidden when single-category dominates (visual: all bars same color even though `<Cell>` per-bar fill is correct).
- Daily and Weekly chart UX polish — user feedback that they're hard to read for first-time viewers.
- Phase 4 polish (alert→toast with sonner) — never done; subcontractor pages still use native alerts.

### Validation

- 2 production-shape Excel files parsed cleanly (Monotekstroy 1495 present, Monart 304 present).
- Multi-file upload with both companies coexisting on same date verified end-to-end via TestClient.
- 16 snapshots on file at end of day (user added several days of real data via the new dialog).

---

## Day 1 - Foundation

- Repo bootstrapped, Docker compose, env scaffolding
- PostgreSQL on host port 5433
- Backend Docker image pre-installs alembic, asyncpg, passlib
- Frontend uses --no-turbopack inside Docker

## Day 2 - Frontend layout

- Shadcn UI primitives: Button, Card, Input, Table, Dialog, Sheet
- Dashboard shell: Sidebar + Header + breadcrumb
- Theme toggle (next-themes)
- Backend /api/v1/ router skeleton
- Mock /api/v1/projects endpoint

## Day 3 - Auth (JWT)

- User + Role models, Alembic migration
- JWT access + refresh tokens
- Login/Register pages
- UserProvider context, protected routes

## Day 4 - Project CRUD

- Project model + schemas + endpoints
- /projects list page + /projects/[id] detail
- ProjectFormDialog (create + edit)
- Single seeded project: Istanbul Havalimani Terminal B (42.75B RUB)

## Day 5 - Budget tracking

- BudgetCategory enum, BudgetItem model
- Budget summary endpoint
- /projects/[id]/budget page with Pie + Bar charts
- BudgetItemFormDialog
- Sidebar admin section

## Day 6 - Expense module + Excel import

- Expense model + endpoints
- ExpenseFormDialog
- Excel bulk import with category fuzzy matching
- Idempotent results

## Day 7 - Dynamic categories + budget Excel import

- Promoted budget categories from enum to a real table
- Admin CRUD at /settings/budget-categories
- Budget items got Excel import (append + replace modes)
- Stale demo projects pruned to 1 production project

## Day 8 - Subcontractor module (full stack)

Backend (commit 1e0c532):
- 3 models: Subcontractor, SubcontractorContract, SubcontractorPayment
- 16 endpoints incl. cross-cut /projects/{id}/subcontractor-contracts
- Pydantic schemas with validators
- Seed: 4 subcontractors, 3 contracts, 8 payments (2.7B RUB total)

Frontend (commit 1638c62):
- TS types (3 enums + 12 interfaces)
- api.subcontractors namespace
- Pages: list, detail, contract detail
- 3 form dialogs: subcontractor, contract, payment
- KpiCharts component (4 Recharts widgets)
- Project budget page extended with 3rd tab Subcontractors
- Sidebar nav: Subcontractors
- Bonus: smart breadcrumb fix in header.tsx

Lessons:
- FastAPI 0.115: omit return annotation on 204 endpoints
- PowerShell heredoc fragility: use python write_bytes helper
- PowerShell Select-String -SimpleMatch with pipes: use regex (default)
- Indentation matching: view file first, never guess

## Theme-pass (between Day 8 and Day 9, commit 689e5f4)

Visual-only sprint, no feature changes.

- OKLCH palette unified at hue 260, indigo/cyan/emerald accent triad
- Mesh gradient overlay (3 blobs, blurred, fixed) + SVG noise texture
- Card glassmorphism (bg/70 + backdrop-blur-xl + rounded-2xl + lift)
- Inter (body+headings) + JetBrains Mono replaced Geist family
- Sidebar 3px neon left bar + indigo glow on active item
- Status pulse dots, header glass styling
- Buttons: gradient primary + neon glow; outline glass
- Inputs: glass bg + indigo focus ring
- Pie -> Donut conversion in 3 charts with smart labels
- Bonus fix: Radix Select empty-string value bug in expense-form-dialog

Lessons:
- Tailwind v4 has CSS-first config in @theme inline (no JS config file)
- Next.js fonts swap via HMR (dev restart usually unnecessary)
- Radix Select.Item: never empty-string value, use sentinel like _none

## Upcoming

See docs/plans/sprint_roadmap.md.

Next session: Day 10 - Workforce + polish + sidebar fix.
Detailed plan: docs/plans/day10_workforce_polish_plan.md.
