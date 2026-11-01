from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

FEATURES = ["site_id", "hour_sin", "hour_cos", "dow_sin", "dow_cos", "weekend", "lag_1", "lag_24", "lag_168", "rolling_24", "rolling_168"]
NUMERIC_FEATURES = [name for name in FEATURES if name != "site_id"]
MIN_HISTORY_HOURS = 24 * 14


@dataclass
class DataQuality:
    rows_read: int
    accepted_sessions: int
    rejected_sessions: int
    duplicate_sessions: int
    missing_intervals_filled: int
    provenance: str
    dataset_sha256: str


def _field(row: pd.Series, *names: str) -> Any:
    for name in names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return None


def load_hourly_demand(
    csv_path: str | Path,
    timezone: str,
    coverage_start: str,
    coverage_end: str,
    provenance: str,
) -> tuple[pd.DataFrame, DataQuality]:
    """Validate session CSV and aggregate complete coverage to site-local hour bins.

    Energy is assigned to the session connection hour, so this is an arrival-hour
    cohort measure, not a measured per-hour meter profile.
    """
    if not provenance.strip():
        raise ValueError("A non-empty data provenance label is required.")
    p = Path(csv_path)
    raw = pd.read_csv(p)
    if raw.empty:
        raise ValueError("The session file contains no rows.")
    start = pd.Timestamp(coverage_start)
    end = pd.Timestamp(coverage_end)
    if start.tzinfo is None:
        start = start.tz_localize(timezone)
    else:
        start = start.tz_convert(timezone)
    if end.tzinfo is None:
        end = end.tz_localize(timezone)
    else:
        end = end.tz_convert(timezone)
    if start.minute or start.second or start.microsecond or start.nanosecond or end.minute or end.second or end.microsecond or end.nanosecond or end <= start:
        raise ValueError("Coverage boundaries must be increasing, whole-hour timestamps.")

    rows: list[dict[str, Any]] = []
    duplicate_ids: set[str] = set()
    seen_ids: dict[str, tuple[str, str, str]] = {}
    duplicate_count = 0
    conflicting_duplicates = 0
    outside_coverage = 0
    invalid_rows = 0
    for _, row in raw.iterrows():
        session_id = _field(row, "sessionID", "session_id", "_id")
        if session_id is not None:
            sid = str(session_id)
            if sid in seen_ids:
                duplicate_count += 1
                signature = tuple(str(_field(row, field)) for field in ("connectionTime", "start_time", "start_timestamp", "kWhDelivered", "energy_kwh", "energy", "siteID", "site_id", "station_id"))
                if signature != seen_ids[sid]:
                    conflicting_duplicates += 1
                continue
            signature = tuple(str(_field(row, field)) for field in ("connectionTime", "start_time", "start_timestamp", "kWhDelivered", "energy_kwh", "energy", "siteID", "site_id", "station_id"))
            seen_ids[sid] = signature
        try:
            raw_timestamp = _field(row, "connectionTime", "start_time", "start_timestamp")
            if raw_timestamp is None:
                raise ValueError("Missing session timestamp")
            ts = pd.to_datetime(raw_timestamp, utc=True, errors="raise")
            # Floor in UTC to avoid ambiguous/nonexistent wall-clock hours at DST transitions,
            # then convert the unambiguous instant into the site's local timezone.
            ts = ts.floor("h").tz_convert(timezone)
            energy = float(_field(row, "kWhDelivered", "energy_kwh", "energy"))
            site = _field(row, "siteID", "site_id", "station_id")
            user_id = _field(row, "user_identifier", "user_id")
            if user_id is not None and str(user_id).upper().startswith(("HIST_USER_", "EV_USER_", "DRIVER_", "SYNTHETIC_")):
                raise ValueError("Known demonstration sessions are present; use an observed-data export without demo rows.")
            if pd.isna(energy) or not math.isfinite(energy) or energy < 0 or site is None or not str(site).strip():
                raise ValueError("Invalid energy or missing site identifier")
            if ts < start or ts >= end:
                outside_coverage += 1
                continue
            rows.append({"site_id": str(site).strip(), "timestamp": ts, "energy_kwh": energy})
        except (TypeError, ValueError, OverflowError):
            invalid_rows += 1

    if conflicting_duplicates:
        raise ValueError(f"Found {conflicting_duplicates} conflicting duplicate session IDs. Resolve them before training.")
    if invalid_rows:
        raise ValueError(f"Found {invalid_rows} invalid in-file session rows. Resolve them before training so unknown demand is not mislabelled as zero.")
    if not rows:
        raise ValueError("No valid sessions fall inside the declared complete coverage window.")
    sessions = pd.DataFrame(rows)
    sites = sorted(sessions.site_id.unique())
    hours = pd.date_range(start=start, end=end, freq="h", inclusive="left")
    full_index = pd.MultiIndex.from_product([sites, hours], names=["site_id", "timestamp"])
    aggregated = sessions.groupby(["site_id", "timestamp"]).energy_kwh.sum()
    demand = aggregated.reindex(full_index, fill_value=0).rename("demand_kwh").reset_index()
    missing_filled = int(len(demand) - sessions.groupby(["site_id", "timestamp"]).ngroups)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return demand, DataQuality(len(raw), len(rows), outside_coverage, duplicate_count, missing_filled, provenance, digest)


def _features(demand: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for site_id, group in demand.groupby("site_id", sort=False):
        g = group.sort_values("timestamp").copy().reset_index(drop=True)
        ts = pd.DatetimeIndex(g.timestamp)
        hour = ts.hour.to_numpy()
        dow = ts.dayofweek.to_numpy()
        y = g.demand_kwh
        g["hour_sin"] = np.sin(2 * np.pi * hour / 24)
        g["hour_cos"] = np.cos(2 * np.pi * hour / 24)
        g["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        g["dow_cos"] = np.cos(2 * np.pi * dow / 7)
        g["weekend"] = (dow >= 5).astype(int)
        g["lag_1"] = y.shift(1)
        g["lag_24"] = y.shift(24)
        g["lag_168"] = y.shift(168)
        g["rolling_24"] = y.shift(1).rolling(24, min_periods=24).mean()
        g["rolling_168"] = y.shift(1).rolling(168, min_periods=168).mean()
        pieces.append(g)
    result = pd.concat(pieces, ignore_index=True)
    return result.dropna(subset=FEATURES).sort_values("timestamp").reset_index(drop=True)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | None]:
    total = float(np.abs(actual).sum())
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "wape_pct": float(np.abs(actual - predicted).sum() / total * 100) if total > 0 else None,
    }


def _fit_model(model: str, seed: int):
    if model == "random_forest":
        estimator = RandomForestRegressor(n_estimators=64, min_samples_leaf=2, random_state=seed, n_jobs=1)
    elif model == "xgboost":
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:
            raise RuntimeError("XGBoost is optional; install backend/requirements-xgboost.txt to enable it.") from exc
        estimator = XGBRegressor(n_estimators=250, max_depth=5, learning_rate=0.04, subsample=0.9, colsample_bytree=0.9, objective="reg:squarederror", random_state=seed, n_jobs=1)
    else:
        raise ValueError(f"Unsupported model: {model}")
    preprocessor = ColumnTransformer([("site", OneHotEncoder(handle_unknown="ignore"), ["site_id"]), ("numeric", "passthrough", NUMERIC_FEATURES)])
    return Pipeline([("features", preprocessor), ("regressor", estimator)])


def _feature_row(timestamp: pd.Timestamp, history: list[float], site_id: str) -> pd.DataFrame:
    hour, dow = timestamp.hour, timestamp.dayofweek
    return pd.DataFrame([{
        "hour_sin": math.sin(2 * math.pi * hour / 24), "hour_cos": math.cos(2 * math.pi * hour / 24),
        "dow_sin": math.sin(2 * math.pi * dow / 7), "dow_cos": math.cos(2 * math.pi * dow / 7),
        "weekend": int(dow >= 5), "site_id": site_id,
        "lag_1": history[-1], "lag_24": history[-24], "lag_168": history[-168],
        "rolling_24": float(np.mean(history[-24:])), "rolling_168": float(np.mean(history[-168:])),
    }], columns=FEATURES)


def _block_predictions(demand: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, models: dict[str, Any]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Evaluate 24-hour recursive forecasts, refreshing history after each day."""
    output: dict[str, tuple[list[float], list[float]]] = {name: ([], []) for name in ["seasonal_naive", *models]}
    for site_id, group in demand.groupby("site_id", sort=False):
        group = group.sort_values("timestamp")
        initial_history = group[group.timestamp < start].demand_kwh.astype(float).tolist()
        histories = {name: list(initial_history) for name in output}
        truth = group[(group.timestamp >= start) & (group.timestamp < end)]
        by_ts = {row.timestamp: float(row.demand_kwh) for row in truth.itertuples()}
        times = sorted(by_ts)
        for block_start in range(0, len(times), 24):
            block_times = times[block_start:block_start + 24]
            for timestamp in block_times:
                actual = by_ts[timestamp]
                for name in output:
                    history = histories[name]
                    if name == "seasonal_naive":
                        pred = history[-168]
                    else:
                        pred = float(models[name].predict(_feature_row(pd.Timestamp(timestamp), history, site_id))[0])
                    output[name][0].append(actual)
                    output[name][1].append(max(0.0, pred))
                    history.append(max(0.0, pred))
            # At a new 24-hour origin, the preceding day's actuals are now observed.
            if block_start + 24 < len(times):
                for history in histories.values():
                    history[-24:] = [by_ts[t] for t in block_times]
    return {name: (np.asarray(values[0]), np.asarray(values[1])) for name, values in output.items()}


def train_and_evaluate(demand: pd.DataFrame, quality: DataQuality, output_dir: str | Path, use_xgboost: bool = False, seed: int = 42) -> dict[str, Any]:
    sites = sorted(demand.site_id.unique())
    if demand.timestamp.nunique() < MIN_HISTORY_HOURS + 48:
        raise ValueError("At least 14 days of hourly history plus 48 evaluation hours are required.")
    features = _features(demand)
    if features.empty or features.timestamp.nunique() < 48:
        raise ValueError("At least 14 days of hourly history plus 48 evaluation hours are required.")
    unique_times = np.array(sorted(features.timestamp.unique()))
    n = len(unique_times)
    train_end = unique_times[int(n * 0.70)]
    val_end = unique_times[int(n * 0.85)]
    train = features[features.timestamp < train_end]
    val = features[(features.timestamp >= train_end) & (features.timestamp < val_end)]
    test = features[features.timestamp >= val_end]
    if min(len(train), len(val), len(test)) == 0:
        raise ValueError("Chronological split produced an empty partition.")

    model_names = ["random_forest"] + (["xgboost"] if use_xgboost else [])
    candidate_metrics: dict[str, dict[str, Any]] = {}
    fitted: dict[str, Any] = {}
    for name in model_names:
        candidate = _fit_model(name, seed)
        candidate.fit(train[FEATURES], train.demand_kwh)
        fitted[name] = candidate
    validation_blocks = _block_predictions(demand, pd.Timestamp(train_end), pd.Timestamp(val_end), fitted)
    for name, (actual, predicted) in validation_blocks.items():
        candidate_metrics[name] = _metrics(actual, predicted)
    seasonal_val = candidate_metrics["seasonal_naive"]
    del candidate_metrics["seasonal_naive"]
    winner = min(candidate_metrics, key=lambda name: candidate_metrics[name]["mae"])
    if seasonal_val["mae"] <= candidate_metrics[winner]["mae"]:
        winner = "seasonal_naive"

    final_models = {}
    for name in model_names:
        final_candidate = _fit_model(name, seed)
        final_candidate.fit(pd.concat([train, val])[FEATURES], pd.concat([train, val]).demand_kwh)
        final_models[name] = final_candidate
    final_model = final_models.get(winner)
    test_models = final_models
    test_blocks = _block_predictions(demand, pd.Timestamp(val_end), pd.Timestamp(unique_times[-1]) + pd.Timedelta(hours=1), test_models)
    test_results = {name: _metrics(actual, predicted) for name, (actual, predicted) in test_blocks.items()}
    per_site_test = {}
    test_start, test_end = pd.Timestamp(val_end), pd.Timestamp(unique_times[-1]) + pd.Timedelta(hours=1)
    for site_id, site_data in demand.groupby("site_id"):
        site_rows = site_data[(site_data.timestamp >= test_start) & (site_data.timestamp < test_end)]
        if len(site_rows) >= 48:
            site_blocks = _block_predictions(site_data, test_start, test_end, test_models)
            per_site_test[site_id] = {name: _metrics(actual, predicted) for name, (actual, predicted) in site_blocks.items()}
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "model_name": winner,
        "model_version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_kind": "seasonal_naive" if winner == "seasonal_naive" else winner,
        "provenance": quality.provenance,
        "dataset_sha256": quality.dataset_sha256,
        "evaluation_fingerprint": hashlib.sha256(json.dumps({
            "dataset_sha256": quality.dataset_sha256,
            "timezone": str(pd.DatetimeIndex(demand.timestamp).tz),
            "coverage_start": str(demand.timestamp.min()),
            "coverage_end_exclusive": str(demand.timestamp.max() + pd.Timedelta(hours=1)),
        }, sort_keys=True).encode("utf-8")).hexdigest(),
        "site_ids": sites,
        "timezone": str(pd.DatetimeIndex(demand.timestamp).tz) if hasattr(pd.DatetimeIndex(demand.timestamp), "tz") else None,
        "history": {site: demand[demand.site_id == site].sort_values("timestamp").tail(168).demand_kwh.astype(float).tolist() for site in sites},
        "history_end": {site: str(demand[demand.site_id == site].timestamp.max()) for site in sites},
        "latest_observed_hour": str(demand.timestamp.max()),
        "validation_metrics": {"seasonal_naive": seasonal_val, **candidate_metrics},
        "test_metrics": test_results,
        "per_site_test_metrics": per_site_test,
        "reference_demand_kwh": demand[demand.timestamp < test_start].demand_kwh.astype(float).tolist(),
        "reference_prediction_kwh": validation_blocks[winner][1].astype(float).tolist(),
        "selected_by": "lowest chronological validation MAE; seasonal naive included",
        "evaluation_protocol": "chronological 24-hour recursive forecasts; actuals refresh the lag history only at each daily forecast origin",
        "quality": asdict(quality),
        "features": FEATURES,
        "target": "session-arrival-associated energy kWh per site-local hour",
        "software_versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": __import__("sklearn").__version__},
        "model_parameters": {
            "random_forest": {"n_estimators": 64, "min_samples_leaf": 2, "random_state": seed},
            **({"xgboost": {"n_estimators": 250, "max_depth": 5, "learning_rate": 0.04, "subsample": 0.9, "colsample_bytree": 0.9, "random_state": seed}} if use_xgboost else {}),
        },
    }
    joblib.dump({"model": final_model, "metadata": metadata}, output / "model.joblib")
    (output / "model_info.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    _log_mlflow(metadata, winner, output / "model.joblib")
    return metadata


def _log_mlflow(metadata: dict[str, Any], winner: str, artifact: Path) -> None:
    provenance = str(metadata.get("provenance", "")).upper()
    if provenance.startswith(("SYNTHETIC", "TEST_")):
        return
    try:
        import mlflow
    except ImportError:
        return
    try:
        mlflow.set_experiment("voltgrid-hourly-demand")
        with mlflow.start_run(run_name=winner):
            mlflow.log_params({"selected_model": winner, "provenance": metadata["provenance"], "dataset_sha256": metadata["dataset_sha256"]})
            for model_name, params in metadata["model_parameters"].items():
                mlflow.log_params({f"{model_name}.{key}": value for key, value in params.items()})
            mlflow.log_metrics({"data.accepted_sessions": metadata["quality"]["accepted_sessions"], "data.duplicate_sessions": metadata["quality"]["duplicate_sessions"], "data.filled_zero_hours": metadata["quality"]["missing_intervals_filled"]})
            for split in ("validation_metrics", "test_metrics"):
                for model_name, metrics in metadata[split].items():
                    for key, value in metrics.items():
                        if value is not None:
                            mlflow.log_metric(f"{split}.{model_name}.{key}", float(value))
            mlflow.log_artifact(str(artifact.parent / "model_info.json"))
            if artifact.exists():
                mlflow.log_artifact(str(artifact), "model_bundle")
                try:
                    model_uri = f"runs:/{mlflow.active_run().info.run_id}/model_bundle/model.joblib"
                    mlflow.register_model(model_uri, "VoltGridHourlyDemand")
                except Exception as exc:
                    print(f"[MLflow] Run and artifact logged; registry versioning unavailable: {type(exc).__name__}")
    except Exception as exc:
        print(f"[MLflow] Tracking unavailable ({type(exc).__name__}); local artifact remains saved.")


def predict_horizon(bundle: dict[str, Any], site_id: str, horizon: int) -> list[dict[str, Any]]:
    meta = bundle["metadata"]
    if site_id not in meta["site_ids"]:
        raise ValueError(f"Unknown site_id '{site_id}'.")
    if not 1 <= horizon <= 168:
        raise ValueError("horizon must be between 1 and 168 hours.")
    history = list(meta["history"][site_id])
    if len(history) < 168:
        raise ValueError("Model artifact does not contain 168 hours of history for this site.")
    origin = pd.Timestamp(meta["history_end"][site_id])
    results = []
    for step in range(1, horizon + 1):
        ts = origin + pd.Timedelta(hours=step)
        if meta["model_kind"] == "seasonal_naive":
            pred = history[-168]
        else:
            features = _feature_row(ts, history, site_id)
            pred = float(bundle["model"].predict(features)[0])
        pred = max(0.0, float(pred))
        history.append(pred)
        results.append({"timestamp": ts.isoformat(), "predicted_kwh": pred})
    return results


def promote_candidate(candidate_path: str | Path, current_path: str | Path) -> dict[str, Any]:
    """Promote only a real-data candidate that passes a validation-only gate.

    Existing incumbents are compared only when their dataset fingerprint matches;
    otherwise the caller must review the changed evaluation window manually.
    """
    candidate_path, current_path = Path(candidate_path), Path(current_path)
    if not candidate_path.is_file():
        raise ValueError("Candidate artifact does not exist.")
    candidate = joblib.load(candidate_path)
    meta = candidate.get("metadata", {})
    if str(meta.get("provenance", "")).upper().startswith(("SYNTHETIC", "TEST_", "DEMO", "MOCK")):
        raise ValueError("Synthetic demonstration models cannot be promoted.")
    selected = meta.get("model_name")
    validation = meta.get("validation_metrics", {})
    candidate_score = validation.get(selected, {}).get("mae")
    baseline_score = validation.get("seasonal_naive", {}).get("mae")
    if candidate_score is None or baseline_score is None or candidate_score > baseline_score:
        raise ValueError("Candidate did not pass the seasonal-naive validation MAE gate.")
    if current_path.is_file():
        incumbent = joblib.load(current_path)
        incumbent_meta = incumbent.get("metadata", {})
        candidate_fingerprint = meta.get("evaluation_fingerprint")
        incumbent_fingerprint = incumbent_meta.get("evaluation_fingerprint")
        if not candidate_fingerprint or not incumbent_fingerprint or incumbent_fingerprint != candidate_fingerprint:
            raise ValueError("Candidate and incumbent do not share a verified data, timezone, and coverage fingerprint; compare them manually before promotion.")
        incumbent_name = incumbent_meta.get("model_name")
        incumbent_score = incumbent_meta.get("validation_metrics", {}).get(incumbent_name, {}).get("mae")
        if incumbent_score is not None and candidate_score >= incumbent_score:
            raise ValueError("Candidate validation MAE does not improve on the incumbent.")
    current_path.parent.mkdir(parents=True, exist_ok=True)
    if current_path.exists():
        archive = current_path.parent / "archive" / f"{incumbent_meta.get('model_version', 'unknown')}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        archive.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current_path, archive / "model.joblib")
    temporary = current_path.with_suffix(current_path.suffix + f".{meta.get('model_version', 'candidate')}.candidate")
    shutil.copy2(candidate_path, temporary)
    temporary.replace(current_path)
    return {"promoted": True, "model_version": meta.get("model_version"), "model_name": selected, "validation_mae": candidate_score, "provenance": meta.get("provenance")}
