"""
DBA Operations & Diagnostics Router
Exposes read-only system catalog metrics, pg_stat_activity diagnostics,
and query execution plans for demonstration in the dashboard.
"""
from typing import Dict, Any, List
from fastapi import APIRouter
from app.database import get_db_connection

router = APIRouter(prefix="/api/dba", tags=["DBA Operations"])

@router.get("/stats")
def get_dba_system_statistics() -> Dict[str, Any]:
    """
    Retrieves key database health metrics:
    - Shared buffers cache hit ratio
    - Table and index disk space consumption
    - Database total size
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Cache hit ratio
            cur.execute("""
            SELECT 
                blks_read, blks_hit,
                round((blks_hit * 100.0) / nullif(blks_hit + blks_read, 0), 2) AS cache_hit_pct
            FROM pg_stat_database 
            WHERE datname = 'ev_db';
            """)
            cache_row = cur.fetchone()

            # 2. Storage footprints
            cur.execute("""
            SELECT 
                relname AS table_name,
                pg_size_pretty(pg_relation_size(oid)) AS data_size,
                pg_size_pretty(pg_total_relation_size(oid) - pg_relation_size(oid)) AS index_size,
                pg_size_pretty(pg_total_relation_size(oid)) AS total_size,
                pg_total_relation_size(oid) AS total_bytes
            FROM pg_class
            WHERE relkind = 'r' 
              AND relnamespace = 'public'::regnamespace
              AND relname IN ('charging_stations', 'charging_ports', 'charging_sessions', 'station_status_history', 'stg_charging_stations')
            ORDER BY total_bytes DESC;
            """)
            tables_storage = cur.fetchall()

            # 3. Total DB Size
            cur.execute("SELECT pg_size_pretty(pg_database_size('ev_db')) AS db_size;")
            db_size = cur.fetchone()['db_size']

            return {
                "database_name": "ev_db",
                "total_size": db_size,
                "cache_hit_percentage": float(cache_row['cache_hit_pct'] or 100.0),
                "blocks_read_disk": int(cache_row['blks_read'] or 0),
                "blocks_hit_memory": int(cache_row['blks_hit'] or 0),
                "tables_storage": [dict(t) for t in tables_storage]
            }

@router.get("/activity")
def get_active_sessions() -> List[Dict[str, Any]]:
    """
    Inspects live database connections and executing queries via pg_stat_activity.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT 
                pid,
                usename AS username,
                client_addr::text AS client_ip,
                application_name,
                state,
                wait_event_type,
                wait_event,
                round(extract(epoch FROM (clock_timestamp() - query_start))::numeric, 2) AS duration_seconds,
                left(query, 120) AS query_snippet
            FROM pg_stat_activity
            WHERE datname = 'ev_db'
              AND pid <> pg_backend_pid()
            ORDER BY query_start DESC NULLS LAST
            LIMIT 20;
            """)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

@router.get("/benchmark")
def get_benchmark_comparison() -> Dict[str, Any]:
    """
    Runs a live EXPLAIN (ANALYZE, BUFFERS) comparison on an indexed fast charger query
    comparing Bitmap Index Scan vs Forced Sequential Scan.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = "SELECT * FROM charging_ports WHERE connector_type = 'CCS-2' AND power_kw >= 50.0;"

            # 1. With Index
            cur.execute("SET enable_seqscan = off;")
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {query}")
            plan_index = [list(r.values())[0] for r in cur.fetchall()]
            cur.execute("RESET enable_seqscan;")

            # 2. Forced Sequential Scan
            cur.execute("SET enable_indexscan = off; SET enable_bitmapscan = off;")
            cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {query}")
            plan_seq = [list(r.values())[0] for r in cur.fetchall()]
            cur.execute("RESET enable_indexscan; RESET enable_bitmapscan;")

            # Extract timings
            time_idx = next((l for l in plan_index if "Execution Time" in l), "N/A")
            time_seq = next((l for l in plan_seq if "Execution Time" in l), "N/A")

            return {
                "test_query": query,
                "with_index": {
                    "node_type": "Bitmap Index Scan on idx_ports_connector_power",
                    "execution_time": time_idx,
                    "plan_snippet": plan_index[:4]
                },
                "without_index": {
                    "node_type": "Sequential Table Scan (enable_seqscan=off)",
                    "execution_time": time_seq,
                    "plan_snippet": plan_seq[:4]
                }
            }
