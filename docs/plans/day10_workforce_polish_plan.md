# Day 10 - Workforce + Polish + Sidebar Fix

**Estimated:** 8.5 hours of focused work
**Goal:** Add workforce tracking module, polish UX, fix broken sidebar links.

## Pre-flight checklist

- Backend on port 8000, frontend on 3000 (start-all.ps1)
- venv activated for any backend python invocation
- TS strict baseline: 6 errors (Day 4-5 debt) - must stay 6
- Recurring traps to avoid:
  - PowerShell heredoc + multi-line file: prefer python write_bytes helper
  - Select-String -SimpleMatch with pipes: use regex (default)
  - Indentation match: read the file with view first, never guess
  - Radix Select.Item: never empty-string value, use sentinel
  - FastAPI 0.115: omit return annotation on 204 endpoints
  - Card component is glass; layout uses mesh-gradient-bg div

## Phase 0 - Verify state (~5 min)
- TS check: 6
- Backend + frontend reachable
- Workforce excel template received from user (or use assumed schema)

## Phase 1 - Sidebar cleanup (~30 min)

### 1.1 Remove broken /budget nav item
- Edit frontend/src/components/layout/sidebar.tsx
- Remove the Budget line from navigation array
- Budget content still reachable via /projects/[id]/budget tabs

### 1.2 Coming Soon pages for /schedule, /risks, /reports
Three minimal pages:
- frontend/src/app/(dashboard)/schedule/page.tsx
- frontend/src/app/(dashboard)/risks/page.tsx
- frontend/src/app/(dashboard)/reports/page.tsx

Each: centered glass card with icon, 'Coming Soon' heading, small description,
back-to-dashboard link. Premium feel matching theme.

### 1.3 Verify
- All 4 sidebar nav items resolve (no 404)
- Active highlight works for placeholder pages
- TS still 6 errors

## Phase 2 - Workforce backend (~3.5 hours)

### Schema (working assumption, may adapt to user's Excel)

workforce_categories enum: direct, indirect, subcontractor

workforce_positions table:
  id, category enum, name varchar, display_order, is_active
  UNIQUE (category, lower(name))

workforce_snapshots (one row per project per day):
  id, project_id FK, snapshot_date date, uploaded_by, source, source_filename, notes
  UNIQUE (project_id, snapshot_date)

workforce_counts (one row per snapshot per position):
  id, snapshot_id FK CASCADE, position_id FK RESTRICT, count >= 0
  UNIQUE (snapshot_id, position_id)

### 2.1 Models + migration (~45 min)
- backend/app/models/workforce.py
- Idempotent: upsert by (project_id, snapshot_date)
- Alembic autogenerate, sanity-check, apply

### 2.2 Pydantic schemas (~30 min)
- backend/app/schemas/workforce.py
- Position, Snapshot, KPI bundle schemas

### 2.3 API endpoints (~1 hour)
File: backend/app/api/v1/endpoints/workforce.py

- GET /workforce/positions
- POST /workforce/positions (admin)
- PATCH /workforce/positions/{id}
- DELETE /workforce/positions/{id}
- GET /projects/{id}/workforce (list snapshots)
- GET /projects/{id}/workforce/{date}
- POST /projects/{id}/workforce (upsert)
- DELETE /projects/{id}/workforce/{date}
- GET /projects/{id}/workforce/kpis
- POST /projects/{id}/workforce/import (Excel)

### 2.4 Excel import (~45 min)
Pattern: copy of expenses.py:import_expenses_from_excel

Two assumed shapes:
A) Wide: columns = positions, rows = dates
B) Long: Date, Category, Position, Count

Pre-implement both, pick after seeing user template.
Header detection: case-insensitive position match. Auto-create unknown
positions (like Day 7 dynamic categories). Idempotent: re-import same
date overwrites snapshot.

### 2.5 Seed (~30 min)
backend/app/db/seed_workforce.py
- ~10 positions across 3 categories
- 30 days of snapshots for project 1, realistic numbers (~85 daily)

## Phase 3 - Workforce frontend (~3 hours)

### 3.1 Types + api-client (~20 min)
- frontend/src/types/workforce.ts
- api.workforce namespace

### 3.2 Sidebar nav (~5 min)
- Add Workforce nav item with Users icon, after Subcontractors

### 3.3 Workforce page (~1.5 hours)
frontend/src/app/(dashboard)/workforce/page.tsx

Premium dashboard layout:
- 3 KPI cards: Direct, Indirect, Subcontractor (today total + delta)
- 2-column row: stacked bar (today by category) + position pie
- Daily trend area chart, last 30 days, three series
- Weekly comparison bar chart, last 8 weeks
- Recent uploads card
- 'Upload Excel' button top right

Single project = silently use project_id=1; multi-project picker later.

### 3.4 Excel upload dialog (~30 min)
Reuse expense-import-dialog.tsx pattern.
File picker, mode toggle (append | replace), result modal.

### 3.5 Manual edit dialog (~30 min, stretch)
Optional: 'Add today's snapshot manually' form. Skip if running long.

## Phase 4 - Polish (~1 hour)

### 4.1 Toast system (~30 min)
- npm install sonner
- Add Toaster to (dashboard)/layout.tsx
- Replace alert() with toast.error / toast.success in:
  - subcontractor list page (delete handlers)
  - subcontractor detail page (contract/payment actions)
  - contract detail page (payment actions)
- Theme toast styling to match glass cards

### 4.2 Edit improvements (~20 min)
- Toast on successful edit
- Failure messages preserve API context

### 4.3 Misc cleanups (~10 min)
- Forms close on success
- Error states visible

## Phase 5 - Browser test + commit (~30 min)

Walk every page in dark + light:
- /
- /projects, /projects/1/budget (3 tabs)
- /subcontractors (charts, filters, table)
- /subcontractors/1, /subcontractors/1/contracts/1
- /workforce (new) - KPIs, charts, upload flow
- /schedule, /risks, /reports - Coming Soon pages
- /settings/budget-categories

Commit message:
feat(day10): workforce module + polish + sidebar fix

## Risks + mitigations

- Excel template differs from assumed: schema is generic, only parser
  changes. Allow 30 min for adaptation.
- Sonner + Tailwind v4 conflicts: add Toaster theme system, verify
  glass cards do not bleed through.
- Coming Soon pages active highlight: verify pathname.startsWith works.
- Time pressure: if Phase 4 polish runs long, defer toast migration to
  Day 11. Workforce is the user-visible win.

## Definition of done

- TS errors: 6 (no new)
- 4 broken sidebar links: all resolve
- /workforce page: KPIs render, Excel upload roundtrips, charts populated
- Subcontractor flows: alert() gone, toasts in place
- All commits pushed to origin/main
