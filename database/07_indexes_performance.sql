-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 07_indexes_performance.sql
-- Topic: Indexing Strategies, B-Tree, GiST & EXPLAIN ANALYZE Query Plans
-- Target Database: ev_db
-- ============================================================================

\c ev_db;

-- ============================================================================
-- 1. INDEX DEFINITIONS & ARCHITECTURAL RATIONALE
-- ============================================================================

-- Index 1: B-Tree on charging_ports(status)
-- Justification: High-frequency operational filter in mobile apps ("Show AVAILABLE ports").
CREATE INDEX IF NOT EXISTS idx_ports_status 
ON charging_ports (status);

-- Index 2: Composite B-Tree on charging_ports(connector_type, power_kw)
-- Justification: Supports multi-column vehicle hardware matching (e.g. CCS-2 >= 50kW).
CREATE INDEX IF NOT EXISTS idx_ports_connector_power 
ON charging_ports (connector_type, power_kw);

-- Index 3: Composite B-Tree on charging_sessions(port_id, session_status)
-- Justification: Optimizes active session lookups and availability joins.
CREATE INDEX IF NOT EXISTS idx_sessions_port_status 
ON charging_sessions (port_id, session_status);

-- Index 4: B-Tree on charging_sessions(start_time DESC)
-- Justification: Optimizes time-series analytics, billing reports, and history pagination.
CREATE INDEX IF NOT EXISTS idx_sessions_start_time 
ON charging_sessions (start_time DESC);

-- Index 5: B-Tree on charging_stations(state, city)
-- Justification: Accelerates regional grouping and administrative city filters.
CREATE INDEX IF NOT EXISTS idx_stations_state_city 
ON charging_stations (state, city);

-- Index 6: Spatial GiST Index on charging_stations
-- Conditionally created when PostGIS is active or using PostgreSQL native point GiST
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'charging_stations' AND column_name = 'geom'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_stations_spatial_gist 
        ON charging_stations USING GIST (geom);
    ELSE
        CREATE INDEX IF NOT EXISTS idx_stations_point_gist 
        ON charging_stations USING GIST (point(longitude, latitude));
    END IF;
END $$;

-- Update PostgreSQL statistics optimizer:
ANALYZE charging_stations;
ANALYZE charging_ports;
ANALYZE charging_sessions;
ANALYZE station_status_history;

-- ============================================================================
-- 2. MEASURED PERFORMANCE EVALUATION (EXPLAIN ANALYZE)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- BENCHMARK 1: FAST CHARGER LOOKUP (CCS-2 >= 50 kW)
-- ----------------------------------------------------------------------------
-- Query:
EXPLAIN (ANALYZE, BUFFERS)
SELECT port_id, station_id, connector_type, power_kw, status
FROM charging_ports
WHERE connector_type = 'CCS-2' AND power_kw >= 50.0;

-- ----------------------------------------------------------------------------
-- BENCHMARK 2: RECENT CHARGING HISTORY (LAST 24 HOURS)
-- ----------------------------------------------------------------------------
-- Query:
EXPLAIN (ANALYZE, BUFFERS)
SELECT session_id, port_id, user_identifier, start_time, energy_kwh, session_status
FROM charging_sessions
WHERE start_time >= NOW() - INTERVAL '24 hour'
ORDER BY start_time DESC
LIMIT 50;

-- ----------------------------------------------------------------------------
-- BENCHMARK 3: STATION AVAILABILITY AGGREGATION JOIN
-- ----------------------------------------------------------------------------
-- Query:
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    s.station_id,
    s.station_name,
    s.city,
    count(p.port_id) AS total_ports,
    count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports
FROM charging_stations s
JOIN charging_ports p ON s.station_id = p.station_id
WHERE s.state = 'Maharashtra'
GROUP BY s.station_id, s.station_name, s.city
ORDER BY available_ports DESC
LIMIT 20;

-- ----------------------------------------------------------------------------
-- BENCHMARK 4: FORCING SEQUENTIAL SCAN VS INDEX SCAN COMPARISON
-- Demonstrates how DBA tests index effectiveness by toggling enable_seqscan:
-- ----------------------------------------------------------------------------

-- Test with Index Enabled (Default):
SET enable_seqscan = off;
EXPLAIN ANALYZE
SELECT * FROM charging_ports WHERE connector_type = 'CCS-2' AND power_kw >= 50.0;

-- Test with Index Disabled (Forces Table Scan):
SET enable_seqscan = on;
SET enable_indexscan = off;
SET enable_bitmapscan = off;
EXPLAIN ANALYZE
SELECT * FROM charging_ports WHERE connector_type = 'CCS-2' AND power_kw >= 50.0;

-- Reset planner settings to defaults:
RESET enable_seqscan;
RESET enable_indexscan;
RESET enable_bitmapscan;

-- ============================================================================
-- 3. DBA ANALYSIS & HONEST ACADEMIC PERFORMANCE FINDINGS
-- ============================================================================
-- OBSERVATION 1:
-- On datasets under 10,000 rows, PostgreSQL's Cost-Based Optimizer (CBO) 
-- frequently chooses a "Seq Scan" because reading consecutive 8KB disk pages 
-- into shared_buffers is cheaper than random I/O index traversal.
-- 
-- OBSERVATION 2:
-- When forcing index usage (`SET enable_seqscan = off`), the planner utilizes 
-- "Bitmap Index Scan on idx_ports_connector_power" followed by "Bitmap Heap Scan",
-- demonstrating how the index scales efficiently for high-cardinality searches.
-- 
-- OBSERVATION 3:
-- Spatial GiST (Generalized Search Tree) indexes hierarchically prune bounding boxes
-- (R-Tree layout), reducing radius search complexity from O(N) to O(log N).
-- ============================================================================
