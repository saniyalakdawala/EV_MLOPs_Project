# ADBMS Comprehensive Viva Preparation Guide & Question Bank

This document prepares you for oral viva examination questions commonly asked by professors and examiners in Advanced Database Management Systems (ADBMS).

---

## 1. Core Architecture & Relational Design

### Q1: Why is this project an ADBMS project rather than just an ordinary CRUD application?
**Examiner Answer:**
> "An ordinary CRUD application merely creates, reads, updates, and deletes records using basic unconstrained queries. Our project solves critical ADBMS-level challenges:
> 1. **Spatial Data Modeling**: Storing and indexing geographic data using PostGIS `geography(Point, 4326)` for true ellipsoidal geodesic distance calculations rather than flat 2D approximations.
> 2. **Concurrency Control**: Managing high-contention simultaneous bookings on physical charging ports using PostgreSQL row-level locks (`SELECT ... FOR UPDATE`) to prevent race conditions.
> 3. **ACID Transaction Safety**: Multi-statement transactional boundaries ensuring that port status changes, session creation, and audit logging succeed atomically or roll back completely on failure.
> 4. **DBA Engineering**: Role-based access control (RBAC) with Least Privilege, buffer cache monitoring via `pg_stat_database`, and automated disaster recovery via custom-format `pg_dump`."

### Q2: What normal form does your database schema satisfy? Prove it.
**Examiner Answer:**
> "Our schema satisfies **Third Normal Form (3NF)**:
> - **1NF**: All attributes are atomic (no repeating groups, comma-separated lists, or nested relations in production tables).
> - **2NF**: It is in 1NF, and all non-key attributes are fully functionally dependent on the entire primary key (no partial dependencies).
> - **3NF**: It is in 2NF, and no non-key attribute is transitively dependent on the primary key. For example, charging port attributes (`connector_type`, `power_kw`) depend directly on `port_id`, not transitively on `station_id`."

### Q3: Why did you use `ON DELETE RESTRICT` for `charging_sessions` but `ON DELETE CASCADE` for `charging_ports`?
**Examiner Answer:**
> "This is a deliberate DBA referential integrity decision:
> - If a physical charging station is demolished, its hardware ports cease to exist, so `ON DELETE CASCADE` cleans up the dependent port records.
> - However, if someone tries to delete a port that has historical charging sessions, `ON DELETE RESTRICT` **blocks the deletion**. Deleting a port with completed sessions would destroy financial billing records and SLA audit trails, leading to orphaned transactions."

---

## 2. Concurrency Control & Transactions

### Q4: Explain the race condition that occurs if two users try to book the same port simultaneously, and how you solved it.
**Examiner Answer:**
> "If two drivers tap 'Start Charging' at the same millisecond:
> 1. Without concurrency control, both transactions execute `SELECT status FROM charging_ports WHERE port_id = 5` and both read `'AVAILABLE'`.
> 2. Both proceed to execute `UPDATE charging_ports SET status = 'IN_USE'`, resulting in a classic **Lost Update** and double-booked physical hardware.
> 
> We solved this using **Pessimistic Row-Level Locking**:
> ```sql
> SELECT port_id, status FROM charging_ports WHERE port_id = 5 FOR UPDATE;
> ```
> When Driver Alice executes this query, PostgreSQL places an exclusive lock on that row. When Driver Bob's transaction attempts the same query, it is put into a **wait state**. When Alice commits, Bob's transaction resumes, inspects the updated status, sees `'IN_USE'`, and safely returns a `409 Conflict` error.
> 
> As a secondary safety net, we created a **Partial Unique Index**:
> ```sql
> CREATE UNIQUE INDEX uq_active_session_per_port ON charging_sessions (port_id) WHERE session_status = 'ACTIVE';
> ```
> Even if application code failed, the PostgreSQL engine itself makes it physically impossible to insert two concurrent `ACTIVE` sessions for the same port."

### Q5: What are the ACID properties, and how does your project demonstrate them?
**Examiner Answer:**
> - **Atomicity**: In [`05_transactions.sql`](file:///c:/Projects/ADBMS/database/05_transactions.sql), if a simulated energy meter failure occurs during session creation, PostgreSQL executes a `ROLLBACK`. The port status remains `'AVAILABLE'` and zero dirty session records remain.
> - **Consistency**: Enforced through schema constraints: `chk_latitude_range` ($[-90, +90]$), `chk_power_positive` ($>0\text{ kW}$), and certified connector standards.
> - **Isolation**: Managed using PostgreSQL's default `Read Committed` isolation level augmented with `SELECT ... FOR UPDATE` row locks to prevent phantom reads and lost updates.
> - **Durability**: Guaranteed by PostgreSQL's Write-Ahead Logging (WAL). Once a transaction commits, its modifications are permanently recorded in WAL logs on disk before acknowledging the client."

---

## 3. GIS & Spatial Database Questions

### Q6: What is the difference between `geometry` and `geography` types in PostGIS?
**Examiner Answer:**
> - `geometry` represents data on a flat, Cartesian 2D plane ($x, y$). Distances are calculated using standard Euclidean distance formulas ($\sqrt{\Delta x^2 + \Delta y^2}$). On a city or regional scale, projecting latitude and longitude onto a flat plane introduces severe geometric distortion.
> - `geography` represents spatial features on an ellipsoidal spherical model of the Earth (WGS-84, SRID 4326). When executing `ST_DWithin(geom, user_point, 10000)`, distances are evaluated along the curved surface of the Earth directly in **meters**, without requiring local coordinate projection transformations."

### Q7: What is a GiST index, and why is it better than a B-Tree for spatial queries?
**Examiner Answer:**
> "A standard B-Tree index is strictly one-dimensional; it sorts keys in linear ascending or descending order. However, geographic coordinates are two-dimensional $(x, y)$ or $(lat, lon)$.
> A **GiST (Generalized Search Tree)** index implements an **R-Tree (Bounding Box Tree)** layout:
> - It groups adjacent geographic points into Minimum Bounding Rectangles (MBRs).
> - When searching for stations within a 10 km radius, PostgreSQL tests whether the search circle intersects the bounding rectangles at the top of the tree, pruning away entire quadrants of the city in $O(\log N)$ time rather than evaluating every station sequentially."

---

## 4. Indexing & Query Optimization

### Q8: In your `EXPLAIN ANALYZE` benchmark, why does PostgreSQL sometimes choose a Sequential Scan over an Index Scan on smaller datasets?
**Examiner Answer:**
> "PostgreSQL uses a **Cost-Based Optimizer (CBO)**:
> 1. Reading an index requires two distinct operations: reading index leaf pages from disk, followed by random-access reads to fetch actual tuple rows from table heap pages.
> 2. For smaller tables (e.g., under a few thousand rows), reading consecutive 8KB table pages via a sequential scan is much faster because consecutive disk blocks are efficiently read into memory in a single sequential I/O burst and cached in `shared_buffers`.
> 3. As data volume scales into tens of thousands of rows, the random I/O overhead of the index becomes dramatically cheaper than scanning thousands of heap blocks, causing the CBO to automatically switch to Index Scans or Bitmap Index Scans."

---

## 5. DBA Responsibilities & Security

### Q9: Explain the Principle of Least Privilege and how you applied it in your database roles.
**Examiner Answer:**
> "The Principle of Least Privilege states that any module, user, or service must be granted only the minimum permissions necessary to perform its legitimate function:
> - **`ev_admin`**: Used exclusively for administrative DDL, maintenance, and migrations.
> - **`ev_app_user`**: Used by our FastAPI backend. It is granted `SELECT`, `INSERT`, `UPDATE` on operational tables and `USAGE` on sequences. It has **no DDL or table dropping privileges**.
> - **`ev_analyst`**: Intended for BI and reporting. It is granted strictly **read-only `SELECT`** permissions. We proved this in [`08_security.sql`](file:///c:/Projects/ADBMS/database/08_security.sql) where an analyst's attempt to run `UPDATE charging_ports` was blocked by the engine with `permission denied for table charging_ports`."

### Q10: Why did you choose the custom archive format (`-Fc`) for `pg_dump`?
**Examiner Answer:**
> "`pg_dump -Fc` produces a compressed binary archive with an embedded Table of Contents (TOC):
> 1. **Size Efficiency**: Reduces backup storage and network bandwidth by up to 80% via built-in compression.
> 2. **Selective Restoration**: Using `pg_restore`, a DBA can choose to restore only specific tables (e.g. restoring only `charging_stations`) or only schema definitions without data.
> 3. **Dependency Ordering**: `pg_restore` automatically orders objects so tables are created before foreign keys are enforced, preventing restoration order failures."
