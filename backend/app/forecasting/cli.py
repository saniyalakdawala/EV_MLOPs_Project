from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.forecasting.monitoring import delayed_accuracy, drift_report
from app.forecasting.pipeline import DataQuality, load_hourly_demand, promote_candidate, train_and_evaluate


def make_demo(path: Path) -> None:
    """Create clearly synthetic sessions for plumbing checks only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2026)
    times = pd.date_range("2025-01-01", periods=24 * 120, freq="h", tz="UTC")
    rows = []
    for site_idx, site in enumerate(("DEMO_SITE_A", "DEMO_SITE_B")):
        for timestamp in times:
            hour_factor = 0.25 + 1.4 * math.exp(-((timestamp.hour - 18) / 4.0) ** 2)
            weekday_factor = 1.0 if timestamp.dayofweek < 5 else 0.55
            weekly_factor = 1.0 + 0.12 * math.sin(2 * math.pi * timestamp.dayofyear / 30)
            hourly_demand = max(0.0, (site_idx + 1) * (2.3 * hour_factor * weekday_factor * weekly_factor + rng.normal(0, 0.15)))
            # Session totals are assigned to their connection hour for the demo target.
            if hourly_demand > 0.15:
                rows.append({"sessionID": f"SYN-{site}-{timestamp.isoformat()}", "connectionTime": timestamp.isoformat(), "kWhDelivered": round(hourly_demand, 4), "siteID": site, "timezone": "UTC"})
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="VoltGrid demand forecasting tools")
    sub = parser.add_subparsers(dest="command", required=True)
    train = sub.add_parser("train", help="Train/evaluate from a complete session CSV")
    train.add_argument("--csv", required=True)
    train.add_argument("--coverage-start", required=True, help="Inclusive whole-hour ISO datetime")
    train.add_argument("--coverage-end", required=True, help="Exclusive whole-hour ISO datetime")
    train.add_argument("--timezone", default="UTC", help="IANA timezone used to bucket hours")
    train.add_argument("--provenance", required=True)
    train.add_argument("--output", default=None, help="Candidate output directory; defaults to a unique models/candidates/<UTC-version> path")
    train.add_argument("--xgboost", action="store_true")
    demo = sub.add_parser("demo", help="Create labelled synthetic data and exercise the pipeline")
    demo.add_argument("--workdir", default="data/forecast_demo")
    delayed = sub.add_parser("delayed-eval", help="Score forecasts once actual hourly observations are available")
    delayed.add_argument("--forecasts", required=True)
    delayed.add_argument("--actuals", required=True)
    promote = sub.add_parser("promote", help="Apply a validation-only quality gate and copy a candidate to the serving path")
    promote.add_argument("--candidate", required=True)
    promote.add_argument("--current", default="models/current/model.joblib")

    args = parser.parse_args()
    if args.command == "demo":
        root = Path(args.workdir)
        csv_path = root / "synthetic_demo_sessions.csv"
        make_demo(csv_path)
        demand, quality = load_hourly_demand(csv_path, "UTC", "2025-01-01T00:00:00Z", "2025-05-01T00:00:00Z", "SYNTHETIC_DEMONSTRATION_NOT_REAL_DEMAND")
        result = train_and_evaluate(demand, quality, root / "model", use_xgboost=False)
        (root / "evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"label": "SYNTHETIC DEMONSTRATION ONLY — not real charging demand", "selected_model": result["model_name"], "validation_metrics": result["validation_metrics"], "test_metrics": result["test_metrics"], "artifact": str(root / "model" / "model.joblib")}, indent=2))
    elif args.command == "train":
        if args.provenance.upper().startswith("SYNTHETIC"):
            parser.error("The real-data training command refuses synthetic provenance; use the explicit demo command instead.")
        demand, quality = load_hourly_demand(args.csv, args.timezone, args.coverage_start, args.coverage_end, args.provenance)
        output = args.output or str(Path("models/candidates") / datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"))
        result = train_and_evaluate(demand, quality, output, args.xgboost)
        print(json.dumps(result, indent=2))
    elif args.command == "delayed-eval":
        print(json.dumps(delayed_accuracy(args.forecasts, args.actuals), indent=2))
    elif args.command == "promote":
        print(json.dumps(promote_candidate(args.candidate, args.current), indent=2))


if __name__ == "__main__":
    main()
