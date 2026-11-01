"""
Inspect National Records across OCM and E-Amrit
"""
import json
import math

def check():
    with open('data/raw/ocm_all_india.json', 'r', encoding='utf-8') as f:
        ocm = json.load(f)
    print(f"OCM total: {len(ocm)}")

    # Check states, cities, nulls
    states = {}
    missing_title = 0
    missing_coords = 0
    zero_coords = 0
    invalid_bounds = 0

    for it in ocm:
        addr = it.get('AddressInfo', {})
        t = addr.get('Title')
        if not t: missing_title += 1
        lat = addr.get('Latitude')
        lon = addr.get('Longitude')
        if lat is None or lon is None:
            missing_coords += 1
            continue
        try:
            lf = float(lat)
            ln = float(lon)
            if lf == 0.0 and ln == 0.0:
                zero_coords += 1
            if not (-90 <= lf <= 90 and -180 <= ln <= 180):
                invalid_bounds += 1
        except Exception:
            invalid_bounds += 1

        state = addr.get('StateOrProvince') or 'unknown'
        states[state] = states.get(state, 0) + 1

    print(f"Missing title: {missing_title}")
    print(f"Missing coords: {missing_coords}")
    print(f"Zero coords: {zero_coords}")
    print(f"Invalid bounds: {invalid_bounds}")
    print(f"Top 10 states in OCM: {sorted(states.items(), key=lambda x: x[1], reverse=True)[:10]}")

    with open('data/raw/indian_ev_charging_stations.geojson', 'r', encoding='utf-8') as f:
        eam = json.load(f)
    print(f"\nE-Amrit total: {len(eam.get('features', []))}")
    e_missing_coords = 0
    e_states = {}
    for ft in eam.get('features', []):
        coords = ft.get('geometry', {}).get('coordinates', [])
        props = ft.get('properties', {})
        if len(coords) < 2:
            e_missing_coords += 1
        st = props.get('state') or 'unknown'
        e_states[st] = e_states.get(st, 0) + 1
    print(f"E-Amrit missing coords: {e_missing_coords}")
    print(f"Top 10 states in E-Amrit: {sorted(e_states.items(), key=lambda x: x[1], reverse=True)[:10]}")

if __name__ == '__main__':
    check()
