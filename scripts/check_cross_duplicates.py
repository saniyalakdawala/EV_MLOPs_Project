"""
Test cross-source proximity between OCM, E-Amrit, and OSM
"""
import json
import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def check_cross_duplicates():
    with open('data/raw/ocm_all_india.json', 'r', encoding='utf-8') as f:
        ocm = json.load(f)
    with open('data/raw/indian_ev_charging_stations.geojson', 'r', encoding='utf-8') as f:
        eam = json.load(f)['features']
    with open('data/raw/osm_mmr_overpass_raw.json', 'r', encoding='utf-8') as f:
        osm = json.load(f)['elements']

    ocm_pts = []
    for it in ocm:
        addr = it.get('AddressInfo', {})
        ocm_pts.append({
            'source': 'OCM',
            'id': it.get('ID'),
            'name': addr.get('Title'),
            'lat': float(addr.get('Latitude')),
            'lon': float(addr.get('Longitude'))
        })

    eam_pts = []
    for it in eam:
        coords = it['geometry']['coordinates']
        props = it['properties']
        eam_pts.append({
            'source': 'EAMRIT',
            'id': props.get('stationid'),
            'name': props.get('name'),
            'lat': float(coords[1]),
            'lon': float(coords[0])
        })

    osm_pts = []
    for it in osm:
        lat = it.get('lat') or it.get('center', {}).get('lat')
        lon = it.get('lon') or it.get('center', {}).get('lon')
        osm_pts.append({
            'source': 'OSM',
            'id': it.get('id'),
            'name': it.get('tags', {}).get('name') or 'Unnamed',
            'lat': float(lat),
            'lon': float(lon)
        })

    print(f"Checking cross proximity across {len(ocm_pts)} OCM and {len(eam_pts)} EAMRIT points...")
    cross_conflicts = []
    for ep in eam_pts:
        for op in ocm_pts:
            dist = haversine(ep['lat'], ep['lon'], op['lat'], op['lon'])
            if dist < 50.0:
                cross_conflicts.append((ep, op, dist))

    print(f"Found {len(cross_conflicts)} cross-source pairs within 50m between EAMRIT and OCM:")
    for ep, op, dist in cross_conflicts:
        print(f"  • EAMRIT {ep['id']} ({ep['name']}) <-> OCM {op['id']} ({op['name']}) : dist = {dist:.1f}m")

    # Check OSM vs OCM in MMR
    osm_ocm_conflicts = []
    for sp in osm_pts:
        for op in ocm_pts:
            dist = haversine(sp['lat'], sp['lon'], op['lat'], op['lon'])
            if dist < 50.0:
                osm_ocm_conflicts.append((sp, op, dist))
    print(f"Found {len(osm_ocm_conflicts)} cross-source pairs within 50m between OSM and OCM in MMR:")
    for sp, op, dist in osm_ocm_conflicts:
        print(f"  • OSM {sp['id']} ({sp['name']}) <-> OCM {op['id']} ({op['name']}) : dist = {dist:.1f}m")

if __name__ == '__main__':
    check_cross_duplicates()
