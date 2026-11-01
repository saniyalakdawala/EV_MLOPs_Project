# VoltGrid Mumbai: Implementation Gaps, Discrepancy Audit & Remediation Plan

This document establishes an honest, rigorous audit of the **VoltGrid Mumbai** ADBMS project. In accordance with university academic integrity standards, this audit distinguishes **fully implemented features**, **partially implemented features**, **simulated demonstrations**, and **proposed future enhancements**.

---

## 1. Summary Implementation Audit Matrix

| Feature / Component | Relevant File / Table | Implementation Status | Actual Evidence in Project | Missing Work / Remediation Needed |
| :--- | :--- | :---: | :--- | :--- |
| **Relational 3NF Schema & Constraints** | `database/01_schema.sql`, `02_constraints.sql` | **Fully Implemented** | `charging_stations` (952), `charging_ports` (2,026), `charging_sessions` (13), `station_status_history` (2,027). All PK, FK, CHECK, and partial unique constraints verified in system catalogs. | None. Production schema is fully operational. |
| **Spatial Indexing & Radius Search** | `charging_stations`, `database/07_indexes_performance.sql` | **Fully Implemented (Native GiST)** | GiST index `idx_stations_point_gist` on `point(longitude, latitude)`. EXPLAIN ANALYZE confirms Bitmap Index Scan (0.225 ms vs 0.502 ms seq scan). Bounding-box queries with Haversine distance. | PostGIS `geography` type extension activation requires Administrator elevation (see Gap 1). |
| **ACID Transactions & Row-Level Locking** | `database/05_transactions.sql`, `backend/app/routers/sessions.py` | **Fully Implemented** | `SELECT ... FOR UPDATE` acquires exclusive row locks; concurrent conflict detection tested via `scripts/test_concurrency.py` (Alice locks, Bob rejected). Rollback verified. | None. Fully functional in backend and SQL scripts. |
| **Role-Based Access Control (RBAC)** | `database/08_security.sql`, `pg_roles` | **Fully Implemented** | Roles `ev_admin`, `ev_app_user`, `ev_analyst` created. Tested via `scripts/test_security.py`: `ev_analyst` can SELECT 952 rows but receives `permission denied` on UPDATE. | None. Least privilege principle strictly enforced. |
| **DBA Monitoring & System Catalogs** | `database/09_monitoring.sql`, `backend/app/routers/dba.py` | **Fully Implemented** | Live queries on `pg_stat_activity`, `pg_stat_database` (99.85% cache hit), and `pg_class` storage sizes. Exposed via FastAPI `/api/dba/*` endpoints. | None. Operational in backend dashboard. |
| **MMR Boundary Point-in-Polygon Validation** | `data/mmr_boundary.geojson`, `scripts/test_pipeline_boundary_filter.py` | **Fully Implemented (Application Layer)** | Shapely Point-in-Polygon containment tests 2,141 raw records: 8 accepted, 2,133 non-MMR quarantined. Correctly rejects Tamil Nadu, UP, HP records. | PostGIS database-level polygon table not yet loaded (see Gap 4). |
| **National Master Dataset** | `stg_national_master_ev_stations`, `data/national_master_ev_stations.csv` | **Partially Implemented (Staging Only)** | 30,263 validated records loaded into `stg_national_master_ev_stations` (947 inside MMR, 29,316 outside MMR). Searchable via API `scope=all`. | Intentionally not merged into production `charging_stations` to preserve Mumbai focus. |
| **PostGIS Extension Activation** | `database/01_schema.sql`, `scripts/activate_postgis.py` | **Fully Implemented & Active** | PostGIS 3.6.2 is active in `ev_db`. `geom geography(Point, 4326)` populated for all 952 stations. Spatial GiST index `idx_stations_spatial_gist` verified with `ST_DWithin`. | None. PostGIS is fully operational. |
| **Live Charger Availability Telemetry** | `charging_ports.status`, `backend/app/routers/stations.py` | **Simulated / Synthetic** | Initial statuses seeded. Port booking transitions status from `AVAILABLE` to `IN_USE`. | Neither BEE nor OCM provides real-time OCPP / WebSocket telemetry for all stations. Live occupancy is simulated. |
| **Disaster Recovery Restore Test** | `database/10_backup_recovery.md`, `data/ev_db_backup.dump` | **Partially Implemented (Verified TOC)** | Compressed backup `ev_db_backup.dump` (348 KB) exists. Table of Contents verified using `pg_restore -l`. | Live restore into a fresh database (`ev_db_recovery_test`) marked **UNTESTED** to prevent accidental production overwrite. |
| **Documentation Metrics Consistency** | `docs/dataset_documentation.md` | **Documentation Drift** | Old docs cite 1,951 stations and 3,186 ports from preliminary Kaggle tests. | Needs updating to actual verified counts: 952 stations and 2,026 ports in production DB. |

---

## 2. Detailed Technical Gaps & Remediation Steps

### Gap 1: PostGIS Extension Activation — [RESOLVED & ACTIVE]
- **Previous Status**: PostGIS binaries were pending OS-level copying due to Windows UAC and running service locks.
- **Resolution**: The PostgreSQL 17 service (`postgresql-x64-17`) was safely stopped, PostGIS 3.6.2 binaries were merged via `robocopy`, the service was restarted, and `scripts/activate_postgis.py` was executed.
- **Active State in Production**:
  - `SELECT PostGIS_Full_Version();` confirms: `POSTGIS="3.6.2 3.6.2" [EXTENSION] PGSQL="170" GEOS="3.14.1dev" PROJ="8.2.1"`.
  - Column `geom geography(Point, 4326)` is present and populated for **100% of the 952 stations** in `charging_stations`.
  - Spatial GiST index `idx_stations_spatial_gist` is active on `geom`.
  - Native PostGIS queries (`ST_DWithin`, `ST_Distance`, and spatial sorting `<->`) are now running natively in PostgreSQL!

---

### Gap 2: Production Table (`charging_stations`) vs National Staging Table (`stg_national_master_ev_stations`)
- **Current State**: 
  - `charging_stations` contains **952 verified stations** (936 BEE, 8 OCM, 8 OSM), all located strictly within the Mumbai Metropolitan Region (latitude 18.64° to 19.48° N, longitude 72.77° to 73.35° E).
  - `stg_national_master_ev_stations` contains **30,263 stations** across all 36 Indian states and UTs (with `is_inside_mmr` boolean flag).
  - `data/master_ev_stations.csv` contains **947 stations**.
- **Explanation of 5-Record Difference**:
  In `charging_stations`, there are 952 records compared to 947 in `master_ev_stations.csv`. The 5 additional records represent 1 OpenChargeMap and 4 OpenStreetMap stations that were flagged as pending ground review in the latest CSV build (due to generic names or proximity), but were retained in the production database from an earlier approved deployment.
- **Design Decision**: The national dataset was intentionally **not** dumped into `charging_stations`. In a production architecture, keeping regional operational data isolated from nationwide reference catalogs prevents bloated index sizes and preserves sub-millisecond query performance.

---

### Gap 3: Live Hardware Availability vs Static Directory Data
- **Current State**: The Bureau of Energy Efficiency (BEE) and OpenChargeMap provide static directory data (geocoding, addresses, operator names, connector types, rated power kW). They do **not** provide live real-time charging gun occupancy.
- **Implementation**: The project implements port status transitions (`AVAILABLE` $\to$ `IN_USE` $\to$ `AVAILABLE`) and status history logging within transactional application boundaries (`backend/app/routers/sessions.py`).
- **Academic Distinction**: The report must clearly state that **real-time port status transitions are simulated within the local database engine**, rather than fed from a live commercial OCPP network.

---

### Gap 4: Database Spatial Boundary Table vs Application-Layer Boundary Filtering
- **Current State**: Spatial point-in-polygon filtering against the official Mumbai Metropolitan Region boundary (`data/mmr_boundary.geojson`) is performed in Python using the `shapely.geometry` library during data ingestion.
- **Proposed Enhancement**: Load `mmr_boundary.geojson` into a PostgreSQL table `spatial_boundaries (boundary_id, boundary_name, geom geometry(MultiPolygon, 4326))` so that spatial containment can be executed directly in SQL via `ST_Contains(b.geom, s.geom)`.
- **Status**: Proposed future work (dependent on PostGIS extension activation).

---

### Gap 5: Disaster Recovery Testing Status
- **Current State**: Logical backup was created using `pg_dump -Fc` into `data/ev_db_backup.dump` (348 KB). The archive Table of Contents was inspected and verified using `pg_restore -l`.
- **Integrity Rule**: A live restore was not executed against the production database `ev_db` to strictly avoid data corruption.
- **Remediation for Viva Demo**: Demonstrate restore into an isolated test database:
  ```powershell
  psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE ev_db_recovery_test;"
  pg_restore -h localhost -p 5432 -U postgres -d ev_db_recovery_test -v "data/ev_db_backup.dump"
  ```

---

## 3. Checklist for Academic Defense

1. **Do not claim 30,263 stations are in `charging_stations`**: State that 952 verified stations are in `charging_stations`, and 30,263 nationwide stations are in `stg_national_master_ev_stations`.
2. **Do not claim PostGIS `ST_DWithin` is currently executing if PostGIS is not enabled**: State that spatial queries are currently powered by PostgreSQL native GiST point indexing (`idx_stations_point_gist`) with bounding-box filters and geodesic Haversine distance, with PostGIS ready for activation once administrator permissions are granted.
3. **Be proud of the data cleaning pipeline**: The discovery and quarantine of 2,133 non-MMR stations (including the Tardeo vs Kurla root-cause analysis) is a stellar ADBMS case study demonstrating real-world data quality engineering.
