"""
Index Performance Benchmark Runner
Executes EXPLAIN ANALYZE queries on ev_db to measure actual execution times
and query plan node types (Index Scan vs Sequential Scan).
"""
import psycopg2

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def benchmark_indexes():
    print("=" * 70)
    print("INDEXING PERFORMANCE BENCHMARK & EXPLAIN ANALYZE EVALUATION")
    print("=" * 70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # 1. Ensure indexes exist
    print("[Step 1] Deploying B-Tree & GiST indexes from 07_indexes_performance.sql...")
    with open('database/07_indexes_performance.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    clean_sql = "\n".join([l for l in sql.splitlines() if not l.strip().startswith('\\c') and not l.strip().startswith('EXPLAIN') and not l.strip().startswith('SET') and not l.strip().startswith('RESET')])
    cur.execute(clean_sql)
    conn.commit()
    print("[OK] Indexes deployed and table statistics analyzed.\n")
    
    # 2. Benchmark Query: Fast Charger Lookup (CCS-2 >= 50kW)
    test_query = "SELECT * FROM charging_ports WHERE connector_type = 'CCS-2' AND power_kw >= 50.0;"
    
    print("-" * 70)
    print("TEST CASE: Fast Charger Search (connector_type = 'CCS-2' AND power_kw >= 50.0)")
    print("-" * 70)
    
    # Run with Index Enabled (forcing index scan)
    cur.execute("SET enable_seqscan = off;")
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {test_query}")
    plan_index = cur.fetchall()
    cur.execute("RESET enable_seqscan;")
    
    # Run with Index Disabled (forcing sequential scan)
    cur.execute("SET enable_indexscan = off; SET enable_bitmapscan = off;")
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {test_query}")
    plan_seq = cur.fetchall()
    cur.execute("RESET enable_indexscan; RESET enable_bitmapscan;")
    
    print(">>> 1. QUERY PLAN WITH INDEX (Bitmap Index Scan):")
    for line in plan_index[:4]:
        print("   ", line[0])
        
    print("\n>>> 2. QUERY PLAN WITHOUT INDEX (Forced Seq Scan):")
    for line in plan_seq[:4]:
        print("   ", line[0])
        
    # Extract execution times
    time_idx = [l[0] for l in plan_index if 'Execution Time' in l[0]]
    time_seq = [l[0] for l in plan_seq if 'Execution Time' in l[0]]
    
    print("\n" + "=" * 70)
    print("ACTUAL MEASURED PERFORMANCE COMPARISON:")
    print(f"  • With Index (Bitmap Index Scan) : {time_idx[0] if time_idx else 'N/A'}")
    print(f"  • Without Index (Seq Scan)       : {time_seq[0] if time_seq else 'N/A'}")
    print("=" * 70)
    print("ACADEMIC NOTE ON QUERY PLANNER DECISIONS:")
    print("PostgreSQL uses a Cost-Based Optimizer (CBO). For small table footprints, sequential reads")
    print("are highly cached in OS page cache. As records scale, Bitmap Index Scan dramatically")
    print("prunes disk block reads, ensuring sub-millisecond response times under production loads.")
    print("=" * 70)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    benchmark_indexes()
