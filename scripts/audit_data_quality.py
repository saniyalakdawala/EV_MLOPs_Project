"""
Data Quality and Ingestion Pipeline Audit
=========================================
Performs a deep audit on raw source files, staging tables, and production database records.
Tracks the exact origin of erroneous geographic records (e.g. Tamil Nadu, UP, HP in Mumbai DB).
"""
import json
import os
import math
import psycopg2

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000 # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# MMR Standard Pilot Bounding Box:
# Latitude: 18.53 to 19.50 N (Alibaug/Panvel to Palghar/Virar)
# Longitude: 72.75 to 73.35 E (Arabian Sea to Kalyan/Ambernath/Badlapur)
MMR_MIN_LAT, MMR_MAX_LAT = 18.53, 19.50
MMR_MIN_LON, MMR_MAX_LON = 72.75, 73.35

def is_in_mmr(lat, lon):
    return (MMR_MIN_LAT <= lat <= MMR_MAX_LAT) and (MMR_MIN_LON <= lon <= MMR_MAX_LON)

def audit_raw_sources():
    print("=" * 80)
    print("PHASE 1: RAW DATA SOURCE AUDIT")
    print("=" * 80)

    # 1. Audit ocm_all_india.json
    ocm_path = os.path.join('data', 'raw', 'ocm_all_india.json')
    with open(ocm_path, 'r', encoding='utf-8') as f:
        ocm_data = json.load(f)

    print(f"\n1. Source: OpenChargeMap (ocm_all_india.json)")
    print(f"   Total Raw Records: {len(ocm_data)}")

    ocm_valid_coords = 0
    ocm_invalid_coords = 0
    ocm_inside_mmr = 0
    ocm_outside_mmr = 0
    ocm_missing_name = 0
    ocm_missing_address = 0
    ocm_missing_operator = 0
    ocm_missing_connectors = 0
    ocm_conflicting_state = 0 # e.g. state says Maharashtra but coords outside

    target_samples = [
        "Fleettrack", "Drise", "khuurampur", "E-Fill Electric Hotel Food Mania", "SEL Dev"
    ]
    found_targets = {}

    for idx, item in enumerate(ocm_data):
        addr = item.get('AddressInfo', {})
        name = addr.get('Title')
        lat = addr.get('Latitude')
        lon = addr.get('Longitude')
        town = addr.get('Town')
        state = addr.get('StateOrProvince')
        line1 = addr.get('AddressLine1')
        conns = item.get('Connections', [])
        op = item.get('OperatorInfo', {}).get('Title') if item.get('OperatorInfo') else None

        for t in target_samples:
            if name and t.lower() in name.lower():
                found_targets[t] = {
                    'source': 'OpenChargeMap',
                    'raw_id': item.get('ID'),
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'town': town,
                    'state': state,
                    'operator': op
                }

        if not name or len(str(name).strip()) < 2:
            ocm_missing_name += 1
        if not line1:
            ocm_missing_address += 1
        if not op:
            ocm_missing_operator += 1
        if not conns:
            ocm_missing_connectors += 1

        try:
            lat_f = float(lat)
            lon_f = float(lon)
            if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                ocm_valid_coords += 1
                if is_in_mmr(lat_f, lon_f):
                    ocm_inside_mmr += 1
                else:
                    ocm_outside_mmr += 1
                    # Check if labeled Maharashtra or Mumbai
                    if state and 'maharashtra' in str(state).lower() and not (15.5 <= lat_f <= 22.5 and 72.5 <= lon_f <= 81.0):
                        ocm_conflicting_state += 1
            else:
                ocm_invalid_coords += 1
        except (ValueError, TypeError):
            ocm_invalid_coords += 1

    print(f"   - Valid Coordinates: {ocm_valid_coords}")
    print(f"   - Invalid Coordinates: {ocm_invalid_coords}")
    print(f"   - Inside MMR Boundary (18.53-19.50N, 72.75-73.35E): {ocm_inside_mmr}")
    print(f"   - Outside MMR Boundary: {ocm_outside_mmr}")
    print(f"   - Missing/Empty Address Line: {ocm_missing_address}")
    print(f"   - Missing Explicit Operator: {ocm_missing_operator}")
    print(f"   - Missing Connections/Connectors: {ocm_missing_connectors}")
    print(f"   - False State Attribution in Raw (coords outside MH but state=MH): {ocm_conflicting_state}")

    # 2. Audit indian_ev_charging_stations.geojson
    geo_path = os.path.join('data', 'raw', 'indian_ev_charging_stations.geojson')
    with open(geo_path, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)

    features = geo_data.get('features', [])
    print(f"\n2. Source: NITI Aayog / E-Amrit (indian_ev_charging_stations.geojson)")
    print(f"   Total Raw Records: {len(features)}")

    geo_valid_coords = 0
    geo_invalid_coords = 0
    geo_inside_mmr = 0
    geo_outside_mmr = 0
    geo_missing_name = 0
    geo_missing_address = 0

    for idx, feat in enumerate(features):
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})
        coords = geom.get('coordinates', [])
        name = props.get('name')
        addr = props.get('address')
        city = props.get('city')
        state = props.get('state')

        for t in target_samples:
            if name and t.lower() in name.lower() and t not in found_targets:
                found_targets[t] = {
                    'source': 'NITI_Aayog_EAmrit',
                    'raw_id': props.get('stationid'),
                    'name': name,
                    'lat': coords[1] if len(coords) > 1 else None,
                    'lon': coords[0] if len(coords) > 0 else None,
                    'town': city,
                    'state': state
                }

        if not name:
            geo_missing_name += 1
        if not addr:
            geo_missing_address += 1

        if len(coords) >= 2:
            try:
                lon_f = float(coords[0])
                lat_f = float(coords[1])
                if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                    geo_valid_coords += 1
                    if is_in_mmr(lat_f, lon_f):
                        geo_inside_mmr += 1
                    else:
                        geo_outside_mmr += 1
                else:
                    geo_invalid_coords += 1
            except (ValueError, TypeError):
                geo_invalid_coords += 1
        else:
            geo_invalid_coords += 1

    print(f"   - Valid Coordinates: {geo_valid_coords}")
    print(f"   - Invalid Coordinates: {geo_invalid_coords}")
    print(f"   - Inside MMR Boundary (18.53-19.50N, 72.75-73.35E): {geo_inside_mmr}")
    print(f"   - Outside MMR Boundary: {geo_outside_mmr}")

    # 3. User Samples Origin Trace
    print("\n3. Trace of User Sample Stations in Raw Data:")
    for t, info in found_targets.items():
        in_mmr_flag = is_in_mmr(info['lat'], info['lon']) if info['lat'] and info['lon'] else False
        print(f"   • '{t}':")
        print(f"       Source: {info['source']} (Raw ID: {info['raw_id']})")
        print(f"       Name in Source: {info['name']}")
        print(f"       Coordinates: Lat {info['lat']}, Lon {info['lon']}")
        print(f"       Raw City/State: {info['town']}, {info['state']}")
        print(f"       Is Inside MMR Boundary? {in_mmr_flag}")

def audit_database():
    print("\n" + "=" * 80)
    print("PHASE 2: DATABASE AUDIT (PostgreSQL ev_db)")
    print("=" * 80)

    conn = psycopg2.connect(dbname='ev_db', user='postgres', password='postgres', host='localhost', port=5432)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM charging_stations;")
    total_db = cur.fetchone()[0]

    cur.execute(f"""
        SELECT count(*) FROM charging_stations 
        WHERE latitude BETWEEN {MMR_MIN_LAT} AND {MMR_MAX_LAT} 
          AND longitude BETWEEN {MMR_MIN_LON} AND {MMR_MAX_LON};
    """)
    inside_mmr_db = cur.fetchone()[0]
    outside_mmr_db = total_db - inside_mmr_db

    print(f"Total Stations currently in 'charging_stations': {total_db}")
    print(f"  • Truly Inside MMR Boundary: {inside_mmr_db}")
    print(f"  • Leaked Outside MMR Boundary (Entire India): {outside_mmr_db}")

    cur.execute("""
        SELECT state, count(*) FROM charging_stations 
        GROUP BY state ORDER BY count(*) DESC;
    """)
    print("\nGeographic Spread of Stations in 'charging_stations' by State:")
    for state, cnt in cur.fetchall():
        print(f"  • {state}: {cnt}")

    # Check stations with city = 'Mumbai'
    cur.execute("SELECT station_id, station_name, city, state, latitude, longitude FROM charging_stations WHERE city ILIKE '%Mumbai%';")
    mumbai_labeled = cur.fetchall()
    print(f"\nStations labeled city='Mumbai': {len(mumbai_labeled)}")
    for s in mumbai_labeled:
        in_mmr = is_in_mmr(float(s[4]), float(s[5]))
        print(f"  ID {s[0]}: {s[1]} at ({s[4]}, {s[5]}) - In MMR: {in_mmr}")

    # Let's inspect where 461 might come from:
    # Check charging_ports with various statuses
    cur.execute("SELECT status, count(*) FROM charging_ports GROUP BY status;")
    print("\nPort Status breakdown:")
    for st, cnt in cur.fetchall():
        print(f"  • {st}: {cnt}")

    cur.execute("SELECT count(*) FROM charging_sessions;")
    print(f"Total Charging Sessions in DB: {cur.fetchone()[0]}")

if __name__ == '__main__':
    audit_raw_sources()
    audit_database()
