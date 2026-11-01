"""
Data Ingestion and Validation Pipeline
======================================
Pipeline Architecture:
Raw Data (JSON/GeoJSON) -> Staging Table (stg_charging_stations) 
  -> Python Validation & Cleaning -> Main Tables (charging_stations, charging_ports)
  -> Seed Initial History and Realistic Simulated Sessions.

Target Database: ev_db
"""

import json
import os
import math
import sys
import psycopg2
from psycopg2.extras import execute_batch
from shapely.geometry import shape, Point

def load_mmr_polygon():
    path = os.path.join('data', 'mmr_boundary.geojson')
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing MMR boundary file at {path}")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return shape(data['features'][0]['geometry'])

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

CONNECTOR_MAP = {
    33: 'CCS-2',
    25: 'Type 2 AC',
    2: 'CHAdeMO',
    1: 'Type 2 AC',
    27: 'CCS-2',
    0: 'Bharat AC-001',
    1036: 'Bharat DC-001',
    1037: 'Type 2 AC',
    1038: 'CCS-2'
}

DEFAULT_POWER = {
    'CCS-2': 60.0,
    'Type 2 AC': 22.0,
    'CHAdeMO': 50.0,
    'GB/T': 50.0,
    'Bharat AC-001': 3.3,
    'Bharat DC-001': 15.0
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def load_ocm_raw():
    path = os.path.join('data', 'raw', 'ocm_all_india.json')
    if not os.path.exists(path):
        print(f"Warning: {path} not found.")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_geojson_raw():
    path = os.path.join('data', 'raw', 'indian_ev_charging_stations.geojson')
    if not os.path.exists(path):
        print(f"Warning: {path} not found.")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('features', [])

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000 # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def run_pipeline(apply_production=False):
    print("=" * 60)
    mode_str = "APPLY TO PRODUCTION" if apply_production else "DRY-RUN / STAGING ONLY"
    print(f"STARTING DATA INGESTION & VALIDATION PIPELINE [{mode_str}]")
    print("=" * 60)
    
    mmr_polygon = load_mmr_polygon()
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Reset staging (and production if apply_production)
    if apply_production:
        print("\n[Step 1] Resetting staging and production tables (APPLY MODE)...")
        cur.execute("TRUNCATE TABLE station_status_history, charging_sessions, charging_ports, charging_stations, stg_charging_stations RESTART IDENTITY CASCADE;")
    else:
        print("\n[Step 1] Resetting staging table only (DRY-RUN MODE)...")
        cur.execute("TRUNCATE TABLE stg_charging_stations RESTART IDENTITY;")
    conn.commit()

    # 2. Parse Raw Sources
    print("\n[Step 2] Ingesting raw external datasets into Staging...")
    ocm_data = load_ocm_raw()
    geojson_data = load_geojson_raw()
    print(f"Loaded {len(ocm_data)} OCM records and {len(geojson_data)} GeoJSON records.")

    staging_rows = []
    
    # Parse OCM
    for item in ocm_data:
        raw_id = f"OCM-{item.get('ID')}"
        addr = item.get('AddressInfo', {})
        name = str(addr.get('Title') or 'Unnamed Station').strip()
        op_info = item.get('OperatorInfo', {})
        operator = op_info.get('Title') if op_info else None
        if not operator:
            operator = 'Tata Power' if 'tata' in name.lower() else ('Jio-bp' if 'jio' in name.lower() else 'Independent / Other')
            
        address = str(addr.get('AddressLine1') or '').strip()
        town = str(addr.get('Town') or '').strip()
        state = str(addr.get('StateOrProvince') or '').strip()
        postal = str(addr.get('Postcode') or '').strip()
        lat_raw = str(addr.get('Latitude', ''))
        lon_raw = str(addr.get('Longitude', ''))
        
        connections = item.get('Connections', [])
        conn_types = []
        powers = []
        for c in connections:
            cid = c.get('ConnectionTypeID')
            ctype = CONNECTOR_MAP.get(cid, 'CCS-2')
            conn_types.append(ctype)
            p = c.get('PowerKW')
            if p and p > 0:
                powers.append(str(p))
            else:
                powers.append(str(DEFAULT_POWER.get(ctype, 22.0)))
                
        num_ports = str(item.get('NumberOfPoints') or len(connections) or 2)
        
        staging_rows.append((
            raw_id, name, operator, address, town, state, postal,
            lat_raw, lon_raw,
            ",".join(conn_types) if conn_types else 'CCS-2,Type 2 AC',
            ",".join(powers) if powers else '60,22',
            num_ports, 'OpenChargeMap'
        ))

    # Parse GeoJSON (NITI Aayog)
    for feat in geojson_data:
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})
        coords = geom.get('coordinates', [0, 0])
        raw_id = f"EAMRIT-{props.get('stationid', '0')}"
        name = props.get('name', 'E-Amrit Station').strip()
        address = props.get('address', '').strip()
        town = props.get('city', '').strip()
        state = props.get('state', '').strip()
        postal = str(props.get('pincode', '')).strip()
        lat_raw = str(coords[1]) if len(coords) > 1 else str(props.get('lattitude', ''))
        lon_raw = str(coords[0]) if len(coords) > 0 else str(props.get('longitude', ''))
        
        staging_rows.append((
            raw_id, name, 'EESL / Government PSU', address, town, state, postal,
            lat_raw, lon_raw, 'Bharat AC-001,Type 2 AC', '3.3,22.0', '2', 'NITI_Aayog_EAmrit'
        ))

    insert_staging_sql = """
    INSERT INTO stg_charging_stations (
        raw_station_id, station_name, operator_name, address, city, state, postal_code,
        latitude_raw, longitude_raw, connector_type, power_kw_raw, number_of_ports_raw, source_name
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    execute_batch(cur, insert_staging_sql, staging_rows)
    conn.commit()
    print(f"Staged {len(staging_rows)} records into stg_charging_stations.")

    # 3. Clean and Validate
    print("\n[Step 3] Running Validation & Cleaning Engine...")
    cur.execute("SELECT staging_id, raw_station_id, station_name, operator_name, address, city, state, postal_code, latitude_raw, longitude_raw, connector_type, power_kw_raw, number_of_ports_raw, source_name FROM stg_charging_stations;")
    staged = cur.fetchall()

    valid_stations = []
    rejected_count = 0
    outside_mmr_count = 0
    duplicate_count = 0
    seen_locations = [] # (lat, lon, name)

    for row in staged:
        s_id, raw_id, name, op, addr, city, state, postal, lat_str, lon_str, conns, powers, ports_str, src = row
        
        # Validation 1: Required Name
        if not name or len(name) < 2:
            cur.execute("UPDATE stg_charging_stations SET validation_status = 'REJECTED', validation_error = 'Missing station name' WHERE staging_id = %s;", (s_id,))
            rejected_count += 1
            continue

        # Validation 2: Coordinate Parse and Range Checks
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except (ValueError, TypeError):
            cur.execute("UPDATE stg_charging_stations SET validation_status = 'REJECTED', validation_error = 'Invalid numeric coordinate' WHERE staging_id = %s;", (s_id,))
            rejected_count += 1
            continue

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            cur.execute("UPDATE stg_charging_stations SET validation_status = 'REJECTED', validation_error = 'Coordinate out of valid WGS-84 bounds' WHERE staging_id = %s;", (s_id,))
            rejected_count += 1
            continue

        # India bounding box sanity check (Lat: 6 to 38, Lon: 68 to 98)
        if not (6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0):
            cur.execute("UPDATE stg_charging_stations SET validation_status = 'REJECTED', validation_error = 'Coordinate outside Indian subcontinent' WHERE staging_id = %s;", (s_id,))
            rejected_count += 1
            continue

        # Validation 2b: Mumbai Metropolitan Region (MMR) Official Boundary Check
        # Rejects stations outside the designated Mumbai project boundary polygon
        pt = Point(lon, lat)
        if not mmr_polygon.contains(pt):
            cur.execute("UPDATE stg_charging_stations SET validation_status = 'REJECTED', validation_error = 'Coordinate outside Mumbai Metropolitan Region (MMR) boundary polygon' WHERE staging_id = %s;", (s_id,))
            rejected_count += 1
            outside_mmr_count += 1
            continue

        # Validation 3: State & City Normalization
        city_clean = city.title().strip() if (city and city.strip() not in ['None', 'null', '']) else 'Mumbai'
        state_clean = 'Maharashtra'
        if city_clean in ['Unknown', 'None', '', 'Mh']:
            city_clean = 'Mumbai'

        # Validation 4: Spatial Deduplication (< 30 meters)
        is_dup = False
        for ex_lat, ex_lon, ex_name in seen_locations:
            dist = haversine_distance(lat, lon, ex_lat, ex_lon)
            if dist < 30.0:
                is_dup = True
                break
        if is_dup:
            cur.execute("UPDATE stg_charging_stations SET validation_status = 'REJECTED', validation_error = 'Duplicate station detected within 30m radius' WHERE staging_id = %s;", (s_id,))
            duplicate_count += 1
            continue

        seen_locations.append((lat, lon, name))

        # Parse ports count
        try:
            num_ports = max(1, min(int(ports_str), 8))
        except (ValueError, TypeError):
            num_ports = 2

        # Parse connectors
        c_list = [c.strip() for c in conns.split(',') if c.strip() in ['CCS-2', 'Type 2 AC', 'CHAdeMO', 'GB/T', 'Bharat AC-001', 'Bharat DC-001']]
        if not c_list:
            c_list = ['CCS-2', 'Type 2 AC']

        p_list = []
        for p in powers.split(','):
            try:
                val = float(p.strip())
                if val > 0:
                    p_list.append(val)
            except ValueError:
                pass
        if not p_list:
            p_list = [60.0, 22.0]

        valid_stations.append({
            'staging_id': s_id,
            'name': name[:150],
            'operator': op[:100] if op else 'Independent Operator',
            'address': addr or f"{city_clean}, {state_clean}",
            'city': city_clean[:60],
            'state': state_clean[:60],
            'postal': postal[:12] if postal else None,
            'lat': lat,
            'lon': lon,
            'source': src,
            'num_ports': num_ports,
            'connectors': c_list,
            'powers': p_list
        })
        cur.execute("UPDATE stg_charging_stations SET validation_status = 'VALID' WHERE staging_id = %s;", (s_id,))

    conn.commit()
    print(f"Validation finished. Valid: {len(valid_stations)}, Rejected: {rejected_count} (Outside MMR: {outside_mmr_count}), Duplicates removed: {duplicate_count}")

    if not apply_production:
        print("\n" + "=" * 60)
        print("STAGING VALIDATION COMPLETE [DRY-RUN MODE]")
        print("=" * 60)
        print(f"Total Staged Raw Records : {len(staged)}")
        print(f"Valid Inside MMR Boundary: {len(valid_stations)}")
        print(f"Rejected Outside MMR     : {outside_mmr_count}")
        print(f"Rejected Other Errors    : {rejected_count - outside_mmr_count}")
        print(f"Duplicates Purged (<30m) : {duplicate_count}")
        print("\n[SAFETY GUARD] Production tables were NOT modified.")
        print("To promote the validated MMR stations to production, run:")
        print("  python scripts/ingest_pipeline.py --apply")
        print("=" * 60)
        cur.close()
        conn.close()
        return

    # 4. Insert into Production Tables
    print("\n[Step 4] Loading Cleaned Records into Production (3NF) Tables...")
    
    insert_station_sql = """
    INSERT INTO charging_stations (
        station_name, operator_name, address, city, state, postal_code, latitude, longitude, source_name
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING station_id;
    """
    
    insert_port_sql = """
    INSERT INTO charging_ports (
        station_id, port_number, connector_type, power_kw, status
    ) VALUES (%s, %s, %s, %s, %s)
    RETURNING port_id, status;
    """

    port_statuses = ['AVAILABLE', 'AVAILABLE', 'AVAILABLE', 'IN_USE', 'AVAILABLE', 'AVAILABLE', 'OUT_OF_SERVICE']
    
    total_ports = 0
    active_ports = []
    
    import random
    random.seed(42) # Deterministic seeding for reproducible academic grading

    for s in valid_stations:
        cur.execute(insert_station_sql, (
            s['name'], s['operator'], s['address'], s['city'], s['state'], s['postal'],
            s['lat'], s['lon'], s['source']
        ))
        st_id = cur.fetchone()[0]

        # Provision Ports for this Station
        for p_idx in range(1, s['num_ports'] + 1):
            conn_type = s['connectors'][(p_idx - 1) % len(s['connectors'])]
            power = s['powers'][(p_idx - 1) % len(s['powers'])] if s['powers'] else DEFAULT_POWER.get(conn_type, 22.0)
            status = random.choice(port_statuses)
            
            cur.execute(insert_port_sql, (st_id, p_idx, conn_type, power, status))
            p_id, stat = cur.fetchone()
            total_ports += 1
            if stat == 'IN_USE':
                active_ports.append(p_id)

    conn.commit()
    print(f"Loaded {len(valid_stations)} stations and {total_ports} charging ports into database.")

    # 5. Seed Realistic Operational Charging Sessions (Clearly Labeled as Simulated)
    print("\n[Step 5] Seeding Operational Sessions and Status History...")
    
    # Insert active sessions for currently IN_USE ports
    insert_active_session_sql = """
    INSERT INTO charging_sessions (
        port_id, user_identifier, start_time, session_status, energy_kwh
    ) VALUES (%s, %s, NOW() - INTERVAL '%s minute', 'ACTIVE', %s);
    """
    
    for idx, port_id in enumerate(active_ports):
        user_id = f"EV_USER_{1000 + idx}"
        elapsed_min = random.randint(10, 55)
        consumed = round((elapsed_min / 60.0) * random.uniform(15.0, 45.0), 2)
        cur.execute(insert_active_session_sql, (port_id, user_id, elapsed_min, consumed))

    # Insert completed historical sessions to demonstrate time-series queries & revenue tracking
    insert_hist_session_sql = """
    INSERT INTO charging_sessions (
        port_id, user_identifier, start_time, end_time, energy_kwh, session_status
    ) VALUES (%s, %s, NOW() - INTERVAL '%s hour', NOW() - INTERVAL '%s hour' + INTERVAL '%s minute', %s, 'COMPLETED');
    """
    
    # Pick 100 ports for past sessions
    cur.execute("SELECT port_id FROM charging_ports LIMIT 100;")
    sample_ports = [r[0] for r in cur.fetchall()]
    for p_id in sample_ports:
        hours_ago = random.randint(1, 48)
        duration_min = random.randint(20, 90)
        kwh = round((duration_min / 60.0) * random.uniform(10.0, 50.0), 2)
        cur.execute(insert_hist_session_sql, (p_id, f"HIST_USER_{random.randint(100, 999)}", hours_ago, hours_ago, duration_min, kwh))

    conn.commit()
    
    # Check Summary
    cur.execute("SELECT count(*) FROM charging_stations;")
    c_st = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM charging_stations WHERE state = 'Maharashtra';")
    c_mh = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM charging_ports;")
    c_po = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM charging_sessions;")
    c_se = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM station_status_history;")
    c_hi = cur.fetchone()[0]
    
    print("\n" + "=" * 60)
    print("INGESTION PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print(f"Total Charging Stations Imported : {c_st}")
    print(f"Maharashtra Stations             : {c_mh}")
    print(f"Total Charging Ports Provisioned : {c_po}")
    print(f"Operational Sessions (Live+Past) : {c_se}")
    print(f"Status History Audit Records     : {c_hi}")
    print("=" * 60)

    cur.close()
    conn.close()

if __name__ == '__main__':
    apply = '--apply' in sys.argv
    run_pipeline(apply_production=apply)
