"""
VoltGrid National Master EV Charging Stations Dataset Pipeline
==============================================================
Builds a reliable, deduplicated National EV Charging Station dataset
with precise point-in-polygon classification against the official
Mumbai Metropolitan Region (MMR) boundary (data/mmr_boundary.geojson).

Sources:
1. OpenStreetMap (OSM) via Overpass API (data/raw/osm_mmr_overpass_raw.json)
2. OpenChargeMap (OCM) All-India Registry (data/raw/ocm_all_india.json)
3. NITI Aayog / E-Amrit Government Dataset (data/raw/indian_ev_charging_stations.geojson)
4. Bureau of Energy Efficiency (BEE), Ministry of Power official public dataset
   (data/raw/bee_india_ev_charging_stations.json)

Outputs:
- data/national_master_ev_stations.csv (National dataset with is_inside_mmr)
- data/master_ev_stations.csv (MMR-filtered view for production staging)
- data/review/pending_stations.csv (Records pending ground survey or cross-source review)
- data/review/rejected_stations.csv (Records with invalid coordinates or critical defects)
- Loads stg_national_master_ev_stations in PostgreSQL safely without altering production tables.
"""
import os
import csv
import json
import math
import time
from datetime import datetime
from collections import defaultdict, Counter
import psycopg2
import psycopg2.extras
from shapely.geometry import shape, Point

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000.0 # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def load_mmr_boundary():
    b_path = os.path.join('data', 'mmr_boundary.geojson')
    with open(b_path, 'r', encoding='utf-8') as f:
        b_data = json.load(f)
    polygon = shape(b_data['features'][0]['geometry'])
    metadata = b_data.get('metadata', {})
    return polygon, metadata

def classify_mmr_subregion(lat, lon, text=""):
    text = text.lower()
    
    # 1. Municipal/locality keyword overrides
    if any(k in text for k in ['navi mumbai', 'nerul', 'vashi', 'turbhe', 'belapur', 'airoli', 'koparkhairane', 'kopar khairane', 'ghansoli', 'sanpada', 'kharghar', 'cbd belapur', 'juinagar', 'seawoods', 'mahape']):
        return 'Navi Mumbai'
    if any(k in text for k in ['panvel', 'kamothe', 'kalamboli', 'khandeshwar', 'taloja', 'rasayani', 'mohopada', 'karanjade', 'dronagiri']):
        return 'Panvel'
    if any(k in text for k in ['kalyan', 'dombivli', 'dombivali', 'titwala', 'khadakpada', 'patharli']):
        return 'Kalyan-Dombivli'
    if any(k in text for k in ['mira road', 'bhayandar', 'bhayander', 'mira-bhayandar', 'mira bhayandar']):
        return 'Mira-Bhayandar'
    if any(k in text for k in ['vasai', 'virar', 'nalasopara', 'naigaon']):
        return 'Vasai-Virar'
    if any(k in text for k in ['ulhasnagar', 'ambernath', 'ambarnath', 'badlapur']):
        return 'Ulhasnagar / Ambernath'
    if 'bhiwandi' in text:
        return 'Bhiwandi-Nizampur'
    if any(k in text for k in ['alibag', 'alibaug', 'pen', 'uran', 'karjat', 'khalapur', 'khopoli', 'raigad', 'matheran']):
        return 'Raigad / South MMR'
    if any(k in text for k in ['thane', 'majiwada', 'ghodbunder', 'wagle', 'naupada', 'kopri', 'hiranandani estate']):
        return 'Thane'
    if any(k in text for k in ['colaba', 'nariman', 'fort', 'cuffe', 'marine drive', 'byculla', 'worli', 'dadar', 'parel', 'lower parel', 'tardeo', 'mahalaxmi', 'malabar hill', 'churchgate', 'grant road', 'girgaon', 'mazgaon', 'wadala', 'sewri', 'sion', 'prabhadevi', 'kemps corner', 'pedder road', 'breach candy', 'walkeshwar']):
        return 'Mumbai City'
    if any(k in text for k in ['andheri', 'bandra', 'borivali', 'goregaon', 'malad', 'juhu', 'kandivali', 'kurla', 'ghatkopar', 'vikhroli', 'mulund', 'bkc', 'santacruz', 'vile parle', 'dahisar', 'chembur', 'powai', 'sakinaka', 'marol', 'bhandup', 'mankhurd', 'govandi', 'jogeshwari', 'mumbai suburban']):
        return 'Mumbai Suburban'
        
    # Spatial bounding fallback
    if lat < 18.92 and lon < 73.10:
        return 'Raigad / South MMR'
    if lat < 19.03 and lon < 72.88:
        return 'Mumbai City'
    if 19.33 <= lat <= 19.55 and lon <= 72.93:
        return 'Vasai-Virar'
    if 19.26 <= lat <= 19.34 and 72.80 <= lon <= 72.89:
        return 'Mira-Bhayandar'
    if 19.00 <= lat <= 19.27 and 72.78 <= lon <= 72.94:
        return 'Mumbai Suburban'
    if 19.16 <= lat <= 19.35 and 72.94 <= lon <= 73.06:
        return 'Thane'
    if 18.98 <= lat <= 19.18 and 72.98 <= lon <= 73.10:
        return 'Navi Mumbai'
    if 18.90 <= lat <= 19.08 and 73.08 <= lon <= 73.22:
        return 'Panvel'
    if 19.18 <= lat <= 19.32 and 73.08 <= lon <= 73.25:
        return 'Kalyan-Dombivli'
    if 19.25 <= lat <= 19.40 and 73.02 <= lon <= 73.15:
        return 'Bhiwandi-Nizampur'
    if 19.12 <= lat <= 19.24 and 73.12 <= lon <= 73.30:
        return 'Ulhasnagar / Ambernath'
        
    return 'Other MMR Area'

def build_national_master_dataset():
    t0 = time.time()
    print("=" * 80)
    print("VOLTGRID MUMBAI: NATIONAL MASTER EV CHARGING DATASET PIPELINE")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    mmr_polygon, boundary_meta = load_mmr_boundary()
    print(f"Loaded MMR Polygon: {boundary_meta.get('name', 'Mumbai Metropolitan Region')}")
    print(f"Polygon Bounding Box: {mmr_polygon.bounds}\n")

    os.makedirs('data/review', exist_ok=True)
    os.makedirs('data/raw', exist_ok=True)
    os.makedirs('data/reports', exist_ok=True)

    stats = {
        'sources': Counter(),
        'total_raw': 0,
        'exact_id_duplicates': 0,
        'invalid_coords': 0,
        'raw_inside_mmr': 0,
        'raw_outside_mmr': 0,
        'pending_generic_or_unnamed': 0,
        'pending_cross_source_proximity': 0,
        'valid_national_total': 0,
        'valid_mmr_total': 0,
        'valid_outside_mmr_total': 0,
        'pending_total': 0,
        'pending_inside_mmr': 0,
        'pending_outside_mmr': 0,
        'rejected_total': 0
    }

    raw_candidates = []
    seen_source_keys = set()
    rejected_records = []
    pending_records = []

    # -------------------------------------------------------------------------
    # 1. PARSE OPENSTREETMAP OVERPASS EXTRACT
    # -------------------------------------------------------------------------
    osm_path = os.path.join('data', 'raw', 'osm_mmr_overpass_raw.json')
    if os.path.exists(osm_path):
        with open(osm_path, 'r', encoding='utf-8') as f:
            osm_data = json.load(f)
        elements = osm_data.get('elements', [])
        stats['sources']['OpenStreetMap'] = len(elements)
        stats['total_raw'] += len(elements)
        print(f"[Source 1] OpenStreetMap: {len(elements)} raw features.")

        for el in elements:
            el_type = el.get('type')
            el_id = el.get('id')
            lat = el.get('lat') or el.get('center', {}).get('lat')
            lon = el.get('lon') or el.get('center', {}).get('lon')
            tags = el.get('tags', {})

            name = tags.get('name') or tags.get('operator') or tags.get('brand')
            operator = tags.get('operator') or tags.get('brand') or 'unknown'
            address = tags.get('addr:street') or tags.get('addr:full') or tags.get('branch') or 'unknown'
            city = tags.get('addr:city') or 'Mumbai'
            locality = tags.get('addr:suburb') or tags.get('addr:district') or tags.get('addr:neighbourhood') or 'unknown'

            conns = []
            if 'socket:type2' in tags: conns.append('Type 2 AC')
            if 'socket:type2_combo' in tags or 'socket:ccs' in tags: conns.append('CCS-2')
            if 'socket:chademo' in tags: conns.append('CHAdeMO')
            conn_str = "; ".join(conns) if conns else 'unknown'

            power_kw = tags.get('charging_station:output') or tags.get('output') or 'unknown'
            access = tags.get('access') or 'unknown'
            op_status = tags.get('operational_status') or ('operational' if tags.get('amenity') == 'charging_station' else 'unknown')
            cap = int(tags.get('capacity')) if str(tags.get('capacity', '')).isdigit() else 1

            raw_candidates.append({
                'source_name': 'OpenStreetMap',
                'source_id': f"{el_type}/{el_id}",
                'source_url': f"https://www.openstreetmap.org/{el_type}/{el_id}",
                'source_license': 'Open Data Commons Open Database License (ODbL) 1.0',
                'station_name': name,
                'operator': operator,
                'address': address,
                'locality': locality,
                'city': city,
                'state': 'Maharashtra',
                'latitude': lat,
                'longitude': lon,
                'connector_types': conn_str,
                'power_kw': power_kw,
                'access_type': access,
                'operational_status': op_status,
                'chargers': cap,
                'connectors': cap
            })

    # -------------------------------------------------------------------------
    # 2. PARSE OPENCHARGEMAP ALL-INDIA SNAPSHOT
    # -------------------------------------------------------------------------
    ocm_path = os.path.join('data', 'raw', 'ocm_all_india.json')
    if os.path.exists(ocm_path):
        with open(ocm_path, 'r', encoding='utf-8') as f:
            ocm_data = json.load(f)
        stats['sources']['OpenChargeMap'] = len(ocm_data)
        stats['total_raw'] += len(ocm_data)
        print(f"[Source 2] OpenChargeMap: {len(ocm_data)} raw records.")

        for item in ocm_data:
            s_id = item.get('ID')
            addr = item.get('AddressInfo', {})
            name = addr.get('Title')
            op_info = item.get('OperatorInfo')
            operator = op_info.get('Title') if op_info else 'unknown'
            address = addr.get('AddressLine1') or 'unknown'
            locality = addr.get('AddressLine2') or addr.get('Town') or 'unknown'
            city = addr.get('Town') or addr.get('City') or 'unknown'
            state = addr.get('StateOrProvince') or 'unknown'
            if isinstance(state, str):
                state = state.strip()

            lat = addr.get('Latitude')
            lon = addr.get('Longitude')

            conns = []
            powers = []
            for c in item.get('Connections', []):
                ctype = c.get('ConnectionType', {}).get('Title')
                if ctype: conns.append(ctype)
                p = c.get('PowerKW')
                if p: powers.append(str(p))

            conn_str = "; ".join(sorted(list(set(conns)))) if conns else 'unknown'
            p_str = "; ".join(sorted(list(set(powers)))) if powers else 'unknown'
            status_type = item.get('StatusType', {}).get('Title') or 'unknown'
            usage_type = item.get('UsageType', {}).get('Title') or 'unknown'
            pts = item.get('NumberOfPoints') or len(conns) or 1

            raw_candidates.append({
                'source_name': 'OpenChargeMap',
                'source_id': f"OCM-{s_id}",
                'source_url': f"https://openchargemap.org/site/poi/details/{s_id}",
                'source_license': 'Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)',
                'station_name': name,
                'operator': operator,
                'address': address,
                'locality': locality,
                'city': city,
                'state': state,
                'latitude': lat,
                'longitude': lon,
                'connector_types': conn_str,
                'power_kw': p_str,
                'access_type': usage_type,
                'operational_status': status_type,
                'chargers': pts,
                'connectors': len(conns) if conns else pts
            })

    # -------------------------------------------------------------------------
    # 3. PARSE NITI AAYOG / E-AMRIT GEOJSON
    # -------------------------------------------------------------------------
    eamrit_path = os.path.join('data', 'raw', 'indian_ev_charging_stations.geojson')
    if os.path.exists(eamrit_path):
        with open(eamrit_path, 'r', encoding='utf-8') as f:
            eamrit_data = json.load(f)
        features = eamrit_data.get('features', [])
        stats['sources']['NITI_Aayog_EAmrit'] = len(features)
        stats['total_raw'] += len(features)
        print(f"[Source 3] NITI Aayog / E-Amrit: {len(features)} raw features.")

        for feat in features:
            props = feat.get('properties', {})
            coords = feat.get('geometry', {}).get('coordinates', [])
            lat = coords[1] if len(coords) > 1 else props.get('lattitude')
            lon = coords[0] if len(coords) > 0 else props.get('longitude')
            raw_id = props.get('stationid', '0')
            name = props.get('name') or 'unknown'
            addr = props.get('address') or 'unknown'
            city = props.get('city') or 'unknown'
            st = props.get('state') or 'unknown'

            raw_candidates.append({
                'source_name': 'NITI_Aayog_EAmrit',
                'source_id': f"EAMRIT-{raw_id}",
                'source_url': "https://e-amrit.niti.gov.in",
                'source_license': 'Government Open Data License - India (GODL-India)',
                'station_name': name,
                'operator': 'EESL / Government PSU',
                'address': addr,
                'locality': city,
                'city': city,
                'state': st,
                'latitude': lat,
                'longitude': lon,
                'connector_types': 'unknown',
                'power_kw': 'unknown',
                'access_type': 'Public',
                'operational_status': 'unknown',
                'chargers': 1,
                'connectors': 1
            })

    # -------------------------------------------------------------------------
    # 4. PARSE BUREAU OF ENERGY EFFICIENCY (BEE) OFFICIAL DATASET
    # -------------------------------------------------------------------------
    bee_path = os.path.join('data', 'raw', 'bee_india_ev_charging_stations.json')
    if os.path.exists(bee_path):
        with open(bee_path, 'r', encoding='utf-8') as f:
            bee_data = json.load(f)
        stats['sources']['Bureau_of_Energy_Efficiency_BEE'] = len(bee_data)
        stats['total_raw'] += len(bee_data)
        print(f"[Source 4] Bureau of Energy Efficiency (BEE): {len(bee_data)} raw records.")

        for s in bee_data:
            s_id = s.get('id')
            op = s.get('operator') or 'unknown'
            addr = s.get('address') or 'unknown'
            dist = s.get('district') or s.get('city') or 'unknown'
            city = s.get('city') or 'unknown'
            st = s.get('state') or 'Maharashtra'
            lat = s.get('latitude')
            lon = s.get('longitude')
            stds = s.get('standards', [])
            conn_str = "; ".join(stds) if stds else 'unknown'
            p_kw = str(s.get('max_power_kw')) if s.get('max_power_kw') is not None else 'unknown'
            tot_chargers = s.get('total_chargers', 1) or 1
            tot_conns = s.get('total_connectors', 1) or 1
            
            addr_parts = addr.split(',')
            name = addr_parts[0].strip() if addr_parts and len(addr_parts[0].strip()) > 2 else f"{op} Charging Station"

            raw_candidates.append({
                'source_name': 'Bureau_of_Energy_Efficiency_BEE',
                'source_id': f"BEE-{s_id}",
                'source_url': "http://beeindia.gov.in/WriteReadData/RTF1984/EV_PCS_Data_29277.pdf",
                'source_license': 'Government of India Public EVCI Records (GODL-India / Fair Use Attribution)',
                'station_name': name,
                'operator': op,
                'address': addr,
                'locality': dist,
                'city': city,
                'state': st,
                'latitude': lat,
                'longitude': lon,
                'connector_types': conn_str,
                'power_kw': p_kw,
                'access_type': 'Public',
                'operational_status': 'unknown',
                'chargers': tot_chargers,
                'connectors': tot_conns
            })

    print(f"\nTotal Parsed Candidates: {len(raw_candidates):,}")

    # -------------------------------------------------------------------------
    # 5. COORDINATE & ATTRIBUTE VALIDATION + EXACT ID DEDUPLICATION
    # -------------------------------------------------------------------------
    valid_coords_candidates = []

    for c in raw_candidates:
        src_key = (c['source_name'], c['source_id'])
        if src_key in seen_source_keys:
            stats['exact_id_duplicates'] += 1
            continue
        seen_source_keys.add(src_key)

        lat = c['latitude']
        lon = c['longitude']
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
                c['rejection_reason'] = f"Coordinates out of WGS-84 bounds ({lat}, {lon})"
                rejected_records.append(c)
                stats['invalid_coords'] += 1
                continue
            if lat_f == 0.0 and lon_f == 0.0:
                c['rejection_reason'] = "Coordinates are (0.0, 0.0) null island"
                rejected_records.append(c)
                stats['invalid_coords'] += 1
                continue
        except (ValueError, TypeError):
            c['rejection_reason'] = f"Non-numeric coordinate: lat={lat}, lon={lon}"
            rejected_records.append(c)
            stats['invalid_coords'] += 1
            continue

        c['latitude'] = lat_f
        c['longitude'] = lon_f

        # ---------------------------------------------------------------------
        # POINT-IN-POLYGON MMR BOUNDARY CLASSIFICATION
        # ---------------------------------------------------------------------
        pt = Point(lon_f, lat_f)
        is_in_mmr = mmr_polygon.contains(pt)
        c['is_inside_mmr'] = is_in_mmr

        if is_in_mmr:
            stats['raw_inside_mmr'] += 1
        else:
            stats['raw_outside_mmr'] += 1

        # ---------------------------------------------------------------------
        # INCOMPLETE / GENERIC IDENTIFIER SCREENING
        # ---------------------------------------------------------------------
        name = str(c.get('station_name') or '').strip()
        address = str(c.get('address') or '').strip()

        is_generic_name = (
            not name or
            len(name) < 3 or
            name.lower() in ['charging station', 'ev charging station', 'station', 'electric vehicle charging station', 'unknown'] or
            name.startswith('Station ')
        )

        if is_generic_name and (not address or address == 'unknown'):
            c_copy = dict(c)
            c_copy['pending_reason'] = "Generic or missing station name and missing address; requires ground verification"
            c_copy['validation_status'] = 'PENDING_REVIEW'
            pending_records.append(c_copy)
            stats['pending_generic_or_unnamed'] += 1
            continue

        valid_coords_candidates.append(c)

    print(f"\nValidation Screening:")
    print(f"  • Valid Coordinates: {len(valid_coords_candidates):,}")
    print(f"  • Rejected Invalid Coordinates: {len(rejected_records)}")
    print(f"  • Flagged Generic / Incomplete: {stats['pending_generic_or_unnamed']}")
    print(f"  • Candidates Inside MMR Polygon: {stats['raw_inside_mmr']:,}")
    print(f"  • Candidates Outside MMR: {stats['raw_outside_mmr']:,}")

    # -------------------------------------------------------------------------
    # 6. CROSS-SOURCE PROXIMITY CHECK (<50m Conservative Flagging)
    # -------------------------------------------------------------------------
    grid = defaultdict(list)
    for idx, c in enumerate(valid_coords_candidates):
        grid[(int(c['latitude'] * 100), int(c['longitude'] * 100))].append(idx)

    proximity_conflicts = set()
    conflict_map = {}

    for (gx, gy), indices in grid.items():
        neighbor_indices = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbor_indices.extend(grid.get((gx + dx, gy + dy), []))

        for i in indices:
            c1 = valid_coords_candidates[i]
            for j in neighbor_indices:
                if i < j:
                    c2 = valid_coords_candidates[j]
                    if c1['source_name'] != c2['source_name']:
                        dist = haversine_distance(c1['latitude'], c1['longitude'], c2['latitude'], c2['longitude'])
                        if dist < 50.0:
                            proximity_conflicts.add(i)
                            proximity_conflicts.add(j)
                            conflict_map[i] = f"{c2['source_name']}:{c2['source_id']} ({c2['station_name']}, dist={dist:.1f}m)"
                            conflict_map[j] = f"{c1['source_name']}:{c1['source_id']} ({c1['station_name']}, dist={dist:.1f}m)"

    print(f"\nCross-Source Proximity (<50m):")
    print(f"  • Records Flagged for Review: {len(proximity_conflicts):,}")

    final_valid_records = []
    for idx, c in enumerate(valid_coords_candidates):
        if idx in proximity_conflicts:
            c_copy = dict(c)
            partner = conflict_map.get(idx, 'nearby cross-source record')
            c_copy['pending_reason'] = f"Cross-source candidate within 50m of {partner}; flagged for manual review without automatic merge"
            c_copy['validation_status'] = 'PENDING_REVIEW'
            pending_records.append(c_copy)
            stats['pending_cross_source_proximity'] += 1
        else:
            if c['is_inside_mmr']:
                c['validation_status'] = 'VERIFIED_MMR'
            else:
                c['validation_status'] = 'VERIFIED_NATIONAL'
            final_valid_records.append(c)

    # -------------------------------------------------------------------------
    # 7. ASSIGN STABLE UNIQUE STATION IDS
    # -------------------------------------------------------------------------
    mmr_valid = [r for r in final_valid_records if r['is_inside_mmr']]
    national_outside_mmr = [r for r in final_valid_records if not r['is_inside_mmr']]

    # MMR stations receive VG-MUM-XXXX
    for idx, st in enumerate(mmr_valid):
        st['station_id'] = f"VG-MUM-{idx+1:04d}"

    # All-India non-MMR stations receive VG-IND-XXXXX
    for idx, st in enumerate(national_outside_mmr):
        st['station_id'] = f"VG-IND-{idx+1:05d}"

    for idx, st in enumerate(pending_records):
        st['station_id'] = f"VG-PEND-{idx+1:05d}"

    stats['valid_national_total'] = len(final_valid_records)
    stats['valid_mmr_total'] = len(mmr_valid)
    stats['valid_outside_mmr_total'] = len(national_outside_mmr)
    stats['pending_total'] = len(pending_records)
    stats['pending_inside_mmr'] = sum(1 for r in pending_records if r.get('is_inside_mmr'))
    stats['pending_outside_mmr'] = stats['pending_total'] - stats['pending_inside_mmr']
    stats['rejected_total'] = len(rejected_records)

    print(f"\nFinal Deduplicated & Validated Counts:")
    print(f"  • Total Valid National Master Stations: {stats['valid_national_total']:,}")
    print(f"  • Unique Valid Inside MMR Boundary    : {stats['valid_mmr_total']:,}")
    print(f"  • Unique Valid Outside MMR (All-India): {stats['valid_outside_mmr_total']:,}")
    print(f"  • Total Pending Review Candidates     : {stats['pending_total']:,} ({stats['pending_inside_mmr']} inside MMR)")
    print(f"  • Total Rejected Invalid Records      : {stats['rejected_total']}")

    # -------------------------------------------------------------------------
    # 8. WRITE CSV ARTIFACTS
    # -------------------------------------------------------------------------
    national_fieldnames = [
        'station_id', 'station_name', 'operator', 'address', 'locality', 'city', 'state',
        'latitude', 'longitude', 'connector_types', 'power_kw', 'access_type',
        'operational_status', 'source_name', 'source_id', 'source_url', 'source_license',
        'is_inside_mmr', 'validation_status'
    ]

    # A. National Master CSV
    national_csv_path = os.path.join('data', 'national_master_ev_stations.csv')
    with open(national_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=national_fieldnames)
        writer.writeheader()
        for r in final_valid_records:
            writer.writerow({
                'station_id': r['station_id'],
                'station_name': r['station_name'],
                'operator': r['operator'],
                'address': r['address'],
                'locality': r['locality'],
                'city': r['city'],
                'state': r['state'],
                'latitude': f"{r['latitude']:.6f}",
                'longitude': f"{r['longitude']:.6f}",
                'connector_types': r['connector_types'],
                'power_kw': r['power_kw'],
                'access_type': r['access_type'],
                'operational_status': r['operational_status'],
                'source_name': r['source_name'],
                'source_id': r['source_id'],
                'source_url': r['source_url'],
                'source_license': r['source_license'],
                'is_inside_mmr': 'TRUE' if r['is_inside_mmr'] else 'FALSE',
                'validation_status': r['validation_status']
            })
    print(f"\n[Artifact 1] Written {len(final_valid_records):,} rows to {national_csv_path}")

    # B. MMR-Filtered Master CSV
    mmr_csv_path = os.path.join('data', 'master_ev_stations.csv')
    with open(mmr_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=national_fieldnames)
        writer.writeheader()
        for r in mmr_valid:
            writer.writerow({
                'station_id': r['station_id'],
                'station_name': r['station_name'],
                'operator': r['operator'],
                'address': r['address'],
                'locality': r['locality'],
                'city': r['city'],
                'state': r['state'],
                'latitude': f"{r['latitude']:.6f}",
                'longitude': f"{r['longitude']:.6f}",
                'connector_types': r['connector_types'],
                'power_kw': r['power_kw'],
                'access_type': r['access_type'],
                'operational_status': r['operational_status'],
                'source_name': r['source_name'],
                'source_id': r['source_id'],
                'source_url': r['source_url'],
                'source_license': r['source_license'],
                'is_inside_mmr': 'TRUE',
                'validation_status': r['validation_status']
            })
    print(f"[Artifact 2] Written {len(mmr_valid):,} MMR rows to {mmr_csv_path}")

    # C. Pending Stations CSV
    pending_csv_path = os.path.join('data', 'review', 'pending_stations.csv')
    pending_fields = national_fieldnames + ['pending_reason']
    with open(pending_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=pending_fields)
        writer.writeheader()
        for r in pending_records:
            writer.writerow({
                'station_id': r['station_id'],
                'station_name': r['station_name'],
                'operator': r['operator'],
                'address': r['address'],
                'locality': r['locality'],
                'city': r['city'],
                'state': r['state'],
                'latitude': f"{r['latitude']:.6f}",
                'longitude': f"{r['longitude']:.6f}",
                'connector_types': r['connector_types'],
                'power_kw': r['power_kw'],
                'access_type': r['access_type'],
                'operational_status': r['operational_status'],
                'source_name': r['source_name'],
                'source_id': r['source_id'],
                'source_url': r['source_url'],
                'source_license': r['source_license'],
                'is_inside_mmr': 'TRUE' if r['is_inside_mmr'] else 'FALSE',
                'validation_status': 'PENDING_REVIEW',
                'pending_reason': r['pending_reason']
            })
    print(f"[Artifact 3] Written {len(pending_records):,} pending review rows to {pending_csv_path}")

    # D. Rejected Stations CSV
    rejected_csv_path = os.path.join('data', 'review', 'rejected_stations.csv')
    rejected_fields = ['source_name', 'source_id', 'station_name', 'latitude', 'longitude', 'rejection_reason', 'source_url', 'source_license']
    with open(rejected_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rejected_fields)
        writer.writeheader()
        for r in rejected_records:
            writer.writerow({
                'source_name': r.get('source_name'),
                'source_id': r.get('source_id'),
                'station_name': r.get('station_name') or 'Unknown',
                'latitude': r.get('latitude'),
                'longitude': r.get('longitude'),
                'rejection_reason': r.get('rejection_reason'),
                'source_url': r.get('source_url'),
                'source_license': r.get('source_license')
            })
    print(f"[Artifact 4] Written {len(rejected_records)} rejected rows to {rejected_csv_path}")

    # -------------------------------------------------------------------------
    # 9. SAFE POSTGRESQL STAGING INGESTION (stg_national_master_ev_stations)
    # -------------------------------------------------------------------------
    try:
        conn = psycopg2.connect(dbname='ev_db', user='postgres', password='postgres', host='localhost', port=5432)
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS stg_national_master_ev_stations (
            station_id VARCHAR(50) PRIMARY KEY,
            station_name TEXT NOT NULL,
            operator TEXT,
            address TEXT,
            locality TEXT,
            city TEXT,
            state TEXT,
            latitude NUMERIC(10, 6) NOT NULL,
            longitude NUMERIC(10, 6) NOT NULL,
            connector_types TEXT,
            power_kw TEXT,
            access_type TEXT,
            operational_status TEXT,
            source_name TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_url TEXT,
            source_license TEXT,
            is_inside_mmr BOOLEAN NOT NULL DEFAULT FALSE,
            validation_status VARCHAR(50) NOT NULL DEFAULT 'PENDING_REVIEW',
            staged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Truncate and batch load staging
        cur.execute("TRUNCATE TABLE stg_national_master_ev_stations;")

        insert_sql = """
        INSERT INTO stg_national_master_ev_stations (
            station_id, station_name, operator, address, locality, city, state,
            latitude, longitude, connector_types, power_kw, access_type,
            operational_status, source_name, source_id, source_url, source_license,
            is_inside_mmr, validation_status
        ) VALUES %s;
        """

        records_to_insert = [
            (
                r['station_id'], r['station_name'], r['operator'], r['address'],
                r['locality'], r['city'], r['state'], r['latitude'], r['longitude'],
                r['connector_types'], r['power_kw'], r['access_type'], r['operational_status'],
                r['source_name'], r['source_id'], r['source_url'], r['source_license'],
                r['is_inside_mmr'], r['validation_status']
            )
            for r in final_valid_records
        ]

        psycopg2.extras.execute_values(cur, insert_sql, records_to_insert, page_size=2000)

        conn.commit()
        cur.execute("SELECT count(*) FROM stg_national_master_ev_stations;")
        stg_cnt = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM stg_national_master_ev_stations WHERE is_inside_mmr = TRUE;")
        stg_mmr_cnt = cur.fetchone()[0]
        print(f"\n[PostgreSQL Staging] Loaded {stg_cnt:,} records into stg_national_master_ev_stations ({stg_mmr_cnt:,} inside MMR).")
        print("  [SAFETY CHECK] Existing production tables 'charging_stations' and 'charging_ports' were untouched.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"\n[PostgreSQL Warning] Could not connect or load staging table: {e}")

    print(f"\nTotal Pipeline Execution Time: {time.time()-t0:.2f}s")
    return stats, mmr_valid, national_outside_mmr, pending_records, rejected_records

if __name__ == '__main__':
    build_national_master_dataset()
