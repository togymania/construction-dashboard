# Sprint Log - ConstructHub

Living, day-by-day log. Forward-looking master plan is in
docs/plans/sprint_roadmap.md. Day-specific plans live under
docs/plans/dayN_*_plan.md.

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
