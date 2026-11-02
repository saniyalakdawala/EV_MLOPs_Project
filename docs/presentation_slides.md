# 12-Slide Academic Presentation Deck: VoltGrid Mumbai

**Project Title:** VoltGrid Mumbai: Smart EV Charging Infrastructure Database for the Mumbai Metropolitan Region (MMR)  
**Primary Track:** Track C — GIS-Based Database  
**Course:** Advanced Database Management Systems (ADBMS)  
**Author:** B.Tech Data Science Student  
**Evaluation Standard:** Reconciled Empirical Data (31,335 Raw Records | 952 Production MMR Stations)  

---

### Slide 1: Title & Project Overview
* **Title:** VoltGrid Mumbai: Smart EV Charging Infrastructure Database
* **Subtitle:** Spatial Modeling, Concurrency Control, and DBA Operations for Urban EV Networks
* **Primary Track:** **Track C — GIS-Based Database**
* **Technical Stack:** PostgreSQL 17 (x64), PostGIS, Python FastAPI, Streamlit dashboard, psycopg2
* **Key Theme:** Demonstrating what an Enterprise Database Administrator (DBA) does behind the scenes to collect, validate, store, query, secure, optimize, and recover urban spatial infrastructure data.

---

### Slide 2: Real-World Problem Statement & Context
* **Urban EV Challenge in Mumbai:**
  * Rapid EV adoption across two-wheelers, passenger cars, and commercial fleets is hindered by range anxiety and charger discovery.
  * Public EV directories suffer from severe **geographic contamination**: stations in Tamil Nadu, Uttar Pradesh, and Himachal Pradesh were found falsely labeled as "Mumbai" due to city normalization bugs.
  * Searching for **Tardeo (South Mumbai)** was returning **Kurla (12.67 km away)** because historical crowdsourced datasets had zero entries south of latitude 19.07° N.
* **The ADBMS Mandate:**
  * Basic CRUD applications cannot enforce spatial boundary containment or handle high-concurrency port bookings.
  * Requires an enterprise spatial database engine supporting sub-millisecond proximity queries and race-condition-free reservations.

---

### Slide 3: Multi-Source Ingestion & Spatial Boundary Validation
* **Evaluated Data Feeds (31,335 Raw Records Preserved in `data/raw/`):**
  * **Bureau of Energy Efficiency (BEE), Ministry of Power:** 29,184 official census records.
  * **OpenChargeMap (OCM) Global Registry:** 1,982 records.
  * **NITI Aayog / E-Amrit National Portal:** 159 records.
  * **OpenStreetMap (OSM) via Overpass API:** 10 records.
* **Spatial Boundary Filtering Pipeline (`scripts/ingest_pipeline.py`):**
  * Evaluated coordinates against the **official administrative MMR polygon** (`data/mmr_boundary.geojson`, OSM Relation ID 13312356).
  * **2,133 non-MMR stations quarantined** (including out-of-state records in Tamil Nadu, UP, and HP).
  * **952 authentic stations inside MMR** approved and loaded into production `charging_stations`.
  * **30,263 validated all-India records** maintained in staging `stg_national_master_ev_stations`.

---

### Slide 4: Relational Database Architecture (3NF) & Schema Design
* **Entities & Relationships:**
  * `charging_stations` (1) $\longleftrightarrow$ (N) `charging_ports` $\longleftrightarrow$ (N) `charging_sessions`
  * `charging_ports` (1) $\longleftrightarrow$ (N) `station_status_history` (Audit Log)
* **Verified Database Counts (`ev_db`):**
  * `charging_stations`: **952 rows** (936 BEE, 8 OCM, 8 OSM — 100% inside MMR)
  * `charging_ports`: **2,026 rows** (CCS-2, Type 2 AC, Bharat DC-001, etc.)
  * `charging_sessions`: **13 rows** (UUID primary keys, energy metering)
  * `station_status_history`: **2,027 rows** (temporal audit trail)
* **Referential Integrity Decisions:**
  * `charging_ports` $\to$ `charging_stations`: `ON DELETE CASCADE` (Decommissioning removes hardware).
  * `charging_sessions` $\to$ `charging_ports`: `ON DELETE RESTRICT` (Protects billing and SLA audit trail).

---

### Slide 5: The Critical Safeguard — Double-Booking Prevention
* **The Business Challenge:**
  * A physical charging connector will service thousands of sessions over its lifetime, but must **never** host more than one active charging session simultaneously.
* **The Solution: Partial Unique Index:**
  ```sql
  CREATE UNIQUE INDEX uq_active_session_per_port 
  ON charging_sessions (port_id) 
  WHERE session_status = 'ACTIVE';
  ```
* **Engine-Level Guarantee:**
  * A standard unique constraint would block historical completed sessions after a single use.
  * The partial unique index enforces uniqueness **only** when `session_status = 'ACTIVE'`, making double-booking physically impossible at the PostgreSQL engine level.

---

### Slide 6: Primary Track C: GIS & PostGIS Spatial Operations
* **Active PostGIS Extension:** PostGIS 3.6.2 active (`geom geography(Point, 4326)` on all 952 stations).
* **Data Structure:** **GiST R-Tree (Bounding Box Tree)** paired with a **Min-Heap (Priority Queue)** for Best-First k-NN nearest-neighbor search.
* **Spatial Radius Query (5 km from BKC, Mumbai):**
  ```sql
  SELECT station_name, operator_name, round((ST_Distance(geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography)/1000.0)::numeric, 2) AS dist_km
  FROM charging_stations
  WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography, 5000)
  ORDER BY geom <-> ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography LIMIT 5;
  ```
* **Performance:** PostGIS spatial index pruning in **0.150 ms**; total execution time **0.920 ms** (sub-millisecond across the entire city).

---

### Slide 7: ACID Transactions & Automatic Rollback Proof
* **Atomic Session Workflow:**
  * `BEGIN` $\to$ `SELECT ... FOR UPDATE` (Row Lock) $\to$ Verify `AVAILABLE` $\to$ `UPDATE port status = 'IN_USE'` $\to$ `INSERT charging_sessions` $\to$ `INSERT station_status_history` $\to$ `COMMIT`.
* **Fault Injection Demonstration (`database/05_transactions.sql`):**
  * Simulated fatal hardware exception: `'METER_HARDWARE_FAULT: Energy meter failed to communicate with dispensing unit!'`.
  * PostgreSQL engine caught the exception and executed an immediate `ROLLBACK`.
* **Empirical Verification:**
  * **Before Test:** Port 2 status = `'AVAILABLE'` | Total sessions = 13
  * **After Rollback:** Port 2 status = `'AVAILABLE'` | Total sessions = 13
  * **ACID Atomicity Proof Verified:** Zero dirty data written; zero orphaned records.

---

### Slide 8: Concurrency Control & Race Condition Mitigation
* **Simultaneous Double-Booking Scenario:**
  * Driver Alice and Driver Bob attempt to book the same charging port (`port_id = 2`) at the same millisecond.
* **DBA Mechanism: Pessimistic Row-Level Locking:**
  * `SELECT port_id, status FROM charging_ports WHERE port_id = 2 FOR UPDATE;`
* **Empirical Multi-Threaded Results (`scripts/test_concurrency.py`):**
  * **Driver Alice:** Acquires lock (0.01s), status = `'AVAILABLE'`, holds lock for 2s (vehicle handshake), updates to `'IN_USE'`, commits session `0ceb75f6...`.
  * **Driver Bob:** Attempts lock, **enters wait state for 1.71s**. When Alice commits, Bob's lock unblocks, reads updated status `'IN_USE'`, detects conflict, and is **REJECTED with HTTP 409 Conflict**.
  * **Verification:** Total active sessions on port 2 = **exactly 1**.

---

### Slide 9: Indexing Strategies & Query Optimization (`EXPLAIN ANALYZE`)
* **Index Strategy:**
  * B-Tree Composite: `idx_ports_connector_power (connector_type, power_kw)`
  * Spatial GiST: `idx_stations_spatial_gist (geom)`
  * Temporal B-Tree: `idx_sessions_start_time (start_time DESC)`
* **Empirical Benchmark (`EXPLAIN (ANALYZE, BUFFERS)` on CCS-2 $\ge 50\text{ kW}$):**
  * **With Composite Index (Bitmap Index Scan):**
    * Execution Time: **0.225 ms** | Cost: **4.63 .. 25.58** | Heap blocks read: 17
  * **Without Index (Forced Sequential Table Scan):**
    * Execution Time: **0.502 ms** | Cost: **0.00 .. 50.39** | Rows filtered: 1,816
  * **DBA Performance Gain:** **55.2% latency reduction** and **49.2% cost reduction**.

---

### Slide 10: Security, RBAC & Disaster Recovery
* **Role-Based Access Control (RBAC) & Least Privilege:**
  * `ev_admin`: Full schema administration, DDL, and maintenance.
  * `ev_app_user`: FastAPI service account; DML on operational tables; **no DDL or DROP rights**.
  * `ev_analyst`: Read-only reporting; strictly `SELECT` permissions.
* **Empirical Security Verification (`scripts/test_security.py`):**
  * `ev_analyst` executes `SELECT count(*) FROM charging_stations;` $\to$ **SUCCEEDED (952 rows)**.
  * `ev_analyst` attempts `UPDATE charging_ports SET status = 'AVAILABLE';` $\to$ **BLOCKED BY POSTGRESQL**:
    `ERROR: permission denied for table charging_ports`.
* **Disaster Recovery Preparedness:**
  * Compressed custom archive `data/ev_db_backup.dump` (**348 KB**) created using `pg_dump -Fc`.
  * Table of Contents verified via `pg_restore -l`. Zero data loss architecture.

---

### Slide 11: Real-Time Monitoring & Web Application Architecture
* **DBA Health Telemetry:**
  * **Buffer Cache Hit Ratio:** **99.85%** (760,938 RAM hits vs 1,134 disk reads) via `pg_stat_database`.
  * **Active Connections:** Live connection and query tracking via `pg_stat_activity`.
  * **Storage Footprint:** Monitored via `pg_class` (Stations: 896 kB, Ports: 888 kB, Staging: 1,304 kB).
* **Full-Stack Application Flow:**
  * `Streamlit Dashboard (port 8501)` $\longleftrightarrow$ `FastAPI Backend (port 8000)` $\longleftrightarrow$ `PostgreSQL 17 / PostGIS (port 5432)`.
  * Features: Interactive radius slider, dynamic station cards, simulated port booking modal, and live DBA diagnostic panel.

---

### Slide 12: Conclusion, Technical Learnings & Viva Highlights
* **Summary of Outcomes:**
  * Reconciled 31,335 raw records into 952 verified MMR stations and 30,263 national staging records with zero fabrication.
  * Solved geographic data contamination through automated point-in-polygon boundary containment.
  * Activated PostGIS 3.6.2 and built spatial GiST indexing, delivering sub-millisecond proximity queries.
  * Proved enterprise DBA guarantees: ACID rollback proof, row-level concurrency locking, RBAC Least Privilege, and 99.85% cache hit rates.
* **Key Academic Takeaway:**
  * Spatial databases require both rigorous geospatial validation at data ingestion and enterprise transaction guarantees at the database engine level.
