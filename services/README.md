# services/ — Automation & data flywheel

This layer is what turns product usage into a compounding asset. It sits
at the **edges** of the product: it feeds and monitors the data, but no ML
logic and no domain knowledge live here — that belongs to `tasador-core`.

```
Real listings  ──▶  listings-agent  ──▶  Supabase (single source of truth)  ──▶  n8n  ──▶  product value
 (SuperCasas)       collect + validate     listings · price history                alerts · reports
```

## Services

### `listings-agent/` — data collection

An autonomous agent (Anthropic tool use) that collects real rental
listings from Santo Domingo classifieds and validates them against the
model's exact schema. Guardrails live in the tools, not the prompt:
robots.txt is enforced per request, fetches are rate-limited, and only
listings with explicit core fields are saved. Budgets cap the cost of any
run. It writes validated listings and price snapshots into Supabase.

- **Why an agent, not a scraper:** the LLM is the extractor, so a site
  layout change doesn't break a hardcoded parser.
- **Runs outside n8n** (cron / GitHub Actions / Task Scheduler) so missed
  schedules don't create silent gaps in collection.
- See [`listings-agent/README.md`](listings-agent/README.md).

### `n8n/` — product automation

Importable n8n workflows that turn the collected data into product value,
delivered via Telegram:

- **Bargain alerts** — listings asking below 85% of the model estimate.
- **Ingest monitor** — alerts if collection stalls.
- **Weekly market summary** — per-sector aggregation; the seed of the
  monthly agency price report (the first paid product).

Workflows only read Supabase (PostgREST) and call the public appraisal
API, so they can never drift from the model. See
[`n8n/README.md`](n8n/README.md).

## The business case

A tasador is consulted once; a **bargain feed and a trends report are paid
for every month**. The price-history snapshots this layer produces are the
proprietary market index that makes recurring revenue defensible. This is
Fase 4 of the [scalability roadmap](../docs/SCALABILITY-ROADMAP.md).

## Operational note

Neither service is part of the Vercel deploy — they run on demand or on a
schedule, independent of the live web/API. That isolation is deliberate:
the product stays up regardless of the data pipeline's state.
