#!/usr/bin/env python3
"""Production watch for Tasador SD.

Runs the checks a customer would notice -- the API answers, the model is
loaded and still returns believable numbers, the web app serves, and every
table the migrations create is reachable -- then reports every problem it
found at once instead of stopping at the first one.

Two incidents are the reason this exists. The API went dark because a
Vercel rewrite quietly stopped forwarding the request path, and nobody
noticed for months. And the Supabase free tier pauses a project after
about a week without traffic, which is how the database ended up
suspended. Hitting PostgREST on a schedule does both jobs: it detects an
outage and it resets that inactivity clock.

Standard library only, so CI needs no install step and the script runs
anywhere Python 3 does:

    python scripts/monitor_production.py
    python scripts/monitor_production.py --report report.md

Exit code is 0 when everything is healthy and 1 when anything is wrong,
which is what makes the GitHub Actions job red.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_URL = os.environ.get("MONITOR_API_URL", "https://tasador-sd.vercel.app").rstrip("/")
WEB_URL = os.environ.get("MONITOR_WEB_URL", "https://tasadorsd.vercel.app").rstrip("/")

# Every table the migrations create. Checking all of them is what tells a
# half-restored database apart from a healthy one: while Supabase was
# bringing the project back, PostgREST answered but reported PGRST205
# ("could not find the table in the schema cache") for tables that were
# not back yet.
TABLES = (
    "listings",
    "listing_prices",
    "listing_queue",
    "saved_estimates",
    "profiles",
    "usage_counters",
)

# A cold serverless function plus a model load is slow, so the timeout is
# generous, and one retry keeps a single network blip from raising an alarm
# at three in the morning. Every request here is read-only, so retrying is
# always safe.
TIMEOUT = 25
ATTEMPTS = 2
RETRY_PAUSE = 3


def fetch(url, *, method="GET", body=None, headers=None):
    """Return (status, text, error).

    An HTTP error status is an answer, not a failure, so it comes back as a
    normal status. `error` is set only when the request never completed at
    all (DNS, TLS, timeout, connection reset), and then `status` is None.
    """
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    last_error = ""

    for attempt in range(ATTEMPTS):
        request = urllib.request.Request(url, data=payload, method=method)
        request.add_header("user-agent", "tasador-sd-production-watch")
        if payload is not None:
            request.add_header("content-type", "application/json")
        for name, value in (headers or {}).items():
            request.add_header(name, value)

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.status, response.read().decode("utf-8", "replace"), None
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace"), None
        except Exception as exc:  # timeout, DNS, TLS, reset
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < ATTEMPTS:
                time.sleep(RETRY_PAUSE)

    return None, "", last_error


def as_json(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def clip(text, limit=200):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + "..."


def check_api(problems, passed):
    """The appraisal API: reachable, model loaded, numbers still sane."""
    health = None

    status, text, error = fetch(f"{API_URL}/health")
    if error:
        problems.append(f"`/health` did not answer: {error}")
    elif status != 200:
        problems.append(f"`/health` returned HTTP {status}: {clip(text)}")
    else:
        health = as_json(text)
        if not health or health.get("status") != "ok":
            problems.append(f'`/health` did not report status "ok": {clip(text)}')
        else:
            passed.append(f"`/health` ok, model `{health.get('model_version')}`")

    # The model's own sector list drives the appraisal probe below, so a
    # renamed sector can never fail the test on its own.
    sector = None
    params_version = None
    status, text, error = fetch(f"{API_URL}/v1/model/params")
    if error:
        problems.append(f"`/v1/model/params` did not answer: {error}")
    elif status != 200:
        problems.append(f"`/v1/model/params` returned HTTP {status}: {clip(text)}")
    else:
        params = as_json(text) or {}
        params_version = params.get("version")
        sectors = (params.get("params") or {}).get("sectors")
        if not isinstance(sectors, list) or not sectors:
            problems.append("`/v1/model/params` returned no sector list.")
        else:
            sector = sectors[0]
            passed.append(f"model exposes {len(sectors)} sectors")

    if sector:
        sample = {
            "sector": sector,
            "area_m2": 100,
            "bedrooms": 2,
            "bathrooms": 2,
            "parking_spots": 1,
            "furnished": 0,
            "age_years": 5,
        }
        status, text, error = fetch(
            f"{API_URL}/v1/appraisals", method="POST", body=sample
        )
        if error:
            problems.append(f"`/v1/appraisals` did not answer: {error}")
        elif status != 200:
            problems.append(f"`/v1/appraisals` returned HTTP {status}: {clip(text)}")
        else:
            result = as_json(text) or {}
            estimate = result.get("estimate")
            low, high = result.get("range_low"), result.get("range_high")
            if not isinstance(estimate, (int, float)) or estimate <= 0:
                problems.append(f"appraisal returned an invalid estimate: {clip(text)}")
            elif result.get("currency") != "DOP" or result.get("period") != "monthly":
                problems.append(
                    "appraisal returned an unexpected currency/period: "
                    f"{result.get('currency')}/{result.get('period')}"
                )
            elif not (
                isinstance(low, (int, float))
                and isinstance(high, (int, float))
                and low <= estimate <= high
            ):
                problems.append(f"incoherent range: {low} <= {estimate} <= {high}")
            else:
                passed.append(f"sample appraisal in {sector}: RD$ {estimate:,.0f}/month")

    # A half-finished deploy can leave two different model versions live.
    if health and params_version:
        served = health.get("model_version")
        if served and served != params_version:
            problems.append(
                f"model version mismatch: health={served} vs params={params_version}"
            )


def check_web(problems, passed):
    """The web app serves its own page, not a platform error page."""
    status, text, error = fetch(WEB_URL + "/")
    if error:
        problems.append(f"the web app did not answer: {error}")
    elif status != 200:
        problems.append(f"the web app returned HTTP {status}")
    elif "Tasador SD" not in text:
        problems.append("the web app answered 200 but the page is not Tasador SD.")
    else:
        passed.append("web app serving")


def check_database(problems, passed):
    """Every table answers through PostgREST, and RLS is still on.

    This doubles as the keep-alive: the free tier pauses a project after
    about a week with no traffic, and these requests are that traffic.
    """
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        problems.append(
            "SUPABASE_URL / SUPABASE_ANON_KEY are not set, so the database was "
            "neither checked nor kept awake. Add them as repository secrets."
        )
        return

    headers = {"apikey": key, "authorization": f"Bearer {key}"}
    # Grouped by what came back, because the interesting cases are uniform:
    # a wrong key fails all six tables identically, and reading that six
    # times buries the one table a half-restored project is still missing.
    failures: dict[tuple, list[str]] = {}
    for table in TABLES:
        status, text, error = fetch(
            f"{url}/rest/v1/{table}?select=*&limit=1", headers=headers
        )
        if error:
            problems.append(f"the database did not answer for `{table}`: {error}")
            return  # one unreachable host is one problem, not six
        if status != 200:
            failures.setdefault((status, clip(text, 140)), []).append(table)

    if failures:
        for (status, detail), names in failures.items():
            problems.append(
                f"{len(names)} of {len(TABLES)} tables not servable, HTTP "
                f"{status} ({', '.join(names)}): {detail}"
            )
    else:
        passed.append(f"all {len(TABLES)} tables reachable, project awake")

    # Row level security guards every table: an anonymous caller must see no
    # rows at all. If that ever returns data, a policy was dropped. Revisit
    # this check the day listings are meant to be publicly readable.
    status, text, _ = fetch(f"{url}/rest/v1/listings?select=*&limit=1", headers=headers)
    if status == 200 and as_json(text):
        problems.append(
            "the anonymous key can read rows from `listings` -- row level "
            "security looks disabled."
        )
    elif status == 200:
        passed.append("row level security still blocking anonymous reads")


def build_report(problems, passed):
    lines = []
    if problems:
        lines.append(f"## Production watch found {len(problems)} problem(s)")
    else:
        lines.append("## Production watch: everything healthy")
    lines += ["", f"- API: {API_URL}", f"- Web: {WEB_URL}", ""]

    if problems:
        lines.append("### Problems")
        lines += [f"- {problem}" for problem in problems]
        lines.append("")
    if passed:
        lines.append("### Passed")
        lines += [f"- {item}" for item in passed]
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check Tasador SD in production.")
    parser.add_argument("--report", help="write a Markdown report to this file")
    args = parser.parse_args()

    problems, passed = [], []
    check_api(problems, passed)
    check_web(problems, passed)
    check_database(problems, passed)

    report = build_report(problems, passed)
    print(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            handle.write(report)

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
