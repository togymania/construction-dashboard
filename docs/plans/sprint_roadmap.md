# ConstructHub - Sprint Roadmap (Master)

This is the living source of truth for what's done, what's next, and what's
deferred. Updated at the end of each sprint day.

## Status snapshot (end of theme-pass)

- Total commits on main: 13
- Latest commit: 689e5f4 chore(theme-pass)
- Sprint position: between Day 9 and Day 10 (theme-pass was unscheduled)
- Original 15-day plan extended to 17-18 days
- TS strict-mode debt: 6 errors (Day 4-5, deferred to Day 13)

## Completed sprints

### Day 1 - Foundation
- Repo, Docker compose, env scaffolding
- PostgreSQL, FastAPI, Next.js 16 boot

### Day 2 - Frontend layout
- Shadcn UI primitives
- Dashboard shell: Sidebar + Header + breadcrumb
- Theme toggle

### Day 3 - Auth (JWT)
- User + Role models
- Login/Register pages
- UserProvider context

### Day 4 - Project CRUD
- Project model + endpoints
- ProjectFormDialog
- Single seeded project: Istanbul Havalimani Terminal B (42.75B RUB)

### Day 5 - Budget tracking
- BudgetCategory + BudgetItem models
- Budget summary endpoint with category breakdown
- /projects/[id]/budget page

### Day 6 - Expense module + Excel import
- Expense model + endpoints
- Excel bulk import with category fuzzy matching

### Day 7 - Dynamic categories + budget Excel import
- Promoted budget categories from enum to a real table
- Admin CRUD at /settings/budget-categories

### Day 8 - Subcontractor module (full stack)
- 3 models, 16 endpoints, full UI
- Commits: 1e0c532 (BE) + 1638c62 (FE)

### Theme-pass (between Day 8 and Day 9)
- OKLCH palette, mesh gradient, glassmorphism cards
- Inter + JetBrains Mono fonts
- Sidebar neon glow, status pulse dots
- Pie to Donut chart conversion
- Commit: 689e5f4

## Upcoming sprints

### Day 10 - Workforce + polish + sidebar fix (DONE)
Detailed plan: docs/plans/day10_workforce_polish_plan.md

### Day 11 - Subcontractor Intelligence (DONE, 2026-05-02)
- FAZ 2: Cash Flow Forecast — EMA + quarterly seasonality, 3 scenarios,
  confidence + insufficient_data flag, contract-end capping.
- FAZ 1: PDF upload + LLM extraction scaffolding (mock LLM — API key pending).
- FAZ 3: Insight generator extension (3 new rule families) + in-memory cache
  + manual "Yenile" refresh button + LLM mock hooks.
- Commit deferred to host machine (sandbox mount truncates large files).

### Day 12 - LLM go-live + real-PDF validation
- Add ANTHROPIC_API_KEY → flip all mock paths to real Claude calls.
- Drop in real signed PDF contract fixtures, end-to-end validation.
- Cache invalidation hooks on payment write paths.
- Replace inline contract descriptions with extracted_data.summary
  when present (cross-cut from FAZ 1).

### Day 13 - Tasks/Milestones
- Task model linked to projects, milestone tracker

### Day 14 - Reports/Export + TS strict-mode debt cleanup
- Excel + PDF export, fix the 6 strict errors

### Day 15 - Demo data + final polish
- Richer seed data, performance audit

### Day 16 - Demo prep
- Demo script, screen recording prep

### Day 16-18 (stretch / buffer)
- i18n (TR/EN/RU) only if time and demand
- Production deployment if all else done

## Tech-debt registry

- TS strict mode (6 errors) - fix in Day 13
- alert() in error handlers - replace with toast in Day 10
- No optimistic updates anywhere - revisit if sluggish
- Single project assumption - multi-project support in Day 12
- Localization stretch goal in Day 16-18
