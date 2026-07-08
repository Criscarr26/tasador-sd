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

## 2. API (Hugging Face Spaces, free)

1. Create a Space at huggingface.co > New Space > SDK: **Docker**.
2. Push this repository to the Space (or upload `Dockerfile`,
   `packages/core_py`, `apps/api` and `ml/training/models`).
3. The `Dockerfile` at the repo root serves the API on port 7860.
4. Set the CORS allowlist to your web origins (Space settings > Variables):
   `ALLOWED_ORIGINS=https://YOUR-WEB.vercel.app`
   (without it, only http://localhost:3000 may call the API from a browser).
5. Optional: tune `RATE_LIMIT_PER_MINUTE` (default 60 requests/IP/min; 0
   disables). The limit is per instance — see the audit for the
   Redis-backed version needed once the API scales horizontally.
6. Verify: `https://YOUR-SPACE.hf.space/health` returns the model version.

Alternative: Render free web service with the same Dockerfile (set the
port to 7860 or override the CMD).

## 3. Web (Vercel, free)

1. vercel.com > New Project > import the GitHub repo.
2. **Root Directory: `apps/web`** (critical in a monorepo).
3. Environment variables:
   - `NEXT_PUBLIC_API_URL` = the API URL from step 2
   - `NEXT_PUBLIC_SUPABASE_URL` = your Supabase project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = the publishable key
4. Deploy. Every push to `main` redeploys automatically.

## 4. Mobile (Expo)

In the mobile repo's `.env`, point the app at the deployed API so its
weights stay in sync with the served model:

```
EXPO_PUBLIC_MODEL_API_URL=https://YOUR-SPACE.hf.space
```

## 5. Agent (optional, manual or scheduled)

With `0002` applied, set in `agents/listings-agent/.env`:

```
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>   # never ship this to clients
```

Then `python agent.py --site supercasas --target 20 --sink supabase`.
A GitHub Actions cron can run this on a schedule when collection
becomes recurring; budgets inside the agent cap the cost of any run.
