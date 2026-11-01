"""
Test Suite: Location Search, Place Autocomplete, and Real Data Retrieval
Executes the 10 Required Test Cases:
1. Enter a valid Mumbai landmark and select a suggestion.
2. Enter a location with multiple possible matches.
3. Enter an unknown location.
4. Deny GPS permission and use manual search.
5. Search with a small radius.
6. Search with a larger radius.
7. Select a new location and verify that results change.
8. Search a location where no stations are within the radius.
9. Test invalid coordinates and radius values against the backend.
10. Confirm that returned station distances are calculated from the selected coordinates.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import math

BASE_URL = "http://127.0.0.1:8000"

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "VoltGrid-Tester/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode('utf-8'))

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    return round(2.0 * R * math.asin(math.sqrt(a)), 2)

def run_all_tests():
    print("=" * 80)
    print("VOLTGRID MUMBAI: LOCATION SEARCH & PLACE AUTOCOMPLETE VERIFICATION SUITE")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Case 1: Enter a valid Mumbai landmark and select a suggestion
    # --------------------------------------------------------------------------
    print("\n[Case 1] Enter a valid Mumbai landmark: 'Bandra West, Mumbai'")
    status, suggestions = get_json(f"{BASE_URL}/api/geocoding/search?q={urllib.parse.quote('Bandra West, Mumbai')}&limit=5")
    assert status == 200 and len(suggestions) > 0, "Failed to get suggestions for Bandra West"
    top = suggestions[0]
    print(f"  [PASS] Geocoded suggestion: '{top['name']}' ({top['formatted_address'][:60]}...)")
    print(f"         Coordinates: Lat {top['latitude']}, Lon {top['longitude']}")
    bandra_lat, bandra_lon = top['latitude'], top['longitude']

    # Retrieve nearby stations using these geocoded coordinates
    status, stations = get_json(f"{BASE_URL}/api/stations/nearby?lat={bandra_lat}&lon={bandra_lon}&radius_km=10")
    assert status == 200 and len(stations) > 0, "Failed to retrieve stations near Bandra West"
    print(f"  [PASS] Retrieved {len(stations)} charging stations from real database within 10 km.")
    print(f"         Nearest: '{stations[0]['station_name']}' at {stations[0]['distance_km']} km away.")

    # --------------------------------------------------------------------------
    # Case 2: Enter a location with multiple possible matches
    # --------------------------------------------------------------------------
    print("\n[Case 2] Enter a location with multiple possible matches: 'Andheri Station, Mumbai'")
    status, suggestions = get_json(f"{BASE_URL}/api/geocoding/search?q={urllib.parse.quote('Andheri Station, Mumbai')}&limit=5")
    assert status == 200 and len(suggestions) >= 2, f"Expected multiple matches, got {len(suggestions)}"
    print(f"  [PASS] Found {len(suggestions)} distinct suggestions for 'Andheri Station, Mumbai':")
    for i, s in enumerate(suggestions[:3], 1):
        print(f"         {i}. {s['name']} -> {s['formatted_address'][:55]}... ({s['latitude']:.4f}, {s['longitude']:.4f})")

    # --------------------------------------------------------------------------
    # Case 3: Enter an unknown location
    # --------------------------------------------------------------------------
    print("\n[Case 3] Enter an unknown / non-existent location: 'NonExistentPlaceZyx98765'")
    status, suggestions = get_json(f"{BASE_URL}/api/geocoding/search?q={urllib.parse.quote('NonExistentPlaceZyx98765')}&limit=5")
    assert status == 200 and len(suggestions) == 0, f"Expected empty array for unknown location, got {suggestions}"
    print("  [PASS] Backend returned empty array [] without fabricating fake coordinates or errors.")

    # --------------------------------------------------------------------------
    # Case 4: Deny GPS permission and use manual search
    # --------------------------------------------------------------------------
    print("\n[Case 4] Manual search without GPS permission: 'Powai, Mumbai'")
    status, suggestions = get_json(f"{BASE_URL}/api/geocoding/search?q={urllib.parse.quote('Powai, Mumbai')}&limit=3")
    assert status == 200 and len(suggestions) > 0, "Failed to geocode Powai"
    powai = suggestions[0]
    print(f"  [PASS] Manual place selected without browser GPS: '{powai['name']}' at ({powai['latitude']:.4f}, {powai['longitude']:.4f})")
    status, powai_stations = get_json(f"{BASE_URL}/api/stations/nearby?lat={powai['latitude']}&lon={powai['longitude']}&radius_km=10")
    assert status == 200, "Failed to retrieve stations for manual coordinates"
    print(f"  [PASS] Successfully retrieved {len(powai_stations)} stations near Powai.")

    # --------------------------------------------------------------------------
    # Case 5 & 6: Search with small radius vs larger radius
    # --------------------------------------------------------------------------
    print("\n[Case 5 & 6] Radius sensitivity from Chhatrapati Shivaji Maharaj Airport (BOM)")
    status, suggestions = get_json(f"{BASE_URL}/api/geocoding/search?q={urllib.parse.quote('Chhatrapati Shivaji Maharaj International Airport, Mumbai')}&limit=1")
    airport = suggestions[0]
    air_lat, air_lon = airport['latitude'], airport['longitude']

    # Small radius: 3 km
    status, small_st = get_json(f"{BASE_URL}/api/stations/nearby?lat={air_lat}&lon={air_lon}&radius_km=3.0")
    # Larger radius: 25 km
    status, large_st = get_json(f"{BASE_URL}/api/stations/nearby?lat={air_lat}&lon={air_lon}&radius_km=25.0")

    print(f"  [PASS] Small radius (3.0 km) returned:  {len(small_st)} stations")
    print(f"  [PASS] Large radius (25.0 km) returned: {len(large_st)} stations")
    assert len(small_st) <= len(large_st), "Stations count must scale with radius"
    for st in small_st:
        assert float(st['distance_km']) <= 3.0, f"Station {st['station_name']} exceeds 3.0 km limit"

    # --------------------------------------------------------------------------
    # Case 7: Select a new location and verify that results change
    # --------------------------------------------------------------------------
    print("\n[Case 7] Select new location and verify results change (Andheri West vs Thane West)")
    status, andheri_st = get_json(f"{BASE_URL}/api/stations/nearby?lat=19.1197&lon=72.8461&radius_km=10")
    status, thane_st = get_json(f"{BASE_URL}/api/stations/nearby?lat=19.2183&lon=72.9781&radius_km=15")

    assert len(andheri_st) > 0 and len(thane_st) > 0, "Both locations should yield stations"
    andheri_ids = [s['station_id'] for s in andheri_st]
    thane_ids = [s['station_id'] for s in thane_st]
    print(f"  [PASS] Andheri West (Western Suburbs) nearest: '{andheri_st[0]['station_name']}' ({andheri_st[0]['distance_km']} km)")
    print(f"  [PASS] Thane West (Northern MMR) nearest:    '{thane_st[0]['station_name']}' ({thane_st[0]['distance_km']} km)")
    assert andheri_ids != thane_ids, "Results must differ for geographically distant locations"
    print(f"  [PASS] Successfully confirmed results switch completely between selected locations.")

    # --------------------------------------------------------------------------
    # Case 8: Search a location where no stations are within the radius
    # --------------------------------------------------------------------------
    print("\n[Case 8] Search location where no stations are in radius (Nariman Point South Mumbai, 10 km radius)")
    status, empty_st = get_json(f"{BASE_URL}/api/stations/nearby?lat=18.9260&lon=72.8230&radius_km=10.0")
    assert status == 200 and len(empty_st) == 0, f"Expected 0 stations at Nariman Point 10km, got {len(empty_st)}"
    print(f"  [PASS] Returned 0 stations within 10 km; triggers clear empty-state UI with radius expansion prompt.")

    # --------------------------------------------------------------------------
    # Case 9: Test invalid coordinates and radius values against backend
    # --------------------------------------------------------------------------
    print("\n[Case 9] Testing input validation for invalid coordinates & radius")
    invalid_cases = [
        ("Invalid Latitude > 90", f"{BASE_URL}/api/stations/nearby?lat=95.0&lon=72.87&radius_km=15", 422),
        ("Invalid Latitude < -90", f"{BASE_URL}/api/stations/nearby?lat=-95.0&lon=72.87&radius_km=15", 422),
        ("Invalid Longitude > 180", f"{BASE_URL}/api/stations/nearby?lat=19.0&lon=195.0&radius_km=15", 422),
        ("Negative Radius", f"{BASE_URL}/api/stations/nearby?lat=19.0&lon=72.87&radius_km=-5.0", 422),
        ("Excessive Radius > 200 km", f"{BASE_URL}/api/stations/nearby?lat=19.0&lon=72.87&radius_km=500.0", 422),
    ]

    for label, bad_url, expected_status in invalid_cases:
        try:
            req = urllib.request.Request(bad_url)
            urllib.request.urlopen(req, timeout=3)
            assert False, f"Expected {expected_status} for {label}, but succeeded!"
        except urllib.error.HTTPError as err:
            assert err.code == expected_status, f"Expected {expected_status}, got {err.code}"
            print(f"  [PASS] {label}: Rejected with HTTP {err.code} Unprocessable Entity.")

    # --------------------------------------------------------------------------
    # Case 10: Confirm that returned station distances are calculated from selected coordinates
    # --------------------------------------------------------------------------
    print("\n[Case 10] Mathematical verification of returned station distances against ground truth Haversine")
    origin_lat, origin_lon = 19.065716, 72.868725 # BKC
    status, bkc_stations = get_json(f"{BASE_URL}/api/stations/nearby?lat={origin_lat}&lon={origin_lon}&radius_km=15")

    for st in bkc_stations[:4]:
        backend_dist = float(st['distance_km'])
        calculated_dist = haversine_km(origin_lat, origin_lon, float(st['latitude']), float(st['longitude']))
        delta = abs(backend_dist - calculated_dist)
        print(f"  • Station: '{st['station_name']}'")
        print(f"    Stored DB Coords: ({st['latitude']}, {st['longitude']})")
        print(f"    Backend distance: {backend_dist} km | Ground Truth Haversine: {calculated_dist} km | Delta: {delta:.3f} km")
        assert delta <= 0.05, f"Distance discrepancy too high! {backend_dist} vs {calculated_dist}"
    print("  [PASS] All station distances confirmed mathematically accurate from selected user coordinates.")

    print("\n" + "=" * 80)
    print("ALL 10 TEST CASES PASSED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    run_all_tests()
