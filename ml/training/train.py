"""Train the rental price model.

Reads data/rentals_sd.csv, trains the shared preprocessing +
LinearRegression pipeline defined in tasador-core, prints test metrics
and coefficients, and saves every runtime artifact in one pass:

- models/rental_model.pkl     the fitted pipeline (web app / API)
- models/metrics.json         metrics + sector averages (all clients)
- models/model_params.json    plain weights + reference predictions for
                              clients without scikit-learn (mobile app);
                              replaces the old manual export step, so a
                              retrain can never leave a client behind
- reports/*.png               diagnostic plots
"""

import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")  # render PNGs without needing a display

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from tasador_core.model import build_pipeline, export_params
from tasador_core.schema import FEATURES, TARGET

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "rentals_sd.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"


def print_metrics(mae: float, rmse: float, r2: float) -> None:
    print("Test metrics (20% hold-out):")
    print(f"  MAE:  RD$ {mae:,.0f} -> on average, estimates miss the real rent by this amount")
    print(f"  RMSE: RD$ {rmse:,.0f} -> typical error weighting big misses; shown as the +/- range")
    print(f"  R2:   {r2:.3f} -> the model explains {r2:.0%} of the variation in rents")


def print_coefficients(pipeline) -> None:
    names = pipeline.named_steps["preprocess"].get_feature_names_out()
    coefs = pipeline.named_steps["model"].coef_
    ranked = sorted(zip(names, coefs), key=lambda item: abs(item[1]), reverse=True)

    print("\nCoefficients (DOP), sorted by absolute impact:")
    print("  sector_*: location premium vs. the average sector")
    print("  numeric features: impact per +1 standard deviation (scaled)")
    for name, coef in ranked:
        clean = name.split("__", 1)[1]  # drop the transformer prefix
        print(f"  {clean:<30} {coef:>+12,.0f}")


def save_artifacts(pipeline, df: pd.DataFrame, mae, rmse, r2, n_train, n_test) -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(pipeline, MODELS_DIR / "rental_model.pkl")

    metrics = {
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "r2": round(float(r2), 4),
        "n_train": int(n_train),
        "n_test": int(n_test),
        "avg_price_by_sector": {
            sector: round(float(avg), 2)
            for sector, avg in df.groupby("sector")[TARGET].mean().items()
        },
    }
    with open(MODELS_DIR / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)

    params = export_params(pipeline, metrics)
    with open(MODELS_DIR / "model_params.json", "w", encoding="utf-8") as fh:
        json.dump(params, fh, ensure_ascii=False, indent=2)


def save_plots(y_test: pd.Series, y_pred: np.ndarray) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(y_test, y_pred, alpha=0.6, edgecolors="none")
    lims = [0, max(y_test.max(), y_pred.max()) * 1.05]
    ax.plot(lims, lims, "r--", linewidth=1, label="Perfect prediction")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Actual rent (RD$)")
    ax.set_ylabel("Predicted rent (RD$)")
    ax.set_title("Actual vs. predicted rent (test set)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "actual_vs_predicted.png", dpi=150)
    plt.close(fig)

    # Residuals should look like a shapeless cloud around zero; visible
    # structure would mean the linearity assumption is breaking down.
    residuals = y_test - y_pred
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(y_pred, residuals, alpha=0.6, edgecolors="none")
    ax.axhline(0, color="r", linestyle="--", linewidth=1)
    ax.set_xlabel("Predicted rent (RD$)")
    ax.set_ylabel("Residual (actual - predicted, RD$)")
    ax.set_title("Residuals vs. predicted rent (test set)")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "residuals.png", dpi=150)
    plt.close(fig)


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = r2_score(y_test, y_pred)

    print_metrics(mae, rmse, r2)
    print_coefficients(pipeline)
    save_artifacts(pipeline, df, mae, rmse, r2, len(X_train), len(X_test))
    save_plots(y_test, y_pred)

    print(f"\nSaved: {MODELS_DIR / 'rental_model.pkl'}")
    print(f"Saved: {MODELS_DIR / 'metrics.json'}")
    print(f"Saved: {MODELS_DIR / 'model_params.json'}")
    print(f"Saved: {REPORTS_DIR / 'actual_vs_predicted.png'}")
    print(f"Saved: {REPORTS_DIR / 'residuals.png'}")


if __name__ == "__main__":
    main()
