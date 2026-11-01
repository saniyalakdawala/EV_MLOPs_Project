import psycopg2
import json
import sys

def inspect_db():
    try:
        conn = psycopg2.connect(dbname='ev_db', user='postgres', password='postgres', host='localhost', port=5432)
        cur = conn.cursor()
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    report = {}

    # 1. PostGIS version
    try:
        cur.execute("SELECT PostGIS_Full_Version();")
        report['postgis_version'] = cur.fetchone()[0]
    except Exception as e:
        report['postgis_version'] = f"Error: {e}"
        conn.rollback()

    # 2. Tables and row counts
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [r[0] for r in cur.fetchall()]
    table_counts = {}
    for t in tables:
        try:
            cur.execute(f'SELECT count(*) FROM "{t}";')
            cnt = cur.fetchone()[0]
            table_counts[t] = cnt
        except Exception as e:
            table_counts[t] = f"Error: {e}"
            conn.rollback()
    report['tables'] = table_counts

    # 3. Table columns and types
    columns_info = {}
    for t in tables:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (t,))
        columns_info[t] = [
            {'column': r[0], 'type': r[1], 'nullable': r[2], 'default': r[3]}
            for r in cur.fetchall()
        ]
    report['columns'] = columns_info

    # 4. Constraints
    cur.execute("""
        SELECT conname, contype, conrelid::regclass::text as table_name, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE n.nspname = 'public'
        ORDER BY table_name, conname;
    """)
    constraints = [
        {'name': r[0], 'type': r[1], 'table': r[2], 'definition': r[3]}
        for r in cur.fetchall()
    ]
    report['constraints'] = constraints

    # 5. Indexes
    cur.execute("""
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    """)
    indexes = [
        {'table': r[0], 'name': r[1], 'definition': r[2]}
        for r in cur.fetchall()
    ]
    report['indexes'] = indexes

    # 6. Roles and Privileges
    cur.execute("""
        SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin
        FROM pg_roles
        WHERE rolname IN ('postgres', 'ev_app_user', 'ev_readonly', 'ev_admin') OR rolname NOT LIKE 'pg_%';
    """)
    roles = [
        {'name': r[0], 'superuser': r[1], 'inherit': r[2], 'createrole': r[3], 'createdb': r[4], 'canlogin': r[5]}
        for r in cur.fetchall()
    ]
    report['roles'] = roles

    # 7. Triggers
    cur.execute("""
        SELECT event_object_table, trigger_name, event_manipulation, action_statement, action_timing
        FROM information_schema.triggers
        WHERE trigger_schema = 'public';
    """)
    triggers = [
        {'table': r[0], 'name': r[1], 'event': r[2], 'statement': r[3], 'timing': r[4]}
        for r in cur.fetchall()
    ]
    report['triggers'] = triggers

    # 8. Sample Stations Data in charging_stations
    cur.execute("SELECT station_id, station_name, operator_name, city, state, latitude, longitude, source_name FROM charging_stations ORDER BY station_id LIMIT 20;")
    report['sample_charging_stations'] = [
        {'id': r[0], 'name': r[1], 'operator': r[2], 'city': r[3], 'state': r[4], 'lat': float(r[5]) if r[5] else None, 'lon': float(r[6]) if r[6] else None, 'source': r[7]}
        for r in cur.fetchall()
    ]

    # Save to json file
    with open('data/db_audit_snapshot.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    print("DB Inspection successfully saved to data/db_audit_snapshot.json")

    cur.close()
    conn.close()

if __name__ == '__main__':
    inspect_db()
