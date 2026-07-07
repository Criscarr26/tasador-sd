# Tasador SD

Unified platform for the Santo Domingo rental appraisal product: one domain
contract, one data plane and (soon) one API serving every client.

This monorepo is the convergence of three formerly independent projects:
the [web estimator](https://github.com/Criscarr26/rental-price-estimator-sd)
(Streamlit, stays as public demo), the
[mobile app](https://github.com/Criscarr26/rental-estimator-mobile) (Expo +
Supabase) and the
[listings agent](https://github.com/Criscarr26/rental-listings-agent)
(autonomous data collection).

## Structure

```
packages/core_py/    tasador-core: schema, sectors, validation ranges and
                     model helpers -- the single source of truth that used
                     to be duplicated (and had already diverged) across
                     the three projects
ml/training/         training pipeline; one run produces every runtime
                     artifact: .pkl (API/web), metrics.json and
                     model_params.json (clients without scikit-learn)
agents/listings-agent/  data agent; writes CSV locally and can mirror
                     validated listings to the shared Postgres (--sink supabase)
supabase/migrations/ formal migration history for the shared database
apps/api/            FastAPI inference core: POST /v1/appraisals and
                     GET /v1/model/params (versioned weights that keep
                     on-device clients in sync with the served model)
apps/                (upcoming) commercial web app
```

## Verified invariants

- `packages/core_py/tests`: schema validation + the export contract
  (exported plain weights reproduce the sklearn pipeline exactly).
- `ml/training/train.py` reproduces the deployed model's metrics
  (MAE RD$3,983 / RMSE RD$6,749 / R2 0.928) and emits `model_params.json`
  byte-equivalent to the one shipped in the mobile app.
- `agents/listings-agent`: `python agent.py --dry-run` exercises the full
  pipeline offline (fixture fetch, validation, CSV, budgets, report).
- `apps/api/tests`: the API's appraisals reproduce the exported reference
  predictions exactly, and invalid inputs are rejected with the shared
  validation messages. Verified live end-to-end: the mobile app syncs
  weights from GET /v1/model/params and appraises with them.

## Development setup

Each Python component runs in its own venv. `tasador-core` has zero hard
dependencies; install it into a venv with:

```
pip install -e packages/core_py
```

Run the core tests:

```
cd packages/core_py
python -m unittest discover tests -v
```

## Database

Migrations live in `supabase/migrations` and are applied in order in the
Supabase SQL Editor. `0001` is the baseline already in production;
`0002` adds the `listings` table (service-role only, no RLS policies) that
the agent writes to with `--sink supabase`.
