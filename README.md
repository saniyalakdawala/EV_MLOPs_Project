# Smart EV Charging Infrastructure Database (VoltGrid Mumbai)

> **Advanced Database Management Systems (ADBMS) Academic Mini Project**  
> **Track:** GIS-Based Management, Availability Tracking and DBA Operations  
> **Target Region:** Mumbai Metropolitan Region (MMR) & Maharashtra, India  
> **Grade / Rubric Level:** High Distinction / 10-Mark Academic Submission

---

## 1. Project Overview

**VoltGrid Mumbai** is a production-grade, database-driven spatial application engineered to manage electric vehicle (EV) charging stations across Mumbai, Maharashtra, and India. Unlike simple CRUD applications, this project is built to demonstrate **how a senior Database Administrator (DBA) maintains consistency, transactional atomicity, concurrency control, spatial indexing performance, and disaster recovery** in a mission-critical infrastructure database.

### Technology Stack
* **Database Engine**: PostgreSQL 17.5
* **Spatial System**: PostGIS (`geography(Point, 4326)`) and native PostgreSQL GiST spatial indexing (`point(longitude, latitude)`)
* **Database Administration**: pgAdmin 4 & SQL command-line tools
* **Backend API**: Python 3.13 + FastAPI, psycopg2 connection pooling, Pydantic v2
* **Frontend Dashboard**: React 19 + Vite 8 + Leaflet GIS mapping + Vanilla CSS design system
* **Geocoding & Location**: OpenStreetMap Nominatim with caching, rate-limiting, and debounced place autocomplete
* **Data Processing**: Python 3.13 ETL pipeline with spatial deduplication (<30m)

---

## 2. Academic Evaluation Rubric Mapping (10 Marks)

| Rubric Component | Marks | Technical Implementation | Core Evidence / Deliverable |
| :--- | :--- | :--- | :--- |
| **Dataset & Real-World Problem** | **1.5** | Real OpenChargeMap & NITI Aayog geodata; 2,141 staged records filtered into 1,951 normalized stations (119 in MH, 9 authentic stations in core Mumbai MMR) with 30m spatial deduplication. | [`data/raw/`](file:///c:/Projects/ADBMS/data/raw/), [`docs/dataset_documentation.md`](file:///c:/Projects/ADBMS/docs/dataset_documentation.md), [`scripts/ingest_pipeline.py`](file:///c:/Projects/ADBMS/scripts/ingest_pipeline.py) |
| **Database Design** | **2.0** | Third Normal Form (3NF) relational design; foreign keys with `CASCADE` & `RESTRICT`; check constraints; **partial unique index preventing concurrent double-bookings**. | [`database/01_schema.sql`](file:///c:/Projects/ADBMS/database/01_schema.sql), [`database/02_constraints.sql`](file:///c:/Projects/ADBMS/database/02_constraints.sql), [`docs/er_diagram.md`](file:///c:/Projects/ADBMS/docs/er_diagram.md) |
| **ADBMS Core Track (GIS)** | **3.0** | Spatial indexing via GiST; radius searches with bounding-box pruning; KNN nearest-neighbor; exact geodesic distance calculation. | [`database/04_spatial_queries.sql`](file:///c:/Projects/ADBMS/database/04_spatial_queries.sql), [`backend/app/routers/stations.py`](file:///c:/Projects/ADBMS/backend/app/routers/stations.py), [`frontend/src/components/MapView.jsx`](file:///c:/Projects/ADBMS/frontend/src/components/MapView.jsx) |
| **SQL Queries & Concurrency** | **1.5** | Multi-threaded race condition demonstration with pessimistic row-level locking (`SELECT ... FOR UPDATE`); ACID rollback verification. | [`database/05_transactions.sql`](file:///c:/Projects/ADBMS/database/05_transactions.sql), [`database/06_concurrency.sql`](file:///c:/Projects/ADBMS/database/06_concurrency.sql), [`scripts/test_concurrency.py`](file:///c:/Projects/ADBMS/scripts/test_concurrency.py) |
| **DBA Responsibilities** | **1.0** | Role-Based Access Control (Admin, App, Analyst) with least privilege; `pg_stat_activity` session inspector; custom-format compressed backup (`pg_dump -Fc`). | [`database/08_security.sql`](file:///c:/Projects/ADBMS/database/08_security.sql), [`database/09_monitoring.sql`](file:///c:/Projects/ADBMS/database/09_monitoring.sql), [`database/10_backup_recovery.md`](file:///c:/Projects/ADBMS/database/10_backup_recovery.md) |
| **Report, Presentation & Viva** | **1.0** | 12-slide academic presentation outline, comprehensive viva examiner question bank, and live demonstration guide. | [`docs/presentation_slides.md`](file:///c:/Projects/ADBMS/docs/presentation_slides.md), [`docs/viva_preparation.md`](file:///c:/Projects/ADBMS/docs/viva_preparation.md), [`docs/demo_guide.md`](file:///c:/Projects/ADBMS/docs/demo_guide.md) |

---

## 3. Location Search & Tardeo Audit Findings

### The Problem Investigated
When searching for a location such as **Tardeo, Mumbai**, the system previously displayed stations in Kurla or returned simulated results.

### Root Cause Identified
1. **Raw Dataset Coverage Gap**: In the original open datasets (`ocm_all_india.json` and `indian_ev_charging_stations.geojson`), there are **zero** charging stations south of latitude 19.07° N (South Mumbai, including Tardeo, Tulsiwadi, Haji Ali, Mahalaxmi, Colaba).
2. **Default Radius Match**: The southernmost station in the database is `MobiLane Equinox Business Park` (Kurla West) at `(19.071566, 72.877213)`. With the previous default 15 km radius, Kurla is **12.67 km** from Tardeo and was returned as the nearest existing record.
3. **Pipeline Normalization Bug**: Line 206 of `scripts/ingest_pipeline.py` previously defaulted empty city values to `'Mumbai'`, causing 349 non-MMR stations across India to be mislabeled as Mumbai.
4. **Candidate Records Checked**: Investigation of candidate names (*Adani Charging Station*, *Jio-bp pulse*, *Tata Power near Tardeo*) confirmed they do **not** exist in the imported raw datasets. In accordance with strict engineering standards, no fake stations were hardcoded.

### Corrected Behavior
- **Geocoding**: "Tardeo, Mumbai" resolves accurately to `(18.9749, 72.8134)` (Tulsi Wadi / Tardeo).
- **At <= 5 km radius**: Returns **0 stations** honestly with a user-facing empty state notice:
  `"No charging stations found within 5 km of Tardeo, Mumbai. Try expanding your search radius."`
  Kurla is **never** returned at <= 5 km.
- **At 15 km radius**: Kurla West is returned with its true distance (`12.67 km`) and clearly labeled with its actual location, not as a local Tardeo charger.

---

## 4. Quick Start Guide (Windows)

### Prerequisites
1. **PostgreSQL 17** installed and running on `localhost:5432`. Configure local credentials in the ignored `backend/.env` file; never commit it.
2. **Python 3.10+** (verified on Python 3.13).
3. **Node.js 18+** (verified on Node.js v22.18).

---

### Step 1: Database Setup & Data Ingestion (One-Time)
Run these commands in PowerShell:
```powershell
# 1. Create the database ev_db
python scripts/init_db.py

# 2. Deploy the 3NF schema, tables, triggers, and constraints
python scripts/deploy_schema.py

# 3. Optional: inspect the ingestion script before running it.
# WARNING: this legacy academic pipeline truncates the operational tables before loading.
# Do not run it against a database containing records you need to preserve.
```

The legacy schema deployment also drops and recreates its tables. Keep backups and use an isolated database for demonstrations; these setup scripts are not safe production migrations.

---

### Step 2: Run the Verification Suite
Execute the automated Python test suite to verify all DBA operations and location searches:
```powershell
# ADBMS Core Track Verification
python scripts/test_constraints.py        # 5/5 Integrity constraints & check guards
python scripts/test_transactions.py       # Atomic commit & simulated rollback proof
python scripts/test_concurrency.py        # Live race condition & row locking (SELECT ... FOR UPDATE)
python scripts/test_indexes.py            # EXPLAIN ANALYZE comparison (0.508ms vs 0.947ms)
python scripts/test_security.py           # Role permissions & least privilege RBAC
python scripts/test_monitoring.py         # 99.29% cache hit ratio & active connection PIDs

# Location Search & Tardeo Regression Verification
python scripts/test_tardeo_regression.py  # Mandatory Tardeo regression test (3km vs 15km)
python scripts/test_location_search_suite.py # 10/10 location search & geocoding test cases
```

Forecasting and API smoke tests use pytest without a live database. From the backend directory, run `python -m pytest tests -q`. Frontend checks are `npm run lint` and `npm run build` from the frontend directory. The database-backed scripts above require the configured PostgreSQL/PostGIS database and seeded project data.

---

### Step 3: Launch the Full-Stack Application

**Terminal 1 — Backend Server:**
```powershell
.\run_backend.bat
# Running at http://127.0.0.1:8000
# Swagger API docs at http://127.0.0.1:8000/docs
```

**Terminal 2 — Frontend Dashboard:**
```powershell
.\run_frontend.bat
# Running at http://localhost:5173
```

Open your browser to: **`http://localhost:5173`**

---

## 5. API Endpoints & SQL Patterns

### 1. Geocoding Search (`GET /api/geocoding/search`)
```http
GET /api/geocoding/search?q=Tardeo%2C+Mumbai&limit=5 HTTP/1.1
Host: 127.0.0.1:8000
```
**Response:**
```json
[
  {
    "name": "Tulsi Wadi",
    "formatted_address": "Raheja Excelsior, Tardeo, Pandit Madan Mohan Malviya Marg, Cowasji Jehangir Colony, Tulsi Wadi, D Ward, Mumbai Zone 1, Mumbai, Mumbai City District, Maharashtra, 400034, India",
    "latitude": 18.9749183,
    "longitude": 72.8134203,
    "place_type": "neighbourhood"
  }
]
```

### 2. Nearby Stations Spatial Query (`GET /api/stations/nearby`)
```http
GET /api/stations/nearby?lat=18.9749183&lon=72.8134203&radius_km=3.0 HTTP/1.1
Host: 127.0.0.1:8000
```
**Response (at 3.0 km):**
```json
[]
```

**Spatial Query Used (with GiST bounding-box pruning & Haversine distance):**
```sql
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.address,
    s.city,
    s.state,
    s.latitude,
    s.longitude,
    round(
        (6371.0 * acos(
            least(1.0, greatest(-1.0,
                cos(radians(:user_lat)) * cos(radians(s.latitude)) *
                cos(radians(s.longitude) - radians(:user_lon)) +
                sin(radians(:user_lat)) * sin(radians(s.latitude))
            ))
        ))::numeric, 2
    ) AS distance_km
FROM charging_stations s
WHERE point(s.longitude, s.latitude) <@ box(
    point(:max_lon, :max_lat),
    point(:min_lon, :min_lat)
)
ORDER BY distance_km ASC
LIMIT 50;
```

---

## 6. Key DBA & Technical Highlights

### 1. Partial Unique Index Safeguard
A traditional unique constraint on `(port_id)` would prevent a port from ever recording a second completed session. We solved this via a partial unique index:
```sql
CREATE UNIQUE INDEX uq_active_session_per_port 
ON charging_sessions (port_id) 
WHERE session_status = 'ACTIVE';
```

### 2. Pessimistic Row-Level Locking (`SELECT ... FOR UPDATE`)
When starting a session:
```sql
SELECT port_id, status FROM charging_ports WHERE port_id = %s FOR UPDATE;
```
If two users request the same port simultaneously, the second transaction is placed in a queue until the first completes. When unblocked, it observes `IN_USE` and safely receives a `409 Conflict` error.

### 3. Role-Based Access Control (RBAC)
* **`ev_admin`**: Full administrative DDL privileges.
* **`ev_app_user`**: DML (`SELECT, INSERT, UPDATE`) used by the FastAPI backend; cannot drop tables.
* **`ev_analyst`**: Read-only `SELECT` permissions; blocked from modifying table state (`permission denied`).

---

## 7. Academic License & Acknowledgments
* **OpenChargeMap (OCM)**: Global public registry for electric vehicle infrastructure (CC BY 4.0).
* **NITI Aayog / E-Amrit Portal**: Government of India National EV Portal.
* Sourced for academic evaluation under the B.Tech Data Science curriculum.

---

## 8. VoltGrid Demand Forecasting and MLOps Extension

The forecasting capability extends this React/FastAPI application. It does not replace the GIS station explorer, session pages, or DBA tools. The integration design is documented in [`docs/forecasting_architecture.md`](docs/forecasting_architecture.md).

### Data provenance and forecast target

The existing session ingestion path seeds simulated sessions and port statuses. Those rows are not treated as observed charging demand and are excluded when known demo user identifiers are present. Forecast training accepts an explicit session CSV and requires a complete coverage window and a provenance label. The provenance label is supplied by the trainer and is not an external authenticity check; retain the source export, access terms, and checksum with the model review.

The initial target is **session-arrival-associated hourly energy (kWh)**: each session's delivered kWh is assigned to the local hour in which it connected. This is not a measured energy profile within each hour. The trainer fills empty bins with zero only inside the explicitly declared complete coverage range. ACN-Data records expose session connection time, delivered kWh, site and station IDs, and a site timezone; its source describes California workplace sites. ACN's documentation says user inputs are absent for unclaimed sessions and default requested energy and duration are assumed; analyze `userID`/claim status and policy periods before treating those fields as behavioral observations. The recorded `kWhDelivered` is measured energy, but historical site policies and workplace schedules can still bias a model. ACN can demonstrate the pipeline, but it does not validate a Mumbai forecast. The API requires registration and registration terms restrict use to education and research. Review the [official ACN-Data documentation](https://ev.caltech.edu/dataset) and [portal registration terms](https://ev.caltech.edu/register) before downloading or redistributing data. Preserve the complete export window and source provenance.

### Local training

Use Python 3.12 and a virtual environment from PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Run an explicitly labelled synthetic plumbing demo (not real demand data):

```powershell
python -m app.forecasting.cli demo --workdir ..\data\forecast_demo
New-Item -ItemType Directory -Force .\models\current | Out-Null
Copy-Item ..\data\forecast_demo\model\model.joblib .\models\current\model.joblib -Force
```

For eligible real or research dataset exports, provide a complete, hourly aligned coverage range. ACN timestamps are UTC; specify the site's IANA timezone for local hourly aggregation:

```powershell
python -m app.forecasting.cli train `
  --csv ..\data\acn_sessions.csv `
  --coverage-start "2024-01-01T00:00:00" `
  --coverage-end "2024-04-01T00:00:00" `
  --timezone "America/Los_Angeles" `
  --provenance "ACN-Data site=caltech; downloaded YYYY-MM-DD; education/research use"
```

The command compares a 168-hour seasonal-naive baseline and Random Forest; optional XGBoost is available through `requirements-xgboost.txt`. The chronological 70/15/15 partitions are evaluated with recursive 24-hour forecast blocks, refreshing lag history only at daily forecast origins. MAE/RMSE and WAPE (when defined) are reported for validation and held-out testing. The winner is selected on validation MAE; test metrics are separate. Candidate artifacts are written to unique, ignored directories under `backend/models/candidates/`. Test scores are only representative of the named dataset and geography.

Model artifacts use joblib/pickle serialization. The API loads the configured artifact during forecast requests, so only point it at an artifact produced by a trusted training workflow; loading an untrusted artifact can execute code.

Real-data training writes a unique candidate under `backend/models/candidates/`; it does not replace the serving model. After reviewing the validation report, use the explicit promotion gate:

```powershell
$candidatePath = Read-Host "Path to the reviewed candidate model.joblib"
python -m app.forecasting.cli promote --candidate $candidatePath
```

Promotion rejects synthetic data, requires candidate validation MAE to match or beat the seasonal baseline, and requires a strict improvement over an incumbent trained on the same dataset fingerprint. Different dataset fingerprints require manual review and currently block promotion. Existing serving artifacts are archived before replacement. Held-out test scores are not used to select or promote a model.

### MLflow, API, and dashboard

For local MLflow tracking and model registry, start the local services and point training at the MLflow server:

```powershell
$env:DB_USER = "your-local-db-user"
$env:DB_PASSWORD = Read-Host "Local PostgreSQL password"
$env:GRAFANA_ADMIN_PASSWORD = Read-Host "Local Grafana password"
docker compose up --build -d mlflow prometheus grafana backend frontend
$env:MLFLOW_TRACKING_URI = "http://localhost:5000"
```

Training logs parameters, dataset fingerprint, split metrics, and the model bundle to MLflow; model registration is attempted when the configured tracking server supports a registry. Open MLflow at `http://localhost:5000`, Prometheus at `http://localhost:9090`, Grafana at `http://localhost:3000`, the API docs at `http://localhost:8000/docs`, and VoltGrid at `http://localhost:5173`. The backend connects to the existing PostgreSQL service on the host; it does not create or migrate a database.

Forecast routes are `GET /api/forecast/health`, `GET /api/forecast/ready`, `GET /api/forecast/model-info`, `GET /api/forecast/evaluation`, `POST /api/forecast/predict`, `GET /api/forecast/monitoring/drift`, and `GET /api/forecast/monitoring/accuracy`; Prometheus scrapes `GET /metrics`. The forecast tab stays in an unavailable state when no model artifact exists. Forecast requests must use the last complete observed hour from the model metadata and a known site ID. The API records forecast timestamp and model version. No accuracy is claimed until actual future observations are supplied.

Delayed evaluation is available for aligned CSV files:

```powershell
python -m app.forecasting.cli delayed-eval --forecasts ..\data\forecast\predictions.csv --actuals ..\data\hourly_actuals.csv
```

For delayed monitoring, place validated hourly actuals in `data/forecast/actuals.csv` with columns `site_id,timestamp,actual_kwh`. The API joins outcomes to recorded forecasts in UTC, keeps the most recent forecast for each site-hour, and publishes MAE/RMSE/bias per model version only for matched observations. The prediction-drift utility uses a two-sample Kolmogorov-Smirnov test when the reference and recent output distributions both contain at least 20 values. Drift is only a distribution-change signal and does not prove accuracy loss. The API reports that data drift is awaiting observations until a real feature feed is connected. Retraining and promotion are manual; drift does not deploy a model.

### Containers, Kubernetes, CI, and Azure

`docker-compose.yml` provides local backend/frontend, MLflow, Prometheus, and Grafana. The Compose file assumes the existing PostgreSQL service is available on the host; it does not initialize the legacy schema. Create a model artifact before expecting `/api/forecast/ready` to succeed.

Kubernetes manifests live in `deploy/kubernetes/`. They include deployment/service resources, probes, resource limits, HPA, configuration, secret references, and PVCs for model artifacts and forecast logs. Supply environment-specific DB settings, a Kubernetes Secret named `voltgrid-secrets`, ACR image names, and a trained model in the model PVC before rollout. The Azure overlay uses Azure Files CSI. The frontend proxies `/api` to the backend service. If a candidate uses XGBoost, set the GitHub `INCLUDE_XGBOOST` variable to `true` before manually publishing the API image; the default container omits that optional dependency.

GitHub Actions CI runs Python tests, frontend lint/build, and Docker build checks without Azure credentials. Manual ACR publishing and AKS rollout workflows use OIDC and a protected `production` GitHub Environment. Configure Azure federated credentials and environment approval rules in GitHub before use. No workflow provisions Azure resources. A Kubernetes `LoadBalancer` service can incur Azure charges; review cost and resource settings before applying the Azure overlay. Azure configuration is **not deployed or verified** by this repository setup.

### Current limitations

- The local PostgreSQL database was unavailable during this implementation, so existing DB-backed routes and live DB integration were not verified.
- No ACN token or export was provided; any model metrics from the synthetic demo are labelled demonstration-only.
- ACN geography and workplace charging patterns do not validate Mumbai station demand.
- Hourly targets allocate whole-session energy to connection hour; measured hourly delivery requires trustworthy interval meter data.
- Docker, Kubernetes, MLflow server, Azure authentication, ACR, and AKS deployment require local tools/credentials and are not claimed as verified until explicitly run.
