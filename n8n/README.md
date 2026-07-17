# n8n workflows

The automation layer of Tasador SD: n8n sits at the **edges** of the
product (alerts, reports, monitoring) and never inside it. The rule is
strict on purpose: no ML logic, no feature engineering and no schema
knowledge lives in a workflow -- workflows only read Supabase through
PostgREST and call the public appraisal API, so they can never drift
from the model.

```
Python agent (discovery.py + agent.py)      <- collects data (scheduled outside n8n)
        v
Supabase (listings, listing_prices)         <- single source of truth
        v
n8n workflows (this folder)                 <- product layer: alerts + reports
        v
Telegram                                    <- delivery
```

## Workflows

| File | Schedule | What it does |
|---|---|---|
| `workflows/gangas-telegram.json` | hourly | Appraises listings first seen in the last 24h against the live API and sends a Telegram alert for each one asking below 85% of the model's estimate. A tasador gets consulted once; a bargain feed gets paid for monthly -- this is the retention product. |
| `workflows/monitor-ingesta.json` | daily 8:00 | Alerts if not a single listing entered in 7 days. A collector that died three weeks ago unnoticed is worse than no collector. |
| `workflows/resumen-semanal.json` | Sunday 19:00 | Aggregates the active market by sector (count, new this week, average, range) into one Telegram message. This is the seed of the monthly per-sector price report for real-estate agencies. |

## Prerequisites

1. **Migration 0005 applied** (`supabase/migrations/0005_listing_history.sql`)
   -- the workflows read `is_active` / `first_seen`, which it adds.
2. **Some real listings collected** (`agents/listings-agent`, see its README).
3. **Node.js 20.19-24.x** (already required by `apps/web`).

## Running n8n locally (free)

```bash
npx n8n          # try it without installing
# or, persistent:
npm install -g n8n
n8n
```

Open http://localhost:5678. n8n stores its data (SQLite + encryption
key) in `~/.n8n` -- on Windows that is `C:\Users\<you>\.n8n`, which is
already outside OneDrive, exactly where it should be.

Behind a TLS-inspecting network (campus): if n8n or npm fail on HTTPS,
export the network's root certificate and point Node at it with
`NODE_EXTRA_CA_CERTS=C:\path\to\root-ca.pem` (same problem truststore
solves for the Python side).

## Importing the workflows

UI: **Workflows > ⋯ > Import from File** and pick each JSON, or:

```bash
n8n import:workflow --input=n8n/workflows/gangas-telegram.json
n8n import:workflow --input=n8n/workflows/monitor-ingesta.json
n8n import:workflow --input=n8n/workflows/resumen-semanal.json
```

Then wire the two credentials (create each once, reuse everywhere):

1. **Supabase API** -- host `https://rprhpgopebqgpeodixpy.supabase.co`,
   secret = the `service_role` key (dashboard > Project Settings > API
   keys). Assign it to every "(Supabase)" HTTP Request node. Service
   role is required: `listings` has RLS with no policies.
2. **Telegram** -- a bot token from @BotFather. Assign it to every
   Telegram node and replace `REPLACE_WITH_YOUR_CHAT_ID` with your chat
   id (send the bot a message, then check
   `https://api.telegram.org/bot<TOKEN>/getUpdates`).

Finally, toggle each workflow **Active**.

## Two honest caveats

- **Schedules only fire while n8n is running, and missed runs are NOT
  backfilled** (no catch-up in the Schedule Trigger). On a laptop that
  sleeps, expect gaps in the hourly bargain scan -- acceptable for
  alerts, not for collection. That is why ingestion itself stays in
  Python (GitHub Actions cron or Task Scheduler), outside n8n.
- **n8n Cloud is not needed.** Self-hosted Community Edition is free;
  the cloud Starter plan (~EUR 20-24/month) buys always-on schedules,
  which only makes sense once a paying client depends on these alerts.

## Editing workflows with Claude Code (optional)

n8n ships an instance-level MCP server (Settings > Instance-level MCP;
workflow-builder tools need n8n >= 2.18.4). Once enabled:

```bash
claude mcp add --transport http n8n-mcp http://localhost:5678/mcp-server/http
```

Claude Code can then list, build and edit workflows on this instance
directly. Never trust a generated workflow without executing it once.
