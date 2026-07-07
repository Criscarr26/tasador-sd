"""Tasador SD API: the single inference source for every client.

Serves the trained pipeline behind two endpoints:

- POST /v1/appraisals      appraise one property (validated against the
                           shared domain contract in tasador-core)
- GET  /v1/model/params    versioned plain weights, so clients that
                           predict on-device (mobile) stay in sync with
                           the deployed model instead of shipping a
                           frozen copy

The model artifacts come from ml/training (override with MODEL_DIR).
The model version is a content hash of the exported params: retraining
changes it, clients notice, nobody drifts silently.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tasador_core.model import load_pipeline, predict_price
from tasador_core.schema import validate_appraisal_input

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = Path(os.environ.get("MODEL_DIR", BASE_DIR.parent.parent / "ml" / "training" / "models"))

pipeline = load_pipeline(MODELS_DIR / "rental_model.pkl")
with open(MODELS_DIR / "metrics.json", encoding="utf-8") as fh:
    metrics = json.load(fh)
_params_text = (MODELS_DIR / "model_params.json").read_text(encoding="utf-8")
model_params = json.loads(_params_text)
MODEL_VERSION = hashlib.sha256(_params_text.encode("utf-8")).hexdigest()[:12]

app = FastAPI(
    title="Tasador SD API",
    version="0.1.0",
    description="Rental price appraisals for Santo Domingo, DR.",
)

# Web clients (the Next.js app, local dev) call this API directly from
# the browser. Tighten allow_origins when the production domain exists.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    estimate = predict_price(pipeline, record)
    # A linear model can extrapolate below zero on extreme inputs;
    # better to refuse than to return a nonsense price.
    if estimate <= 0:
        raise HTTPException(
            status_code=422,
            detail=["combination outside the model's reliable range"],
        )

    rmse = metrics["rmse"]
    sector_avg = metrics["avg_price_by_sector"][record["sector"]]
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
    return {"version": MODEL_VERSION, "params": model_params}
