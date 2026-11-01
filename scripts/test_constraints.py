"""
Constraint Verification Runner
Executes 02_constraints.sql on database 'ev_db'
Verifies domain checks, partial unique index, and foreign key rules.
"""
import psycopg2

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def test_constraints():
    print("=" * 60)
    print("RUNNING CONSTRAINTS & INTEGRITY VERIFICATION SUITE")
    print("=" * 60)
    
    conn = psycopg2.connect(**DB_CONFIG)
    # Enable notices
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    with open('database/02_constraints.sql', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Filter out psql meta commands like \c
    sql_commands = []
    current_block = []
    for line in lines:
        if line.strip().startswith('\\c'):
            continue
        current_block.append(line)
        if line.strip().endswith('$$;') or (line.strip().endswith(';') and not any('DO $$' in l for l in current_block)):
            sql_commands.append("".join(current_block))
            current_block = []
            
    for cmd in sql_commands:
        cmd_clean = cmd.strip()
        if not cmd_clean:
            continue
        try:
            cur.execute(cmd_clean)
            for notice in conn.notices:
                print(notice.strip())
            conn.notices.clear()
        except Exception as e:
            print(f"Command failed: {e}")

    cur.close()
    conn.close()
    print("=" * 60)
    print("CONSTRAINTS VERIFICATION SUITE COMPLETED")
    print("=" * 60)

if __name__ == '__main__':
    test_constraints()
