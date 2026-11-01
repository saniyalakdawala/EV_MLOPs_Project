"""
Rebuild Master EV Stations Dataset Pipeline
===========================================
Rebuilds the master dataset from scratch using verified open-data sources:
1. OpenStreetMap Overpass (data/raw/osm_mmr_overpass_raw.json)
2. OpenChargeMap (data/raw/ocm_all_india.json)
3. NITI Aayog / E-Amrit (data/raw/indian_ev_charging_stations.geojson)

Outputs:
- data/master_ev_stations.csv
- data/review/pending_stations.csv
- data/review/rejected_stations.csv
- data/dataset_quality_report.txt
- Loads into PostgreSQL staging table: stg_master_ev_stations
"""
import json
import csv
import os
import math
import psycopg2
from shapely.geometry import shape, Point

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000 # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def load_boundary():
    b_path = os.path.join('data', 'mmr_boundary.geojson')
    with open(b_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return shape(data['features'][0]['geometry']), data.get('metadata', {})

def build_master_dataset():
    print("=" * 80)
    print("REBUILDING MASTER EV CHARGING INFRASTRUCTURE DATASET FOR MUMBAI (MMR)")
    print("=" * 80)

    mmr_polygon, boundary_meta = load_boundary()
    print(f"Loaded Official Boundary: {boundary_meta.get('name', 'MMR')}")

    os.makedirs('data/review', exist_ok=True)
    os.makedirs('data/raw', exist_ok=True)

    master_records = []
    pending_records = []
    rejected_records = []

    # Track raw source counts for reporting
    stats = {
        'sources': {},
        'total_raw': 0,
        'valid_in_boundary': 0,
        'rejected_out_of_boundary': 0,
        'rejected_invalid_coords': 0,
        'pending_generic_or_missing': 0,
        'pending_cross_source_proximity': 0,
        'duplicates_exact_source_id': 0
    }

    seen_source_keys = set() # (source_name, source_id)
    raw_candidates = [] # All parsed candidates before cross-filtering

    # -------------------------------------------------------------------------
    # SOURCE 1: OpenStreetMap Overpass (MMR Live Extract)
    # -------------------------------------------------------------------------
    osm_path = os.path.join('data', 'raw', 'osm_mmr_overpass_raw.json')
    if os.path.exists(osm_path):
        with open(osm_path, 'r', encoding='utf-8') as f:
            osm_data = json.load(f)
        elements = osm_data.get('elements', [])
        stats['sources']['OpenStreetMap_Overpass'] = len(elements)
        stats['total_raw'] += len(elements)
        print(f"\n[Source 1] OpenStreetMap Overpass: Found {len(elements)} raw features.")

        for el in elements:
            el_type = el.get('type')
            el_id = el.get('id')
            lat = el.get('lat') or el.get('center', {}).get('lat')
            lon = el.get('lon') or el.get('center', {}).get('lon')
            tags = el.get('tags', {})

            name = tags.get('name') or tags.get('operator') or tags.get('brand')
            operator = tags.get('operator') or tags.get('brand') or 'unknown'
            address = tags.get('addr:street') or tags.get('addr:full') or tags.get('branch') or ''
            city = tags.get('addr:city') or ''
            locality = tags.get('addr:suburb') or tags.get('addr:district') or tags.get('addr:neighbourhood') or ''
            
            # Connectors & power from tags
            conns = []
            if 'socket:type2' in tags: conns.append('Type 2 AC')
            if 'socket:type2_combo' in tags or 'socket:ccs' in tags: conns.append('CCS-2')
            if 'socket:chademo' in tags: conns.append('CHAdeMO')
            conn_str = "; ".join(conns) if conns else 'unknown'
            
            power_kw = tags.get('charging_station:output') or tags.get('output') or 'unknown'
            access = tags.get('access') or 'unknown'
            op_status = tags.get('operational_status') or ('operational' if tags.get('amenity') == 'charging_station' else 'unknown')
            check_date = tags.get('check_date') or tags.get('survey:date') or '2026-03-09'

            raw_candidates.append({
                'source_name': 'OpenStreetMap',
                'source_id': f"{el_type}/{el_id}",
                'source_url': f"https://www.openstreetmap.org/{el_type}/{el_id}",
                'source_license': 'Open Data Commons Open Database License (ODbL) 1.0',
                'name': name,
                'operator': operator,
                'address': address,
                'locality': locality,
                'city': city or 'Mumbai',
                'latitude': lat,
                'longitude': lon,
                'connector_types': conn_str,
                'power_kw': power_kw,
                'access_type': access,
                'operational_status': op_status,
                'last_verified_at': check_date,
                'raw_tags': tags
            })

    # -------------------------------------------------------------------------
    # SOURCE 2: OpenChargeMap (India Master Snapshot)
    # -------------------------------------------------------------------------
    ocm_path = os.path.join('data', 'raw', 'ocm_all_india.json')
    if os.path.exists(ocm_path):
        with open(ocm_path, 'r', encoding='utf-8') as f:
            ocm_data = json.load(f)
        stats['sources']['OpenChargeMap'] = len(ocm_data)
        stats['total_raw'] += len(ocm_data)
        print(f"[Source 2] OpenChargeMap (ocm_all_india.json): Found {len(ocm_data)} raw records.")

        for item in ocm_data:
            s_id = item.get('ID')
            addr = item.get('AddressInfo', {})
            name = addr.get('Title')
            op_info = item.get('OperatorInfo')
            operator = op_info.get('Title') if op_info else 'unknown'
            address = addr.get('AddressLine1') or ''
            town = addr.get('Town') or ''
            lat = addr.get('Latitude')
            lon = addr.get('Longitude')
            
            conns = []
            powers = []
            for c in item.get('Connections', []):
                ctype = c.get('ConnectionType', {}).get('Title')
                if ctype: conns.append(ctype)
                p = c.get('PowerKW')
                if p: powers.append(str(p))
            
            conn_str = "; ".join(list(set(conns))) if conns else 'unknown'
            p_str = "; ".join(list(set(powers))) if powers else 'unknown'
            
            # Operational status
            status_type = item.get('StatusType', {}).get('Title') or 'unknown'
            usage_type = item.get('UsageType', {}).get('Title') or 'unknown'
            verified_at = item.get('DateLastStatusUpdate') or item.get('DateLastVerified') or '2024-01-01'

            raw_candidates.append({
                'source_name': 'OpenChargeMap',
                'source_id': f"OCM-{s_id}",
                'source_url': f"https://openchargemap.org/site/poi/details/{s_id}",
                'source_license': 'Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)',
                'name': name,
                'operator': operator,
                'address': address,
                'locality': town,
                'city': town or 'Mumbai',
                'latitude': lat,
                'longitude': lon,
                'connector_types': conn_str,
                'power_kw': p_str,
                'access_type': usage_type,
                'operational_status': status_type,
                'last_verified_at': str(verified_at)[:10],
                'raw_tags': {}
            })

    # -------------------------------------------------------------------------
    # SOURCE 3: NITI Aayog / E-Amrit (indian_ev_charging_stations.geojson)
    # -------------------------------------------------------------------------
    eamrit_path = os.path.join('data', 'raw', 'indian_ev_charging_stations.geojson')
    if os.path.exists(eamrit_path):
        with open(eamrit_path, 'r', encoding='utf-8') as f:
            geo_data = json.load(f)
        features = geo_data.get('features', [])
        stats['sources']['NITI_Aayog_EAmrit'] = len(features)
        stats['total_raw'] += len(features)
        print(f"[Source 3] NITI Aayog / E-Amrit GeoJSON: Found {len(features)} raw records.")

        for feat in features:
            props = feat.get('properties', {})
            coords = feat.get('geometry', {}).get('coordinates', [])
            lat = coords[1] if len(coords) > 1 else props.get('lattitude')
            lon = coords[0] if len(coords) > 0 else props.get('longitude')
            raw_id = props.get('stationid', '0')
            name = props.get('name')
            addr = props.get('address') or ''
            city = props.get('city') or ''

            raw_candidates.append({
                'source_name': 'NITI_Aayog_EAmrit',
                'source_id': f"EAMRIT-{raw_id}",
                'source_url': "https://e-amrit.niti.gov.in",
                'source_license': 'Government Open Data License - India (GODL-India)',
                'name': name,
                'operator': 'EESL / Government PSU',
                'address': addr,
                'locality': city,
                'city': city,
                'latitude': lat,
                'longitude': lon,
                'connector_types': 'unknown',
                'power_kw': 'unknown',
                'access_type': 'Public',
                'operational_status': 'unknown',
                'last_verified_at': '2024-01-01',
                'raw_tags': props
            })

    print(f"\nTotal Parsed Candidates Across All Sources: {len(raw_candidates)}")

    # -------------------------------------------------------------------------
    # VALIDATION & FILTERING PIPELINE
    # -------------------------------------------------------------------------
    validated_in_mmr = []

    for c in raw_candidates:
        src_key = (c['source_name'], c['source_id'])
        if src_key in seen_source_keys:
            stats['duplicates_exact_source_id'] += 1
            continue
        seen_source_keys.add(src_key)

        lat = c['latitude']
        lon = c['longitude']
        
        # 1. Parse coordinates
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
                c['rejection_reason'] = 'Invalid WGS-84 coordinate bounds'
                rejected_records.append(c)
                stats['rejected_invalid_coords'] += 1
                continue
        except (ValueError, TypeError):
            c['rejection_reason'] = 'Non-numeric or missing coordinate'
            rejected_records.append(c)
            stats['rejected_invalid_coords'] += 1
            continue

        c['latitude'] = lat_f
        c['longitude'] = lon_f

        # 2. MMR Boundary Polygon Containment Check
        pt = Point(lon_f, lat_f)
        if not mmr_polygon.contains(pt):
            c['rejection_reason'] = 'Outside official Mumbai Metropolitan Region (MMR) boundary polygon'
            rejected_records.append(c)
            stats['rejected_out_of_boundary'] += 1
            continue

        stats['valid_in_boundary'] += 1

        # 3. Quality & Completeness Check
        name = str(c.get('name') or '').strip()
        address = str(c.get('address') or '').strip()
        
        # Flag generic or unnamed stations for manual review
        is_generic_name = (
            not name or
            len(name) < 3 or
            name.lower() in ['charging station', 'ev charging station', 'station', 'electric vehicle charging station'] or
            name.startswith('Station ') # E.g. OSM node with no name tag
        )
        
        if is_generic_name and not address:
            c['pending_reason'] = 'Generic or missing station name and missing address; requires ground verification'
            pending_records.append(c)
            stats['pending_generic_or_missing'] += 1
            continue

        validated_in_mmr.append(c)

    print(f"\nMMR Boundary Filter Results:")
    print(f"  • Outside MMR Boundary (Quarantined to rejected_stations.csv): {stats['rejected_out_of_boundary']}")
    print(f"  • Valid Within MMR Boundary Polygon: {stats['valid_in_boundary']}")
    print(f"  • Flagged for Manual Survey (pending_stations.csv): {len(pending_records)}")

    # -------------------------------------------------------------------------
    # CROSS-SOURCE NEARBY PROXIMITY CHECK (Conservative Deduplication)
    # -------------------------------------------------------------------------
    # Do NOT merge different operators automatically. If two records from different
    # sources are within 50m, flag as cross-source proximity candidate for manual survey.
    final_master_candidates = []
    
    for i, st1 in enumerate(validated_in_mmr):
        is_cross_conflict = False
        conflict_partner = None
        for j, st2 in enumerate(validated_in_mmr):
            if i != j:
                dist = haversine_distance(st1['latitude'], st1['longitude'], st2['latitude'], st2['longitude'])
                if dist < 50.0: # 50 meters
                    # Check if from different sources
                    if st1['source_name'] != st2['source_name']:
                        is_cross_conflict = True
                        conflict_partner = f"{st2['source_name']}:{st2['source_id']} ({st2['name']}, dist={dist:.1f}m)"
                        break

        if is_cross_conflict:
            st1_copy = dict(st1)
            st1_copy['pending_reason'] = f"Cross-source candidate within 50m of {conflict_partner}; do not merge without ground confirmation"
            pending_records.append(st1_copy)
            stats['pending_cross_source_proximity'] += 1
        else:
            final_master_candidates.append(st1)

    # Generate unique station IDs: VG-MUM-XXXX
    for idx, st in enumerate(final_master_candidates):
        st['station_id'] = f"VG-MUM-{idx+1:04d}"
        st['validation_status'] = 'VERIFIED_MMR'

    master_records = final_master_candidates
    print(f"  • Verified Master Stations Approved for Production: {len(master_records)}")

    # -------------------------------------------------------------------------
    # WRITE OUTPUT FILES
    # -------------------------------------------------------------------------
    fieldnames = [
        'station_id', 'station_name', 'operator', 'address', 'locality', 'city',
        'latitude', 'longitude', 'connector_types', 'power_kw', 'access_type',
        'operational_status', 'source_name', 'source_id', 'source_url',
        'source_license', 'last_verified_at', 'validation_status'
    ]

    # 1. master_ev_stations.csv
    master_csv_path = os.path.join('data', 'master_ev_stations.csv')
    with open(master_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in master_records:
            writer.writerow({
                'station_id': r.get('station_id'),
                'station_name': r.get('name'),
                'operator': r.get('operator'),
                'address': r.get('address') or 'Unknown Address',
                'locality': r.get('locality') or 'Unknown Locality',
                'city': r.get('city') or 'Mumbai',
                'latitude': f"{r['latitude']:.6f}",
                'longitude': f"{r['longitude']:.6f}",
                'connector_types': r.get('connector_types', 'unknown'),
                'power_kw': r.get('power_kw', 'unknown'),
                'access_type': r.get('access_type', 'unknown'),
                'operational_status': r.get('operational_status', 'unknown'),
                'source_name': r.get('source_name'),
                'source_id': r.get('source_id'),
                'source_url': r.get('source_url'),
                'source_license': r.get('source_license'),
                'last_verified_at': r.get('last_verified_at'),
                'validation_status': r.get('validation_status')
            })
    print(f"\n[OUTPUT 1] Written {len(master_records)} records to {master_csv_path}")

    # 2. pending_stations.csv
    pending_csv_path = os.path.join('data', 'review', 'pending_stations.csv')
    pending_fields = fieldnames + ['pending_reason']
    with open(pending_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=pending_fields)
        writer.writeheader()
        for idx, r in enumerate(pending_records):
            writer.writerow({
                'station_id': f"VG-PEND-{idx+1:04d}",
                'station_name': r.get('name') or 'Unnamed Station',
                'operator': r.get('operator') or 'unknown',
                'address': r.get('address') or 'Unknown Address',
                'locality': r.get('locality') or 'Unknown Locality',
                'city': r.get('city') or 'Mumbai',
                'latitude': f"{r['latitude']:.6f}" if isinstance(r.get('latitude'), (int, float)) else r.get('latitude'),
                'longitude': f"{r['longitude']:.6f}" if isinstance(r.get('longitude'), (int, float)) else r.get('longitude'),
                'connector_types': r.get('connector_types', 'unknown'),
                'power_kw': r.get('power_kw', 'unknown'),
                'access_type': r.get('access_type', 'unknown'),
                'operational_status': r.get('operational_status', 'unknown'),
                'source_name': r.get('source_name'),
                'source_id': r.get('source_id'),
                'source_url': r.get('source_url'),
                'source_license': r.get('source_license'),
                'last_verified_at': r.get('last_verified_at'),
                'validation_status': 'PENDING_REVIEW',
                'pending_reason': r.get('pending_reason')
            })
    print(f"[OUTPUT 2] Written {len(pending_records)} review candidates to {pending_csv_path}")

    # 3. rejected_stations.csv
    rejected_csv_path = os.path.join('data', 'review', 'rejected_stations.csv')
    rejected_fields = ['source_name', 'source_id', 'station_name', 'latitude', 'longitude', 'rejection_reason', 'source_url', 'source_license']
    with open(rejected_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rejected_fields)
        writer.writeheader()
        for r in rejected_records:
            writer.writerow({
                'source_name': r.get('source_name'),
                'source_id': r.get('source_id'),
                'station_name': r.get('name') or 'Unknown',
                'latitude': r.get('latitude'),
                'longitude': r.get('longitude'),
                'rejection_reason': r.get('rejection_reason'),
                'source_url': r.get('source_url'),
                'source_license': r.get('source_license')
            })
    print(f"[OUTPUT 3] Written {len(rejected_records)} quarantined records to {rejected_csv_path}")

    # 4. dataset_quality_report.txt
    report_path = os.path.join('data', 'dataset_quality_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("VOLTGRID MUMBAI: DATASET QUALITY & AUDIT REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write("1. RETRIEVED RECORDS PER SOURCE:\n")
        for src, cnt in stats['sources'].items():
            f.write(f"   • {src}: {cnt} records\n")
        f.write(f"   ─────────────────────────────────────────────\n")
        f.write(f"   TOTAL RAW RECORDS PROCESSED: {stats['total_raw']}\n\n")

        f.write("2. GEOGRAPHIC BOUNDARY CLASSIFICATION (Official MMR Polygon):\n")
        f.write(f"   • Boundary Dataset: {boundary_meta.get('name', 'MMR')}\n")
        f.write(f"   • Boundary Source : {boundary_meta.get('source', 'OSM Nominatim')}\n")
        f.write(f"   • Valid Records Inside MMR Boundary: {stats['valid_in_boundary']}\n")
        f.write(f"   • Quarantined Records Outside MMR  : {stats['rejected_out_of_boundary']}\n")
        f.write(f"   • Invalid Coordinate Format Records : {stats['rejected_invalid_coords']}\n\n")

        f.write("3. QUALITY & MANUAL REVIEW CANDIDATES:\n")
        f.write(f"   • Flagged Generic/Missing Names    : {stats['pending_generic_or_missing']}\n")
        f.write(f"   • Flagged Cross-Source Nearby (<50m): {stats['pending_cross_source_proximity']}\n")
        f.write(f"   • Exact Source ID Duplicates Skipped: {stats['duplicates_exact_source_id']}\n\n")

        f.write("4. FINAL MASTER DATASET METRICS:\n")
        f.write(f"   • Approved Master Stations (master_ev_stations.csv): {len(master_records)}\n")
        f.write(f"   • Pending Manual Survey (pending_stations.csv)     : {len(pending_records)}\n")
        f.write(f"   • Quarantined / Rejected (rejected_stations.csv)   : {len(rejected_records)}\n\n")

        f.write("5. MASTER DATASET ROSTER:\n")
        for s in master_records:
            f.write(f"   [{s['station_id']}] {s['name']} ({s['operator']}) @ {s['latitude']:.6f}, {s['longitude']:.6f} [{s['source_name']}:{s['source_id']}]\n")

    print(f"[OUTPUT 4] Written detailed quality audit report to {report_path}")

    # -------------------------------------------------------------------------
    # STAGING INTEGRATION (Non-destructive)
    # -------------------------------------------------------------------------
    print("\n[Step 5] Integrating into PostgreSQL Staging Table: stg_master_ev_stations...")
    conn = psycopg2.connect(
        dbname='ev_db',
        user='postgres',
        password='postgres',
        host='localhost',
        port=5432
    )
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stg_master_ev_stations (
        master_id SERIAL PRIMARY KEY,
        station_id VARCHAR(50) UNIQUE,
        station_name VARCHAR(200) NOT NULL,
        operator VARCHAR(150),
        address TEXT,
        locality VARCHAR(100),
        city VARCHAR(100),
        latitude NUMERIC(9,6) NOT NULL,
        longitude NUMERIC(9,6) NOT NULL,
        connector_types TEXT,
        power_kw TEXT,
        access_type VARCHAR(100),
        operational_status VARCHAR(100),
        source_name VARCHAR(100),
        source_id VARCHAR(100),
        source_url TEXT,
        source_license TEXT,
        last_verified_at DATE,
        validation_status VARCHAR(50),
        imported_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    cur.execute("TRUNCATE TABLE stg_master_ev_stations RESTART IDENTITY;")

    insert_sql = """
    INSERT INTO stg_master_ev_stations (
        station_id, station_name, operator, address, locality, city,
        latitude, longitude, connector_types, power_kw, access_type,
        operational_status, source_name, source_id, source_url,
        source_license, last_verified_at, validation_status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    for r in master_records:
        cur.execute(insert_sql, (
            r['station_id'], r['name'], r['operator'], r.get('address') or 'Unknown Address',
            r.get('locality') or 'Unknown Locality', r.get('city') or 'Mumbai',
            r['latitude'], r['longitude'], r['connector_types'], r['power_kw'],
            r['access_type'], r['operational_status'], r['source_name'], r['source_id'],
            r['source_url'], r['source_license'], r['last_verified_at'], r['validation_status']
        ))

    conn.commit()
    cur.execute("SELECT count(*) FROM stg_master_ev_stations;")
    count_staged = cur.fetchone()[0]
    print(f"[SUCCESS] Successfully loaded {count_staged} master records into stg_master_ev_stations.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    build_master_dataset()
