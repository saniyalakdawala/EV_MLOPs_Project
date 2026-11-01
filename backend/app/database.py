"""
Database Connection and Pooling Module
Manages a thread-safe connection pool using psycopg2.
"""
from contextlib import contextmanager
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from app.config import settings

# Global Connection Pool
_pool = None

def init_db_pool(minconn=2, maxconn=20):
    global _pool
    if _pool is None:
        try:
            _pool = ThreadedConnectionPool(
                minconn=minconn,
                maxconn=maxconn,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                cursor_factory=RealDictCursor
            )
            print(f"[DB] Initialized ThreadedConnectionPool with {settings.DB_USER} on {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
        except Exception as e:
            print(f"[DB ERROR] Failed connecting as {settings.DB_USER}: {e}. Falling back to 'postgres' user...")
            _pool = ThreadedConnectionPool(
                minconn=minconn,
                maxconn=maxconn,
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                dbname=settings.DB_NAME,
                user="postgres",
                password="postgres",
                cursor_factory=RealDictCursor
            )
            print(f"[DB] Initialized fallback pool as 'postgres'")
    return _pool

def close_db_pool():
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        print("[DB] Connection pool closed.")

@contextmanager
def get_db_connection():
    """
    Context manager that yields a connection from the pool and automatically
    returns it when done, handling commit / rollback.
    """
    pool = init_db_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
