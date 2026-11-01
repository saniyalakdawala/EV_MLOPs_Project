"""
Database Initialization Script for PostgreSQL
Creates the 'ev_db' database if it doesn't already exist.
Connects using superuser 'postgres' on port 5432.
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

DB_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def create_database(target_db='ev_db'):
    print(f"Connecting to PostgreSQL server at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
            exists = cur.fetchone()
            if not exists:
                print(f"Database '{target_db}' does not exist. Creating...")
                cur.execute(f"CREATE DATABASE {target_db};")
                print(f"Database '{target_db}' created successfully.")
            else:
                print(f"Database '{target_db}' already exists.")
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

if __name__ == '__main__':
    success = create_database()
    if not success:
        sys.exit(1)
