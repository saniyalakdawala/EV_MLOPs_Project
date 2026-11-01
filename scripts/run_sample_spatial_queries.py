import psycopg2
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = psycopg2.connect(dbname='ev_db', user='postgres', password='postgres', host='localhost', port=5432)
cur = conn.cursor()

# Test point: Bandra Kurla Complex (BKC), Mumbai
# Lat: 19.065716, Lon: 72.868725
lat_bkc, lon_bkc = 19.065716, 72.868725

print("=" * 80)
print("GIS QUERY 1: Radius Search (Stations within 5 km of BKC, Mumbai)")
print("=" * 80)
query1 = """
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.city,
    s.latitude,
    s.longitude,
    round((
        6371.0 * 2.0 * asin(sqrt(
            power(sin(radians(s.latitude - %s) / 2.0), 2) +
            cos(radians(%s)) * cos(radians(s.latitude)) *
            power(sin(radians(s.longitude - %s) / 2.0), 2)
        ))
    )::numeric, 2) AS distance_km,
    count(p.port_id) AS total_ports,
    count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports
FROM charging_stations s
JOIN charging_ports p ON s.station_id = p.station_id
WHERE point(s.longitude, s.latitude) <@ box(point(%s, %s), point(%s, %s))
GROUP BY s.station_id, s.station_name, s.operator_name, s.city, s.latitude, s.longitude
HAVING (
    6371.0 * 2.0 * asin(sqrt(
        power(sin(radians(s.latitude - %s) / 2.0), 2) +
        cos(radians(%s)) * cos(radians(s.latitude)) *
        power(sin(radians(s.longitude - %s) / 2.0), 2)
    ))
) <= 5.0
ORDER BY distance_km ASC
LIMIT 5;
"""
# 5 km bounding box
radius_km = 5.0
dlat = radius_km / 111.32
dlon = radius_km / (111.32 * 0.945) # cos(19 deg) approx 0.945
params1 = [lat_bkc, lat_bkc, lon_bkc, lon_bkc - dlon, lat_bkc - dlat, lon_bkc + dlon, lat_bkc + dlat, lat_bkc, lat_bkc, lon_bkc]
cur.execute(query1, params1)
rows1 = cur.fetchall()
for r in rows1:
    print(f"ID {r[0]} | {r[1]} | Op: {r[2]} | {r[3]} | Lat: {r[4]}, Lon: {r[5]} | Dist: {r[6]} km | Ports: {r[7]} (Avail: {r[8]})")

print("\n" + "=" * 80)
print("GIS QUERY 2: Nearest Charging Station to Gateway of India (Lat 18.9220, Lon 72.8347)")
print("=" * 80)
lat_gw, lon_gw = 18.9220, 72.8347
query2 = """
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.address,
    s.latitude,
    s.longitude,
    round((
        6371.0 * 2.0 * asin(sqrt(
            power(sin(radians(s.latitude - %s) / 2.0), 2) +
            cos(radians(%s)) * cos(radians(s.latitude)) *
            power(sin(radians(s.longitude - %s) / 2.0), 2)
        ))
    )::numeric, 2) AS distance_km
FROM charging_stations s
ORDER BY point(s.longitude, s.latitude) <-> point(%s, %s)
LIMIT 3;
"""
cur.execute(query2, [lat_gw, lat_gw, lon_gw, lon_gw, lat_gw])
rows2 = cur.fetchall()
for r in rows2:
    print(f"ID {r[0]} | {r[1]} | Op: {r[2]} | Dist: {r[6]} km | Addr: {r[3]}")

print("\n" + "=" * 80)
print("GIS QUERY 3: Retrieve Stations Inside MMR Boundary with Port Breakdown")
print("=" * 80)
query3 = """
SELECT 
    s.city,
    count(DISTINCT s.station_id) AS stations_count,
    count(p.port_id) AS total_ports,
    round(avg(p.power_kw), 1) AS avg_power_kw
FROM charging_stations s
LEFT JOIN charging_ports p ON s.station_id = p.station_id
GROUP BY s.city
ORDER BY stations_count DESC
LIMIT 8;
"""
cur.execute(query3)
for r in cur.fetchall():
    print(f"City: {r[0]:25s} | Stations: {r[1]:4d} | Ports: {r[2]:4d} | Avg Power: {r[3]} kW")

print("\n" + "=" * 80)
print("GIS QUERY 4: Spatial Index Scan (EXPLAIN ANALYZE of GiST Point Bounding Box)")
print("=" * 80)
query4 = """
EXPLAIN (ANALYZE, BUFFERS)
SELECT station_id, station_name, latitude, longitude
FROM charging_stations
WHERE point(longitude, latitude) <@ box(point(72.80, 19.00), point(72.95, 19.15));
"""
cur.execute(query4)
for r in cur.fetchall():
    print("   ", r[0])

cur.close()
conn.close()
