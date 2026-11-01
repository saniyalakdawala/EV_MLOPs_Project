"""
Exact Conflict Resolution and Pipeline Simulation
"""
import json
import math
from shapely.geometry import shape, Point

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def simulate():
    with open('data/mmr_boundary.geojson', 'r', encoding='utf-8') as f:
        mmr_poly = shape(json.load(f)['features'][0]['geometry'])

    with open('data/raw/osm_mmr_overpass_raw.json', 'r', encoding='utf-8') as f:
        osm_raw = json.load(f)['elements']
    with open('data/raw/ocm_all_india.json', 'r', encoding='utf-8') as f:
        ocm_raw = json.load(f)
    with open('data/raw/indian_ev_charging_stations.geojson', 'r', encoding='utf-8') as f:
        eam_raw = json.load(f)['features']

    print(f"Raw Counts: OSM={len(osm_raw)}, OCM={len(ocm_raw)}, EAMRIT={len(eam_raw)}")
    print(f"Total Raw Collected: {len(osm_raw) + len(ocm_raw) + len(eam_raw)}")

    # Parse candidates
    candidates = []

    # 1. OSM
    for el in osm_raw:
        el_type = el.get('type')
        el_id = el.get('id')
        lat = float(el.get('lat') or el.get('center', {}).get('lat'))
        lon = float(el.get('lon') or el.get('center', {}).get('lon'))
        tags = el.get('tags', {})
        name = tags.get('name') or tags.get('operator') or tags.get('brand')
        op = tags.get('operator') or tags.get('brand') or 'unknown'
        addr = tags.get('addr:street') or tags.get('addr:full') or tags.get('branch') or 'unknown'
        city = tags.get('addr:city') or 'Mumbai'
        loc = tags.get('addr:suburb') or tags.get('addr:district') or tags.get('addr:neighbourhood') or 'unknown'
        
        conns = []
        if 'socket:type2' in tags: conns.append('Type 2 AC')
        if 'socket:type2_combo' in tags or 'socket:ccs' in tags: conns.append('CCS-2')
        if 'socket:chademo' in tags: conns.append('CHAdeMO')
        
        candidates.append({
            'source_name': 'OpenStreetMap',
            'source_id': f"{el_type}/{el_id}",
            'source_url': f"https://www.openstreetmap.org/{el_type}/{el_id}",
            'source_license': 'Open Data Commons Open Database License (ODbL) 1.0',
            'name': name,
            'operator': op,
            'address': addr,
            'locality': loc,
            'city': city,
            'state': 'Maharashtra',
            'latitude': lat,
            'longitude': lon,
            'connector_types': "; ".join(conns) if conns else 'unknown',
            'power_kw': tags.get('charging_station:output') or tags.get('output') or 'unknown',
            'access_type': tags.get('access') or 'unknown',
            'operational_status': tags.get('operational_status') or 'unknown'
        })

    # 2. OCM
    for it in ocm_raw:
        s_id = it.get('ID')
        addr_info = it.get('AddressInfo', {})
        name = addr_info.get('Title')
        op_info = it.get('OperatorInfo')
        op = op_info.get('Title') if op_info else 'unknown'
        addr = addr_info.get('AddressLine1') or 'unknown'
        loc = addr_info.get('AddressLine2') or addr_info.get('Town') or 'unknown'
        city = addr_info.get('Town') or 'unknown'
        st = addr_info.get('StateOrProvince') or 'unknown'
        st = st.strip() if isinstance(st, str) else 'unknown'
        lat = float(addr_info.get('Latitude'))
        lon = float(addr_info.get('Longitude'))

        conns = []
        powers = []
        for c in it.get('Connections', []):
            ct = c.get('ConnectionType', {}).get('Title')
            if ct: conns.append(ct)
            p = c.get('PowerKW')
            if p: powers.append(str(p))

        candidates.append({
            'source_name': 'OpenChargeMap',
            'source_id': f"OCM-{s_id}",
            'source_url': f"https://openchargemap.org/site/poi/details/{s_id}",
            'source_license': 'Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)',
            'name': name,
            'operator': op,
            'address': addr,
            'locality': loc,
            'city': city,
            'state': st,
            'latitude': lat,
            'longitude': lon,
            'connector_types': "; ".join(list(set(conns))) if conns else 'unknown',
            'power_kw': "; ".join(list(set(powers))) if powers else 'unknown',
            'access_type': it.get('UsageType', {}).get('Title') or 'unknown',
            'operational_status': it.get('StatusType', {}).get('Title') or 'unknown'
        })

    # 3. E-Amrit
    for ft in eam_raw:
        coords = ft['geometry']['coordinates']
        props = ft['properties']
        raw_id = props.get('stationid', '0')
        candidates.append({
            'source_name': 'NITI_Aayog_EAmrit',
            'source_id': f"EAMRIT-{raw_id}",
            'source_url': "https://e-amrit.niti.gov.in",
            'source_license': 'Government Open Data License - India (GODL-India)',
            'name': props.get('name') or 'unknown',
            'operator': 'EESL / Government PSU',
            'address': props.get('address') or 'unknown',
            'locality': props.get('city') or 'unknown',
            'city': props.get('city') or 'unknown',
            'state': props.get('state') or 'unknown',
            'latitude': float(coords[1]),
            'longitude': float(coords[0]),
            'connector_types': 'unknown',
            'power_kw': 'unknown',
            'access_type': 'Public',
            'operational_status': 'unknown'
        })

    print(f"Total Parsed Candidates: {len(candidates)}")

    # Point in polygon
    in_mmr_count = 0
    out_mmr_count = 0
    for c in candidates:
        pt = Point(c['longitude'], c['latitude'])
        is_in = mmr_poly.contains(pt)
        c['is_inside_mmr'] = is_in
        if is_in:
            in_mmr_count += 1
        else:
            out_mmr_count += 1

    print(f"Inside MMR polygon: {in_mmr_count}, Outside MMR: {out_mmr_count}")

    # Flag incomplete/generic
    pending = []
    clean_candidates = []
    for c in candidates:
        name = str(c.get('name') or '').strip()
        addr = str(c.get('address') or '').strip()
        is_generic_name = (
            not name or
            len(name) < 3 or
            name.lower() in ['charging station', 'ev charging station', 'station', 'electric vehicle charging station', 'unknown'] or
            name.startswith('Station ')
        )
        if is_generic_name and (not addr or addr == 'unknown'):
            c['pending_reason'] = 'Generic or missing station name and missing address; requires ground verification'
            pending.append(c)
        else:
            clean_candidates.append(c)

    print(f"Flagged for incomplete metadata: {len(pending)}")
    print(f"Clean candidates remaining: {len(clean_candidates)}")

    # Cross-source proximity check (<50m)
    # Using spatial grid / KD-tree or pairwise within state
    proximity_conflicts = set()
    from collections import defaultdict
    # Bucket by 0.01 deg lat/lon (approx 1.1km)
    grid = defaultdict(list)
    for idx, c in enumerate(clean_candidates):
        grid[(int(c['latitude'] * 100), int(c['longitude'] * 100))].append(idx)

    for (gx, gy), indices in grid.items():
        # check neighboring buckets
        neighbor_indices = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbor_indices.extend(grid.get((gx + dx, gy + dy), []))

        for i in indices:
            c1 = clean_candidates[i]
            for j in neighbor_indices:
                if i < j:
                    c2 = clean_candidates[j]
                    if c1['source_name'] != c2['source_name']:
                        dist = haversine(c1['latitude'], c1['longitude'], c2['latitude'], c2['longitude'])
                        if dist < 50.0:
                            proximity_conflicts.add(i)
                            proximity_conflicts.add(j)

    print(f"Candidates flagged for cross-source proximity (<50m): {len(proximity_conflicts)}")

    final_valid_national = []
    for idx, c in enumerate(clean_candidates):
        if idx in proximity_conflicts:
            c_copy = dict(c)
            c_copy['pending_reason'] = "Cross-source candidate within 50m of another source; flagged for review without automatic merge"
            pending.append(c_copy)
        else:
            if c['is_inside_mmr']:
                c['validation_status'] = 'VERIFIED_MMR'
            else:
                c['validation_status'] = 'VERIFIED_NATIONAL'
            final_valid_national.append(c)

    print(f"Total Valid National Master Records: {len(final_valid_national)}")
    mmr_valid = sum(1 for c in final_valid_national if c['is_inside_mmr'])
    non_mmr_valid = sum(1 for c in final_valid_national if not c['is_inside_mmr'])
    print(f"  • Valid Inside MMR: {mmr_valid}")
    print(f"  • Valid Outside MMR (National): {non_mmr_valid}")
    print(f"Total Pending Review: {len(pending)}")

if __name__ == '__main__':
    simulate()
