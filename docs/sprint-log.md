# Sprint Log - ConstructHub

Living, day-by-day log. Forward-looking master plan is in
docs/plans/sprint_roadmap.md. Day-specific plans live under
docs/plans/dayN_*_plan.md.

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
