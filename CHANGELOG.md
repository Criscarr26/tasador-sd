# Changelog

## 0.1.0 — 2026-07-08

First unified release: three standalone projects (Streamlit estimator,
data-collection agent, Expo mobile app) become one platform.

### Added
- `packages/core_py` (**tasador-core**): single source of truth for the
  domain — features, sectors, validation ranges, pipeline build/predict
  and weight export. Includes the parity contract test that keeps every
  client port honest against the sklearn pipeline.
- `apps/api`: FastAPI inference core. `POST /v1/appraisals` (validation,
  appraisal, confidence range, sector delta) and `GET /v1/model/params`
  (weights versioned by content hash). 5 contract tests.
- `apps/web`: commercial web app (Next.js 16). Landing with live
  appraiser backed by the API, market panorama per sector, and a
  history page sharing the same Supabase account and data as the
  mobile app. Design tokens shared with mobile.
- `agents/listings-agent`: now imports tasador-core and gained
  `--sink supabase` to mirror validated listings into Postgres
  (service-role, upsert by source URL).
- `ml/training`: training now emits `model_params.json` in the same run
  (no manual export step can drift the clients).
- `supabase/migrations`: formal history — appraisal history with RLS
  (0001), agent listings (0002), plans + monthly usage limits enforced
  by database triggers (0003).
- CI (GitHub Actions): core + API contract tests and the web
  production build on every push.
- `Dockerfile` for the API (Hugging Face Spaces / any container host)
  and a deployment guide in `docs/DEPLOY.md`.

### Security
- API: per-IP sliding-window rate limit (`RATE_LIMIT_PER_MINUTE`,
  default 60), structured request logging, CORS restricted to an
  allowlist (`ALLOWED_ORIGINS`), and security headers (CSP, nosniff,
  `X-Frame-Options`, HSTS, Referrer-Policy).
- Web: full security-header set via `next.config.ts` (CSP with
  `connect-src` limited to Supabase and the API, `frame-ancestors 'none'`,
  Permissions-Policy, HSTS).
- Hardened container: non-root user, dependency install layer cached,
  `.dockerignore` keeps secrets and `node_modules` out of the build.
- `0004_estimate_constraints.sql`: value CHECK constraints on the
  appraisal history as defense in depth behind RLS.
- `SECURITY.md` with the disclosure process and security model.

### Fixed
- Validation ranges had diverged across clients (area 20–500 on web,
  20–1000 on mobile, 15–1000 in the agent); resolved product-wide in
  tasador-core with documented decisions.
- The agent's dry-run fixture was misnamed, so its simulated fetch had
  always failed silently.

### Related
- Mobile app (separate demo repo):
  https://github.com/Criscarr26/rental-estimator-mobile — gained cloud
  auth with `processLock`, automatic appraisal history, and model
  weight sync from the API with bundled fallback.
