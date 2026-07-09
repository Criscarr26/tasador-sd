"""Tasador SD API - serverless entry (Vercel Python runtime).

Same public contract as the container version in apps/api, but predicts
from the exported model weights (tasador_core.predict_from_params) instead
of loading the scikit-learn pipeline. The parity contract test guarantees
both produce identical numbers, so this is a lightweight, dependency-free
deployment target (no sklearn/pandas/joblib) that fits a free serverless
tier. The model_version is the same content hash of model_params.json, so
clients cannot tell which backend served them.

Note on rate limiting: the container's in-memory per-IP limit is useless in
serverless (each invocation may be a fresh instance). Abuse is bounded by
the platform edge and by per-user metering at the database (usage_counters
trigger). Documented in the audit.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tasador_core.model import predict_from_params
from tasador_core.schema import validate_appraisal_input

ROOT = Path(__file__).resolve().parent.parent
_params_text = (ROOT / "ml" / "training" / "models" / "model_params.json").read_text(encoding="utf-8")
model_params = json.loads(_params_text)
MODEL_VERSION = hashlib.sha256(_params_text.encode("utf-8")).hexdigest()[:12]

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

    estimate = predict_from_params(model_params, record)
    if estimate <= 0:
        raise HTTPException(
            status_code=422,
            detail=["combination outside the model's reliable range"],
        )

    rmse = model_params["metrics"]["rmse"]
    sector_avg = model_params["avg_price_by_sector"][record["sector"]]
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
