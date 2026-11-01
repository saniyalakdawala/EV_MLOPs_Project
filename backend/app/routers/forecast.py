from __future__ import annotations

import time
from datetime import datetime
import math
from pathlib import Path

import joblib
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram

from app.config import settings
from app.forecasting.monitoring import delayed_accuracy, drift_report, record_predictions
from app.forecasting.pipeline import predict_horizon

router = APIRouter(prefix="/api/forecast", tags=["Demand Forecasting"])
PREDICTIONS = Counter("voltgrid_forecast_requests_total", "Forecast requests", ["result", "model_version"])
PREDICTION_ERRORS = Counter("voltgrid_forecast_errors_total", "Forecast errors", ["reason"])
PREDICTION_LATENCY = Histogram("voltgrid_forecast_latency_seconds", "Forecast request latency")
DELAYED_ACCURACY = Gauge("voltgrid_forecast_delayed_accuracy_kwh", "Delayed forecast error metrics in kWh", ["model_version", "metric"])
DELAYED_MATCHES = Gauge("voltgrid_forecast_delayed_matched_observations", "Number of matched delayed forecast observations", ["model_version"])


class ForecastRequest(BaseModel):
    site_id: str = Field(..., min_length=1, max_length=100)
    forecast_origin: datetime
    horizon_hours: int = Field(..., ge=1, le=168)


def _load_bundle() -> dict:
    path = Path(settings.FORECAST_MODEL_PATH)
    if not path.is_file():
        raise HTTPException(status_code=503, detail="No trained forecast model is available. Import eligible data and train a model first.")
    try:
        bundle = joblib.load(path)
        if not isinstance(bundle, dict) or "metadata" not in bundle or "model" not in bundle:
            raise ValueError("Unexpected model artifact format")
        metadata = bundle["metadata"]
        if not isinstance(metadata, dict):
            raise ValueError("Model metadata must be an object")
        site_ids = metadata.get("site_ids")
        if (not isinstance(site_ids, list) or not site_ids or not all(isinstance(site, str) and site for site in site_ids)
                or not isinstance(metadata.get("model_version"), str) or not metadata.get("model_version")
                or not isinstance(metadata.get("latest_observed_hour"), str)
                or not isinstance(metadata.get("provenance"), str) or not metadata.get("provenance")
                or not isinstance(metadata.get("target"), str) or not metadata.get("target")
                or not isinstance(metadata.get("model_name"), str)
                or not isinstance(metadata.get("validation_metrics"), dict)
                or not isinstance(metadata.get("test_metrics"), dict)
                or not isinstance(metadata.get("selected_by"), str)):
            raise ValueError("Model metadata is incomplete")
        latest = datetime.fromisoformat(metadata["latest_observed_hour"])
        if latest.tzinfo is None:
            raise ValueError("Latest observed hour must include a timezone offset")
        history = metadata.get("history")
        history_end = metadata.get("history_end")
        if not isinstance(history, dict) or not isinstance(history_end, dict):
            raise ValueError("Model history metadata is incomplete")
        for site in site_ids:
            values = history.get(site)
            if not isinstance(values, list) or len(values) < 168:
                raise ValueError("Model history is incomplete")
            if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in values):
                raise ValueError("Model history contains invalid energy values")
            site_end = history_end.get(site)
            if not isinstance(site_end, str) or datetime.fromisoformat(site_end) != latest:
                raise ValueError("Site history does not end at the latest observed hour")
        model_kind = metadata.get("model_kind")
        if model_kind == "seasonal_naive":
            pass
        elif model_kind in {"random_forest", "xgboost"} and callable(getattr(bundle["model"], "predict", None)):
            pass
        else:
            raise ValueError("Model artifact has an unsupported or incompatible model kind")
        return bundle
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Forecast model could not be loaded ({type(exc).__name__}).") from exc


@router.get("/health")
def health():
    return {"status": "ok", "service": "voltgrid-forecast"}


@router.get("/ready")
def readiness():
    try:
        bundle = _load_bundle()
        return {"ready": True, "model_version": bundle["metadata"]["model_version"]}
    except HTTPException:
        return {"ready": False, "reason": "model_unavailable"}


@router.get("/model-info")
def model_info():
    bundle = _load_bundle()
    return bundle["metadata"]


@router.get("/evaluation")
def evaluation_summary():
    bundle = _load_bundle()
    metadata = bundle["metadata"]
    return {"provenance": metadata["provenance"], "selected_model": metadata["model_name"], "validation_metrics": metadata["validation_metrics"], "held_out_test_metrics": metadata["test_metrics"], "per_site_test_metrics": metadata.get("per_site_test_metrics", {}), "selected_by": metadata["selected_by"]}


@router.post("/predict")
def forecast(req: ForecastRequest):
    started = time.perf_counter()
    try:
        bundle = _load_bundle()
        metadata = bundle["metadata"]
        if req.forecast_origin.tzinfo is None:
            raise HTTPException(status_code=422, detail="forecast_origin must include a timezone offset.")
        expected = datetime.fromisoformat(metadata["latest_observed_hour"])
        origin = req.forecast_origin
        if expected.tzinfo is None:
            expected = expected.replace(tzinfo=origin.tzinfo)
        if origin != expected:
            raise HTTPException(status_code=422, detail=f"forecast_origin must equal the latest complete observed hour: {expected.isoformat()}.")
        rows = predict_horizon(bundle, req.site_id, req.horizon_hours)
        record_predictions(rows, req.site_id, metadata["model_version"], metadata["provenance"], settings.FORECAST_LOG_PATH)
        PREDICTIONS.labels("success", metadata["model_version"]).inc()
        return {"site_id": req.site_id, "forecast_origin": origin.isoformat(), "model_version": metadata["model_version"], "provenance": metadata["provenance"], "target": metadata["target"], "demonstration_only": metadata["provenance"].upper().startswith("SYNTHETIC"), "forecasts": rows}
    except HTTPException as exc:
        PREDICTION_ERRORS.labels(str(exc.status_code)).inc()
        raise
    except ValueError as exc:
        PREDICTION_ERRORS.labels("validation").inc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        PREDICTION_ERRORS.labels("internal").inc()
        raise HTTPException(status_code=500, detail="Forecast generation failed.") from exc
    finally:
        PREDICTION_LATENCY.observe(time.perf_counter() - started)


@router.get("/monitoring/drift")
def drift_status():
    bundle = _load_bundle()
    path = Path(settings.FORECAST_LOG_PATH)
    if not path.is_file():
        return {"status": "awaiting_predictions", "prediction_distribution_drift": None, "data_drift": "awaiting_observations", "message": "No prediction history or new observed demand is available."}
    import pandas as pd
    recent = pd.read_csv(path)
    recent = recent[recent.model_version == bundle["metadata"]["model_version"]].tail(168)
    prediction_drift = drift_report(pd.Series(bundle["metadata"].get("reference_prediction_kwh", [])), recent.predicted_kwh)
    return {"status": "evaluated" if prediction_drift["status"] == "evaluated" else prediction_drift["status"], "prediction_distribution_drift": prediction_drift, "data_drift": "awaiting_observations", "accuracy": "not evaluated until delayed actual demand is supplied"}


@router.get("/monitoring/accuracy")
def accuracy_status():
    forecasts = Path(settings.FORECAST_LOG_PATH)
    actuals = Path(settings.FORECAST_ACTUALS_PATH)
    if not forecasts.is_file() or not actuals.is_file():
        return {"status": "waiting_for_actuals", "matched_observations": 0, "accuracy": None, "message": "Add validated actuals.csv rows when outcomes arrive; accuracy is not estimated."}
    try:
        result = delayed_accuracy(forecasts, actuals)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result["accuracy"]:
        for version, scores in result.get("by_model_version", {}).items():
            DELAYED_MATCHES.labels(version).set(scores["matched_observations"])
            for metric in ("mae", "rmse", "bias_kwh"):
                DELAYED_ACCURACY.labels(version, metric).set(scores[metric])
    return result
