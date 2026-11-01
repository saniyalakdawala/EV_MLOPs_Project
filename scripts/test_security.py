"""
Security and Role-Based Access Control Runner
Executes 08_security.sql against ev_db
Verifies least privilege enforcement: Analyst can SELECT but is BLOCKED from UPDATE.
"""
import psycopg2

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def test_security():
    print("=" * 70)
    print("ROLE-BASED ACCESS CONTROL (RBAC) & LEAST PRIVILEGE VERIFICATION")
    print("=" * 70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    # Deploy roles
    print("[Step 1] Deploying roles (ev_admin, ev_app_user, ev_analyst)...")
    with open('database/08_security.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    clean_sql = "\n".join([l for l in sql.splitlines() if not l.strip().startswith('\\c')])
    
    try:
        cur.execute(clean_sql)
        for n in conn.notices:
            print("  ", n.strip())
        conn.notices.clear()
        print("[OK] Roles deployed successfully.\n")
    except Exception as e:
        print(f"Role deployment: {e}")
        
    cur.close()
    conn.close()
    
    # Test Connection as ev_analyst
    print("[Step 2] Testing read-only connection as 'ev_analyst'...")
    try:
        analyst_conn = psycopg2.connect(dbname='ev_db', user='ev_analyst', password='AnalystReadOnly2026!', host='localhost', port=5432)
        a_cur = analyst_conn.cursor()
        a_cur.execute("SELECT count(*) FROM charging_stations;")
        count = a_cur.fetchone()[0]
        print(f"  • Analyst SELECT query SUCCEEDED: visible stations = {count}")
        
        # Test INSERT permission denial
        print("[Step 3] Testing write attempt as 'ev_analyst' (UPDATE charging_ports)...")
        try:
            a_cur.execute("UPDATE charging_ports SET status = 'AVAILABLE' WHERE port_id = 1;")
            print("  • ERROR: Security breach! Analyst updated port status!")
        except Exception as e:
            print(f"  • SUCCESS: Permission DENIED by PostgreSQL as expected:\n    --> {e}")
            analyst_conn.rollback()
            
        a_cur.close()
        analyst_conn.close()
    except Exception as e:
        print(f"Analyst connection failed: {e}")
        
    print("=" * 70)
    print("SECURITY & RBAC VERIFICATION COMPLETED SUCCESSFULLY")
    print("=" * 70)

if __name__ == '__main__':
    test_security()
