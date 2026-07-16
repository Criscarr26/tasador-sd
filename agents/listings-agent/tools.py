"""Tools the agent can call: fetch pages, save listings, track progress.

Responsible-scraping rules live here, not in the model's prompt, so
they cannot be skipped: robots.txt is checked before every request,
fetches are rate-limited, and pages are trimmed before they reach the
model (HTML boilerplate is token cost, not signal).
"""

from __future__ import annotations

import csv
import ipaddress
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import truststore

# Global TLS fix, applied where HTTP lives so it works even when this
# module is used standalone: the dev machine sits behind TLS inspection
# and Python must trust the Windows certificate store, not certifi.
# The injection is process-wide, so it also covers the Anthropic SDK.
truststore.inject_into_ssl()

import requests
from bs4 import BeautifulSoup

from tasador_core import schema

USER_AGENT = (
    "rental-listings-agent/1.0 (educational portfolio project; "
    "+https://github.com/Criscarr26/rental-listings-agent)"
)
MIN_SECONDS_BETWEEN_FETCHES = 3.0
FETCH_TIMEOUT_SECONDS = 25
MAX_PAGE_CHARS = 18_000  # keep per-page token cost bounded

BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "data" / "samples"

# SSRF guard: the agent decides which URLs to visit from scraped page
# content, so a malicious page could try to make it fetch internal
# services (cloud metadata at 169.254.169.254, localhost, private nets).
# Only these host suffixes are fetchable, and only if they resolve to a
# public IP. Override via AGENT_ALLOWED_HOSTS (comma-separated) when
# adding a new source site.
ALLOWED_HOST_SUFFIXES = tuple(
    h.strip().lower()
    for h in os.environ.get("AGENT_ALLOWED_HOSTS", "supercasas.com").split(",")
    if h.strip()
)


def _url_allowed(url: str) -> str | None:
    """Return an error string if the URL must NOT be fetched, else None."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"scheme not allowed: {parsed.scheme!r}"
    host = (parsed.hostname or "").lower()
    if not host or not any(host == s or host.endswith("." + s) for s in ALLOWED_HOST_SUFFIXES):
        return f"host not in allowlist: {host!r}"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return f"cannot resolve {host!r}: {exc}"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return f"{host!r} resolves to a non-public IP ({ip})"
    return None


class FetchSession:
    """Polite HTTP session: robots.txt aware and rate-limited."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_fetch = 0.0
        self.fetch_count = 0
        # url -> "ok" or the error message; lets the run report queue
        # outcomes (done/skipped/failed) per seed after the agent stops.
        self.results: dict[str, str] = {}

    def _robots_for(self, url: str) -> robotparser.RobotFileParser:
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in self._robots:
            parser = robotparser.RobotFileParser(origin + "/robots.txt")
            try:
                response = self._session.get(
                    origin + "/robots.txt", timeout=FETCH_TIMEOUT_SECONDS
                )
                parser.parse(response.text.splitlines() if response.ok else [])
            except requests.RequestException:
                parser.parse([])  # unreachable robots.txt -> assume allowed
            self._robots[origin] = parser
        return self._robots[origin]

    def fetch(self, url: str) -> dict:
        """Fetch a URL and return cleaned text content for the model."""
        if url.startswith("sample:"):  # offline fixture for --dry-run
            path = SAMPLES_DIR / (url.split(":", 1)[1] + ".html")
            if not path.exists():
                return {"ok": False, "error": f"sample fixture not found: {path.name}"}
            return {"ok": True, "url": url, "content": _clean_html(path.read_text(encoding="utf-8"))}

        blocked = _url_allowed(url)
        if blocked:
            self.results[url] = blocked
            return {"ok": False, "error": blocked}

        if not self._robots_for(url).can_fetch(USER_AGENT, url):
            self.results[url] = f"robots.txt disallows fetching {url}"
            return {"ok": False, "error": self.results[url]}

        wait = MIN_SECONDS_BETWEEN_FETCHES - (time.monotonic() - self._last_fetch)
        if wait > 0:
            time.sleep(wait)
        self._last_fetch = time.monotonic()

        try:
            response = self._session.get(url, timeout=FETCH_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            self.results[url] = f"request failed: {exc}"
            return {"ok": False, "error": self.results[url]}

        self.fetch_count += 1
        if response.status_code != 200:
            self.results[url] = f"HTTP {response.status_code} for {url}"
            return {"ok": False, "error": self.results[url]}
        self.results[url] = "ok"
        return {"ok": True, "url": url, "content": _clean_html(response.text)}


def _clean_html(raw_html: str) -> str:
    """Strip scripts/styles/tags; return readable text plus link targets.

    Links are kept because the agent navigates by choosing hrefs from
    listing-index pages.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    links = []
    for anchor in soup.find_all("a", href=True):
        text = " ".join(anchor.get_text(" ", strip=True).split())
        if text:
            links.append(f"[{text}]({anchor['href']})")

    text = " ".join(soup.get_text(" ", strip=True).split())
    combined = text + "\n\nLINKS:\n" + "\n".join(links)
    if len(combined) > MAX_PAGE_CHARS:
        combined = combined[:MAX_PAGE_CHARS] + "\n[...page truncated...]"
    return combined


class SupabaseSink:
    """Mirrors validated listings into the shared Postgres listings table.

    Uses the service-role key: RLS on listings has no policies, so only
    the service context can write (clients never touch this table).
    Upserts on source_url with merge semantics: a re-sighted listing
    refreshes last_seen/is_active and, when its price moved, the
    listings_price_history trigger (migration 0005) snapshots the new
    price into listing_prices -- that trajectory is the market signal
    the future price reports are built on. first_seen and collected_at
    are not in the payload, so the original values survive every merge.
    A failed push does not abort the run -- the local CSV remains the
    source of truth and can be re-synced later.
    """

    def __init__(self, url: str, service_key: str, run_id: str) -> None:
        self._endpoint = url.rstrip("/") + "/rest/v1/listings?on_conflict=source_url"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }
        self._run_id = run_id
        self.pushed = 0
        self.failed = 0

    def push(self, row: dict) -> None:
        payload = {key: row[key] for key in schema.COLUMNS}
        payload["furnished"] = bool(row["furnished"])
        payload["run_id"] = self._run_id
        payload["last_seen"] = datetime.now(timezone.utc).isoformat()
        payload["is_active"] = True
        try:
            response = requests.post(
                self._endpoint, headers=self._headers, json=payload,
                timeout=FETCH_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            self.failed += 1
            print(f"  [sink] push failed: {exc}")
            return
        if response.status_code in (200, 201):
            self.pushed += 1
        else:
            self.failed += 1
            print(f"  [sink] push failed: HTTP {response.status_code} {response.text[:120]}")


class ListingStore:
    """Appends validated listings to the output CSV, skipping duplicates.

    When a sink is provided, every saved row is also mirrored to it --
    including re-sightings of listings already in the CSV: the CSV keeps
    one row per listing, but the sink's merge upsert turns each
    re-sighting into a refreshed last_seen and, on price changes, a new
    listing_prices snapshot.
    """

    def __init__(self, csv_path: Path, sink: SupabaseSink | None = None) -> None:
        self.csv_path = csv_path
        self.saved = 0
        self.rejected = 0
        self.refreshed = 0
        # URLs saved or refreshed by THIS run (the CSV-wide set below
        # also holds every URL from previous runs).
        self.session_urls: set[str] = set()
        self._sink = sink
        self._seen_urls: set[str] = set()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        if csv_path.exists():
            with open(csv_path, encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    self._seen_urls.add(row.get("source_url", ""))
                    self.saved += 1
        else:
            with open(csv_path, "w", encoding="utf-8", newline="") as fh:
                csv.DictWriter(fh, fieldnames=schema.COLUMNS).writeheader()

    def save(self, record: dict) -> dict:
        problems = schema.validate_listing(record)
        if problems:
            self.rejected += 1
            return {"ok": False, "problems": problems}

        row = dict(record)
        row["sector"] = schema.normalize_sector(record["sector"])
        for field in schema.RANGES:
            row[field] = int(row[field])

        if row["source_url"] in self._seen_urls:
            if self._sink is None:
                return {"ok": False, "problems": ["duplicate: this listing is already saved"]}
            self._sink.push(row)
            self.refreshed += 1
            self.session_urls.add(row["source_url"])
            return {
                "ok": True,
                "note": "already in the CSV; sighting and price refreshed in Supabase",
            }

        with open(self.csv_path, "a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=schema.COLUMNS).writerow(row)

        self._seen_urls.add(row["source_url"])
        self.saved += 1
        self.session_urls.add(row["source_url"])
        if self._sink:
            self._sink.push(row)
        return {"ok": True, "saved_so_far": self.saved}


class QueueClient:
    """Consumes the listing_queue table (migration 0005).

    Sitemap discovery (discovery.py) fills the queue; collection runs
    pull pending URLs as direct seeds and record what happened to each
    one, so a failed page is retried on the next run (up to 3 attempts)
    and a processed one is never pulled again.
    """

    MAX_ATTEMPTS = 3

    def __init__(self, url: str, service_key: str) -> None:
        self._endpoint = url.rstrip("/") + "/rest/v1/listing_queue"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

    def pull_pending(self, limit: int) -> list[dict]:
        """Oldest pending URLs first, skipping ones that failed too often."""
        response = requests.get(
            self._endpoint,
            headers=self._headers,
            params={
                "select": "url,attempts",
                "status": "eq.pending",
                "attempts": f"lt.{self.MAX_ATTEMPTS}",
                "order": "discovered_at.asc",
                "limit": str(limit),
            },
            timeout=FETCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def record_outcome(self, item: dict, fetch_result: str | None, processed: bool) -> str:
        """Update one queue row after a run; returns the status written.

        - saved/refreshed by the agent      -> done
        - fetched fine but not saved        -> skipped (sale, USD-only, ...)
        - fetch failed                      -> pending again, or failed
                                               after MAX_ATTEMPTS
        - never fetched (budget ran out)    -> left pending, untouched
        """
        now = datetime.now(timezone.utc).isoformat()
        if processed:
            # attempts resets: it budgets retries within one collection
            # cycle, not over the URL's lifetime (re-queued URLs start
            # fresh; see DiscoverySync.requeue_stale).
            payload = {"status": "done", "scraped_at": now, "attempts": 0, "last_error": None}
        elif fetch_result == "ok":
            payload = {"status": "skipped", "scraped_at": now}
        elif fetch_result is not None:
            attempts = item.get("attempts", 0) + 1
            payload = {
                "status": "failed" if attempts >= self.MAX_ATTEMPTS else "pending",
                "attempts": attempts,
                "last_error": fetch_result[:500],
                "scraped_at": now,
            }
        else:
            return "pending"

        response = requests.patch(
            self._endpoint,
            headers=self._headers,
            params={"url": f"eq.{item['url']}"},
            json=payload,
            timeout=FETCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return payload["status"]
