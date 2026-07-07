"""Autonomous agent that collects real Santo Domingo rental listings.

The agent is a tool-use loop around the Anthropic API: it gets a goal
(save N complete listings), three tools (fetch_url, save_listing,
finish_run) and decides by itself which pages to visit and what to
extract. Hard budget guards (fetch count, turn count) cap what a run
can ever cost.

Usage:
    python agent.py --dry-run                 # full pipeline, no API key, no network
    python agent.py --site corotos --target 20
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

import tools  # importing tools also applies the global TLS fix (truststore)
from tasador_core import schema

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "claude-haiku-4-5"
# USD per million tokens for the default model, used for the cost
# estimate in the run report (verify at anthropic.com/pricing).
PRICE_PER_MTOK = {"input": 1.00, "output": 5.00}

# Site survey (2026-07-05, documented in the README):
# - SuperCasas: server-rendered, detail pages allowed by robots.txt
#   (only /buscar/, /buscador/ and /vender/ are disallowed -- the
#   robots gate in tools.py enforces that automatically). The homepage
#   lists recent listings and each detail page links similar ones, so
#   the agent can navigate without ever touching /buscar/.
# - Corotos: evaluated and dropped for v1 -- its result pages render
#   client-side (JavaScript), so plain HTTP fetches see no listings.
SEED_URLS = {
    "supercasas": [
        "https://www.supercasas.com/",
    ],
}

SYSTEM_PROMPT = f"""You are a data-collection agent for a rental price \
model of Santo Domingo, Dominican Republic.

MISSION: find apartments FOR RENT with a monthly price in DOP, extract
their data and save each one with save_listing, until you reach the
target count or exhaust the fetch budget.

RULES:
- Only listings in these sectors: {", ".join(schema.KNOWN_SECTORS)}.
  Skip listings from any other sector or city.
- Skip: sales (venta), vacation/daily rentals, commercial units, and
  listings whose price is only in USD (unless the monthly DOP price is
  explicit).
- Field conventions (be honest, never invent):
  * sector, price_dop, area_m2, bedrooms, bathrooms: must be explicit
    in the listing text; if any is missing, skip the listing.
  * parking_spots: if parking is not mentioned, use 0.
  * furnished: 1 only if it says amueblado; otherwise 0.
  * age_years: from explicit information only. On SuperCasas pages,
    "Ano Construccion: YYYY" means age_years = 2026 - YYYY; "a
    estrenar" or "En Planos" means 0; "N/D" or absent means skip the
    listing.
- SuperCasas page hints: "Construccion: X Mt2" is the area in m2;
  "US$ X/Mes" is a USD price (skip unless RD$ is also given); the
  sector is the last part of "Localizacion:" (e.g. "Santo Domingo
  Centro > Ensanche Naco" -> sector "Ensanche Naco"); round half
  bathrooms down (1.5 banos -> 1).
- Navigate efficiently: start at the seed URLs, open listing detail
  links (paths like /apartamentos-alquiler-SECTOR/ID/), and use each
  page's "Anuncios Similares" links to keep exploring. Prefer links
  whose sector slug matches the allowed sectors. Never fetch the same
  URL twice; never fetch search pages (/buscar/) -- they are blocked.
- If save_listing rejects a record, read the problems, fix only what
  is fixable from the page text, otherwise move on.
- When the target is reached or the fetch budget is exhausted, call
  finish_run with a short summary (pages visited, listings saved and
  skipped, difficulties found).
"""

TOOL_DEFINITIONS = [
    {
        "name": "fetch_url",
        "description": (
            "Fetch a web page and return its readable text plus its links. "
            "Rate-limited and robots.txt-aware. Costs one unit of the fetch budget."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Absolute URL to fetch"}},
            "required": ["url"],
        },
    },
    {
        "name": "save_listing",
        "description": (
            "Validate and save one rental listing. Returns ok or a list of "
            "problems. All fields are required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "area_m2": {"type": "integer"},
                "bedrooms": {"type": "integer"},
                "bathrooms": {"type": "integer"},
                "parking_spots": {"type": "integer"},
                "furnished": {"type": "integer", "description": "1 furnished, 0 not"},
                "age_years": {"type": "integer"},
                "price_dop": {"type": "integer", "description": "Monthly rent in DOP"},
                "source_url": {"type": "string"},
            },
            "required": [
                "sector", "area_m2", "bedrooms", "bathrooms", "parking_spots",
                "furnished", "age_years", "price_dop", "source_url",
            ],
        },
    },
    {
        "name": "finish_run",
        "description": "End the run with a short summary of the results.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]


def dispatch(block, store: tools.ListingStore, fetcher: tools.FetchSession, max_fetches: int) -> dict:
    """Execute one tool call and return its JSON-serializable result."""
    if block.name == "fetch_url":
        if fetcher.fetch_count >= max_fetches:
            return {
                "ok": False,
                "error": "fetch budget exhausted: save pending data and call finish_run",
            }
        url = block.input.get("url", "")
        print(f"  [fetch {fetcher.fetch_count + 1}] {url}")
        return fetcher.fetch(url)

    if block.name == "save_listing":
        result = store.save(block.input)
        label = "saved" if result.get("ok") else f"rejected ({'; '.join(result.get('problems', []))})"
        print(f"  [listing] {block.input.get('sector', '?')} RD${block.input.get('price_dop', '?')} -> {label}")
        return result

    if block.name == "finish_run":
        return {"ok": True}

    return {"ok": False, "error": f"unknown tool: {block.name}"}


def prune_old_pages(messages: list) -> None:
    """Clear bulky page contents from old tool results.

    Fetched pages are only needed while the agent works on them; after
    a couple of turns they are dead weight in the context window (and
    in the bill), so their content is replaced with a stub.
    """
    for message in messages[:-2]:
        if message.get("role") != "user" or not isinstance(message.get("content"), list):
            continue
        for item in message["content"]:
            if isinstance(item, dict) and len(str(item.get("content", ""))) > 2_000:
                item["content"] = json.dumps({"note": "page content cleared to save tokens"})


def run_agent(client, model, seeds, target, max_fetches, max_turns, store, fetcher):
    task = (
        f"Target: save {target} complete rental listings. "
        f"Fetch budget: {max_fetches} pages.\nSeed URLs:\n" + "\n".join(seeds)
    )
    messages = [{"role": "user", "content": task}]
    tokens_in = tokens_out = 0
    summary = None

    for _ in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        tokens_in += response.usage.input_tokens
        tokens_out += response.usage.output_tokens

        tool_results = []
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"  [agent] {block.text.strip()}")
            elif block.type == "tool_use":
                result = dispatch(block, store, fetcher, max_fetches)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
                if block.name == "finish_run":
                    summary = block.input.get("summary", "")

        if response.stop_reason != "tool_use" or summary is not None:
            break
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
        prune_old_pages(messages)

    return summary, tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Dry-run support: a scripted stand-in for the Anthropic client that
# replays a fixed tool-use sequence against the bundled sample fixture.
# It exercises the full pipeline (tools, validation, CSV, budgets,
# reporting) with zero network calls and zero API cost.
# ---------------------------------------------------------------------------

def _tool_use(id_: str, name: str, input_: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


class ScriptedClient:
    def __init__(self) -> None:
        self.messages = self  # mimic client.messages.create
        self._turns = iter(
            [
                [_tool_use("t1", "fetch_url", {"url": "sample:listing"})],
                [
                    _tool_use(
                        "t2",
                        "save_listing",
                        {
                            "sector": "Bella Vista",
                            "area_m2": 95,
                            "bedrooms": 2,
                            "bathrooms": 2,
                            "parking_spots": 1,
                            "furnished": 0,
                            "age_years": 8,
                            "price_dop": 38500,
                            "source_url": "sample:listing",
                        },
                    )
                ],
                [
                    _tool_use(
                        "t3",
                        "finish_run",
                        {"summary": "Dry run complete: 1 fixture listing saved."},
                    )
                ],
            ]
        )

    def create(self, **_kwargs) -> SimpleNamespace:
        return SimpleNamespace(
            content=next(self._turns),
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", choices=sorted(SEED_URLS), default="supercasas")
    parser.add_argument("--target", type=int, default=20, help="listings to collect")
    parser.add_argument("--max-fetches", type=int, default=25, help="hard cap on page fetches")
    parser.add_argument("--max-turns", type=int, default=60, help="hard cap on agent turns")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", default=None, help="output CSV path")
    parser.add_argument("--dry-run", action="store_true", help="offline run, no API key needed")
    parser.add_argument(
        "--sink",
        choices=["csv", "supabase"],
        default="csv",
        help="besides the CSV, mirror saved listings to the shared Postgres (supabase)",
    )
    args = parser.parse_args()

    if args.dry_run:
        out_path = Path(args.out) if args.out else BASE_DIR / "data" / "rentals_dry_run.csv"
        if out_path.exists():
            out_path.unlink()  # dry runs are idempotent
        client = ScriptedClient()
        seeds = ["sample:listing"]
        print("DRY RUN: scripted client, bundled fixture, no network, no API cost.\n")
    else:
        load_dotenv(BASE_DIR / ".env")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print(
                "ANTHROPIC_API_KEY is not set.\n"
                "Copy .env.example to .env and paste your key there "
                "(see README, section 'Setup')."
            )
            return 1
        import anthropic  # imported here so --dry-run works without it

        client = anthropic.Anthropic()
        out_path = Path(args.out) if args.out else BASE_DIR / "data" / "rentals_real.csv"
        seeds = SEED_URLS[args.site]

    sink = None
    if args.sink == "supabase":
        if args.dry_run:
            print("NOTE: --sink supabase is ignored in dry-run (no network by design).\n")
        else:
            supabase_url = os.environ.get("SUPABASE_URL", "")
            service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
            if not supabase_url or not service_key:
                print(
                    "SUPABASE_URL / SUPABASE_SERVICE_KEY are not set.\n"
                    "Copy .env.example to .env and fill them in (Supabase dashboard\n"
                    "> Project Settings > API keys > service_role)."
                )
                return 1
            run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
            sink = tools.SupabaseSink(supabase_url, service_key, run_id)

    store = tools.ListingStore(out_path, sink=sink)
    fetcher = tools.FetchSession()

    summary, tokens_in, tokens_out = run_agent(
        client, args.model, seeds, args.target, args.max_fetches, args.max_turns, store, fetcher
    )

    cost = tokens_in / 1e6 * PRICE_PER_MTOK["input"] + tokens_out / 1e6 * PRICE_PER_MTOK["output"]
    print("\n----- RUN REPORT -----")
    print(f"Listings saved:     {store.saved}")
    print(f"Listings rejected:  {store.rejected}")
    print(f"Pages fetched:      {fetcher.fetch_count}")
    print(f"Tokens in/out:      {tokens_in:,} / {tokens_out:,}")
    print(f"Estimated cost:     ${cost:.4f} USD")
    print(f"Output CSV:         {out_path}")
    if sink:
        print(f"Pushed to Supabase: {sink.pushed} (failed: {sink.failed})")
    if summary:
        print(f"Agent summary:      {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
