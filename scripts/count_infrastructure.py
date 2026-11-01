"""
Count physical locations vs connectors vs ports in raw data
"""
import json

def count_infrastructure():
    with open('data/raw/ocm_all_india.json', 'r', encoding='utf-8') as f:
        ocm = json.load(f)
    
    total_ocm_stations = len(ocm)
    total_ocm_connections = sum(len(x.get('Connections', [])) for x in ocm)
    total_ocm_number_of_points = sum(x.get('NumberOfPoints') or 0 for x in ocm)
    
    # Inside MMR for OCM
    import os
    from shapely.geometry import shape, Point
    with open('data/mmr_boundary.geojson', 'r', encoding='utf-8') as f:
        mmr_poly = shape(json.load(f)['features'][0]['geometry'])
    
    ocm_mmr_stations = 0
    ocm_mmr_connections = 0
    ocm_mmr_points = 0
    for x in ocm:
        addr = x.get('AddressInfo', {})
        lat = float(addr.get('Latitude', 0))
        lon = float(addr.get('Longitude', 0))
        if mmr_poly.contains(Point(lon, lat)):
            ocm_mmr_stations += 1
            ocm_mmr_connections += len(x.get('Connections', []))
            ocm_mmr_points += (x.get('NumberOfPoints') or 0)

    print(f"OCM All India:")
    print(f"  • Physical Stations: {total_ocm_stations}")
    print(f"  • Listed Connections: {total_ocm_connections}")
    print(f"  • Number of Charging Points (capacity metadata): {total_ocm_number_of_points}")
    print(f"OCM Inside MMR:")
    print(f"  • Physical Stations: {ocm_mmr_stations}")
    print(f"  • Listed Connections: {ocm_mmr_connections}")
    print(f"  • Number of Charging Points: {ocm_mmr_points}")

    # OSM inside MMR
    with open('data/raw/osm_mmr_overpass_raw.json', 'r', encoding='utf-8') as f:
        osm = json.load(f)['elements']
    
    osm_stations = len(osm)
    osm_capacity = 0
    for el in osm:
        cap = el.get('tags', {}).get('capacity')
        try:
            osm_capacity += int(cap)
        except (ValueError, TypeError):
            pass
    print(f"\nOSM Inside MMR:")
    print(f"  • Physical Stations: {osm_stations}")
    print(f"  • Explicit capacity tagged ports: {osm_capacity}")

    # E-Amrit
    with open('data/raw/indian_ev_charging_stations.geojson', 'r', encoding='utf-8') as f:
        eam = json.load(f)['features']
    print(f"\nE-Amrit All India:")
    print(f"  • Physical Stations: {len(eam)}")
    print(f"  • Inside MMR: 0")

if __name__ == '__main__':
    count_infrastructure()
