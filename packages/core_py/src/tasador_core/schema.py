"""Domain contract: features, sectors, sanity ranges and validation.

This module is the canonical definition. The audit that led to this
package found the ranges had already diverged across clients (area
20-500 on the web, 20-1000 on mobile, 15-1000 in the agent); the values
below are the resolved, product-wide decision:

- area_m2 20-1000: below 20 m2 is not a residential rental in this
  market; above 500 exists (penthouses), so the old web cap was wrong.
- age_years 0-80: the housing stock in the covered sectors goes well
  past the old 60-year web cap.
- bedrooms 0-10: 0 is a studio. UIs may offer narrower pickers, but
  data validation must accept what the market publishes.
"""

from __future__ import annotations

import unicodedata

# Appraisal features, in training order. TARGET only exists on listings.
NUMERIC_FEATURES = [
    "area_m2",
    "bedrooms",
    "bathrooms",
    "parking_spots",
    "furnished",
    "age_years",
]
FEATURES = ["sector"] + NUMERIC_FEATURES
TARGET = "price_dop"

# Columns of a collected listing (agent output / listings table),
# source_url for provenance and auditability.
COLUMNS = FEATURES + [TARGET, "source_url"]

# The 10 sectors the deployed model knows. Listings outside these are
# skipped: the model cannot price a sector it has no baseline for.
KNOWN_SECTORS = [
    "Piantini",
    "Naco",
    "Serrallés",
    "Bella Vista",
    "Arroyo Hondo",
    "Los Prados",
    "Gazcue",
    "Santo Domingo Este",
    "Villa Mella",
    "Los Alcarrizos",
]

# Sanity ranges for the Santo Domingo rental market. Records outside
# these are almost always data errors (sale prices, USD amounts, typos).
RANGES = {
    "area_m2": (20, 1000),
    "bedrooms": (0, 10),
    "bathrooms": (1, 10),
    "parking_spots": (0, 10),
    "furnished": (0, 1),
    "age_years": (0, 80),
    TARGET: (5_000, 1_000_000),
}


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


# Accent/spelling variants seen in real listings, normalized form.
_SECTOR_LOOKUP = {_strip_accents(s).lower(): s for s in KNOWN_SECTORS}
_SECTOR_LOOKUP.update(
    {
        "sto dgo este": "Santo Domingo Este",
        "sto. dgo. este": "Santo Domingo Este",
        "santo domingo e.": "Santo Domingo Este",
        "ensanche naco": "Naco",
        "ensanche serralles": "Serrallés",
    }
)


def normalize_sector(raw: str) -> str | None:
    """Map a raw sector name to a known sector, or None if unknown."""
    key = _strip_accents(raw.strip()).lower()
    return _SECTOR_LOOKUP.get(key)


def _check_fields(record: dict, fields: list[str]) -> list[str]:
    problems = []

    sector = record.get("sector", "")
    if not isinstance(sector, str) or normalize_sector(sector) is None:
        problems.append(
            f"unknown sector '{sector}' (must be one of: {', '.join(KNOWN_SECTORS)})"
        )

    for field in fields:
        lo, hi = RANGES[field]
        value = record.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            problems.append(f"{field} must be a number, got {value!r}")
        elif not lo <= value <= hi:
            problems.append(f"{field}={value} outside sane range [{lo}, {hi}]")

    return problems


def validate_listing(record: dict) -> list[str]:
    """Validate a collected listing (features + price + provenance).

    Returns a list of problems; empty list means the record is valid.
    """
    problems = _check_fields(record, NUMERIC_FEATURES + [TARGET])

    url = record.get("source_url", "")
    if not isinstance(url, str) or not url.startswith(("http://", "https://", "sample:")):
        problems.append(f"source_url must be a URL, got {url!r}")

    return problems


def validate_appraisal_input(record: dict) -> list[str]:
    """Validate the 7 features of an appraisal request (no price, no URL)."""
    return _check_fields(record, NUMERIC_FEATURES)
