"""Generate a synthetic rental dataset for Santo Domingo, DR.

Writes data/rentals_sd.csv with the exact schema train.py expects:
sector, area_m2, bedrooms, bathrooms, parking_spots, furnished,
age_years, price_dop.

The schema is the contract of the whole project: to move to real
scraped data later, produce a CSV with these same columns and rerun
train.py -- neither train.py nor app.py needs to change.
"""

from pathlib import Path

import numpy as np
import pandas as pd

np.random.seed(42)  # same seed -> same dataset -> reproducible metrics

N_RECORDS = 500
OUTLIER_RATE = 0.05   # share of listings deliberately priced off-market
NOISE_STD_DOP = 3500  # gaussian noise: negotiation, condition, timing...
MIN_PRICE_DOP = 8000  # floor so noise/outliers never produce absurd rents

# Each tier defines its sectors (with the DOP base rent the location adds),
# how large its homes tend to be, and its amenity profile.
TIERS = {
    "premium": {
        "share": 0.25,
        "bases": {"Piantini": 32000, "Naco": 30000, "Serrallés": 28500},
        "area": (150, 40, 70, 280),  # mean, std, min, max (m2)
        "parking": (1, 3),
        "furnished_prob": 0.50,
        "age_max": 25,
    },
    "mid": {
        "share": 0.40,
        "bases": {
            "Bella Vista": 12000,
            "Arroyo Hondo": 11000,
            "Los Prados": 10000,
            "Gazcue": 9000,
        },
        "area": (100, 30, 50, 200),
        "parking": (0, 2),
        "furnished_prob": 0.35,
        "age_max": 35,
    },
    "popular": {
        "share": 0.35,
        "bases": {
            "Santo Domingo Este": 2500,
            "Villa Mella": 1500,
            "Los Alcarrizos": 1000,
        },
        "area": (70, 20, 35, 120),
        "parking": (0, 1),
        "furnished_prob": 0.20,
        "age_max": 40,
    },
}

# DOP contribution per unit of each feature. Kept global across tiers so
# the ground truth stays linear -- exactly what Linear Regression models.
COEF = {
    "area_m2": 210,
    "bedrooms": 2800,
    "bathrooms": 3200,
    "parking_spots": 3500,
    "furnished": 5500,
    "age_years": -280,
}


def generate_tier(cfg: dict, n: int) -> pd.DataFrame:
    """Generate n listings for one market tier."""
    sectors = np.random.choice(list(cfg["bases"]), size=n)
    mean, std, lo, hi = cfg["area"]
    area = np.clip(np.random.normal(mean, std, n), lo, hi).round()
    # Bigger homes have more rooms; noise keeps it from being deterministic.
    bedrooms = np.clip((area / 55 + np.random.normal(0, 0.6, n)).round(), 1, 5)
    bathrooms = np.clip(bedrooms - np.random.randint(0, 2, n), 1, 4)
    parking = np.random.randint(cfg["parking"][0], cfg["parking"][1] + 1, n)
    furnished = np.random.binomial(1, cfg["furnished_prob"], n)
    age = np.random.randint(0, cfg["age_max"] + 1, n)

    sector_base = pd.Series(sectors).map(cfg["bases"]).to_numpy()
    price = (
        sector_base
        + COEF["area_m2"] * area
        + COEF["bedrooms"] * bedrooms
        + COEF["bathrooms"] * bathrooms
        + COEF["parking_spots"] * parking
        + COEF["furnished"] * furnished
        + COEF["age_years"] * age
        + np.random.normal(0, NOISE_STD_DOP, n)
    )

    return pd.DataFrame(
        {
            "sector": sectors,
            "area_m2": area.astype(int),
            "bedrooms": bedrooms.astype(int),
            "bathrooms": bathrooms.astype(int),
            "parking_spots": parking,
            "furnished": furnished,
            "age_years": age,
            "price_dop": price,
        }
    )


def apply_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Reprice ~5% of listings off-market (over- and under-priced)."""
    n_outliers = int(len(df) * OUTLIER_RATE)
    idx = np.random.choice(df.index, size=n_outliers, replace=False)
    overpriced = np.random.rand(n_outliers) < 0.5
    factors = np.where(
        overpriced,
        np.random.uniform(1.25, 1.60, n_outliers),
        np.random.uniform(0.55, 0.80, n_outliers),
    )
    df.loc[idx, "price_dop"] *= factors
    return df


def main() -> None:
    counts = [int(cfg["share"] * N_RECORDS) for cfg in TIERS.values()]
    counts[-1] = N_RECORDS - sum(counts[:-1])  # make counts sum exactly

    frames = [generate_tier(cfg, n) for cfg, n in zip(TIERS.values(), counts)]
    df = pd.concat(frames, ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    df = apply_outliers(df)
    df["price_dop"] = (
        df["price_dop"].clip(lower=MIN_PRICE_DOP).round(-2).astype(int)
    )

    out_path = Path(__file__).resolve().parent / "data" / "rentals_sd.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")

    sector_to_tier = {
        sector: tier for tier, cfg in TIERS.items() for sector in cfg["bases"]
    }
    summary = (
        df.assign(tier=df["sector"].map(sector_to_tier))
        .groupby("tier")["price_dop"]
        .agg(["count", "min", "median", "max"])
    )
    print(f"Saved {len(df)} records to {out_path}")
    print("\nPrice (DOP) by tier:")
    print(summary.to_string())


if __name__ == "__main__":
    main()
