"""
Simulation Script for MMR Master -> Production Migration
=========================================================
Calculates exact insert, overlap, duplicate, and port provisioning counts
without modifying production tables.
"""
import os
import csv
import json
import psycopg2

def simulate():
    print("=" * 80)
    print("VOLTGRID MUMBAI: PRODUCTION INTEGRATION IMPACT & SIMULATION PLAN")
    print("=" * 80)

    conn = psycopg2.connect(dbname='ev_db', user='postgres', password='postgres', host='localhost', port=5432)
    cur = conn.cursor()

    # 1. Baseline Counts
    cur.execute("SELECT count(*) FROM charging_stations;")
    baseline_stations = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM charging_ports;")
    baseline_ports = cur.fetchone()[0]

    # 2. Staging Counts
    cur.execute("SELECT count(*) FROM stg_national_master_ev_stations;")
    total_national_staging = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM stg_national_master_ev_stations WHERE is_inside_mmr = TRUE;")
    mmr_staging = cur.fetchone()[0]

    # 3. Master CSV
    csv_path = os.path.join('data', 'master_ev_stations.csv')
    with open(csv_path, 'r', encoding='utf-8') as f:
        master_rows = list(csv.DictReader(f))

    # 4. Overlap with Existing Production
    cur.execute("SELECT station_id, latitude, longitude, source_name, source_id, station_name FROM charging_stations;")
    existing_rows = cur.fetchall()
    existing_coords = set((float(r[1]), float(r[2])) for r in existing_rows)
    existing_source_keys = set((r[3], r[4]) for r in existing_rows if r[3] and r[4])

    already_present = []
    brand_new = []

    for r in master_rows:
        lat, lon = float(r['latitude']), float(r['longitude'])
        s_key = (r['source_name'], r['source_id'])
        if (lat, lon) in existing_coords or s_key in existing_source_keys:
            already_present.append(r)
        else:
            brand_new.append(r)

    # 5. BEE Raw Guns Analysis
    bee_path = os.path.join('data', 'raw', 'bee_india_ev_charging_stations.json')
    new_ports_count = 0
    port_types_counter = {}

    def map_connector(std, kw):
        std_u = (std or '').upper().replace('-', '_').strip()
        if 'CCS' in std_u: return 'CCS-2'
        if 'TYPE2' in std_u or 'TYPE_2' in std_u: return 'Type 2 AC'
        if 'CHADEMO' in std_u: return 'CHAdeMO'
        if 'GB/T' in std_u or 'GBT' in std_u: return 'GB/T'
        if 'DC001' in std_u or 'DC_001' in std_u or 'LEV_DC' in std_u: return 'Bharat DC-001'
        if 'AC001' in std_u or 'AC_001' in std_u or 'LEV_AC' in std_u or 'SOCKET' in std_u: return 'Bharat AC-001'
        if kw and float(kw) <= 3.3: return 'Bharat AC-001'
        return 'Type 2 AC'

    if os.path.exists(bee_path):
        with open(bee_path, 'r', encoding='utf-8') as f:
            raw_list = json.load(f)
            bee_data = {'BEE-' + s['id']: s for s in raw_list}
        
        for r in brand_new:
            s_raw = bee_data.get(r['source_id'])
            if s_raw and s_raw.get('chargers'):
                for ch in s_raw.get('chargers', []):
                    count = ch.get('count', 1) or 1
                    ch_kw = ch.get('charger_kw') or 3.3
                    for _ in range(count):
                        guns = ch.get('guns', [])
                        if guns:
                            for g in guns:
                                std = g.get('standard')
                                kw = g.get('kw') or ch_kw
                                m_conn = map_connector(std, kw)
                                port_types_counter[m_conn] = port_types_counter.get(m_conn, 0) + 1
                                new_ports_count += 1
                        else:
                            stds = ch.get('standards', [])
                            std = stds[0] if stds else 'unknown'
                            m_conn = map_connector(std, ch_kw)
                            port_types_counter[m_conn] = port_types_counter.get(m_conn, 0) + 1
                            new_ports_count += 1
            else:
                conns = r.get('connector_types', '').split('; ')
                p_str = r.get('power_kw', '3.3').split('; ')[0]
                try: p_kw = max(1.0, float(p_str))
                except: p_kw = 25.0
                for c in conns:
                    m_conn = map_connector(c, p_kw)
                    port_types_counter[m_conn] = port_types_counter.get(m_conn, 0) + 1
                    new_ports_count += 1

    print(f"\n1. Current Production Database State:")
    print(f"  • Active charging_stations : {baseline_stations}")
    print(f"  • Active charging_ports    : {baseline_ports}")

    print(f"\n2. Staging & Master CSV Dataset State:")
    print(f"  • Total in stg_national_master_ev_stations : {total_national_staging:,}")
    print(f"  • Staging rows inside MMR                  : {mmr_staging:,}")
    print(f"  • Verified stations in master_ev_stations  : {len(master_rows):,}")

    print(f"\n3. Overlap & Idempotency Breakdown:")
    print(f"  • Already Present in Production (Preserved Untouched) : {len(already_present)}")
    for r in already_present:
        print(f"      = [{r['station_id']}] {r['station_name']} ({r['source_name']}:{r['source_id']})")
    print(f"  • Brand New Stations to Insert                       : {len(brand_new)}")

    print(f"\n4. Individual Charging Ports to Provision ({new_ports_count} total):")
    for ct, cnt in sorted(port_types_counter.items(), key=lambda x: -x[1]):
        print(f"  • {ct:20s}: {cnt:4d} ports")

    print(f"\n5. Expected Before-and-After Reconciliation:")
    print(f"  • charging_stations : {baseline_stations}  -->  {baseline_stations + len(brand_new)} (+{len(brand_new)})")
    print(f"  • charging_ports    : {baseline_ports}  -->  {baseline_ports + new_ports_count} (+{new_ports_count})")
    print("=" * 80)

    cur.close()
    conn.close()

if __name__ == '__main__':
    simulate()
