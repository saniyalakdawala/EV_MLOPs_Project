-- ============================================================================
-- ADBMS MINI PROJECT CUM CASE STUDY: SQL EVIDENCE SCRIPT
-- Project: VoltGrid Mumbai - Smart EV Charging Infrastructure Database
-- Primary Track: Track C — GIS-Based Database
-- Database: ev_db (PostgreSQL 17)
-- Author: B.Tech Data Science Student
-- Description: Safe, read-only and transactional demonstration queries
--              for capturing screenshots and viva examination proof.
-- ============================================================================

-- ============================================================================
-- 1. VERIFY EXTENSIONS AND ENGINE CAPABILITIES
-- ============================================================================

-- Query 1.1: Check installed extensions
SELECT 
    extname AS extension_name, 
    extversion AS installed_version
FROM pg_extension
ORDER BY extname;

-- Query 1.2: Check PostGIS availability in PostgreSQL directory
SELECT 
    name, 
    default_version, 
    installed_version, 
    comment 
FROM pg_available_extensions 
WHERE name LIKE '%postgis%';


-- ============================================================================
-- 2. DATABASE SCHEMA AND RECORD COUNTS
-- ============================================================================

-- Query 2.1: Actual Record Counts across all tables
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
SELECT 'stg_master_ev_stations', count(*) FROM stg_master_ev_stations
UNION ALL
SELECT 'stg_national_master_ev_stations', count(*) FROM stg_national_master_ev_stations
ORDER BY row_count DESC;

-- Query 2.2: Station Provenance by Upstream Source in Production
SELECT 
    source_name, 
    count(*) AS station_count,
    round((count(*) * 100.0 / sum(count(*)) OVER ()), 2) AS percentage_share
FROM charging_stations
GROUP BY source_name
ORDER BY station_count DESC;

-- Query 2.3: Port Operational Status Breakdown
SELECT 
    status, 
    count(*) AS total_ports,
    round((count(*) * 100.0 / sum(count(*)) OVER ()), 2) AS percentage
FROM charging_ports
GROUP BY status
ORDER BY total_ports DESC;

-- Query 2.4: Port Connector Standard Breakdown
SELECT 
    connector_type, 
    count(*) AS port_count,
    round(min(power_kw), 1) AS min_kw,
    round(avg(power_kw), 1) AS avg_kw,
    round(max(power_kw), 1) AS max_kw
FROM charging_ports
GROUP BY connector_type
ORDER BY port_count DESC;


-- ============================================================================
-- 3. GIS CORE IMPLEMENTATION (SPATIAL QUERIES)
-- ============================================================================

-- Reference Point: Bandra Kurla Complex (BKC), Mumbai
-- Latitude: 19.065716 N, Longitude: 72.868725 E

-- Query 3.1: Radius Search (Stations within 5 km of BKC, Mumbai)
-- Uses bounding box filtering via GiST point index + exact geodesic Haversine distance
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.city,
    s.latitude,
    s.longitude,
    round((
        6371.0 * 2.0 * asin(sqrt(
            power(sin(radians(s.latitude - 19.065716) / 2.0), 2) +
            cos(radians(19.065716)) * cos(radians(s.latitude)) *
            power(sin(radians(s.longitude - 72.868725) / 2.0), 2)
        ))
    )::numeric, 2) AS distance_km,
    count(p.port_id) AS total_ports,
    count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports
FROM charging_stations s
JOIN charging_ports p ON s.station_id = p.station_id
WHERE point(s.longitude, s.latitude) <@ box(point(72.818, 19.015), point(72.918, 19.115))
GROUP BY s.station_id, s.station_name, s.operator_name, s.city, s.latitude, s.longitude
HAVING (
    6371.0 * 2.0 * asin(sqrt(
        power(sin(radians(s.latitude - 19.065716) / 2.0), 2) +
        cos(radians(19.065716)) * cos(radians(s.latitude)) *
        power(sin(radians(s.longitude - 72.868725) / 2.0), 2)
    ))
) <= 5.0
ORDER BY distance_km ASC
LIMIT 10;

-- Query 3.2: Nearest Charging Station to Gateway of India, Colaba
-- Latitude: 18.9220 N, Longitude: 72.8347 E
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.address,
    round((
        6371.0 * 2.0 * asin(sqrt(
            power(sin(radians(s.latitude - 18.9220) / 2.0), 2) +
            cos(radians(18.9220)) * cos(radians(s.latitude)) *
            power(sin(radians(s.longitude - 72.8347) / 2.0), 2)
        ))
    )::numeric, 2) AS distance_km
FROM charging_stations s
ORDER BY point(s.longitude, s.latitude) <-> point(72.8347, 18.9220)
LIMIT 5;

-- Query 3.3: Geographic Scope & Administrative Area Breakdown (MMR Municipalities)
SELECT 
    s.city,
    count(DISTINCT s.station_id) AS stations_count,
    count(p.port_id) AS total_ports,
    round(avg(p.power_kw), 1) AS avg_power_kw
FROM charging_stations s
LEFT JOIN charging_ports p ON s.station_id = p.station_id
GROUP BY s.city
ORDER BY stations_count DESC
LIMIT 10;

-- Query 3.4: PostGIS Native Spatial Query (Active in ev_db)
-- Evaluates ST_DWithin and ST_Distance on geography type (SRID 4326) with GiST spatial index
SELECT 
    s.station_id, 
    s.station_name, 
    s.operator_name,
    s.city,
    round((ST_Distance(s.geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography) / 1000.0)::numeric, 2) AS distance_km
FROM charging_stations s
WHERE s.geom IS NOT NULL 
  AND ST_DWithin(s.geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography, 5000)
ORDER BY s.geom <-> ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography
LIMIT 5;

-- Query 3.5: PostGIS Spatial Index Execution Plan (EXPLAIN ANALYZE)
EXPLAIN (ANALYZE, BUFFERS)
SELECT station_id, station_name 
FROM charging_stations 
WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography, 5000);


-- ============================================================================
-- 4. CONCURRENCY CONTROL & ROW-LEVEL LOCKING
-- ============================================================================

-- Query 4.1: Test Port Selection and Status Verification
SELECT port_id, station_id, port_number, connector_type, power_kw, status
FROM charging_ports
WHERE status = 'AVAILABLE'
ORDER BY port_id
LIMIT 5;

-- Query 4.2: Concurrency Isolation Simulation (Session 1)
-- BEGIN;
-- SELECT port_id, status FROM charging_ports WHERE port_id = 2 FOR UPDATE;
-- (Simulate delay, then UPDATE status = 'IN_USE')
-- COMMIT;

-- Query 4.3: Active Session Partial Unique Index Check
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE indexname = 'uq_active_session_per_port';


-- ============================================================================
-- 5. ACID TRANSACTIONS & ROLLBACK DEMONSTRATION
-- ============================================================================

-- Run from psql or pgAdmin Query Tool to observe notice logs:
DO $$
DECLARE
    v_test_port_id INT;
    v_initial_status VARCHAR(20);
    v_post_test_status VARCHAR(20);
    v_session_count_before INT;
    v_session_count_after INT;
BEGIN
    -- Pick an available port
    SELECT port_id, status INTO v_test_port_id, v_initial_status
    FROM charging_ports WHERE status = 'AVAILABLE' LIMIT 1;

    SELECT count(*) INTO v_session_count_before FROM charging_sessions;

    RAISE NOTICE '--- BEFORE TEST --- Port: % | Status: % | Total Sessions: %', 
                 v_test_port_id, v_initial_status, v_session_count_before;

    -- Sub-transaction simulating failure
    BEGIN
        UPDATE charging_ports SET status = 'IN_USE' WHERE port_id = v_test_port_id;
        INSERT INTO charging_sessions (port_id, user_identifier, session_status)
        VALUES (v_test_port_id, 'DEMO_USER_ROLLBACK', 'ACTIVE');
        
        -- Simulate fatal dispenser meter fault
        RAISE EXCEPTION 'DISPENSER_COMMUNICATION_ERROR: Firmware response timeout!';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'CAUGHT INTENTIONAL EXCEPTION: "%"', SQLERRM;
        RAISE NOTICE 'Rolling back transaction to preserve consistency...';
    END;

    -- Verify post-test state
    SELECT status INTO v_post_test_status FROM charging_ports WHERE port_id = v_test_port_id;
    SELECT count(*) INTO v_session_count_after FROM charging_sessions;

    RAISE NOTICE '--- AFTER ROLLBACK --- Port: % | Status: % | Total Sessions: %', 
                 v_test_port_id, v_post_test_status, v_session_count_after;

    IF v_post_test_status = v_initial_status AND v_session_count_before = v_session_count_after THEN
        RAISE NOTICE 'RESULT: ACID ATOMICITY PROOF VERIFIED! Zero dirty data written.';
    END IF;
END $$;


-- ============================================================================
-- 6. INDEXING AND EXPLAIN ANALYZE PERFORMANCE
-- ============================================================================

-- Query 6.1: Active Indexes on Production Schema
SELECT 
    tablename, 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Query 6.2: Benchmark with Index (Bitmap Index Scan on idx_ports_connector_power)
SET enable_seqscan = off;
EXPLAIN (ANALYZE, BUFFERS)
SELECT * 
FROM charging_ports 
WHERE connector_type = 'CCS-2' AND power_kw >= 50.0;
RESET enable_seqscan;

-- Query 6.3: Benchmark without Index (Forced Sequential Scan)
SET enable_indexscan = off;
SET enable_bitmapscan = off;
EXPLAIN (ANALYZE, BUFFERS)
SELECT * 
FROM charging_ports 
WHERE connector_type = 'CCS-2' AND power_kw >= 50.0;
RESET enable_indexscan;
RESET enable_bitmapscan;

-- Query 6.4: Spatial Index Scan (GiST Bounding Box)
EXPLAIN (ANALYZE, BUFFERS)
SELECT station_id, station_name, latitude, longitude
FROM charging_stations
WHERE point(longitude, latitude) <@ box(point(72.80, 19.00), point(72.95, 19.15));


-- ============================================================================
-- 7. ROLE-BASED ACCESS CONTROL (RBAC) & SECURITY
-- ============================================================================

-- Query 7.1: Active PostgreSQL Roles in Project
SELECT 
    rolname AS role_name, 
    rolsuper AS is_superuser, 
    rolinherit AS can_inherit, 
    rolcreaterole AS can_create_role, 
    rolcreatedb AS can_create_db, 
    rolcanlogin AS can_login
FROM pg_roles
WHERE rolname IN ('postgres', 'ev_admin', 'ev_app_user', 'ev_analyst');

-- Query 7.2: Effective Table Privileges by Role
SELECT 
    grantee, 
    table_name, 
    privilege_type
FROM information_schema.role_table_grants 
WHERE table_name IN ('charging_stations', 'charging_ports', 'charging_sessions', 'stg_charging_stations')
  AND grantee IN ('ev_admin', 'ev_app_user', 'ev_analyst')
ORDER BY grantee, table_name, privilege_type;

-- Query 7.3: Least-Privilege Verification (Analyst Blocked from UPDATE)
-- SET ROLE ev_analyst;
-- SELECT count(*) FROM charging_stations; -- SUCCEEDS (952 rows)
-- UPDATE charging_ports SET status = 'AVAILABLE' WHERE port_id = 1; -- FAILS: permission denied
-- RESET ROLE;


-- ============================================================================
-- 8. SYSTEM MONITORING & HEALTH DIAGNOSTICS
-- ============================================================================

-- Query 8.1: Buffer Cache Hit Ratio (pg_stat_database)
SELECT 
    datname AS database_name,
    blks_read AS disk_blocks_read,
    blks_hit AS memory_blocks_hit,
    round(
        (blks_hit * 100.0) / nullif(blks_hit + blks_read, 0), 
        2
    ) AS buffer_cache_hit_pct
FROM pg_stat_database
WHERE datname = 'ev_db';

-- Query 8.2: Table and Index Disk Space Footprint (pg_class)
SELECT 
    relname AS table_name,
    pg_size_pretty(pg_relation_size(oid)) AS heap_table_size,
    pg_size_pretty(pg_total_relation_size(oid) - pg_relation_size(oid)) AS index_size,
    pg_size_pretty(pg_total_relation_size(oid)) AS total_storage_size
FROM pg_class
WHERE relkind = 'r' 
  AND relnamespace = 'public'::regnamespace
  AND relname IN ('charging_stations', 'charging_ports', 'charging_sessions', 'station_status_history', 'stg_charging_stations', 'stg_national_master_ev_stations')
ORDER BY pg_total_relation_size(oid) DESC;

-- Query 8.3: Live Client Connections and Queries (pg_stat_activity)
SELECT 
    pid,
    usename AS username,
    client_addr AS client_ip,
    application_name,
    state,
    wait_event_type,
    wait_event,
    round(extract(epoch FROM (clock_timestamp() - query_start))::numeric, 2) AS query_duration_sec,
    left(query, 80) AS query_snippet
FROM pg_stat_activity
WHERE datname = 'ev_db'
  AND pid <> pg_backend_pid()
ORDER BY query_start ASC NULLS LAST;

-- Query 8.4: Lock Contention Detection
SELECT 
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS blocking_statement
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
