# VoltGrid Mumbai: 12-Slide ADBMS Presentation Outline

**Project Title:** VoltGrid Mumbai: Smart EV Charging Infrastructure Database for Mumbai  
**Primary Track:** Track C — GIS-Based Database  
**Course:** Advanced Database Management Systems (ADBMS)  
**Target Audience:** Viva Examiners, Faculty Review Committee, B.Tech Data Science Evaluation  

---

### Slide 1: Title & Project Overview
- **Header:** VoltGrid Mumbai: Smart EV Charging Infrastructure Database for the Mumbai Metropolitan Region (MMR)
- **Sub-header:** Track C — GIS & Spatial Database Engineering
- **Student Details:** Candidate Name | Roll No / Reg No | B.Tech Data Science | Department of Computer Science & Engineering
- **Core Theme:** Demonstrating what an Enterprise Database Administrator (DBA) does in the background to collect, validate, store, query, secure, optimize, and recover urban spatial infrastructure data.
- **Visuals:** Project Logo / Dual-theme map snapshot of Mumbai Metropolitan Region.

---

### Slide 2: Problem Statement & Real-World Context
- **The EV Charging Challenge in Mumbai:**
  - Range anxiety and charging station discovery are the top barriers to EV adoption in Mumbai.
  - Public datasets suffer from severe geographic contamination (e.g., stations in Tamil Nadu, UP, and HP incorrectly tagged as "Mumbai").
  - Lack of hardware standardization (CCS-2, Type 2 AC, Bharat DC-001) and concurrent double-booking conflicts.
- **The ADBMS Mandate:**
  - Standard CRUD applications fail to enforce spatial bounds and transactional hardware safety.
  - Need for an authoritative, 3NF spatial database engine capable of sub-millisecond proximity queries and race-condition-free bookings.

---

### Slide 3: Track C Justification — Why GIS-Based Database?
- **Why Ordinary Relational Queries Fail for Spatial Data:**
  - Relational B-Trees index data in 1D; geographic coordinates require 2D spatial indexing (GiST R-Tree).
  - Flat Euclidean distance formulas ($\sqrt{\Delta x^2 + \Delta y^2}$) introduce severe distortion over regional scale; spherical geodesic calculations (WGS-84 / Haversine) are required.
- **Role of the DBA in Spatial Data Management:**
  1. Ingesting raw external geospatial feeds (GeoJSON, JSON) into isolated staging layers.
  2. Enforcing rigorous point-in-polygon administrative boundary containment.
  3. Building and tuning spatial GiST indexes for sub-millisecond radius search.
  4. Safeguarding database integrity against concurrent multi-user lock contention.

---

### Slide 4: Data Lineage, Collection & Ingestion Pipeline
- **Multi-Source Data Provenance (31,335 Raw Records Processed):**
  - Bureau of Energy Efficiency (BEE), Ministry of Power: 29,184 official records.
  - OpenChargeMap (OCM) Global Registry: 1,982 records.
  - NITI Aayog / E-Amrit National Portal: 159 records.
  - OpenStreetMap (OSM) via Overpass API: 10 records.
- **Pipeline Architecture:**
  - `Raw Source Feeds` $\to$ `Staging Tables (stg_charging_stations, stg_national_master_ev_stations)` $\to$ `Python Validation Engine` $\to$ `Production 3NF Schema`.
- **Spatial Boundary Validation:**
  - Point-in-polygon containment against official MMR boundary (`data/mmr_boundary.geojson`, OSM Relation 13312356).
  - Quarantined 2,133 non-MMR stations; accepted 952 authentic stations inside MMR.

---

### Slide 5: Database Design & Relational Schema (3NF)
- **Entity-Relationship Architecture:**
  - `charging_stations` (1 : N) $\to$ `charging_ports` (1 : N) $\to$ `charging_sessions`
  - `charging_ports` (1 : N) $\to$ `station_status_history` (Audit Trail)
- **Key Integrity Safeguards:**
  - **`ON DELETE CASCADE`** on `charging_ports`: Decommissioned station removes attached hardware.
  - **`ON DELETE RESTRICT`** on `charging_sessions`: Deleting a port with billing history is strictly blocked by the DBA.
  - **Partial Unique Index**:
    ```sql
    CREATE UNIQUE INDEX uq_active_session_per_port ON charging_sessions (port_id) WHERE session_status = 'ACTIVE';
    ```
    Engine-level guarantee preventing two simultaneous active sessions on the same connector.

---

### Slide 6: GIS Core Demonstration — Spatial Queries & Indexing
- **Spatial Index:** GiST index `idx_stations_point_gist` on `point(longitude, latitude)`.
- **Demonstrated GIS Queries:**
  1. **Radius Search (5 km around Bandra Kurla Complex - BKC):**
     - Bounding box filter (`<@ box`) with SQL Haversine distance calculation.
     - Result: 5 stations returned (nearest: M/S Sofitel Hotel at 0.22 km, 5 ports).
  2. **Nearest Neighbor Search (Gateway of India, Colaba):**
     - Spatial distance sorting (`<->`).
     - Result: The Taj Mahal Palace (Tata Power) identified at 0.15 km.
  3. **Administrative Grouping:**
     - Station distribution across Mumbai, Thane, Navi Mumbai, and Raigad.
- **PostGIS Dual-Mode Support:**
  - Codebase automatically switches between PostGIS `geography` (`ST_DWithin`) and native GiST point bounding-box queries.

---

### Slide 7: ACID Transactions & Automatic Rollback Proof
- **Atomic Port Booking Flow:**
  - `BEGIN` $\to$ `SELECT ... FOR UPDATE` (Row Lock) $\to$ Validate status = `'AVAILABLE'` $\to$ `UPDATE port status = 'IN_USE'` $\to$ `INSERT charging_sessions` $\to$ `INSERT station_status_history` $\to$ `COMMIT`.
- **Fault-Injection & Rollback Demonstration:**
  - Simulating a fatal runtime dispenser meter fault halfway through execution.
  - PostgreSQL engine catches exception and triggers `ROLLBACK`.
  - **Empirical Proof:** Port status verified unchanged (`'AVAILABLE'`), and session count verified identical before and after. Zero dirty data or orphaned records.

---

### Slide 8: Concurrency Control & Row-Level Locking
- **The Lost-Update / Double-Booking Threat:**
  - Two drivers attempting to book the same physical charging port at the exact same second.
- **Implementation via Pessimistic Row Locking:**
  - `SELECT port_id, status FROM charging_ports WHERE port_id = 2 FOR UPDATE;`
- **Simulated Test Results (`scripts/test_concurrency.py`):**
  - **Driver Alice:** Acquires lock, status = `'AVAILABLE'`, updates to `'IN_USE'`, commits session `0ceb75f6...`.
  - **Driver Bob:** Enters wait state (1.71s), lock unblocks after Alice commits, reads updated status `'IN_USE'`, conflict detected, transaction rolled back, booking rejected.
  - **Verification:** Exactly 1 active session exists on port 2. Double-booking physically impossible.

---

### Slide 9: Indexing Strategy & EXPLAIN ANALYZE Performance
- **Index Inventory:**
  - B-Tree Composite: `idx_ports_connector_power (connector_type, power_kw)`
  - B-Tree Status: `idx_ports_status (status)`
  - B-Tree Temporal: `idx_sessions_start_time (start_time DESC)`
  - Spatial GiST: `idx_stations_point_gist (point(lon, lat))`
- **Empirical EXPLAIN ANALYZE Benchmark:**
  - **Test Query:** Fast charger search (`connector_type = 'CCS-2' AND power_kw >= 50.0`).
  - **With Index (Bitmap Index Scan):** Execution Time = **0.225 ms** | Cost = **4.63..25.58** | Heap blocks = 17.
  - **Without Index (Sequential Scan):** Execution Time = **0.502 ms** | Cost = **0.00..50.39** | 1,816 rows filtered.
  - **DBA Finding:** > 55% reduction in query latency and 50% lower optimizer cost.

---

### Slide 10: Security, Role-Based Access Control (RBAC) & Recovery
- **Enforcing the Principle of Least Privilege:**
  - **`ev_admin`**: Full schema maintenance, DDL, table modifications, backups.
  - **`ev_app_user`**: Used by FastAPI backend; CRUD on operational tables; **no DDL or DROP permissions**.
  - **`ev_analyst`**: Read-only BI reporting; strictly `SELECT` on production tables.
- **Empirical Security Verification:**
  - `ev_analyst` executes `SELECT count(*) FROM charging_stations` $\to$ **SUCCESS (952 rows)**.
  - `ev_analyst` attempts `UPDATE charging_ports SET status = 'AVAILABLE'` $\to$ **BLOCKED: `permission denied for table charging_ports`**.
- **Backup & Recovery (`pg_dump`):**
  - Custom compressed archive `ev_db_backup.dump` (348 KB) created using `-Fc`.
  - Table of Contents verified using `pg_restore -l`. Zero data loss architecture.

---

### Slide 11: Real-Time Monitoring & Web Application Architecture
- **DBA Health Telemetry:**
  - **Buffer Cache Hit Ratio:** **99.85%** (760,938 hits vs 1,134 disk reads) via `pg_stat_database`.
  - **Storage Footprint:** Monitored via `pg_class` (Stations: 896 kB, Ports: 888 kB, Staging: 1,304 kB).
  - **Active Sessions:** Live diagnostic connection tracking via `pg_stat_activity`.
- **System Architecture:**
  - `React + Leaflet Frontend (port 5173)` $\longleftrightarrow$ `FastAPI REST API (port 8000)` $\longleftrightarrow$ `PostgreSQL 17 Database (port 5432)`.
  - Live features: Interactive radius circle, dynamic station cards, real-time port booking modal, and DBA operations diagnostics panel.

---

### Slide 12: Conclusion, Technical Learnings & Viva Highlights
- **Summary of Project Outcomes:**
  - Reconciled 31,335 raw records into 952 verified MMR stations and 30,263 national stations with zero data fabrication.
  - Proved spatial indexing efficiency with sub-millisecond query response times.
  - Demonstrated enterprise DBA capabilities: ACID rollback proof, row-level concurrency locking, RBAC security, and custom-format disaster recovery.
- **Key Takeaway for B.Tech Data Science:**
  - Spatial databases require a dual mindset: combining rigorous geographic filtering at the data ingestion layer with enterprise transaction guarantees at the database engine layer.
- **Open for Questions & Viva Defense!**
