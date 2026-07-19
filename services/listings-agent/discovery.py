"""Sitemap-based discovery: feeds the listing_queue that agent.py consumes.

Why a sitemap: SuperCasas disallows its paginated search (/buscar/,
/buscador/) in robots.txt, so crawling result pages is off the table.
But the sitemap it advertises in robots.txt lists every listing detail
page (~17.5k URLs as of 2026-07) and detail pages are allowed -- the
sitemap is the portal's own invitation to fetch them. Discovery reads
it, keeps the apartment listings in sectors the model knows, and
upserts them into the listing_queue table (migration 0005); collection
runs (agent.py --from-queue) consume that queue.

The sitemap also gives a market signal for free: a URL that leaves the
sitemap probably got rented, so each sync flags those listings
inactive and refreshes last_seen on the ones still present. That weak
"price accepted by the market" label is raw material for the future
price reports.

Network cost: one GET for the sitemap plus Supabase REST calls. No
Anthropic API usage -- discovery is deterministic and free.

Usage:
    python discovery.py --stats                # parse + filter, no writes
    python discovery.py                        # enqueue new URLs + sync active flags
    python discovery.py --requeue-days 7       # also re-queue old 'done' URLs
                                               # so price history accumulates
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tasador_core import schema

BASE_DIR = Path(__file__).resolve().parent
SITEMAP_URL = "https://www.supercasas.com/sitemap.xml"

# Detail pages look like /apartamentos-<sector-slug>/<numeric-id>/.
# Only apartments: the model is trained on apartment rentals, so casas,
# penthouse, locales, etc. would be fetch budget spent on skips.
_LISTING_RE = re.compile(r"^https://www\.supercasas\.com/apartamentos-([a-z0-9-]+)/\d+/$")


def _slugify(name: str) -> str:
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFD", name) if unicodedata.category(ch) != "Mn"
    )
    return stripped.lower().replace(" ", "-")


def sector_slugs() -> set[str]:
    """URL slugs for the sectors the model knows.

    Derived from the domain contract plus the slugs SuperCasas actually
    uses (sitemap survey 2026-07-12: Naco is 'ensanche-naco' on the
    site, plain 'naco' does not occur; both spellings are kept in case
    the portal ever flips). Sub-sector variants (bella-vista-sur,
    arroyo-hondo-viejo, ...) are excluded on purpose: normalize_sector
    would reject them at save time anyway.
    """
    slugs = {_slugify(sector) for sector in schema.KNOWN_SECTORS}
    slugs.update({"ensanche-naco", "ensanche-serralles"})
    return slugs


def parse_sitemap(xml_text: str) -> list[str]:
    """Extract every <loc> URL from a sitemap document."""
    root = ET.fromstring(xml_text)
    return [
        element.text.strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "loc" and element.text
    ]


def filter_candidates(urls: list[str], slugs: set[str] | None = None) -> list[str]:
    """Keep apartment detail pages in known sectors, preserving order."""
    slugs = slugs if slugs is not None else sector_slugs()
    candidates = []
    for url in urls:
        match = _LISTING_RE.match(url)
        if match and match.group(1) in slugs:
            candidates.append(url)
    return candidates


# --------------------------------------------------------------------------
# Network side. Imports are deferred so the pure functions above stay
# importable in CI, where the agent's HTTP dependencies are not installed.
# --------------------------------------------------------------------------

def fetch_sitemap() -> str:
    import tools  # importing tools also applies the global TLS fix (truststore)
    import requests

    response = requests.get(
        SITEMAP_URL,
        headers={"User-Agent": tools.USER_AGENT},
        timeout=tools.FETCH_TIMEOUT_SECONDS * 2,  # ~3 MB document
    )
    response.raise_for_status()
    return response.text


class DiscoverySync:
    """Writes discovery results to Supabase: queue rows + active flags."""

    BATCH = 40  # source_url=in.(...) filters ride in the URL, keep them short

    def __init__(self, url: str, service_key: str) -> None:
        import requests

        self._requests = requests
        self._rest = url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

    def _raise_for_status(self, response) -> None:
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase HTTP {response.status_code}: {response.text[:200]}")

    def enqueue(self, urls: list[str]) -> int:
        """Insert candidate URLs; already-known ones keep their status."""
        endpoint = f"{self._rest}/listing_queue?on_conflict=url"
        headers = {**self._headers, "Prefer": "resolution=ignore-duplicates"}
        for start in range(0, len(urls), 500):
            rows = [{"url": u, "source": "supercasas"} for u in urls[start : start + 500]]
            response = self._requests.post(endpoint, headers=headers, json=rows, timeout=60)
            self._raise_for_status(response)
        return len(urls)

    def known_listing_urls(self) -> set[str]:
        """All SuperCasas source_urls already in the listings table."""
        urls: set[str] = set()
        page = 0
        while True:
            response = self._requests.get(
                f"{self._rest}/listings",
                headers={**self._headers, "Range": f"{page * 1000}-{page * 1000 + 999}"},
                params={
                    "select": "source_url",
                    "source_url": "like.https://www.supercasas.com/*",
                    # Range paging needs a stable order or Postgres may
                    # repeat/skip rows between requests.
                    "order": "source_url.asc",
                },
                timeout=60,
            )
            self._raise_for_status(response)
            rows = response.json()
            urls.update(row["source_url"] for row in rows)
            if len(rows) < 1000:
                return urls
            page += 1

    def _patch_listings(self, urls: list[str], payload: dict, extra_filter: dict) -> None:
        for start in range(0, len(urls), self.BATCH):
            batch = urls[start : start + self.BATCH]
            quoted = ",".join(f'"{u}"' for u in batch)
            response = self._requests.patch(
                f"{self._rest}/listings",
                headers=self._headers,
                params={"source_url": f"in.({quoted})", **extra_filter},
                json=payload,
                timeout=60,
            )
            self._raise_for_status(response)

    def sync_active_flags(self, candidates: list[str]) -> tuple[int, int]:
        """Refresh sightings: present URLs stay active, absent ones flip off.

        Returns (still_present, gone). "Gone" listings keep their last_seen
        untouched -- that timestamp IS the signal (when the market last saw
        the ask).
        """
        known = self.known_listing_urls()
        candidate_set = set(candidates)
        present = sorted(known & candidate_set)
        gone = sorted(known - candidate_set)
        now = datetime.now(timezone.utc).isoformat()
        if present:
            self._patch_listings(present, {"last_seen": now, "is_active": True}, {})
        if gone:
            self._patch_listings(gone, {"is_active": False}, {"is_active": "eq.true"})
        return len(present), len(gone)

    def requeue_stale(self, days: int) -> None:
        """Send old 'done' URLs back to pending so price history accumulates.

        attempts is reset on purpose: it budgets retries within one
        collection cycle, not over the URL's lifetime -- otherwise every
        listing would accumulate transient timeouts across months of
        re-queue cycles until it got retired as 'failed'.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        response = self._requests.patch(
            f"{self._rest}/listing_queue",
            headers=self._headers,
            params={"status": "eq.done", "scraped_at": f"lt.{cutoff}"},
            json={"status": "pending", "attempts": 0, "last_error": None},
            timeout=60,
        )
        self._raise_for_status(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stats", action="store_true",
        help="parse and filter the sitemap, print counts, write nothing",
    )
    parser.add_argument(
        "--sitemap-file", default=None,
        help="read the sitemap from a local file instead of the network",
    )
    parser.add_argument(
        "--requeue-days", type=int, default=None,
        help="also re-queue 'done' URLs scraped more than N days ago",
    )
    args = parser.parse_args()

    if args.sitemap_file:
        xml_text = Path(args.sitemap_file).read_text(encoding="utf-8")
    else:
        print(f"Fetching {SITEMAP_URL} ...")
        xml_text = fetch_sitemap()

    urls = parse_sitemap(xml_text)
    candidates = filter_candidates(urls)
    print(f"Sitemap URLs:      {len(urls):,}")
    print(f"Candidates:        {len(candidates):,} (apartments in known sectors)")

    if args.stats:
        return 0

    if not candidates:
        # A sitemap with zero candidates means the portal restructured
        # its URLs, not that every listing was rented. Syncing active
        # flags against it would flip is_active off for the ENTIRE
        # dataset, so refuse to write anything.
        print(
            "\nNo candidates found: the sitemap or its URL scheme probably "
            "changed.\nRefusing to touch the queue or the active flags -- "
            "inspect the sitemap and update _LISTING_RE / sector_slugs()."
        )
        return 1

    import os

    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not supabase_url or not service_key:
        print(
            "SUPABASE_URL / SUPABASE_SERVICE_KEY are not set.\n"
            "Copy .env.example to .env and fill them in (Supabase dashboard\n"
            "> Project Settings > API keys > service_role)."
        )
        return 1

    sync = DiscoverySync(supabase_url, service_key)
    sync.enqueue(candidates)
    print(f"Queue upserted:    {len(candidates):,} URLs (existing rows untouched)")
    present, gone = sync.sync_active_flags(candidates)
    print(f"Sightings synced:  {present} still listed, {gone} flagged inactive")
    if args.requeue_days is not None:
        sync.requeue_stale(args.requeue_days)
        print(f"Re-queued 'done' URLs older than {args.requeue_days} days")
    print("\nNext: python agent.py --from-queue 20 --sink supabase")
    return 0


if __name__ == "__main__":
    sys.exit(main())
