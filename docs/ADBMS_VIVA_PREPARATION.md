# VoltGrid Mumbai: Comprehensive ADBMS Viva Examination Preparation Guide

This guide is designed for B.Tech Data Science students defending the **VoltGrid Mumbai** project in their **Advanced Database Management Systems (ADBMS)** oral viva examination. Questions are categorized by topic, accompanied by precise, simple, and high-scoring student-level answers based on the actual implementation.

---

## Category 1: Relational Modeling & Schema Design

### Q1: Why is this project classified as an ADBMS project rather than a routine web development or DBMS project?
**Answer:**
> "A routine DBMS project typically focuses on simple CRUD operations (Create, Read, Update, Delete) on flat, unconstrained tables using basic queries. In contrast, our project addresses enterprise-grade ADBMS challenges:
> 1. **Spatial Data Engineering (Track C)**: Modeling two-dimensional geographic coordinates using spatial GiST indexing and spherical geodesic distance calculations, backed by point-in-polygon administrative boundary validation.
> 2. **Concurrency Control & Locking**: Preventing high-contention double-booking of physical charging hardware using PostgreSQL row-level locks (`SELECT ... FOR UPDATE`).
> 3. **ACID Transaction Boundaries**: Multi-table transactional consistency ensuring port status transitions, session creation, and audit logging commit atomically or roll back completely.
> 4. **DBA Operations in the Background**: Implementing Role-Based Access Control (RBAC) with Least Privilege, buffer cache monitoring via `pg_stat_database`, and automated disaster recovery via custom-format `pg_dump` archives."

---

### Q2: What normal form does your database schema satisfy? Prove it.
**Answer:**
> "Our schema satisfies **Third Normal Form (3NF)**:
> - **1NF**: All column values are atomic (e.g., coordinates are separated into `latitude` and `longitude`, statuses are single values, no multi-valued repeating groups in production tables).
> - **2NF**: It is in 1NF, and all non-key attributes are fully functionally dependent on the entire primary key (no partial dependencies on composite keys).
> - **3NF**: It is in 2NF, and there are no transitive dependencies between non-key attributes. For instance, in `charging_ports`, attributes like `connector_type`, `power_kw`, and `status` depend directly on the primary key `port_id`, and not transitively on the parent `station_id`."

---

### Q3: Why did you use `ON DELETE RESTRICT` for `charging_sessions` but `ON DELETE CASCADE` for `charging_ports`?
**Answer:**
> "This is a deliberate DBA referential integrity policy:
> - **Cascade on Ports**: If a physical charging station is permanently decommissioned and removed from `charging_stations`, its attached hardware ports physically cease to exist. `ON DELETE CASCADE` automatically cleans up dependent port rows.
> - **Restrict on Sessions**: In contrast, if an administrator attempts to delete a port that has historical charging sessions, `ON DELETE RESTRICT` **blocks the operation with an error**. Deleting a port with completed sessions would destroy financial billing records, customer history, and SLA audit trails, resulting in orphaned transactional records."

---

### Q4: Explain the purpose of your Partial Unique Index on `charging_sessions`.
**Answer:**
> "A standard unique constraint on `port_id` in `charging_sessions` would prevent a port from ever having more than one session in its entire history. However, a port will service thousands of charging sessions over its lifetime.
> We created a **Partial Unique Index**:
> ```sql
> CREATE UNIQUE INDEX uq_active_session_per_port 
> ON charging_sessions (port_id) 
> WHERE session_status = 'ACTIVE';
> ```
> This tells PostgreSQL to enforce uniqueness **only** when `session_status = 'ACTIVE'`. As a result, a port can have thousands of `COMPLETED` sessions, but the database engine physically forbids inserting a second `ACTIVE` session on the same port at the same time."

---

## Category 2: GIS & Spatial Database Operations (Primary Track C)

### Q5: What is a GiST index, and why is a B-Tree unsuitable for 2D spatial coordinates?
**Answer:**
> "A standard B-Tree index is strictly one-dimensional; it sorts values in linear ascending or descending order. While you can index latitude and longitude separately in B-Trees, a B-Tree cannot index two-dimensional space simultaneously without scanning large rectangular slices.
> A **GiST (Generalized Search Tree)** index implements an **R-Tree (Bounding Box Tree)**:
> - It hierarchically groups adjacent geographic points into Minimum Bounding Boxes (MBRs).
> - When searching for stations within a 5 km radius, the query optimizer checks whether the search bounding box intersects the bounding boxes at the top of the tree, pruning away 95% of irrelevant geographical quadrants in $O(\log N)$ time."

---

### Q6: How are spatial queries implemented in your PostgreSQL/PostGIS database?
**Answer:**
> "Our database implements spatial queries using **PostGIS 3.6.2** with architectural fallback resilience:
> 1. **Native PostGIS Mode (Active in `ev_db`)**:
>    - `charging_stations` includes a `geom geography(Point, 4326)` column populated for all 952 stations.
>    - Spatial queries utilize the GiST spatial index `idx_stations_spatial_gist ON charging_stations USING GIST (geom)`.
>    - Radius queries execute `ST_DWithin(geom, user_point, radius_meters)`, and nearest-station queries execute spatial distance sorting using the KNN operator `<->`.
>    - In `EXPLAIN ANALYZE`, the spatial GiST index uses `_st_expand` to bound candidate leaf pages in **0.150 ms**, returning results in under 1 ms.
> 2. **Native PostgreSQL Fallback**:
>    - In environments where PostGIS is not loaded, the schema automatically falls back to native PostgreSQL `point(longitude, latitude)` with bounding-box index filtering (`<@ box`) and geodesic Haversine distance in SQL."

---

### Q7: What is the difference between Euclidean distance and Geodesic (Haversine) distance?
**Answer:**
> - **Euclidean Distance** ($\sqrt{\Delta x^2 + \Delta y^2}$) calculates the straight-line distance on a flat 2D plane. It assumes the Earth is flat. At the scale of the Mumbai Metropolitan Region (spanning ~100 km), treating degrees of latitude and longitude as flat coordinates introduces significant distortion because lines of longitude converge toward the poles.
> - **Geodesic Distance (Haversine)** calculates the true shortest distance over the curved surface of a sphere or ellipsoid (WGS-84 reference ellipsoid). It accounts for Earth's curvature ($R = 6,371\text{ km}$) and produces distance values accurate to within a few meters."

---

## Category 3: Transactions, Concurrency & Locking

### Q8: What is the Lost-Update / Double-Booking problem, and how did you solve it?
**Answer:**
> "The double-booking race condition occurs when two drivers (e.g., Driver Alice and Driver Bob) attempt to book the same available charging port at the exact same millisecond:
> 1. Without concurrency control, both transactions execute `SELECT status FROM charging_ports WHERE port_id = 2` and both read `'AVAILABLE'`.
> 2. Both transactions execute `UPDATE charging_ports SET status = 'IN_USE'`, causing a Lost Update where both drivers believe they reserved the same physical hardware plug.
> 
> We resolved this using **Pessimistic Row-Level Locking**:
> ```sql
> SELECT port_id, status FROM charging_ports WHERE port_id = 2 FOR UPDATE;
> ```
> When Alice executes this statement, PostgreSQL places an exclusive row-level lock on that tuple. When Bob's transaction attempts the same query, Bob is placed in a **wait state**. When Alice commits, Bob's transaction awakens, reads the updated status (`'IN_USE'`), detects the conflict, and returns an HTTP 409 Conflict error."

---

### Q9: How did you prove the ACID property of Atomicity in your project?
**Answer:**
> "In [`database/05_transactions.sql`](file:///c:/Projects/ADBMS/database/05_transactions.sql) (Scenario 3), we executed a simulated failure test:
> 1. We selected an available port and recorded initial database counts.
> 2. Inside a transaction block, we updated the port to `'IN_USE'` and inserted an active session record.
> 3. Halfway through execution, we raised a simulated fatal hardware exception (`'METER_HARDWARE_FAULT'`).
> 4. The PostgreSQL engine caught the exception and executed an immediate `ROLLBACK`.
> 5. We then inspected the database: the port status remained `'AVAILABLE'`, and the total session count was identical before and after the test. Zero partial writes or dirty records remained."

---

## Category 4: Indexing & Query Optimization

### Q10: In your `EXPLAIN ANALYZE` benchmark, what were your actual measured execution times?
**Answer:**
> "We benchmarked a high-frequency query: searching for high-power fast chargers (`connector_type = 'CCS-2' AND power_kw >= 50.0`):
> - **With Index (Bitmap Index Scan)** on composite index `idx_ports_connector_power`:
>   - **Execution Time:** **0.225 ms**
>   - **Optimizer Cost:** **4.63 .. 25.58**
>   - **Heap Blocks Read:** 17
> - **Without Index (Sequential Scan)**:
>   - **Execution Time:** **0.502 ms**
>   - **Optimizer Cost:** **0.00 .. 50.39**
>   - **Rows Filtered Out:** 1,816
> 
> The composite B-Tree index reduced query latency by more than **55%** and cut estimated execution cost in half."

---

### Q11: Why does PostgreSQL sometimes choose a Sequential Scan over an Index Scan on small tables?
**Answer:**
> "PostgreSQL uses a **Cost-Based Optimizer (CBO)**:
> 1. An Index Scan involves two I/O steps: first reading the index leaf page, then performing a random-access read on the heap page to retrieve the tuple.
> 2. For small tables (e.g., under a few hundred pages), reading sequential 8 KB pages from disk or memory is much faster because consecutive blocks are loaded into OS cache in a single contiguous read.
> 3. As the dataset scales into thousands or tens of thousands of rows, the random I/O of reading index pages becomes dramatically cheaper than scanning thousands of heap blocks, causing the CBO to automatically favor Index Scans."

---

## Category 5: Security, RBAC & Disaster Recovery

### Q12: Explain the Principle of Least Privilege and show how your database roles enforce it.
**Answer:**
> "The Principle of Least Privilege states that every user and application process must be granted only the minimum permissions necessary to complete its authorized duties:
> - **`ev_admin`**: Full administrative rights for schema creation, DDL changes, and maintenance.
> - **`ev_app_user`**: Used by our FastAPI backend. It is granted `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on operational tables and `USAGE` on sequences. It has **no permission to create or drop tables (`NOCREATEDB`, `NOCREATEROLE`)**.
> - **`ev_analyst`**: Created for data analysts and BI reporting. It is granted strictly **read-only `SELECT`** permissions.
> In [`scripts/test_security.py`](file:///c:/Projects/ADBMS/scripts/test_security.py), we verified this: when `ev_analyst` executed `SELECT count(*) FROM charging_stations`, it returned 952 rows successfully; when it attempted `UPDATE charging_ports`, PostgreSQL threw an error: `permission denied for table charging_ports`."

---

### Q13: Why did you use `pg_dump -Fc` (Custom Format) instead of plain SQL text (`-Fp`)?
**Answer:**
> "The PostgreSQL custom format (`-Fc`) offers critical DBA advantages over plain SQL:
> 1. **Built-in Compression**: Uses zlib compression by default, reducing backup storage size by up to 80% (our database compressed to just 348 KB).
> 2. **Selective Restoration**: With `pg_restore`, a DBA can selectively restore a single table (e.g., `pg_restore -t charging_stations`), or restore only data without schema, or only schema without data.
> 3. **Automatic Dependency Ordering**: `pg_restore` reads the embedded Table of Contents (TOC) and reconstructs tables, indexes, and foreign keys in the correct dependency order, avoiding foreign key constraint violations during restore."

---

## Category 6: Real-World Data Engineering & Quality

### Q14: During your data audit, why did searching for stations in "Tardeo" originally return a station in "Kurla"?
**Answer:**
> "This was a key real-world data discovery during our project audit:
> 1. **Raw Data Coverage Gap**: OpenChargeMap and E-Amrit raw dumps contained zero stations south of latitude 19.07° N (South Mumbai). The southernmost authentic station in that raw dataset was `MobiLane Equinox Business Park` in **Kurla West** (lat 19.0715° N).
> 2. **Radius Fallback**: When a user searched for Tardeo (lat 18.9749° N) with a 15 km radius, the nearest station within 15 km was Kurla West at **12.67 km away**.
> 3. **City Normalization Pipeline Bug**: In the original ingestion script, any station with a missing city name was defaulted to `'Mumbai'`, causing 349 stations across India (including Tamil Nadu and UP) to be erroneously labeled as Mumbai.
> 
> We resolved this by:
> - Fixing the ingestion pipeline to enforce strict coordinate bounding before assigning city names.
> - Incorporating the official Bureau of Energy Efficiency (BEE) census, which added **134 verified stations in Mumbai City (including South Mumbai, Colaba, Worli, and Tardeo)**."
