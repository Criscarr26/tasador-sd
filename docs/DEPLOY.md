# Deployment guide

Everything runs on free tiers. Order matters: database first, then the
API, then the clients that point at it.

## 1. Database (Supabase)

The project already runs on a Supabase instance. To bring a fresh one
(or the current one) up to date, run each file in
`supabase/migrations/` **in order** from the dashboard SQL Editor:

1. `0001_saved_estimates.sql` — appraisal history + RLS (already applied
   in the current production project).
2. `0002_listings.sql` — agent listings table (service-role only).
3. `0003_plans_usage.sql` — profiles, plans and monthly usage limits.
4. `0004_estimate_constraints.sql` — value CHECK constraints on the
   appraisal history (defense in depth against tampered clients).

Also disable **Authentication > Sign In / Up > Email > Confirm email**
for frictionless demo signups, or leave it on for real deployments.

## 2. API (Vercel serverless, free, no credit card)

The API deploys as a Python serverless function (`api/index.py`). It
predicts from the exported model weights (no scikit-learn/pandas), so it
fits a free serverless tier and returns numbers identical to the
container version (guaranteed by the parity contract test).

1. vercel.com > Add New > Project > import the `tasador-sd` GitHub repo.
2. **Root Directory: leave as the repo root (`./`)**; Framework Preset:
   **Other**. Vercel detects `api/index.py` + `requirements.txt` and
   `vercel.json`.
3. Environment variables (Project Settings > Environment Variables):
   `ALLOWED_ORIGINS=https://YOUR-WEB.vercel.app` — the web origin(s) that
   may call the API from a browser (add it after step 3 below). Without
   it, only http://localhost:3000 is allowed.
4. Deploy. Verify: `https://YOUR-API.vercel.app/health` returns the model
   version, and `POST /v1/appraisals` returns an estimate.

Self-host alternative (container): the repo also ships a `Dockerfile` and
`apps/api` (the scikit-learn version on uvicorn, with per-IP rate
limiting). Use it on any container host — build from the repo root and
serve port 7860. Both backends serve the identical contract.

## 3. Web (Vercel, free)

1. vercel.com > Add New > Project > import the same repo again (a second
   Vercel project).
2. **Root Directory: `apps/web`** (critical in a monorepo).
3. Environment variables:
   - `NEXT_PUBLIC_API_URL` = the API URL from step 2
   - `NEXT_PUBLIC_SUPABASE_URL` = your Supabase project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = the publishable key
4. Deploy. Then set the API's `ALLOWED_ORIGINS` to this web URL and
   redeploy the API. Every push to `main` redeploys automatically.

## 4. Mobile (Expo)

In the mobile repo's `.env`, point the app at the deployed API so its
weights stay in sync with the served model:

```
EXPO_PUBLIC_MODEL_API_URL=https://YOUR-API.vercel.app
```

## 5. Data-collection service (optional, manual or scheduled)

With `0002` applied, set in `services/listings-agent/.env`:

```
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>   # never ship this to clients
```

Then `python agent.py --site supercasas --target 20 --sink supabase`.
A GitHub Actions cron can run this on a schedule when collection
becomes recurring; budgets inside the agent cap the cost of any run.
