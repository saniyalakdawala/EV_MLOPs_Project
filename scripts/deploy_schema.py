"""
Schema Deployment Script
Executes database/01_schema.sql on target database 'ev_db'
"""
import psycopg2
import os

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def deploy():
    print(f"Connecting to database '{DB_CONFIG['dbname']}' on {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    with open(os.path.join('database', '01_schema.sql'), 'r', encoding='utf-8') as f:
        sql = f.read()

    print("Deploying DDL from database/01_schema.sql...")
    try:
        cur.execute(sql)
        conn.commit()
        print("[SUCCESS] All tables, triggers, and constraints deployed successfully in ev_db!")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to deploy schema: {e}")
        return False
    finally:
        cur.close()
        conn.close()
    return True

if __name__ == '__main__':
    deploy()
