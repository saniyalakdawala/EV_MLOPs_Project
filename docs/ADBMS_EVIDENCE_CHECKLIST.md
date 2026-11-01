# VoltGrid Mumbai: ADBMS Evidence Checklist & Screenshot Capture Guide

This checklist details every required piece of empirical evidence, SQL output, terminal log, and screenshot needed for the project report and presentation. It provides exact step-by-step instructions to capture each artifact using **pgAdmin 4**, **VS Code**, or the **VoltGrid Web Application**.

---

## 1. Master Evidence Status Table

| Evidence ID | Description | Source Tool | Status in Workspace | How to Capture / Reproduce |
| :--- | :--- | :--- | :---: | :--- |
| **`[FIG-01]`** | PostgreSQL Database Schema & Tables in pgAdmin Object Tree | pgAdmin 4 | **Ready to Capture** | Expand `ev_db` $\to$ `Schemas` $\to$ `public` $\to$ `Tables` in pgAdmin sidebar. Take screenshot. |
| **`[FIG-02]`** | Table Record Counts Execution in pgAdmin Query Tool | pgAdmin 4 | **Executed & Verified** | Run Query 2.1 in `docs/ADBMS_SQL_EVIDENCE.sql` in pgAdmin Query Tool. Take screenshot of result grid. |
| **`[FIG-03]`** | Relational Entity-Relationship (ER) Diagram (3NF) | pgAdmin ERD / Mermaid | **Ready to Capture** | Right click `ev_db` in pgAdmin $\to$ *Generate ERD*, or capture rendered Mermaid diagram from `docs/er_diagram.md`. |
| **`[FIG-04]`** | Spatial Point-in-Polygon Boundary Filter Terminal Log | VS Code Terminal | **Executed & Verified** | Run `python scripts/test_pipeline_boundary_filter.py`. Take screenshot showing 11/11 tests passed and 2,133 non-MMR records quarantined. |
| **`[FIG-05]`** | Spatial Radius Search (5 km of BKC) Query & Result | pgAdmin 4 | **Executed & Verified** | Run Query 3.1 in `docs/ADBMS_SQL_EVIDENCE.sql`. Capture query editor and the 5 returned stations. |
| **`[FIG-06]`** | Nearest Station to Gateway of India (Colaba) Query & Result | pgAdmin 4 | **Executed & Verified** | Run Query 3.2 in `docs/ADBMS_SQL_EVIDENCE.sql`. Capture query editor showing Taj Mahal Palace at 0.15 km. |
| **`[FIG-07]`** | Interactive Map with MMR Stations & Radius Coverage | Web Browser | **Ready to Capture** | Open `http://localhost:5173`. Search "Bandra West", select 10 km radius. Capture map with cluster pins and radius circle. |
| **`[FIG-08]`** | ACID Transaction & Rollback Proof (Zero Dirty Data) | pgAdmin / Terminal | **Executed & Verified** | Run `python scripts/test_transactions.py` or execute Scenario 3 in `database/05_transactions.sql`. Capture notices showing `ROLLBACK`. |
| **`[FIG-09]`** | Concurrency Control (Row Lock & Conflict Resolution) | VS Code Terminal | **Executed & Verified** | Run `python scripts/test_concurrency.py`. Capture output showing Alice acquiring lock and Bob receiving `409 Conflict / REJECTED`. |
| **`[FIG-10]`** | Query Optimizer Execution Plan (`EXPLAIN ANALYZE`) | pgAdmin 4 | **Executed & Verified** | Run Query 6.2 and 6.3 in `docs/ADBMS_SQL_EVIDENCE.sql`. Capture pgAdmin Graphical Explain Plan or text output. |
| **`[FIG-11]`** | Role-Based Access Control (RBAC Permission Denied) | pgAdmin / Terminal | **Executed & Verified** | Run `python scripts/test_security.py`. Capture `permission denied for table charging_ports` for `ev_analyst`. |
| **`[FIG-12]`** | Buffer Cache Hit Ratio & Storage Sizing Query | pgAdmin 4 | **Executed & Verified** | Run Query 8.1 & 8.2 in `docs/ADBMS_SQL_EVIDENCE.sql`. Capture result showing 99.85% cache hit and table sizes. |
| **`[FIG-13]`** | Logical Backup Table of Contents (`pg_restore -l`) | VS Code Terminal | **Executed & Verified** | Run `& "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -l data/ev_db_backup.dump`. Capture output showing archived tables. |
| **`[FIG-14]`** | Live DBA Operations Dashboard Panel | Web Browser | **Ready to Capture** | In the frontend (`http://localhost:5173`), toggle the *DBA Operations Panel*. Capture the cache hit chart and active sessions. |

---

## 2. Step-by-Step Screenshot Capture Walkthrough

### Screenshot 1: Database Object Tree `[FIG-01]`
1. Launch **pgAdmin 4** on your PC.
2. Connect to the local PostgreSQL server (port 5432).
3. Expand: `Servers` $\to$ `PostgreSQL 17` $\to$ `Databases` $\to$ `ev_db` $\to$ `Schemas` $\to$ `public` $\to$ `Tables`.
4. Ensure the 7 tables are visible:
   - `charging_ports`
   - `charging_sessions`
   - `charging_stations`
   - `station_status_history`
   - `stg_charging_stations`
   - `stg_master_ev_stations`
   - `stg_national_master_ev_stations`
5. Press `Windows + Shift + S` to capture the left sidebar navigation tree.
6. Save as: `docs/screenshots/fig01_pgadmin_object_tree.png`.

---

### Screenshot 2: Table Record Counts Query `[FIG-02]`
1. In pgAdmin, open the **Query Tool** on database `ev_db`.
2. Paste and run:
   ```sql
   SELECT 'charging_stations' AS table_name, count(*) AS row_count FROM charging_stations
   UNION ALL
   SELECT 'charging_ports', count(*) FROM charging_ports
   UNION ALL
   SELECT 'charging_sessions', count(*) FROM charging_sessions
   UNION ALL
   SELECT 'station_status_history', count(*) FROM station_status_history
   UNION ALL
   SELECT 'stg_charging_stations', count(*) FROM stg_charging_stations
   UNION ALL
   SELECT 'stg_national_master_ev_stations', count(*) FROM stg_national_master_ev_stations
   ORDER BY row_count DESC;
   ```
3. Take a screenshot showing the SQL editor and the Data Output grid showing:
   - `stg_national_master_ev_stations`: 30,263
   - `station_status_history`: 2,027
   - `charging_ports`: 2,026
   - `stg_charging_stations`: 2,141
   - `charging_stations`: 952
   - `charging_sessions`: 13
4. Save as: `docs/screenshots/fig02_table_record_counts.png`.

---

### Screenshot 3: Relational ER Diagram `[FIG-03]`
1. In pgAdmin, right-click `ev_db` and select **Generate ERD...**.
2. Arrange the 4 core tables: `charging_stations`, `charging_ports`, `charging_sessions`, and `station_status_history`.
3. Capture the foreign key connection lines and column lists.
4. Save as: `docs/screenshots/fig03_erd_schema.png`.

---

### Screenshot 4: Boundary Ingestion Filter Execution `[FIG-04]`
1. In VS Code, open a new PowerShell terminal.
2. Run:
   ```powershell
   python scripts/test_pipeline_boundary_filter.py
   ```
3. Capture the terminal output demonstrating:
   - Point-in-polygon containment against official MMR boundary (`data/mmr_boundary.geojson`).
   - Rejection of out-of-state records (Tamil Nadu, UP, HP).
   - Acceptance of 8 authentic MMR stations from OCM.
4. Save as: `docs/screenshots/fig04_boundary_filter_terminal.png`.

---

### Screenshot 5: GIS Radius Search Query `[FIG-05]`
1. In pgAdmin Query Tool, paste Query 3.1 from `docs/ADBMS_SQL_EVIDENCE.sql` (Stations within 5 km of BKC).
2. Execute the query.
3. Capture the query window and the top rows in the grid:
   - `M/S Sofitel Hotel` (Reliance BP) at 0.22 km (5 ports)
   - `Trent House` (Tata Power) at 0.25 km (2 ports)
   - `Tata Communication` (Tata Power) at 0.48 km (2 ports)
   - `Kotak 27 Bkc` (Tata Power) at 0.69 km (2 ports)
   - `Audi Service` (Tata Power) at 0.70 km (2 ports)
4. Save as: `docs/screenshots/fig05_radius_search_bkc.png`.

---

### Screenshot 6: Nearest Station to Gateway of India `[FIG-06]`
1. In pgAdmin Query Tool, paste Query 3.2 from `docs/ADBMS_SQL_EVIDENCE.sql` (Nearest to Gateway of India).
2. Execute the query.
3. Capture the result showing `The Taj Mahal Palace` (Tata Power, Colaba) at 0.15 km away.
4. Save as: `docs/screenshots/fig06_nearest_gateway_of_india.png`.

---

### Screenshot 7: Web Application Interactive Map `[FIG-07]`
1. Launch the backend: double-click `run_backend.bat` (starts FastAPI on port 8000).
2. Launch the frontend: double-click `run_frontend.bat` (starts Vite on port 5173).
3. Open `http://localhost:5173` in Google Chrome or Edge.
4. In the search bar, search for "Bandra West", select a 10 km radius.
5. Capture the browser window displaying the interactive Leaflet map, station markers, and the station cards list.
6. Save as: `docs/screenshots/fig07_webapp_map_interface.png`.

---

### Screenshot 8: ACID Transaction & Automatic Rollback `[FIG-08]`
1. In VS Code terminal, run:
   ```powershell
   python scripts/test_transactions.py
   ```
2. Capture the output for Scenario 3:
   - Initial port status = `'AVAILABLE'`
   - Simulated fatal exception: `"METER_HARDWARE_FAULT"`
   - `ROLLBACK` caught by PostgreSQL engine
   - Post-test port status verified = `'AVAILABLE'`
   - Notice: `"ACID ATOMICITY PROOF VERIFIED: No dirty records or partial updates remain!"`
3. Save as: `docs/screenshots/fig08_acid_rollback_proof.png`.

---

### Screenshot 9: Concurrency Control Demonstration `[FIG-09]`
1. In VS Code terminal, run:
   ```powershell
   python scripts/test_concurrency.py
   ```
2. Capture the output demonstrating:
   - Driver Alice initiates transaction and acquires row lock with `SELECT ... FOR UPDATE`.
   - Driver Bob attempts simultaneous booking on the same port and enters a wait state.
   - Alice completes and commits, changing status to `'IN_USE'`.
   - Bob's lock is granted, detects `'IN_USE'` conflict, and rolls back cleanly with booking rejected.
   - Total active sessions verified = exactly 1.
3. Save as: `docs/screenshots/fig09_concurrency_locking_terminal.png`.

---

### Screenshot 10: Index Performance (`EXPLAIN ANALYZE`) `[FIG-10]`
1. In VS Code terminal, run:
   ```powershell
   python scripts/test_indexes.py
   ```
2. Capture the output showing:
   - Bitmap Index Scan on `idx_ports_connector_power`: execution time **0.225 ms** (cost: 4.63..25.58).
   - Sequential Scan (index disabled): execution time **0.502 ms** (cost: 0.00..50.39, 1,816 rows filtered).
   - Performance gain: > 55% reduction in latency.
3. Save as: `docs/screenshots/fig10_explain_analyze_benchmark.png`.

---

### Screenshot 11: Security & Least Privilege Enforcement `[FIG-11]`
1. In VS Code terminal, run:
   ```powershell
   python scripts/test_security.py
   ```
2. Capture the terminal output demonstrating:
   - Role `ev_analyst` connects and executes `SELECT count(*) FROM charging_stations` successfully (952 rows).
   - Role `ev_analyst` attempts `UPDATE charging_ports` and is blocked:
     `permission denied for table charging_ports`.
3. Save as: `docs/screenshots/fig11_rbac_permission_denied.png`.

---

### Screenshot 12: Database Monitoring & Buffer Cache Hit Ratio `[FIG-12]`
1. In VS Code terminal, run:
   ```powershell
   python scripts/test_monitoring.py
   ```
2. Capture the output demonstrating:
   - Buffer cache hit ratio: **99.85%** (Blocks hit: 760,938, read: 1,134).
   - Table storage footprints: `stg_charging_stations` (1,304 kB), `charging_stations` (896 kB), `charging_ports` (888 kB).
   - Active client connections in `pg_stat_activity`.
3. Save as: `docs/screenshots/fig12_monitoring_buffer_cache.png`.

---

### Screenshot 13: Logical Backup Archive Verification `[FIG-13]`
1. In VS Code terminal, run:
   ```powershell
   & "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -l "data/ev_db_backup.dump" | Select-String "TABLE DATA"
   ```
2. Capture the output showing table data entries for `charging_stations`, `charging_ports`, `charging_sessions`, and `station_status_history`.
3. Save as: `docs/screenshots/fig13_pgrestore_toc_verification.png`.

---

### Screenshot 14: WebApp DBA Operations Dashboard `[FIG-14]`
1. Open the VoltGrid web application in your browser (`http://localhost:5173`).
2. Click the **DBA Operations** button on the top navigation bar.
3. Capture the dashboard panel showing:
   - Database health metrics (cache hit percentage, database size).
   - Storage utilization table.
   - Real-time client session activity from `pg_stat_activity`.
   - Interactive Index Benchmark viewer.
4. Save as: `docs/screenshots/fig14_webapp_dba_panel.png`.
