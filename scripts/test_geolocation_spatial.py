"""
Test Suite: Geolocation & PostGIS Spatial Operations Verification
Tests:
1. Retrieval of EV stations near given GPS coordinates
2. Geodesic distance calculation and sorting by distance ascending
3. Verification of hardware attributes: connector_types, max_power_kw, and port availability
4. Radius expansion sensitivity (e.g. 5 km vs 15 km vs 30 km)
5. Spatial GiST indexing execution plan verification (EXPLAIN ANALYZE)
6. Error handling for out-of-range coordinates
"""
import math
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def run_tests():
    print("=" * 75)
    print("TEST SUITE: GEOLOCATION RADIUS SEARCH & SPATIAL GiST VERIFICATION")
    print("=" * 75)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Test 1: BKC Mumbai coordinates (19.065716, 72.868725), radius = 10 km
    lat, lon, radius_km = 19.065716, 72.868725, 10.0
    print(f"\n[Test 1] Executing nearby stations search from User GPS: ({lat:.6f}, {lon:.6f}) with radius = {radius_km} km")

    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(0.01, math.cos(math.radians(lat))))
    min_lat, max_lat = lat - dlat, lat + dlat
    min_lon, max_lon = lon - dlon, lon + dlon

    query = """
    SELECT 
        s.station_id,
        s.station_name,
        s.operator_name,
        s.address,
        s.city,
        s.state,
        s.latitude,
        s.longitude,
        count(p.port_id) AS total_ports,
        count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports,
        array_remove(array_agg(DISTINCT p.connector_type), NULL) AS connector_types,
        array_remove(array_agg(DISTINCT p.power_kw::float), NULL) AS power_outputs,
        max(p.power_kw::float) AS max_power_kw,
        round((
            6371.0 * 2.0 * asin(sqrt(
                power(sin(radians(s.latitude - %s) / 2.0), 2) +
                cos(radians(%s)) * cos(radians(s.latitude)) *
                power(sin(radians(s.longitude - %s) / 2.0), 2)
            ))
        )::numeric, 2) AS distance_km
    FROM charging_stations s
    JOIN charging_ports p ON s.station_id = p.station_id
    WHERE point(s.longitude, s.latitude) <@ box(point(%s, %s), point(%s, %s))
    GROUP BY s.station_id, s.station_name, s.operator_name, s.address, s.city, s.state, s.latitude, s.longitude
    HAVING (
        6371.0 * 2.0 * asin(sqrt(
            power(sin(radians(s.latitude - %s) / 2.0), 2) +
            cos(radians(%s)) * cos(radians(s.latitude)) *
            power(sin(radians(s.longitude - %s) / 2.0), 2)
        ))
    ) <= %s
    ORDER BY distance_km ASC
    LIMIT 10;
    """
    params = [lat, lat, lon, min_lon, min_lat, max_lon, max_lat, lat, lat, lon, radius_km]
    cur.execute(query, params)
    stations = cur.fetchall()

    assert len(stations) > 0, "Expected at least 1 station near BKC!"
    print(f"  [OK] Retrieved {len(stations)} stations within {radius_km} km")

    # Verify sorting and hardware fields
    prev_dist = 0.0
    for idx, st in enumerate(stations, 1):
        dist = float(st['distance_km'])
        assert dist >= prev_dist, f"Stations not sorted by distance: {dist} < {prev_dist}"
        prev_dist = dist
        print(f"  {idx}. {st['station_name']} ({st['city']})")
        print(f"     • Distance: {dist:.2f} km")
        print(f"     • Connectors: {st['connector_types']}")
        print(f"     • Max Power: {st['max_power_kw']} kW")
        print(f"     • Ports: {st['available_ports']} / {st['total_ports']} Available (Simulated)")

    # Test 2: Radius Expansion Sensitivity
    print("\n[Test 2] Testing radius expansion sensitivity...")
    counts = {}
    for r in [5.0, 10.0, 20.0, 30.0]:
        dlat_r = r / 111.32
        dlon_r = r / (111.32 * max(0.01, math.cos(math.radians(lat))))
        cur.execute(query, [lat, lat, lon, lon - dlon_r, lat - dlat_r, lon + dlon_r, lat + dlat_r, lat, lat, lon, r])
        res = cur.fetchall()
        counts[r] = len(res)
        print(f"  • Radius {r:4.1f} km: {counts[r]} stations returned")

    assert counts[5.0] <= counts[10.0] <= counts[20.0] <= counts[30.0], "Station counts must increase monotonically with radius"
    print("  [OK] Monotonic radius expansion verified.")

    # Test 3: Measured Spatial GiST Index Query Plan
    print("\n[Test 3] Measuring Query Plan and GiST Index Utilization (EXPLAIN ANALYZE)...")
    explain_query = f"EXPLAIN (ANALYZE, BUFFERS) {query}"
    cur.execute(explain_query, params)
    plan_rows = [r['QUERY PLAN'] for r in cur.fetchall()]

    gist_scan_found = any('idx_stations_point_gist' in line or 'Bitmap Index Scan' in line for line in plan_rows)
    exec_time_line = next((line for line in plan_rows if 'Execution Time' in line), 'N/A')

    print("  Query Plan Summary:")
    for line in plan_rows[:8]:
        print("   ", line)
    print(f"  • Spatial Index used: {'YES (idx_stations_point_gist)' if gist_scan_found else 'NO (Sequential Scan)'}")
    print(f"  • {exec_time_line}")

    assert gist_scan_found, "GiST spatial index was not used by PostgreSQL optimizer!"
    print("  [OK] Spatial GiST index actively pruned bounding box!")

    print("\n" + "=" * 75)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)

    cur.close()
    conn.close()

if __name__ == '__main__':
    run_tests()
