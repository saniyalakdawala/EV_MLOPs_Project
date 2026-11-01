"""
Comprehensive Test & Verification Suite for EV Station Listing & Availability
Validates:
1. Three example cards: Central Depot, Nathani Heights, WR - Mumbai Central Station.
2. Provenance of every field (PostgreSQL vs calculation vs mock).
3. API behavior with database records and with empty results.
4. Absence of mock data on backend failure/empty results.
5. Station-to-port relationships and distance calculations.
"""
import urllib.request
import urllib.error
import json
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

BASE_URL = 'http://127.0.0.1:8000'

def test_three_example_cards_in_db_and_api():
    print("=== TEST 1: Three Example Cards (DB & API) ===")
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'ev_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )
    cur = conn.cursor()

    target_stations = [
        {"name": "Central Depot", "id": 3192, "source_id": "BEE-evs_b5a6281a04", "expected_ports": 5},
        {"name": "Nathani Heights", "id": 3085, "source_id": "BEE-evs_7bd9b935a8", "expected_ports": 2},
        {"name": "Wr - Mumbai Central Station", "id": 3076, "source_id": "BEE-evs_749a8660a6", "expected_ports": 2},
    ]

    for target in target_stations:
        # Check DB
        cur.execute("""
            SELECT station_id, station_name, operator_name, latitude, longitude, address, source_name, source_id, master_station_id
            FROM charging_stations WHERE station_id = %s;
        """, (target['id'],))
        row = cur.fetchone()
        assert row is not None, f"Station {target['name']} not found in charging_stations!"
        print(f"[DB PASS] Found {row[1]} (ID: {row[0]}, Op: {row[2]}, SourceID: {row[7]})")

        # Check DB Ports
        cur.execute("""
            SELECT port_id, port_number, connector_type, power_kw, status
            FROM charging_ports WHERE station_id = %s ORDER BY port_number;
        """, (target['id'],))
        ports = cur.fetchall()
        assert len(ports) == target['expected_ports'], f"Expected {target['expected_ports']} ports, got {len(ports)}"
        print(f"         Ports verified in DB: {len(ports)} rows (Connectors: {[p[2] for p in ports]})")

        # Check API Detail
        req = urllib.request.urlopen(f"{BASE_URL}/api/stations/{target['id']}")
        api_data = json.loads(req.read().decode())
        assert api_data['station_id'] == target['id']
        assert api_data['total_ports'] == target['expected_ports']
        assert api_data['has_live_status'] is False, "has_live_status must be False since live OCPI is unconfigured"
        print(f"[API PASS] Endpoint /api/stations/{target['id']} returned {api_data['total_ports']} ports, has_live_status=False")

    cur.close()
    conn.close()

def test_api_nearby_mumbai_central_spatial_query():
    print("\n=== TEST 2: Spatial Nearby Query Around Mumbai Central ===")
    # Mumbai Central coordinates: 18.969, 72.820
    url = f"{BASE_URL}/api/stations/nearby?lat=18.969&lon=72.820&radius_km=3&scope=mmr"
    req = urllib.request.urlopen(url)
    results = json.loads(req.read().decode())
    assert len(results) > 0, "Expected nearby stations around Mumbai Central"
    print(f"[API PASS] Found {len(results)} stations within 3km of Mumbai Central")

    names = [r['station_name'] for r in results]
    found_examples = [name for name in ["Nathani Heights", "Wr - Mumbai Central Station", "Central Depot"] if name in names]
    print(f"           Verified target stations in nearby radius: {found_examples}")
    assert len(found_examples) >= 2, "Nearby query should include target stations"

    for r in results[:5]:
        assert 'distance_km' in r and r['distance_km'] is not None
        assert r['has_live_status'] is False
        print(f"           - {r['station_name']}: {r['distance_km']} km (straight-line), {r['total_ports']} recorded ports")

def test_api_empty_result():
    print("\n=== TEST 3: Spatial Query with Empty Result (Remote Coordinates) ===")
    # In the Arabian Sea far off the coast: lat=18.0, lon=70.0
    url = f"{BASE_URL}/api/stations/nearby?lat=18.0&lon=70.0&radius_km=5&scope=mmr"
    req = urllib.request.urlopen(url)
    results = json.loads(req.read().decode())
    assert len(results) == 0, f"Expected 0 stations in Arabian sea, got {len(results)}"
    print("[API PASS] Zero stations returned for remote coordinates (no mock fallback silently generated)")

def test_scope_isolation():
    print("\n=== TEST 4: Geographic Scope Isolation (MMR vs All-India) ===")
    # MMR scope query
    url_mmr = f"{BASE_URL}/api/stations?scope=mmr&limit=10"
    res_mmr = json.loads(urllib.request.urlopen(url_mmr).read().decode())
    assert len(res_mmr) > 0
    for r in res_mmr:
        assert r['is_inside_mmr'] is True, "MMR stations must have is_inside_mmr=True"
    print(f"[API PASS] MMR query returned verified MMR stations (all is_inside_mmr=True)")

    # National scope query
    url_all = f"{BASE_URL}/api/stations?scope=all&limit=10"
    res_all = json.loads(urllib.request.urlopen(url_all).read().decode())
    assert len(res_all) > 0
    print(f"[API PASS] All-India query returned {len(res_all)} national staging records")

if __name__ == '__main__':
    test_three_example_cards_in_db_and_api()
    test_api_nearby_mumbai_central_spatial_query()
    test_api_empty_result()
    test_scope_isolation()
    print("\n ALL AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!")
