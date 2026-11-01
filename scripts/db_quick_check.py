import psycopg2
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = psycopg2.connect(dbname='ev_db', user='postgres', password='postgres', host='localhost', port=5432)
cur = conn.cursor()

# 1. Extensions available
cur.execute("SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name LIKE '%postgis%';")
print("PostGIS available:", cur.fetchall())

# 2. Check if geom column exists in charging_stations
cur.execute("""
    SELECT column_name, data_type, udt_name 
    FROM information_schema.columns 
    WHERE table_name = 'charging_stations';
""")
print("charging_stations columns:")
for col in cur.fetchall():
    print(f"  {col[0]}: {col[1]} ({col[2]})")

# 3. Check spatial queries implemented in 04_spatial_queries.sql
# 4. Check indexes
cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'charging_stations';")
print("\nIndexes on charging_stations:")
for idx in cur.fetchall():
    print(f"  {idx[0]}: {idx[1]}")

cur.close()
conn.close()
