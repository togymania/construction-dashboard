# Day 9 — Premium Theme Sprint Plan

**Goal:** Visual overhaul of the entire frontend without changing any feature.
**Duration:** 1 day (~7-8 hours), expandable by 1 if Faz 7 reveals issues.
**Scope:** Both dark and light themes premium-quality.
**Sprint impact:** Sprint extended from 15 to 17-18 days, demo on Day 15+.

## Tech context (verified from codebase)
- Tailwind v4 with CSS-first config in `globals.css` (no `tailwind.config.*`).
- Color space: OKLCH (perceptually uniform — keep using it).
- Font: Geist Sans + Geist Mono via `next/font/google`.
- Theme toggle: `next-themes`, `attribute="class"`, `.dark` class on html.
- Card: shadcn/ui v4 with `bg-card ring-1 ring-foreground/10 rounded-xl`,
  has a `size="sm"` variant — keep both variants working.

## Color philosophy
- Dark mode background: deep midnight blue `oklch(0.155 0.025 260)` (NOT pure
  black; the 260 hue gives premium tone instead of "monitor off" feel).
- Light mode background: pure-feeling near-white `oklch(0.99 0.005 260)`
  (slight tint matches dark hue for thematic consistency).
- Primary brand: indigo `oklch(0.55 0.22 270)` — used for accents, active
  nav, primary buttons.
- Charts unchanged — they already use explicit hex (`#3b82f6`, `#10b981`...)
  in component code, no theme dependency.

## Faz 1 — Color system + background (~1h)
1.1 Update `globals.css` :root and .dark blocks:
    - background, card, popover with new OKLCH values (deep blue dark / off-white light)
    - primary → indigo, accent → cyan, destructive → rose, success → emerald
    - muted, border with appropriate alpha
1.2 Add fixed mesh-gradient overlay in `(dashboard)/layout.tsx`:
    - 3 radial-gradient blobs (indigo top-left, emerald bottom-right, cyan center)
    - opacity 0.08 dark, 0.05 light, blur(120px), pointer-events: none, z-0
    - main content z-10
1.3 Add SVG noise texture overlay (data URI, mix-blend overlay, opacity 0.015)

## Faz 2 — Glassmorphism Card (~1.5h)
2.1 Update Card component default classes:
    - bg-card/70 backdrop-blur-xl
    - ring-1 ring-foreground/10 → border border-white/8 dark:border-white/5
    - rounded-xl → rounded-2xl (already 0.625rem * 1.8 in @theme)
    - shadow-[0_8px_32px_rgba(0,0,0,0.12)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.5)]
2.2 Add hover state via tailwind utility (apply via group/card data-attr or extend class):
    - hover:-translate-y-0.5 hover:shadow-2xl transition-all duration-300
2.3 Top-left edge highlight (optional):
    - before pseudo with linear-gradient mask for subtle glow
    - skip if visual impact unclear

## Faz 3 — Typography + spacing (~1h)
3.1 Geist already loaded — verify and bump letter-spacing for headings:
    - h1/h2: tracking-tight
    - body: feature-settings "cv11", "ss01" for premium glyphs
3.2 KPI card text: text-3xl font-bold tracking-tight (currently text-2xl)
3.3 Section gaps: gap-6 (currently gap-4 in some places)

## Faz 4 — Sidebar refinement (~1.5h)
4.1 Active item neon left bar:
    - 3px indigo gradient via inset box-shadow or before pseudo
4.2 Hover glow:
    - bg-indigo-500/5 hover:bg-indigo-500/10 with text-indigo-400 transition
4.3 Section divider polish ("ADMIN" label):
    - tracking-[0.2em] text-[10px] uppercase font-semibold

## Faz 5 — KPI cards + status dots (~1h)
5.1 KpiCard variant (existing component in subcontractors/page.tsx and
    budget/page.tsx) — verify the global Card upgrade flows through
5.2 Status dots with pulse animation:
    - <span className="relative flex h-2 w-2"> + ping animation
    - Used next to active subcontractor status badges
5.3 Skip trend delta arrows (no time, plan-future)

## Faz 6 — Buttons + inputs polish (~45m)
6.1 Primary button:
    - bg-gradient-to-r from-indigo-500 to-indigo-600
    - hover:shadow-[0_0_20px_rgba(99,102,241,0.4)] (neon glow)
    - active:scale-95
6.2 Input focus state:
    - focus-visible:ring-2 focus-visible:ring-indigo-500/50
    - bg-background/50 backdrop-blur-sm

## Faz 7 — Final polish + browser test (~1h)
Walk every page in BOTH themes:
- /dashboard (if exists)
- /projects
- /projects/1/budget (3 tabs)
- /subcontractors (with charts)
- /subcontractors/1
- /subcontractors/1/contracts/1
- /settings/budget-categories

Check:
- Cards have glass + lift on hover
- Background mesh visible in both modes
- Sidebar neon active works
- Charts readable (tooltips, axis labels)
- Modals/dialogs have glass backdrop
- Form inputs have focus glow
- Light mode: not too washed out
- Skeletons: still visible against new bg

## Faz 8 — Commit (~15m)
feat(day9-theme): premium dark theme overhaul (glass, mesh gradient, neon)

## Risks
- Tailwind v4 utilities may behave differently for arbitrary values like
  hover:shadow-[0_0_20px_rgba(...)] — fallback to defined shadow utilities
- backdrop-blur on Safari needs -webkit-backdrop-filter prefix (autoprefixer
  should handle, verify in Faz 7)
- Mesh gradient performance: monitor first-paint with React DevTools profiler
- Dark/light contrast: WCAG AA compliance kept (4.5:1 text on bg)
