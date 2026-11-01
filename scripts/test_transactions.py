"""
Transaction Demonstration Runner
Executes database/05_transactions.sql against ev_db
Demonstrates Start Session (Commit), End Session (Commit), and Error (Rollback).
"""
import psycopg2

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def run_transactions():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    with open('database/05_transactions.sql', 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Strip \\c ev_db;
    clean_content = "\n".join([line for line in content.splitlines() if not line.strip().startswith('\\c')])
    
    # Split by DO $$ blocks
    parts = clean_content.split('DO $$')
    for part in parts[1:]:
        block = "DO $$" + part
        try:
            cur.execute(block)
            for notice in conn.notices:
                print(notice.strip())
            conn.notices.clear()
        except Exception as e:
            print(f"Transaction block failed: {e}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run_transactions()
