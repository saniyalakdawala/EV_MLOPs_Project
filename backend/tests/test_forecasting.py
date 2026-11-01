from datetime import datetime, timezone

import pandas as pd
import pytest

from app.forecasting.monitoring import delayed_accuracy, drift_report
from app.forecasting.pipeline import load_hourly_demand, predict_horizon, promote_candidate, train_and_evaluate


def write_sessions(path, days=42, include_invalid=False):
    times = pd.date_range("2025-01-01", periods=24 * days, freq="h", tz="UTC")
    rows = [{"sessionID": f"s-{i}", "connectionTime": t.isoformat(), "kWhDelivered": float(2 + (t.hour == 18) * 5), "siteID": "SITE_A"} for i, t in enumerate(times)]
    rows.append({"sessionID": "duplicate", "connectionTime": times[0].isoformat(), "kWhDelivered": 2.0, "siteID": "SITE_A"})
    rows.append({"sessionID": "duplicate", "connectionTime": times[0].isoformat(), "kWhDelivered": 2.0, "siteID": "SITE_A"})
    if include_invalid:
        rows.extend([
            {"sessionID": "invalid", "connectionTime": "not-a-date", "kWhDelivered": 9, "siteID": "SITE_A"},
            {"sessionID": "negative", "connectionTime": times[2].isoformat(), "kWhDelivered": -1, "siteID": "SITE_A"},
        ])
    pd.DataFrame(rows).to_csv(path, index=False)
    return times


def test_loader_counts_bad_rows_and_requires_explicit_coverage(tmp_path):
    path = tmp_path / "sessions.csv"
    times = write_sessions(path)
    demand, quality = load_hourly_demand(path, "UTC", times[0].isoformat(), (times[-1] + pd.Timedelta(hours=1)).isoformat(), "ACN-DATA-EDUCATIONAL-RESEARCH")
    assert len(demand) == len(times)
    assert quality.duplicate_sessions == 1
    assert quality.rejected_sessions == 0
    assert quality.provenance.startswith("ACN")
    invalid_path = tmp_path / "invalid.csv"
    write_sessions(invalid_path, include_invalid=True)
    with pytest.raises(ValueError, match="unknown demand"):
        load_hourly_demand(invalid_path, "UTC", times[0].isoformat(), (times[-1] + pd.Timedelta(hours=1)).isoformat(), "test")
    with pytest.raises(ValueError):
        load_hourly_demand(path, "UTC", "2025-02-01", "2025-01-01", "test")
    with pytest.raises(ValueError, match="whole-hour"):
        load_hourly_demand(path, "UTC", "2025-01-01T00:00:00.000001Z", "2025-01-02T00:00:00Z", "test")
    conflicting_path = tmp_path / "conflicting.csv"
    write_sessions(conflicting_path)
    conflicting = pd.read_csv(conflicting_path)
    conflicting.loc[conflicting.sessionID == "duplicate", "kWhDelivered"] = [3.0, 4.0]
    conflicting.to_csv(conflicting_path, index=False)
    with pytest.raises(ValueError, match="conflicting duplicate"):
        load_hourly_demand(conflicting_path, "UTC", times[0].isoformat(), (times[-1] + pd.Timedelta(hours=1)).isoformat(), "test")


def test_chronological_training_and_forecast_artifact(tmp_path):
    path = tmp_path / "sessions.csv"
    times = write_sessions(path, days=45)
    demand, quality = load_hourly_demand(path, "UTC", times[0].isoformat(), (times[-1] + pd.Timedelta(hours=1)).isoformat(), "TEST_FIXTURE_NOT_PRODUCTION")
    result = train_and_evaluate(demand, quality, tmp_path / "model")
    assert result["selected_by"].startswith("lowest chronological validation MAE")
    assert result["evaluation_fingerprint"]
    assert set(result["test_metrics"]) >= {"seasonal_naive", "random_forest"}
    import joblib
    bundle = joblib.load(tmp_path / "model" / "model.joblib")
    future = predict_horizon(bundle, "SITE_A", 24)
    assert len(future) == 24
    assert all(row["predicted_kwh"] >= 0 for row in future)
    assert "test" in result["test_metrics"]["random_forest"] or "mae" in result["test_metrics"]["random_forest"]
    with pytest.raises(ValueError, match="Unknown site"):
        predict_horizon(bundle, "MISSING", 1)


def test_monitoring_needs_enough_actuals_and_scores_delayed_accuracy(tmp_path):
    assert drift_report(pd.Series(range(10)), pd.Series(range(10)))["status"] == "insufficient_data"
    forecasts = pd.DataFrame([
        {"site_id": "A", "forecast_timestamp": "2025-01-01T01:00:00+00:00", "predicted_kwh": 4.0, "model_version": "v1", "recorded_at": "2025-01-01T00:00:00+00:00"},
        {"site_id": "A", "forecast_timestamp": "2025-01-01T01:00:00+00:00", "predicted_kwh": 5.0, "model_version": "v1", "recorded_at": "2025-01-01T00:05:00+00:00"},
        {"site_id": "A", "forecast_timestamp": "2025-01-01T01:00:00+00:00", "predicted_kwh": 2.0, "model_version": "v0", "recorded_at": "2025-01-01T00:00:00+00:00"},
    ])
    actuals = pd.DataFrame([{"site_id": "A", "timestamp": "2025-01-01T01:00:00+00:00", "actual_kwh": 3.0}])
    forecasts_path, actuals_path = tmp_path / "forecasts.csv", tmp_path / "actuals.csv"
    forecasts.to_csv(forecasts_path, index=False); actuals.to_csv(actuals_path, index=False)
    result = delayed_accuracy(forecasts_path, actuals_path)
    assert result["matched_observations"] == 2
    assert result["accuracy"]["mae"] == 1.5
    assert result["by_model_version"]["v1"]["rmse"] == 2.0
    actuals.loc[0, "actual_kwh"] = float("inf")
    actuals.to_csv(actuals_path, index=False)
    with pytest.raises(ValueError, match="non-negative numeric"):
        delayed_accuracy(forecasts_path, actuals_path)


def test_synthetic_model_cannot_be_promoted(tmp_path):
    import joblib
    candidate = tmp_path / "candidate.joblib"
    joblib.dump({"model": None, "metadata": {"provenance": "SYNTHETIC_DEMONSTRATION", "model_name": "seasonal_naive", "validation_metrics": {"seasonal_naive": {"mae": 0.0}}}}, candidate)
    with pytest.raises(ValueError, match="cannot be promoted"):
        promote_candidate(candidate, tmp_path / "current" / "model.joblib")


def test_promotion_uses_validation_gate_and_archives_incumbent(tmp_path):
    import joblib
    current = tmp_path / "current" / "model.joblib"
    candidate = tmp_path / "candidate.joblib"
    base = {"provenance": "ACN-Data research export", "dataset_sha256": "same-data", "evaluation_fingerprint": "same-eval", "model_name": "random_forest", "model_version": "v2", "validation_metrics": {"random_forest": {"mae": 1.0}, "seasonal_naive": {"mae": 2.0}}}
    joblib.dump({"model": object(), "metadata": base}, candidate)
    assert promote_candidate(candidate, current)["promoted"] is True
    worse = {**base, "model_version": "v3", "validation_metrics": {"random_forest": {"mae": 1.5}, "seasonal_naive": {"mae": 2.0}}}
    joblib.dump({"model": object(), "metadata": worse}, candidate)
    with pytest.raises(ValueError, match="does not improve"):
        promote_candidate(candidate, current)
    better = {**base, "model_version": "v4", "validation_metrics": {"random_forest": {"mae": 0.5}, "seasonal_naive": {"mae": 2.0}}}
    joblib.dump({"model": object(), "metadata": better}, candidate)
    assert promote_candidate(candidate, current)["promoted"] is True
    assert len(list((tmp_path / "current" / "archive").glob("*/model.joblib"))) == 1


def test_api_returns_clear_unavailable_and_valid_forecast(monkeypatch, tmp_path):
    from app.routers import forecast as forecast_router
    from app.config import settings
    from fastapi import HTTPException
    from datetime import timedelta
    monkeypatch.setattr(settings, "FORECAST_MODEL_PATH", str(tmp_path / "missing.joblib"))
    assert forecast_router.readiness()["ready"] is False
    with pytest.raises(HTTPException) as unavailable:
        forecast_router.forecast(forecast_router.ForecastRequest(site_id="A", forecast_origin=datetime.now(timezone.utc), horizon_hours=5))
    assert unavailable.value.status_code == 503

    import joblib
    origin = datetime(2025, 1, 8, tzinfo=timezone.utc)
    metadata = {"site_ids": ["A"], "model_version": "test-v1", "latest_observed_hour": origin.isoformat(), "history_end": {"A": origin.isoformat()}, "model_kind": "seasonal_naive", "model_name": "seasonal_naive", "history": {"A": [1.0] * 168}, "site_codes": {"A": 0}, "provenance": "TEST_FIXTURE", "target": "hourly energy", "validation_metrics": {}, "test_metrics": {}, "selected_by": "fixture", "reference_prediction_kwh": [1.0] * 24}
    model_path = tmp_path / "model.joblib"
    joblib.dump({"model": None, "metadata": metadata}, model_path)
    monkeypatch.setattr(settings, "FORECAST_MODEL_PATH", str(model_path))
    monkeypatch.setattr(settings, "FORECAST_LOG_PATH", str(tmp_path / "predictions.csv"))
    result = forecast_router.forecast(forecast_router.ForecastRequest(site_id="A", forecast_origin=origin, horizon_hours=2))
    assert len(result["forecasts"]) == 2
    assert result["model_version"] == "test-v1"
    assert (tmp_path / "predictions.csv").is_file()
    with pytest.raises(HTTPException) as bad_origin:
        forecast_router.forecast(forecast_router.ForecastRequest(site_id="A", forecast_origin=origin + timedelta(hours=1), horizon_hours=2))
    assert bad_origin.value.status_code == 422

    metadata["model_kind"] = "random_forest"
    joblib.dump({"model": None, "metadata": metadata}, model_path)
    with pytest.raises(HTTPException) as incompatible:
        forecast_router.forecast(forecast_router.ForecastRequest(site_id="A", forecast_origin=origin, horizon_hours=2))
    assert incompatible.value.status_code == 503
