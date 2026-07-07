# Rental Listings Agent — Santo Domingo, DR

An autonomous agent built on the Anthropic API that collects real
rental listings from Santo Domingo classifieds and turns them into a
clean, validated CSV — the exact training contract of
[rental-price-estimator-sd](https://github.com/Criscarr26/rental-price-estimator-sd),
whose deployed demo currently runs on synthetic data. This project is
the "real scraped data" item of that roadmap, turned into working code.

## Why an agent instead of a classic scraper

A classic scraper hardcodes CSS selectors and breaks when the site
changes. Here the LLM is the extractor: the agent receives a goal
("save N complete listings"), three tools, and decides by itself which
pages to visit and what to extract from raw page text. The whole system
is the loop:

```
        ┌────────────────────────────────────────────────┐
        │  Claude (claude-haiku-4-5 by default)          │
        │  goal + rules + page text -> next action       │
        └───────┬────────────────────────────────────────┘
                │ tool calls                 ▲ tool results
                ▼                            │
   ┌────────────────────┐   ┌────────────────────┐   ┌──────────────┐
   │ fetch_url          │   │ save_listing       │   │ finish_run   │
   │ robots.txt gate    │   │ schema validation  │   │ run summary  │
   │ rate limit (3 s)   │   │ range checks       │   └──────────────┘
   │ HTML -> clean text │   │ dedupe by URL      │
   └────────────────────┘   └─────────┬──────────┘
                                      ▼
                          data/rentals_real.csv
```

Design decisions worth reading in the code:

- **Guardrails live in the tools, not in the prompt** (`tools.py`):
  robots.txt is checked before every request, fetches are rate-limited
  to one every 3 seconds, and pages are stripped of markup and capped
  at 18k characters before reaching the model. The model cannot skip
  any of this.
- **Hard budget caps** (`--max-fetches`, `--max-turns`): a run has a
  worst-case cost you set in advance. The run report prints tokens
  used and the estimated cost in USD.
- **Context pruning**: pages already processed are cleared from the
  conversation after two turns — dead weight in the context window is
  dead weight in the bill.
- **Honest data only** (`schema.py`): a listing is saved only if the
  core fields are explicit in the page (price in DOP, area, bedrooms,
  bathrooms, known sector). Missing age or price in USD only? The
  listing is skipped, never guessed. Every row keeps its `source_url`.

## Responsible scraping

- robots.txt is enforced automatically per domain.
- One request every 3 seconds, identifiable User-Agent, tiny volumes
  (dozens of pages per run), public data, educational use.
- **Site survey (July 2026):** SuperCasas serves listing detail pages
  as server-rendered HTML on paths its robots.txt allows (only
  `/buscar/`, `/buscador/` and `/vender/` are disallowed — the agent
  never touches them; the gate refuses if it tries). Corotos was
  evaluated and dropped for v1: its result pages render client-side,
  so plain HTTP sees no listings (see Roadmap).

## Data contract

Output CSV columns (the estimator selects its features by name, so the
extra provenance column is harmless):

| Column | Type | Rule |
| ------ | ---- | ---- |
| sector | str | one of the 10 sectors the estimator knows |
| area_m2 | int | 15–1000, explicit in the listing |
| bedrooms | int | 0–10, explicit |
| bathrooms | int | 1–10, explicit (half baths round down) |
| parking_spots | int | 0–10; 0 when not mentioned |
| furnished | 0/1 | 1 only if "amueblado" |
| age_years | int | 0–80, from explicit construction year only |
| price_dop | int | 5,000–1,000,000 DOP per month, explicit |
| source_url | str | provenance of every row |

## Setup

Requires Python 3.10+.

```
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env          # then paste your Anthropic API key in .env
```

Networks with TLS inspection (corporate/university) are already
handled: the code injects the OS certificate store via `truststore`.

## Usage

```
python agent.py --dry-run                  # full pipeline offline: no key, no network, no cost
python agent.py --target 20                # live run against SuperCasas
python agent.py --target 30 --max-fetches 40 --model claude-sonnet-5
```

Every run ends with a report: listings saved/rejected, pages fetched,
tokens in/out and estimated cost. A typical 20-listing run with the
default model costs a few cents.

## Feeding the estimator

```
copy data\rentals_real.csv ..\rental-price-estimator-sd\data\rentals_sd.csv
cd ..\rental-price-estimator-sd
python train.py
```

Same schema, zero code changes in the estimator — that contract is the
point of both projects.

## Roadmap

- Corotos support through its listings sitemap or a headless browser
  runtime (its search results are client-side rendered).
- Incremental collection runs on a schedule, deduplicated by URL.
- Price-drift report: synthetic model vs. real-data model metrics.
