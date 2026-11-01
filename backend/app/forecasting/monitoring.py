from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

_write_lock = Lock()


def record_predictions(rows: list[dict], site_id: str, model_version: str, provenance: str, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        new_file = not target.exists()
        with target.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["recorded_at", "site_id", "forecast_timestamp", "predicted_kwh", "model_version", "provenance"])
            if new_file:
                writer.writeheader()
            now = datetime.now(timezone.utc).isoformat()
            for row in rows:
                writer.writerow({"recorded_at": now, "site_id": site_id, "forecast_timestamp": row["timestamp"], "predicted_kwh": row["predicted_kwh"], "model_version": model_version, "provenance": provenance})


def drift_report(reference: pd.Series, current: pd.Series, alpha: float = 0.01) -> dict:
    ref = pd.to_numeric(reference, errors="coerce").dropna().to_numpy(dtype=float)
    cur = pd.to_numeric(current, errors="coerce").dropna().to_numpy(dtype=float)
    if len(ref) < 20 or len(cur) < 20:
        return {"status": "insufficient_data", "reference_count": len(ref), "current_count": len(cur), "drift_detected": None}
    result = ks_2samp(ref, cur)
    return {"status": "evaluated", "method": "two-sample Kolmogorov-Smirnov", "alpha": alpha, "statistic": float(result.statistic), "p_value": float(result.pvalue), "reference_count": len(ref), "current_count": len(cur), "drift_detected": bool(result.pvalue < alpha), "interpretation": "Distribution change only; this does not establish forecast inaccuracy."}


def delayed_accuracy(forecasts_path: str | Path, actuals_path: str | Path) -> dict:
    forecasts = pd.read_csv(forecasts_path)
    actuals = pd.read_csv(actuals_path)
    required = {"site_id", "forecast_timestamp", "predicted_kwh"}
    if not required.issubset(forecasts.columns) or not {"site_id", "timestamp", "actual_kwh"}.issubset(actuals.columns):
        raise ValueError("Forecast CSV requires site_id, forecast_timestamp, predicted_kwh; actual CSV requires site_id, timestamp, actual_kwh.")
    forecasts["_hour_utc"] = pd.to_datetime(forecasts.forecast_timestamp, utc=True, errors="coerce").dt.floor("h")
    actuals["_hour_utc"] = pd.to_datetime(actuals.timestamp, utc=True, errors="coerce").dt.floor("h")
    forecast_values = pd.to_numeric(forecasts.predicted_kwh, errors="coerce")
    actual_values = pd.to_numeric(actuals.actual_kwh, errors="coerce")
    if (forecasts._hour_utc.isna().any() or actuals._hour_utc.isna().any()
            or not np.isfinite(forecast_values).all() or (forecast_values < 0).any()
            or not np.isfinite(actual_values).all() or (actual_values < 0).any()):
        raise ValueError("Actuals and forecasts must have valid timestamps and non-negative numeric energy values.")
    forecasts["predicted_kwh"] = forecast_values
    actuals["actual_kwh"] = actual_values
    if "recorded_at" in forecasts:
        forecasts = forecasts.sort_values("recorded_at")
    key = ["site_id", "_hour_utc"]
    if "model_version" in forecasts:
        key.append("model_version")
    forecasts = forecasts.drop_duplicates(key, keep="last")
    if actuals.duplicated(["site_id", "_hour_utc"]).any():
        raise ValueError("Actual observations contain duplicate site-hour rows.")
    joined = forecasts.merge(actuals, on=["site_id", "_hour_utc"], how="inner")
    if joined.empty:
        return {"matched_observations": 0, "status": "waiting_for_actuals", "accuracy": None}
    error = joined.predicted_kwh - joined.actual_kwh
    accuracy = {"mae": float(np.abs(error).mean()), "rmse": float(np.sqrt(np.square(error).mean())), "bias_kwh": float(error.mean())}
    per_version = {}
    if "model_version" in joined:
        for version, group in joined.groupby("model_version"):
            version_error = group.predicted_kwh - group.actual_kwh
            per_version[str(version)] = {"matched_observations": int(len(group)), "mae": float(np.abs(version_error).mean()), "rmse": float(np.sqrt(np.square(version_error).mean())), "bias_kwh": float(version_error.mean())}
    return {"matched_observations": int(len(joined)), "status": "evaluated", "accuracy": accuracy, "by_model_version": per_version}
