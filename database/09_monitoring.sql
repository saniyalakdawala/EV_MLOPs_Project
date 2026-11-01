-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 09_monitoring.sql
-- Topic: DBA Performance Monitoring, System Catalogs & Health Diagnostics
-- Target Database: ev_db
-- ============================================================================

\c ev_db;

-- ============================================================================
-- 1. ACTIVE SESSIONS & REAL-TIME CONNECTIONS (pg_stat_activity)
-- Inspects all active client sessions, current query, state, and wait events
-- ============================================================================
SELECT 
    pid,
    usename AS database_user,
    client_addr AS client_ip,
    application_name,
    state,
    wait_event_type,
    wait_event,
    round(extract(epoch FROM (clock_timestamp() - query_start))::numeric, 2) AS query_duration_seconds,
    left(query, 80) AS current_query_snippet
FROM pg_stat_activity
WHERE datname = 'ev_db'
  AND pid <> pg_backend_pid()
ORDER BY query_start ASC NULLS LAST;

-- ============================================================================
-- 2. IDENTIFY LONG-RUNNING QUERIES & TRANSACTIONS (> 5 SECONDS)
-- Essential DBA alarm query for detecting slow or rogue reporting scripts
-- ============================================================================
SELECT 
    pid,
    usename,
    state,
    now() - query_start AS runtime,
    query
FROM pg_stat_activity
WHERE state != 'idle'
  AND datname = 'ev_db'
  AND (now() - query_start) > INTERVAL '5 seconds'
ORDER BY runtime DESC;

-- How a DBA terminates an unresponsive query safely:
-- SELECT pg_cancel_backend(<pid>);     -- Politely asks query to cancel
-- SELECT pg_terminate_backend(<pid>);  -- Immediately kills the connection

-- ============================================================================
-- 3. LOCK CONTENTION & BLOCKED QUERIES
-- Detects which transaction is holding a lock and which transactions are waiting
-- ============================================================================
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
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- ============================================================================
-- 4. BUFFER CACHE HIT RATIO (SHARED BUFFERS EFFICIENCY)
-- Healthy production databases should achieve > 95% cache hit ratio
-- ============================================================================
SELECT 
    datname,
    blks_read AS disk_blocks_read,
    blks_hit AS memory_blocks_hit,
    round(
        (blks_hit * 100.0) / nullif(blks_hit + blks_read, 0), 
        2
    ) AS cache_hit_percentage
FROM pg_stat_database
WHERE datname = 'ev_db';

-- ============================================================================
-- 5. TABLE & INDEX DISK SPACE CONSUMPTION
-- Measures storage footprint for capacity planning and tablespace sizing
-- ============================================================================
SELECT 
    relname AS entity_name,
    pg_size_pretty(pg_relation_size(oid)) AS data_size,
    pg_size_pretty(pg_total_relation_size(oid) - pg_relation_size(oid)) AS index_size,
    pg_size_pretty(pg_total_relation_size(oid)) AS total_size
FROM pg_class
WHERE relkind = 'r' 
  AND relnamespace = 'public'::regnamespace
  AND relname IN ('charging_stations', 'charging_ports', 'charging_sessions', 'station_status_history', 'stg_charging_stations')
ORDER BY pg_total_relation_size(oid) DESC;

-- ============================================================================
-- 6. INDEX USAGE EFFICIENCY (UNUSED INDEX DETECTION)
-- Helps DBA identify redundant indexes consuming write I/O overhead
-- ============================================================================
SELECT 
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS index_scans_count,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC;
