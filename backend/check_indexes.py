from app.database import get_db_connection

with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename, indexname;")
        rows = cur.fetchall()
        for r in rows:
            print(f"{r['tablename']}: {r['indexname']} -> {r['indexdef']}")
