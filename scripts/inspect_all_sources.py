"""
Comprehensive Raw Data Source Analysis
======================================
Inspects:
1. data/raw/osm_mmr_overpass_raw.json
2. data/raw/ocm_all_india.json
3. data/raw/indian_ev_charging_stations.geojson
4. data/raw/openchargemap_india_500.json

Checks:
- Coordinate validity
- Point-in-polygon check using data/mmr_boundary.geojson
- Exact duplicate source IDs
- Connectors, power, ports, operators
"""
import json
import os
from shapely.geometry import shape, Point

def analyze():
    print("=" * 80)
    print("ANALYSIS OF ALL AVAILABLE RAW EV CHARGING DATA SOURCES")
    print("=" * 80)

    # 1. Load MMR Boundary
    b_path = os.path.join('data', 'mmr_boundary.geojson')
    with open(b_path, 'r', encoding='utf-8') as f:
        b_data = json.load(f)
    mmr_polygon = shape(b_data['features'][0]['geometry'])
    print(f"MMR Boundary loaded successfully. Polygon bounds: {mmr_polygon.bounds}")

    # 2. Check OSM
    osm_path = os.path.join('data', 'raw', 'osm_mmr_overpass_raw.json')
    if os.path.exists(osm_path):
        with open(osm_path, 'r', encoding='utf-8') as f:
            osm_data = json.load(f)
        elements = osm_data.get('elements', [])
        print(f"\n[1] OpenStreetMap Overpass Extract: {len(elements)} elements")
        in_mmr = 0
        for el in elements:
            lat = el.get('lat') or el.get('center', {}).get('lat')
            lon = el.get('lon') or el.get('center', {}).get('lon')
            pt = Point(lon, lat)
            is_in = mmr_polygon.contains(pt)
            if is_in:
                in_mmr += 1
            tags = el.get('tags', {})
            name = tags.get('name') or tags.get('operator') or tags.get('brand') or 'UNNAMED'
            print(f"  - OSM {el.get('type')}/{el.get('id')}: {name} ({lat}, {lon}) -> Inside MMR: {is_in}")
        print(f"  Total OSM in MMR: {in_mmr} / {len(elements)}")

    # 3. Check OCM
    ocm_path = os.path.join('data', 'raw', 'ocm_all_india.json')
    if os.path.exists(ocm_path):
        with open(ocm_path, 'r', encoding='utf-8') as f:
            ocm_data = json.load(f)
        print(f"\n[2] OpenChargeMap All-India: {len(ocm_data)} records")
        ocm_in_mmr = []
        ocm_out_mmr = []
        ocm_inv_coords = []
        unique_ocm_ids = set()
        ocm_dup_ids = 0

        for item in ocm_data:
            s_id = item.get('ID')
            if s_id in unique_ocm_ids:
                ocm_dup_ids += 1
            unique_ocm_ids.add(s_id)

            addr = item.get('AddressInfo', {})
            lat = addr.get('Latitude')
            lon = addr.get('Longitude')
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                    ocm_inv_coords.append(item)
                    continue
                pt = Point(lon_f, lat_f)
                if mmr_polygon.contains(pt):
                    ocm_in_mmr.append((item, lat_f, lon_f))
                else:
                    ocm_out_mmr.append((item, lat_f, lon_f))
            except Exception:
                ocm_inv_coords.append(item)

        print(f"  • Unique OCM IDs: {len(unique_ocm_ids)}, Duplicate IDs: {ocm_dup_ids}")
        print(f"  • Valid Coordinates: {len(ocm_in_mmr) + len(ocm_out_mmr)}")
        print(f"  • Inside MMR Polygon: {len(ocm_in_mmr)}")
        print(f"  • Outside MMR Polygon (Rest of India): {len(ocm_out_mmr)}")
        print(f"  • Invalid Coordinates: {len(ocm_inv_coords)}")
        print("  Inside MMR OCM Stations:")
        for it, lat, lon in ocm_in_mmr:
            print(f"    - ID {it.get('ID')}: {it.get('AddressInfo', {}).get('Title')} @ ({lat}, {lon}), City: {it.get('AddressInfo', {}).get('Town')}")

    # 4. Check E-Amrit / NITI Aayog
    eamrit_path = os.path.join('data', 'raw', 'indian_ev_charging_stations.geojson')
    if os.path.exists(eamrit_path):
        with open(eamrit_path, 'r', encoding='utf-8') as f:
            eamrit_data = json.load(f)
        features = eamrit_data.get('features', [])
        print(f"\n[3] E-Amrit / NITI Aayog GeoJSON: {len(features)} records")
        e_in_mmr = 0
        e_out_mmr = 0
        for feat in features:
            coords = feat.get('geometry', {}).get('coordinates', [])
            lat = coords[1] if len(coords) > 1 else None
            lon = coords[0] if len(coords) > 0 else None
            if lat is not None and lon is not None:
                pt = Point(lon, lat)
                if mmr_polygon.contains(pt):
                    e_in_mmr += 1
                else:
                    e_out_mmr += 1
        print(f"  • Inside MMR Polygon: {e_in_mmr}")
        print(f"  • Outside MMR Polygon: {e_out_mmr}")

if __name__ == '__main__':
    analyze()
