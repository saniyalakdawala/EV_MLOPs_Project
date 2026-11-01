# VoltGrid Demand Forecasting Architecture

## Design decision

Demand forecasting is an additive capability inside VoltGrid. The existing React/Vite application, FastAPI process, PostgreSQL/PostGIS schema, station routes, GIS search, and DBA pages remain the system of record and user interface. Forecast endpoints are added to the existing backend and use a separate forecasting module so ML dependencies and business logic remain isolated without adding a second web service.

## Data and target

Session ingestion accepts explicitly selected CSV exports using ACN-Data-compatible fields (`connectionTime`, `kWhDelivered`, `siteID`, `stationID`, `sessionID`, and `timezone`) or normalized VoltGrid fields. Each imported dataset is tagged with provenance. Existing database sessions are not used for model training by default because the repository ingestion path generates simulated sessions.

The initial target is **hourly session-arrival-associated energy (kWh)**: session energy is assigned to the hour in which the session connects, grouped by site. It is not a meter-level profile of energy physically delivered during each hour. This target can be built from session totals without pretending session energy is known at connection time as an input feature. The forecast is a site-hour aggregate and ACN geography is not treated as Mumbai validation.

An importer must be given a complete coverage window before empty hours inside that window are represented as zero demand. Missing rows outside an explicitly complete window remain unknown. Duplicated session IDs are deduplicated and counted; rows outside the selected range are excluded and counted; invalid in-range rows cause training to stop so missing energy is never silently converted to zero. Timestamps are converted from UTC into the selected site's IANA timezone before hourly bucketing.

## Training and serving

`backend/app/forecasting/` owns data validation, aggregation, lag features, chronological splits, seasonal-naive and Random Forest comparisons, optional XGBoost, evaluation, MLflow logging, artifact metadata, and inference. A CLI supports real CSV ingestion and an opt-in, clearly labelled synthetic plumbing demonstration. The demo cannot be selected as production training data.

The existing FastAPI process loads a locally configured, validated artifact and adds forecast, model-info, evaluation-summary, readiness, and Prometheus routes. With no trained artifact, readiness is false and forecasts return a clear service-unavailable response. No database migration is needed. PostgreSQL session extraction is an explicit future adapter that must require a provenance allowlist; it is not enabled because current session provenance is not reliable.

## Operations

Local development uses the existing backend and frontend, with optional MLflow, Prometheus, and Grafana services in Docker Compose. Docker and Kubernetes configuration is additive. GitHub Actions performs offline checks, tests, frontend build, and container build; Azure publish/deploy jobs are gated by repository variables and secrets. ACR/AKS configuration is documented and checked in but is not provisioned or deployed by this change.

Prediction records carry their timestamp and model version. Delayed outcomes can later be submitted to a separate forecast-observations file/store for evaluation; no accuracy is reported until actual outcomes arrive. Prediction distribution drift uses a two-sample Kolmogorov-Smirnov test when at least 20 baseline and recent predictions exist. Feature drift remains unmeasured until an observed feature feed is connected. Drift is descriptive, not evidence of accuracy loss, and does not automatically promote or deploy models. Training writes unique candidate artifacts; the explicit promotion command rejects synthetic data, gates on validation MAE, and blocks comparisons across differing dataset fingerprints.
