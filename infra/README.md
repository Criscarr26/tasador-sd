# infra/ — Deployment & operations

The operational layer of the product: how it is deployed, what runs where,
and how to keep it healthy. This directory documents operations; the
deployment artifacts themselves live where their platforms require them
(noted below).

## Deployment topology

The whole product runs on **free tiers** (~US$0/month until paying volume
justifies upgrades).

| Piece | Platform | Source | Notes |
|---|---|---|---|
| **Web** (`apps/web`) | Vercel (project `tasador-sd-xlo2`) | Root Directory `apps/web` | [tasadorsd.vercel.app](https://tasadorsd.vercel.app) |
| **API** (`api/index.py`) | Vercel (project `tasador-sd`) | repo root + `vercel.json` | serverless Python; predicts from exported weights |
| **API** (container, alt) | any container host / HF Spaces | root `Dockerfile` | scikit-learn on uvicorn; identical contract |
| **Database + Auth** | Supabase (free) | `supabase/migrations/` | Postgres + RLS |
| **Data services** | on-demand / cron | `services/` | not part of the Vercel deploy |

Both API backends serve the identical contract, guaranteed by the parity
test in CI. Every push to `main` redeploys web and API automatically.

## Why the deploy files are not physically inside infra/

These paths are **location-locked by their platforms** — moving them
breaks production, so they stay put and are documented here instead:

- `vercel.json` (repo root) — configures the serverless function and
  bundles `ml/training/models/model_params.json` into it.
- `api/index.py`, `requirements.txt` (root) — the serverless entrypoint
  Vercel detects.
- `Dockerfile` (root) — the container build context for self-host.
- `.github/workflows/ci.yml` — must live under `.github/workflows/`.

See [docs/PRODUCTION-STRUCTURE.md](../docs/PRODUCTION-STRUCTURE.md) for the
full rationale, and [docs/DEPLOY.md](../docs/DEPLOY.md) for step-by-step
setup.

## Environments & configuration

| Variable | Where | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | API (Vercel) | Browser origins allowed to call the API (CORS) |
| `RATE_LIMIT_PER_MINUTE` | API (Vercel), default 60 | Per-IP throttle; `0` disables |
| `NEXT_PUBLIC_API_URL` | Web (Vercel) | API base URL |
| `NEXT_PUBLIC_SUPABASE_URL` / `_ANON_KEY` | Web (Vercel) | Supabase (publishable key only) |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | `services/listings-agent/.env` | Service-role, **never shipped to clients** |
| `ANTHROPIC_API_KEY` | `services/listings-agent/.env` | Data-collection agent |

Secrets live only in platform env stores and local `.env` files
(gitignored). No secret is committed — verified.

## Operations runbook

- **Deploy** — push to `main`; Vercel builds both projects. CI must be
  green first (see [ci-cd/README.md](ci-cd/README.md)).
- **Database change** — add a numbered migration in `supabase/migrations/`
  and run it in the SQL Editor **in order** before the code that needs it.
- **Model update** — retrain (`ml/training`), commit artifacts, push; the
  content-hash version changes and clients pick it up automatically.
- **Rollback** — revert the commit and push; Vercel redeploys the previous
  state. Database migrations are forward-only; write a compensating
  migration rather than editing an applied one.
- **Rate-limit tuning** — if legitimate users hit 429, raise
  `RATE_LIMIT_PER_MINUTE` in the API project's env and redeploy (no code
  change).

## Hardening status

Security posture (RLS, rate limiting, CSP, secrets) is tracked in
[SECURITY.md](../SECURITY.md). Open operational items (observability,
uptime monitoring, backups verification) are Fase 2 of the
[scalability roadmap](../docs/SCALABILITY-ROADMAP.md).
