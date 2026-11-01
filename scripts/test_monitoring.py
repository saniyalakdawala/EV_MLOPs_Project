"""
Monitoring Diagnostic Runner
Executes 09_monitoring.sql queries on ev_db to display real-time engine statistics.
"""
import psycopg2

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def run_monitoring():
    print("=" * 70)
    print("POSTGRESQL DBA HEALTH & PERFORMANCE MONITORING DIAGNOSTICS")
    print("=" * 70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # 1. Cache hit ratio
    cur.execute("""
    SELECT 
        blks_read, blks_hit,
        round((blks_hit * 100.0) / nullif(blks_hit + blks_read, 0), 2)
    FROM pg_stat_database WHERE datname = 'ev_db';
    """)
    read, hit, ratio = cur.fetchone()
    print(f"[METRIC 1] Buffer Cache Hit Ratio: {ratio}% (Blocks Read: {read}, Blocks Hit: {hit})")
    
    # 2. Table and Index storage sizes
    print("\n[METRIC 2] Table & Index Storage Footprint:")
    cur.execute("""
    SELECT 
        relname,
        pg_size_pretty(pg_relation_size(oid)),
        pg_size_pretty(pg_total_relation_size(oid) - pg_relation_size(oid)),
        pg_size_pretty(pg_total_relation_size(oid))
    FROM pg_class
    WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
      AND relname IN ('charging_stations', 'charging_ports', 'charging_sessions', 'station_status_history', 'stg_charging_stations')
    ORDER BY pg_total_relation_size(oid) DESC;
    """)
    for row in cur.fetchall():
        print(f"   • {row[0]:<25} Table: {row[1]:<8} | Indexes: {row[2]:<8} | Total: {row[3]:<8}")

    # 3. Active Connections in pg_stat_activity
    print("\n[METRIC 3] Active Client Connections (pg_stat_activity):")
    cur.execute("""
    SELECT pid, usename, application_name, state, left(query, 50)
    FROM pg_stat_activity
    WHERE datname = 'ev_db';
    """)
    for row in cur.fetchall():
        print(f"   • PID {row[0]}: User '{row[1]}' | State: {row[3]} | App: '{row[2]}' | Query: {row[4]}...")
        
    cur.close()
    conn.close()
    print("=" * 70)

if __name__ == '__main__':
    run_monitoring()
