# Changelog

## 0.2.0 — 2026-07-13

Market history + automation layer: the collector becomes a flywheel
(sitemap discovery, price trajectories, rented-signal flags) and n8n
turns the data into products (bargain alerts, ingest monitoring,
weekly market summaries).

### Added
- `supabase/migrations/0005_listing_history.sql`: `listing_prices`
  (price trajectory per listing, snapshotted by trigger on every price
  change), `first_seen`/`last_seen`/`is_active` sighting metadata on
  `listings`, and the `listing_queue` table that decouples discovery
  from collection.
- `agents/listings-agent/discovery.py`: sitemap-based discovery.
  SuperCasas disallows its paginated search (`/buscar/`) in robots.txt,
  so discovery reads the sitemap the site advertises there (~17.5k
  URLs), keeps apartment detail pages in the 10 known sectors (~3.9k)
  and feeds the queue. Each sync also flips `is_active` off for
  listings that left the sitemap — a weak "rented" label.
- `agent.py --from-queue N`: pulls pending queue URLs as direct seeds
  (no navigation overhead) and records per-URL outcomes with retry
  (3 attempts) for failed fetches.
- `n8n/`: importable workflows — hourly bargain alerts to Telegram
  (asking price < 85% of the model estimate), daily dead-pipeline
  monitor, and a weekly per-sector market summary (the seed of the
  agency price report) — plus a README covering free self-hosted
  setup, credentials and the n8n MCP server for Claude Code.
- `tests/test_discovery.py`: pins the discovery filter (the legal
  boundary of collection) with real URL shapes from the July 2026
  sitemap survey.

### Changed
- The Supabase sink now upserts with merge semantics: re-sighted
  listings refresh `last_seen`/`is_active`, and price changes create
  `listing_prices` snapshots via the migration's trigger. Re-saving an
  already-collected listing is no longer an error — it refreshes its
  market data. Apply migration 0005 before the next `--sink supabase`
  run.

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
