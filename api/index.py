"""Tasador SD API - serverless entry (Vercel Python runtime).

Self-contained on purpose: Vercel's uv-based builder cannot install the
local/monorepo tasador-core package (uv ignores git `#subdirectory` and
rejects local paths), so this function inlines the tiny prediction and
validation logic instead of importing it. That logic is a reproduction of
the domain contract, exactly like the mobile app's TypeScript port -- and
like it, drift is impossible to miss: tests/test_serverless_parity.py
imports BOTH this module and tasador-core in CI and fails on any mismatch.

Same public contract and identical numbers as the container version in
apps/api (the model is a linear regression, so predicting from the
exported weights matches the scikit-learn pipeline to the cent). The
model_version is the same content hash of model_params.json, so clients
cannot tell which backend served them.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
_params_text = (ROOT / "ml" / "training" / "models" / "model_params.json").read_text(encoding="utf-8")
MODEL = json.loads(_params_text)
MODEL_VERSION = hashlib.sha256(_params_text.encode("utf-8")).hexdigest()[:12]

# Numeric feature order and sanity ranges. Mirrors tasador_core.schema;
# the CI parity test asserts these stay identical to the source of truth.
NUMERIC_FEATURES = ["area_m2", "bedrooms", "bathrooms", "parking_spots", "furnished", "age_years"]
APPRAISAL_RANGES = {
    "area_m2": (20, 1000),
    "bedrooms": (0, 10),
    "bathrooms": (1, 10),
    "parking_spots": (0, 10),
    "furnished": (0, 1),
    "age_years": (0, 80),
}


def validate_appraisal_input(record: dict) -> list[str]:
    """Return a list of problems; empty means valid. Sector is validated
    against the sectors the deployed model actually knows."""
    problems = []
    if record.get("sector") not in MODEL["sectors"]:
        problems.append(f"unknown sector '{record.get('sector')}'")
    for field, (lo, hi) in APPRAISAL_RANGES.items():
        value = record.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            problems.append(f"{field} must be a number, got {value!r}")
        elif not lo <= value <= hi:
            problems.append(f"{field}={value} outside sane range [{lo}, {hi}]")
    return problems


def predict_price(record: dict) -> float:
    """Reproduce the sklearn pipeline from the exported weights: sector
    one-hot offset + standardized-numeric contributions + intercept."""
    sectors = MODEL["sectors"]
    idx = sectors.index(record["sector"])
    price = MODEL["intercept"] + MODEL["coef"][idx]
    for i, name in enumerate(NUMERIC_FEATURES):
        scaled = (record[name] - MODEL["scaler_mean"][i]) / MODEL["scaler_scale"][i]
        price += MODEL["coef"][len(sectors) + i] * scaled
    return price


app = FastAPI(
    title="Tasador SD API",
    version="0.1.0",
    description="Rental price appraisals for Santo Domingo, DR.",
)

_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
    return response


class AppraisalRequest(BaseModel):
    sector: str
    area_m2: float
    bedrooms: int
    bathrooms: int
    parking_spots: int
    furnished: int  # 1 furnished, 0 not (same contract as the dataset)
    age_years: float


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.post("/v1/appraisals")
def create_appraisal(request: AppraisalRequest) -> dict:
    record = request.model_dump()
    problems = validate_appraisal_input(record)
    if problems:
        raise HTTPException(status_code=422, detail=problems)

    estimate = predict_price(record)
    if estimate <= 0:
        raise HTTPException(
            status_code=422,
            detail=["combination outside the model's reliable range"],
        )

    rmse = MODEL["metrics"]["rmse"]
    sector_avg = MODEL["avg_price_by_sector"][record["sector"]]
    return {
        "estimate": round(estimate, 2),
        "range_low": round(max(estimate - rmse, 0.0), 2),
        "range_high": round(estimate + rmse, 2),
        "sector_avg": sector_avg,
        "delta_vs_sector_pct": round((estimate - sector_avg) / sector_avg * 100, 1),
        "currency": "DOP",
        "period": "monthly",
        "model_version": MODEL_VERSION,
    }


@app.get("/v1/model/params")
def get_model_params() -> dict:
    return {"version": MODEL_VERSION, "params": MODEL}
