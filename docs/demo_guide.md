# Live Project Demonstration Script

**Project Title:** Smart EV Charging Infrastructure Database: GIS-Based Management, Availability Tracking and DBA Operations  
**Track:** Advanced Database Management Systems (ADBMS) — Academic Evaluation  
**Estimated Demo Duration:** 7–10 Minutes

---

## 1. Step-by-Step Examiner Walkthrough Plan

### Step 1: Architecture & Dataset Overview (1 Minute)
* **Goal**: Show genuine real-world problem and data lineage.
* **Talking Point**:
  > "Good morning/afternoon, Sir/Madam. Our project addresses the real-world operational challenges of managing EV charging infrastructure across the Mumbai Metropolitan Region and Maharashtra. We did not fabricate our station records; we ingested 2,141 raw records from OpenChargeMap and NITI Aayog's E-Amrit portal through a multi-stage Python data cleaning pipeline, producing 1,951 normalized 3NF charging stations and 3,186 hardware ports."
* **Action**:
  - Show [`docs/dataset_documentation.md`](file:///c:/Projects/ADBMS/docs/dataset_documentation.md) and [`database/01_schema.sql`](file:///c:/Projects/ADBMS/database/01_schema.sql).
  - Point out the 3NF schema and the partial unique index:
    `CREATE UNIQUE INDEX uq_active_session_per_port ON charging_sessions (port_id) WHERE session_status = 'ACTIVE';`

---

### Step 2: GIS Spatial Radius Search & Nearest Neighbor (2 Minutes)
* **Goal**: Prove PostGIS spatial integration and distance calculations.
* **Talking Point**:
  > "In the GIS track, we model station coordinates using WGS-84 decimal latitude and longitude as well as PostGIS geography(Point, 4326). Unlike Euclidean planes, spherical geography calculates exact geodesic distances in meters."
* **Action**:
  - Open the React frontend (`http://localhost:5173`) on the **GIS Map & Stations** tab.
  - Drag the search radius slider to 10 km from BKC Mumbai (`19.0657, 72.8687`).
  - Click on a green station pin on the map (e.g. *MobiLane Equinox Business Park*).
  - Open pgAdmin and run [`database/04_spatial_queries.sql`](file:///c:/Projects/ADBMS/database/04_spatial_queries.sql) to show the underlying SQL executing `ST_DWithin` and `<->` KNN operator.

---

### Step 3: Transactional Session Booking & Concurrency Control (2.5 Minutes)
* **Goal**: Demonstrate ACID transactions, row-level locking (`SELECT ... FOR UPDATE`), and race condition prevention.
* **Talking Point**:
  > "A major DBA responsibility in high-traffic networks is preventing race conditions where two drivers simultaneously tap 'Book' on the same physical dispenser. We use pessimistic row-level locking with `SELECT ... FOR UPDATE`."
* **Action**:
  - In the UI Station Detail modal, click **Start Charging** on an available port.
  - Point out that the port status transitions immediately to **`IN_USE`** and an active charging session is created.
  - Now run the concurrency test script in terminal:
    ```powershell
    python scripts/test_concurrency.py
    ```
  - Show the terminal output: Driver Alice acquires the lock for 2 seconds; Driver Bob's connection blocks for 1.73 seconds, detects `IN_USE`, and is rejected with zero double-bookings!
  - Also run the atomic rollback demonstration:
    ```powershell
    python scripts/test_transactions.py
    ```
  - Show that when a simulated hardware energy-meter failure occurs, PostgreSQL executes an automatic `ROLLBACK`, leaving zero residual dirty records.

---

### Step 4: Indexing & `EXPLAIN ANALYZE` Performance (1.5 Minutes)
* **Goal**: Demonstrate query plan analysis before and after indexing with real measured execution times.
* **Talking Point**:
  > "We implemented B-Tree indexes on port status, composite hardware attributes `(connector_type, power_kw)`, and session start times. We used `EXPLAIN (ANALYZE, BUFFERS)` to measure actual execution plans."
* **Action**:
  - Switch to the **DBA Operations & Health** tab in the dashboard.
  - Show the benchmark card:
    - **With B-Tree Index**: `0.672 ms` (Bitmap Index Scan on `idx_ports_connector_power`)
    - **Without Index**: `1.307 ms` (Sequential Scan on `charging_ports`)
  - Run the terminal script:
    ```powershell
    python scripts/test_indexes.py
    ```

---

### Step 5: DBA Security (RBAC), Health Monitoring & Backup (1.5 Minutes)
* **Goal**: Demonstrate Principle of Least Privilege, live monitoring with `pg_stat_activity`, and backup/restore.
* **Talking Point**:
  > "For security, our FastAPI application connects using the least-privilege `ev_app_user` role, which has DML permissions but cannot drop tables. We also created an `ev_analyst` role who can read analytical data but gets 'Permission Denied' on write attempts."
* **Action**:
  - Run the security test script:
    ```powershell
    python scripts/test_security.py
    ```
  - Show PostgreSQL output: `permission denied for table charging_ports`.
  - In the dashboard, show the **Buffer Cache Hit Ratio Meter** (`99.98%`) and the **Table Storage Size Bar Chart**.
  - Show the physical backup file created: `data/ev_db_backup.dump` (348 KB custom-format dump created via `pg_dump -Fc`).

---

## 2. Quick Command Cheat-Sheet for Demo Day

```powershell
# 1. Start Backend Server (Terminal 1)
.\run_backend.bat

# 2. Start Frontend UI (Terminal 2)
.\run_frontend.bat

# 3. Quick Test Scripts (Terminal 3)
python scripts/test_constraints.py    # Verify all 5 check & unique constraints
python scripts/test_concurrency.py    # Live multi-threaded race condition demonstration
python scripts/test_transactions.py   # Atomic start/end and rollback demonstration
python scripts/test_indexes.py        # EXPLAIN ANALYZE comparison
python scripts/test_security.py       # RBAC least privilege demonstration
python scripts/test_monitoring.py     # Live engine diagnostics & cache ratio
```
