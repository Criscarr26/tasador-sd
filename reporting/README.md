# Reporting

Power BI reads this project; this folder is what git keeps of it.

A `.pbix` is a binary archive: it cannot be diffed, reviewed in a pull
request, or merged when two changes meet. So the `.pbix` stays out of git and
the parts worth versioning live here as plain text — every Power Query
expression and every DAX measure. Rebuilding the report from this folder is a
paste job, not an excavation.

## What the report reads today

`ml/training/models/model_params.json`, an artefact already committed to this
repository. No database, no credentials, no network. Six queries turn it into
tables.

### Read this before showing the report to anyone

The model behind that file was trained on **synthetic data**:
`ml/training/generate_data.py` builds 500 rows from `np.random.seed(42)`. The
published metrics — MAE 3,983 · RMSE 6,749 · R² 0.9283 — measure how well the
regression recovers its own generator, not how well it predicts rents in Santo
Domingo.

The report therefore describes **the model**, not the market. Label every page
that way. Nothing here changes when real data arrives: once `listings` holds
scraped rows and `train.py` runs against them, these same queries read the same
file, which will then mean something.

## Setting it up

1. Power BI Desktop → **Home → Transform data**.
2. **New Source → Blank Query** for each file in `queries/`, in numeric order.
   Open the Advanced Editor, paste the file, and rename the query to the name
   in its header comment. Order matters: later queries call earlier ones by
   name.
3. Edit the single line in `RepoRoot` to point at this repository on your
   machine.
4. **Close & Apply**.
5. Create the six what-if parameters listed at the top of
   `measures/appraiser.dax`, then paste the measures.

## The appraiser page

A linear regression's exported weights reproduce a full appraisal with
arithmetic alone, so `measures/appraiser.dax` prices a property in DAX: move
the sliders, pick a sector, get a number — with no call to the API.

`measures/reference-check.dax` is what keeps that honest. `model_params.json`
ships three reference appraisals with their expected prices, and the API and
the TypeScript port are both tested against them in CI. The check recomputes
them in DAX and flags any row that misses by more than a cent. If this report
ever drifts from the model the product serves, that page says so instead of
quietly showing confident wrong numbers.

## Connecting to Supabase later

When the database pages arrive, do not use the connection string the Supabase
dashboard shows by default. Measured on 1 November 2026:

    db.rprhpgopebqgpeodixpy.supabase.co   AAAA record only, no A record
    this network                          no global IPv6, no IPv6 route out
    port 5432, direct                     unreachable

Use the Supavisor pooler in **session** mode, which answers over IPv4 on ports
5432 and 6543. Take the exact hostname from the dashboard's **Connect** button
rather than guessing the region, and connect as a read-only role — never as
`postgres`.

Import mode, not DirectQuery: the data changes slowly and the free tier does
not want the query load.

## Layout

    queries/    Power Query (M), one query per file, numbered by load order
    measures/   DAX measures and calculated columns
    exports/    dated PDF/PNG exports, ignored by git

## What Power BI is not for here

Power BI Service will not host this: publishing and sharing require a work or
school account, and embedding a report for paying customers starts at a Fabric
capacity. Dashboards that customers see belong in `apps/web`, on the
deployment that already exists.
