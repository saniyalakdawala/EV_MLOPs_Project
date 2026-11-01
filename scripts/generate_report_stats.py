import csv
import json
from collections import Counter
from shapely.geometry import shape, Point

def generate_stats():
    # 1. National master
    with open('data/national_master_ev_stations.csv', 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
    
    total_national = len(reader)
    mmr_stations = [r for r in reader if r['is_inside_mmr'] == 'TRUE']
    non_mmr_stations = [r for r in reader if r['is_inside_mmr'] == 'FALSE']

    # 2. Review records
    with open('data/review/pending_stations.csv', 'r', encoding='utf-8') as f:
        pending = list(csv.DictReader(f))
    pending_mmr = [r for r in pending if r['is_inside_mmr'] == 'TRUE']
    pending_non_mmr = [r for r in pending if r['is_inside_mmr'] == 'FALSE']

    with open('data/review/rejected_stations.csv', 'r', encoding='utf-8') as f:
        rejected = list(csv.DictReader(f))

    # Sources
    sources_national = Counter(r['source_name'] for r in reader)
    sources_mmr = Counter(r['source_name'] for r in mmr_stations)
    sources_pending = Counter(r['source_name'] for r in pending)

    # Top states national
    states_national = Counter(r['state'] for r in reader)

    # Top operators national & MMR
    ops_national = Counter(r['operator'] for r in reader)
    ops_mmr = Counter(r['operator'] for r in mmr_stations)

    # Connectors MMR & National
    conn_types_mmr = Counter()
    for r in mmr_stations:
        for c in r['connector_types'].split('; '):
            if c and c != 'unknown':
                conn_types_mmr[c] += 1

    # Raw counts
    with open('data/raw/osm_mmr_overpass_raw.json', 'r', encoding='utf-8') as f:
        raw_osm = len(json.load(f).get('elements', []))
    with open('data/raw/ocm_all_india.json', 'r', encoding='utf-8') as f:
        raw_ocm = len(json.load(f))
    with open('data/raw/indian_ev_charging_stations.geojson', 'r', encoding='utf-8') as f:
        raw_eamrit = len(json.load(f).get('features', []))
    with open('data/raw/bee_india_ev_charging_stations.json', 'r', encoding='utf-8') as f:
        bee_raw = json.load(f)
        raw_bee = len(bee_raw)

    print("STATS GENERATION COMPLETE:")
    print(f"Total Raw: {raw_osm + raw_ocm + raw_eamrit + raw_bee:,}")
    print(f"  OSM: {raw_osm}, OCM: {raw_ocm:,}, E-Amrit: {raw_eamrit}, BEE: {raw_bee:,}")
    print(f"National Valid: {total_national:,}")
    print(f"MMR Valid: {len(mmr_stations):,}")
    print(f"Non-MMR Valid: {len(non_mmr_stations):,}")
    print(f"Pending Total: {len(pending):,} (MMR: {len(pending_mmr)}, Non-MMR: {len(pending_non_mmr)})")
    print(f"Rejected Total: {len(rejected)}")
    print(f"\nTop 10 States National:")
    for st, c in states_national.most_common(10):
        print(f"  {st:25s}: {c:5d} ({c/total_national*100:.1f}%)")
    print(f"\nTop 10 Operators National:")
    for op, c in ops_national.most_common(10):
        print(f"  {op:25s}: {c:5d} ({c/total_national*100:.1f}%)")
    print(f"\nTop 10 Operators MMR:")
    for op, c in ops_mmr.most_common(10):
        print(f"  {op:25s}: {c:5d} ({c/len(mmr_stations)*100:.1f}%)")

if __name__ == '__main__':
    generate_stats()
