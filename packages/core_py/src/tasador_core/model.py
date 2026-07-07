"""Model helpers: build, load, predict and export the rental pipeline.

The pipeline structure (named steps "preprocess"/"model", transformers
"sector"/"numeric") is a contract: export_params() depends on it to
extract plain weights for clients that predict without scikit-learn
(the mobile app, and any future edge runtime). Keeping build and export
in the same module makes it impossible to change one and forget the
other.

joblib/pandas/scikit-learn are imported lazily so that importing
tasador_core.schema never requires them.
"""

from __future__ import annotations

from pathlib import Path

from tasador_core.schema import FEATURES, NUMERIC_FEATURES

# Inputs whose pipeline predictions ship inside the exported params, so
# every re-implementation (TypeScript today) can prove it matches the
# real model exactly.
REFERENCE_INPUTS = [
    {"sector": "Piantini", "area_m2": 120, "bedrooms": 3, "bathrooms": 2,
     "parking_spots": 2, "furnished": 1, "age_years": 5},
    {"sector": "Villa Mella", "area_m2": 70, "bedrooms": 2, "bathrooms": 1,
     "parking_spots": 1, "furnished": 0, "age_years": 15},
    {"sector": "Gazcue", "area_m2": 95, "bedrooms": 2, "bathrooms": 2,
     "parking_spots": 1, "furnished": 1, "age_years": 30},
]


def build_pipeline():
    """Preprocessing + LinearRegression, fitted only on the training split."""
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    preprocess = ColumnTransformer(
        [
            ("sector", OneHotEncoder(handle_unknown="ignore"), ["sector"]),
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
        ]
    )
    return Pipeline([("preprocess", preprocess), ("model", LinearRegression())])


def load_pipeline(path: str | Path):
    import joblib

    return joblib.load(path)


def predict_price(pipeline, features: dict) -> float:
    """Appraise one property. `features` must contain exactly FEATURES."""
    import pandas as pd

    frame = pd.DataFrame([features])[FEATURES]
    return float(pipeline.predict(frame)[0])


def export_params(pipeline, metrics: dict) -> dict:
    """Extract plain weights + reference predictions for non-sklearn clients.

    Coefficient order in the pipeline output: sector one-hots first,
    scaled numerics after.
    """
    pre = pipeline.named_steps["preprocess"]
    ohe = pre.named_transformers_["sector"]
    scaler = pre.named_transformers_["numeric"]
    model = pipeline.named_steps["model"]

    return {
        "sectors": ohe.categories_[0].tolist(),
        "numeric_features": NUMERIC_FEATURES,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coef": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "metrics": {
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "r2": metrics["r2"],
        },
        "avg_price_by_sector": metrics["avg_price_by_sector"],
        "reference_cases": [
            {"input": case, "expected": predict_price(pipeline, case)}
            for case in REFERENCE_INPUTS
        ],
    }


def predict_from_params(params: dict, features: dict) -> float:
    """Predict using exported params only (no sklearn) — the same math
    every client port implements. Used by tests to prove export_params
    and the pipeline agree, and by runtimes without scikit-learn."""
    sectors = params["sectors"]
    idx = sectors.index(features["sector"])
    price = params["intercept"] + params["coef"][idx]
    for i, name in enumerate(params["numeric_features"]):
        scaled = (features[name] - params["scaler_mean"][i]) / params["scaler_scale"][i]
        price += params["coef"][len(sectors) + i] * scaled
    return price
