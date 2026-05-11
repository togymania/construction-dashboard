# Production Deployment Notes

Deployed May 11, 2026. This file captures the live URLs, ops procedures,
and the workarounds we hit during the initial deploy — so the next time
you (or anyone else) needs to touch production, you don't re-discover
the same things from scratch.

## Live URLs

| Component | URL |
|---|---|
| Frontend (Vercel) | https://monotek-stroy-pm.vercel.app |
| Backend (Render)  | https://monotek-stroy-pm-api.onrender.com |
| API docs          | https://monotek-stroy-pm-api.onrender.com/docs |
| Health check      | https://monotek-stroy-pm-api.onrender.com/health |
| Database (Neon)   | `ep-purple-unit-alaf32f1.c-3.eu-central-1.aws.neon.tech` (Frankfurt) |

All three are on free tiers.

## Hosting accounts

- GitHub: `togymania/construction-dashboard` (public — Render free tier
  requires it; backend `.env` is gitignored)
- Vercel team: `togymanias-projects` (Hobby plan)
- Render workspace: `My Workspace` (Free plan)
- Neon project: `neondb` on Frankfurt (Free plan)

## Auto-deploy flow

- Push to `main` on GitHub
- Render auto-deploys backend from `backend/` (per `render.yaml`)
- Vercel auto-deploys frontend from `frontend/` (Next.js preset)
- Both build logs are visible in their respective dashboards

## Render free-tier quirks

- **Cold start**: spins down after 15 min idle. First request takes
  3–50 s to wake. The browser fetch can show "Failed to fetch" /
  "blocked by CORS" during the cold start — it's just the request
  timing out before CORS headers come back, NOT a real config issue.
  Hit `/health` first to wake the dyno if you're debugging.
- **No shell**: free tier doesn't give web shell or SSH. For ad-hoc
  DB ops use the Neon SQL Editor instead.
- **No persistent disk**: uploads land in `./uploads` and disappear
  on restart. Extracted data is persisted to Postgres, so the demo UX
  impact is small. If you need persistence later, upgrade to Starter
  ($7/mo) and re-add a disk to `render.yaml`.

## Environment variables (Render backend)

Stored in Render dashboard → Environment. Secrets marked `sync: false`
in `render.yaml`:

| Key | Notes |
|---|---|
| `PYTHON_VERSION` | `3.12.7` (rapidfuzz 3.10.1 doesn't build on 3.13) |
| `ENVIRONMENT` | `production` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` |
| `LLM_TIMEOUT_SECONDS` | `120` |
| `MAX_PDF_SIZE_MB` | `100` |
| `MAX_LEDGER_IMPORT_MB` | `25` |
| `MAX_IMPORT_FILE_SIZE_MB` | `10` |
| `UPLOADS_DIR` | `uploads` |
| `DATABASE_URL_OVERRIDE` | Neon connection string with `?sslmode=require` |
| `ANTHROPIC_API_KEY` | (secret) |
| `SECRET_KEY` | (secret, JWT signing) |
| `CORS_ORIGINS` | comma-separated, includes vercel.app + localhost:3000 |

The Vercel-side env vars (Project Settings → Environment Variables):

| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://monotek-stroy-pm-api.onrender.com` (no `/api/v1` suffix — `api-client.ts` appends it) |

## Initial deploy gotchas (resolved)

These all bit us once and are fixed now, but worth knowing about for
similar future deploys:

1. **`disks are not supported for free tier`** — removed the `disk:`
   block from `render.yaml`. Uploads are ephemeral.
2. **`rapidfuzz==3.10.1` metadata-generation-failed on Python 3.13** —
   pinned `PYTHON_VERSION=3.12.7`.
3. **`ImportError: email-validator is not installed`** — pydantic
   `EmailStr` needs it. Added to `requirements.txt`.
4. **Anthropic SDK 0.39 + httpx 0.28 incompat (`proxies` kwarg)** —
   bumped to `anthropic>=0.40`.
5. **Vercel created the project as "Other" / "Services" preset** —
   monorepo detection lumped frontend+backend together. Switched
   Framework Preset to Next.js and set Root Directory to `frontend`.
6. **Vercel Authentication blocking public access (404 NOT_FOUND)** —
   disabled in Project Settings → Deployment Protection.
7. **`NEXT_PUBLIC_API_URL` set with `/api/v1` suffix duplicated the
   path** — `api-client.ts` constructs `${API_BASE_URL}/api/v1` itself,
   so env should be the base URL only.
8. **Recharts `<Tooltip formatter={(value: number)=>...}>` failed
   prod TS build** — Recharts types the formatter arg as
   `ValueType | undefined`. Dropped the annotation and coerced
   with `Number(value) || 0`.
9. **Zod schemas with `.transform()` broke `useForm<T>`** —
   `z.infer` returns the *output* (post-transform) type. Need
   `z.input` for the form type and `z.output` for `handleSubmit`.
   Pattern: `useForm<Input, unknown, Output>({...})`.
10. **CORS preflight returning 405 with no headers** — root cause was
    actually transient; whatever the trigger, `allow_origin_regex`
    matching any `monotek-stroy-pm*.vercel.app` is a reliable
    fallback regardless of how the explicit list is loaded.
11. **`ValueError: password cannot be longer than 72 bytes` crashing
    register** — passlib 1.7.4's startup detection probes bcrypt with
    a long string. bcrypt 4.0 changed that ValueError from silent
    truncation. Pinned `bcrypt==3.2.2`.

## Operational recipes

### Create a new user

The frontend's `/register` page works — visitors land as
`VIEWER` role.

### Promote a user to admin

Free tier has no shell, so use Neon's SQL Editor. The Postgres enum
stores the *name* (`'ADMIN'`), not the value (`'admin'`):

```sql
UPDATE users SET role = 'ADMIN' WHERE email = 'someone@example.com';
```

After updating, the user has to log out and back in to get a fresh
JWT that reflects the new role.

### Rotate the Anthropic API key

1. Generate a new key at https://console.anthropic.com
2. Render dashboard → Environment → `ANTHROPIC_API_KEY` → Edit
3. Save (Render auto-redeploys)
4. Revoke the old key in the Anthropic console

### Update CORS origins

1. Render dashboard → Environment → `CORS_ORIGINS` → Edit
2. Comma-separated, no spaces, no trailing slashes
3. Save → auto-redeploy
4. The `allow_origin_regex` in `app/main.py` covers any
   `monotek-stroy-pm*.vercel.app` so branch/preview deploys work
   even if you forget to add them here.

### Force a redeploy

- Render: Manual Deploy → Deploy latest commit (or Clear build cache & deploy)
- Vercel: Deployments → "..." menu on the latest → Redeploy

### Tail logs

- Render: `Logs` tab. Free tier supports tail + search.
- Vercel: `Logs` (Runtime) or per-deployment `Build Logs`.

### Smoke-test the stack

```js
// In any browser console (no auth needed for these endpoints)
fetch('https://monotek-stroy-pm-api.onrender.com/health')
  .then(r => r.json()).then(console.log)
// → {"status":"ok","service":"construction-api","environment":"production"}
```

If `/health` is slow (>3 s) the dyno was asleep — that's fine, second
request will be instant.

## What's NOT set up yet

- Custom domain (currently using the `*.vercel.app` and
  `*.onrender.com` subdomains)
- Monitoring / alerting (Render's free metrics are basic)
- Automated backups for Neon (Neon has point-in-time recovery on
  the paid plan; free plan keeps ~24h of history)
- Production seed data (`seed_admin` / `seed_projects` only run
  locally; production starts with an empty DB)
- CI on PRs (only auto-deploy on `main`)
