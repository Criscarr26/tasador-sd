"""Tools the agent can call: fetch pages, save listings, track progress.

Responsible-scraping rules live here, not in the model's prompt, so
they cannot be skipped: robots.txt is checked before every request,
fetches are rate-limited, and pages are trimmed before they reach the
model (HTML boilerplate is token cost, not signal).
"""

from __future__ import annotations

import csv
import time
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


class FetchSession:
    """Polite HTTP session: robots.txt aware and rate-limited."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_fetch = 0.0
        self.fetch_count = 0

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

        if not self._robots_for(url).can_fetch(USER_AGENT, url):
            return {"ok": False, "error": f"robots.txt disallows fetching {url}"}

        wait = MIN_SECONDS_BETWEEN_FETCHES - (time.monotonic() - self._last_fetch)
        if wait > 0:
            time.sleep(wait)
        self._last_fetch = time.monotonic()

        try:
            response = self._session.get(url, timeout=FETCH_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            return {"ok": False, "error": f"request failed: {exc}"}

        self.fetch_count += 1
        if response.status_code != 200:
            return {"ok": False, "error": f"HTTP {response.status_code} for {url}"}
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
    Upserts on source_url, so re-running a collection never duplicates.
    A failed push does not abort the run -- the local CSV remains the
    source of truth and can be re-synced later.
    """

    def __init__(self, url: str, service_key: str, run_id: str) -> None:
        self._endpoint = url.rstrip("/") + "/rest/v1/listings?on_conflict=source_url"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates",
        }
        self._run_id = run_id
        self.pushed = 0
        self.failed = 0

    def push(self, row: dict) -> None:
        payload = {key: row[key] for key in schema.COLUMNS}
        payload["furnished"] = bool(row["furnished"])
        payload["run_id"] = self._run_id
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

    When a sink is provided, every saved row is also mirrored to it.
    """

    def __init__(self, csv_path: Path, sink: SupabaseSink | None = None) -> None:
        self.csv_path = csv_path
        self.saved = 0
        self.rejected = 0
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
        if record["source_url"] in self._seen_urls:
            return {"ok": False, "problems": ["duplicate: this listing is already saved"]}

        row = dict(record)
        row["sector"] = schema.normalize_sector(record["sector"])
        for field in schema.RANGES:
            row[field] = int(row[field])
        with open(self.csv_path, "a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=schema.COLUMNS).writerow(row)

        self._seen_urls.add(row["source_url"])
        self.saved += 1
        if self._sink:
            self._sink.push(row)
        return {"ok": True, "saved_so_far": self.saved}
