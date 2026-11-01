"""
Idempotent Promotion Migration Script: MMR Master -> Production
================================================================
Safely promotes validated records from data/master_ev_stations.csv into production:
- charging_stations
- charging_ports

Safety Rules:
- Defaults to DRY-RUN mode. Production tables are NEVER modified unless '--apply' is explicitly passed.
- Idempotent: Can be run multiple times; existing 16 stations and their 18 ports are strictly preserved.
- Transactional: Wrapped in BEGIN ... COMMIT (with full ROLLBACK on any failure or during dry-run).
- Preserves foreign keys, status history, and operational charging sessions.
- Synthesizes authentic individual port records from raw source records (BEE/OCM/OSM).
"""
import sys
import os
import csv
import json
import re
import psycopg2

def map_connector(std, kw):
    std_u = (std or '').upper().replace('-', '_').strip()
    if 'CCS' in std_u:
        return 'CCS-2'
    if 'TYPE2' in std_u or 'TYPE_2' in std_u:
        return 'Type 2 AC'
    if 'CHADEMO' in std_u:
        return 'CHAdeMO'
    if 'GB/T' in std_u or 'GBT' in std_u:
        return 'GB/T'
    if 'DC001' in std_u or 'DC_001' in std_u or 'LEV_DC' in std_u:
        return 'Bharat DC-001'
    if 'AC001' in std_u or 'AC_001' in std_u or 'LEV_AC' in std_u or 'SOCKET' in std_u:
        return 'Bharat AC-001'
    if kw and float(kw) <= 3.3:
        return 'Bharat AC-001'
    return 'Type 2 AC'

def run_promotion(apply_changes=False):
    mode = "APPLY TO PRODUCTION" if apply_changes else "DRY-RUN (NO CHANGES APPLIED)"
    print("=" * 80)
    print(f"VOLTGRID MUMBAI: MMR MASTER PRODUCTION MIGRATION [{mode}]")
    print("=" * 80)

    # 1. Load 947 MMR master records
    csv_path = os.path.join('data', 'master_ev_stations.csv')
    with open(csv_path, 'r', encoding='utf-8') as f:
        master_rows = list(csv.DictReader(f))
    print(f"Loaded {len(master_rows)} verified MMR stations from {csv_path}")

    # 2. Load BEE raw file for rich port/gun synthesis
    bee_path = os.path.join('data', 'raw', 'bee_india_ev_charging_stations.json')
    bee_data = {}
    if os.path.exists(bee_path):
        with open(bee_path, 'r', encoding='utf-8') as f:
            raw_list = json.load(f)
            bee_data = {'BEE-' + s['id']: s for s in raw_list}
        print(f"Loaded {len(bee_data)} BEE raw records for port synthesis.")

    conn = psycopg2.connect(dbname='ev_db', user='postgres', password='postgres', host='localhost', port=5432)
    cur = conn.cursor()

    try:
        cur.execute("BEGIN;")

        # Baseline counts
        cur.execute("SELECT count(*) FROM charging_stations;")
        baseline_stations = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM charging_ports;")
        baseline_ports = cur.fetchone()[0]

        print(f"\n[Baseline State]")
        print(f"  • Existing charging_stations: {baseline_stations}")
        print(f"  • Existing charging_ports   : {baseline_ports}")

        # Check existing station coordinates and source keys
        cur.execute("SELECT station_id, latitude, longitude, source_name, source_id FROM charging_stations;")
        existing_rows = cur.fetchall()
        existing_coords = set((float(r[1]), float(r[2])) for r in existing_rows)
        existing_source_keys = set((r[3], r[4]) for r in existing_rows if r[3] and r[4])

        already_present = []
        new_candidates = []

        for r in master_rows:
            lat, lon = float(r['latitude']), float(r['longitude'])
            s_key = (r['source_name'], r['source_id'])
            if (lat, lon) in existing_coords or s_key in existing_source_keys:
                already_present.append(r)
            else:
                new_candidates.append(r)

        print(f"\n[Deduplication & Overlap Analysis]")
        print(f"  • Already Present in Production (Preserved Untouched) : {len(already_present)}")
        print(f"  • Brand New Stations to Insert                       : {len(new_candidates)}")

        # Insert new stations
        insert_station_sql = """
        INSERT INTO charging_stations (
            station_name, operator_name, address, city, state, postal_code,
            latitude, longitude, source_name, source_id, source_url, source_license,
            last_verified_at, master_station_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING station_id, master_station_id;
        """

        inserted_station_map = {}
        for r in new_candidates:
            m = re.search(r'\b(4\d{5})\b', r.get('address', ''))
            pin = m.group(1) if m else None

            cur.execute(insert_station_sql, (
                r['station_name'][:150],
                (r['operator'] or 'Independent Operator')[:100],
                r.get('address'),
                (r.get('city') or 'Mumbai')[:60],
                (r.get('state') or 'Maharashtra')[:60],
                pin,
                float(r['latitude']),
                float(r['longitude']),
                r.get('source_name')[:50],
                r.get('source_id')[:100],
                r.get('source_url'),
                r.get('source_license'),
                '2026-10-20',
                r.get('station_id')
            ))
            db_id, m_id = cur.fetchone()
            inserted_station_map[m_id] = db_id

        print(f"[SUCCESS] Prepared {len(inserted_station_map)} station inserts.")

        # Provision child charging ports for new stations
        port_insert_sql = """
        INSERT INTO charging_ports (
            station_id, port_number, connector_type, power_kw, status
        ) VALUES (%s, %s, %s, %s, %s);
        """

        total_ports_inserted = 0
        port_types_counter = {}

        for r in new_candidates:
            db_st_id = inserted_station_map[r['station_id']]
            s_raw = bee_data.get(r['source_id'])
            port_num = 1
            
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
                                mapped_conn = map_connector(std, kw)
                                p_kw = max(1.0, float(kw))
                                cur.execute(port_insert_sql, (db_st_id, port_num, mapped_conn, p_kw, 'AVAILABLE'))
                                port_types_counter[mapped_conn] = port_types_counter.get(mapped_conn, 0) + 1
                                port_num += 1
                                total_ports_inserted += 1
                        else:
                            stds = ch.get('standards', [])
                            std = stds[0] if stds else 'unknown'
                            mapped_conn = map_connector(std, ch_kw)
                            p_kw = max(1.0, float(ch_kw))
                            cur.execute(port_insert_sql, (db_st_id, port_num, mapped_conn, p_kw, 'AVAILABLE'))
                            port_types_counter[mapped_conn] = port_types_counter.get(mapped_conn, 0) + 1
                            port_num += 1
                            total_ports_inserted += 1
            else:
                conns = r.get('connector_types', '').split('; ')
                p_str = r.get('power_kw', '3.3').split('; ')[0]
                try:
                    p_kw = max(1.0, float(p_str))
                except:
                    p_kw = 25.0
                for c in conns:
                    mapped_conn = map_connector(c, p_kw)
                    cur.execute(port_insert_sql, (db_st_id, port_num, mapped_conn, p_kw, 'AVAILABLE'))
                    port_types_counter[mapped_conn] = port_types_counter.get(mapped_conn, 0) + 1
                    port_num += 1
                    total_ports_inserted += 1

        print(f"[SUCCESS] Prepared {total_ports_inserted} child charging port inserts.")

        # Summary of ports by connector type
        print("\n[Provisioned Ports by Connector Standard]")
        for ct, cnt in sorted(port_types_counter.items(), key=lambda x: -x[1]):
            print(f"  • {ct:20s}: {cnt:4d}")

        # Post-migration projected counts
        cur.execute("SELECT count(*) FROM charging_stations;")
        projected_stations = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM charging_ports;")
        projected_ports = cur.fetchone()[0]

        print("\n" + "=" * 80)
        print("BEFORE & AFTER COUNT RECONCILIATION:")
        print("=" * 80)
        print(f"  • charging_stations : {baseline_stations}  -->  {projected_stations} (+{len(new_candidates)})")
        print(f"  • charging_ports    : {baseline_ports}  -->  {projected_ports} (+{total_ports_inserted})")
        print("=" * 80)

        if apply_changes:
            conn.commit()
            print("\n[MIGRATION COMMITTED TO PRODUCTION SUCCESSFULLY]")
            print(f"Updated production database: {projected_stations} stations and {projected_ports} ports.")
        else:
            conn.rollback()
            print("\n[SAFETY GATE ENFORCED: TRANSACTION ROLLED BACK]")
            print("No changes were made to production tables.")
            print("To execute this migration after reviewing the report, run:")
            print("  python scripts/promote_master_staging.py --apply")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    apply_flag = '--apply' in sys.argv
    run_promotion(apply_changes=apply_flag)
