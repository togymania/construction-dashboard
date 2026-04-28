# Sprint Log - ConstructHub

Living, day-by-day log. Forward-looking master plan is in
docs/plans/sprint_roadmap.md. Day-specific plans live under
docs/plans/dayN_*_plan.md.

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
