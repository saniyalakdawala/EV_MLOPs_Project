"""
Concurrency Demonstration Runner
Simulates two concurrent database connections (Driver Alice and Driver Bob)
attempting to book the SAME charging port simultaneously.
Demonstrates Row-Level Locking (SELECT ... FOR UPDATE) and conflict resolution.
"""
import threading
import time
import psycopg2

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def book_port(driver_name, port_id, sleep_before_commit, results):
    print(f"[{driver_name}] Attempting to connect to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Start transaction
        cur.execute("BEGIN;")
        print(f"[{driver_name}] TRANSACTION STARTED. Requesting exclusive lock: SELECT ... WHERE port_id = {port_id} FOR UPDATE...")
        
        start_lock = time.time()
        cur.execute("SELECT port_id, status FROM charging_ports WHERE port_id = %s FOR UPDATE;", (port_id,))
        row = cur.fetchone()
        lock_duration = time.time() - start_lock
        print(f"[{driver_name}] LOCK ACQUIRED after {lock_duration:.2f}s! Observed Status: '{row[1]}'")
        
        if row[1] != 'AVAILABLE':
            print(f"[{driver_name}] CONFLICT DETECTED: Port {port_id} is already '{row[1]}'. Rejecting booking request.")
            conn.rollback()
            results[driver_name] = f"REJECTED (Port is {row[1]})"
            return
            
        # Simulate physical plug-in delay
        print(f"[{driver_name}] Port is AVAILABLE! Holding lock for {sleep_before_commit}s (simulating vehicle handshake)...")
        time.sleep(sleep_before_commit)
        
        # Transition status and insert session
        cur.execute("UPDATE charging_ports SET status = 'IN_USE', updated_at = NOW() WHERE port_id = %s;", (port_id,))
        cur.execute("INSERT INTO charging_sessions (port_id, user_identifier, session_status) VALUES (%s, %s, 'ACTIVE') RETURNING session_id;", (port_id, driver_name))
        session_id = cur.fetchone()[0]
        
        conn.commit()
        print(f"[{driver_name}] TRANSACTION COMMITTED! Session {session_id} successfully created.")
        results[driver_name] = f"SUCCESS (Session {session_id})"
        
    except Exception as e:
        conn.rollback()
        print(f"[{driver_name}] TRANSACTION FAILED/ROLLED BACK: {e}")
        results[driver_name] = f"ERROR ({e})"
    finally:
        cur.close()
        conn.close()

def run_concurrency_test():
    print("=" * 70)
    print("CONCURRENCY CONTROL DEMONSTRATION: SIMULTANEOUS DOUBLE-BOOKING")
    print("=" * 70)
    
    # 1. First ensure a specific test port is AVAILABLE
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    # Deploy stored procedure from 06_concurrency.sql
    with open('database/06_concurrency.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    clean_sql = "\n".join([l for l in sql.splitlines() if not l.strip().startswith('\\c')])
    cur.execute(clean_sql)
    conn.commit()
    
    cur.execute("SELECT port_id FROM charging_ports WHERE status = 'AVAILABLE' LIMIT 1;")
    test_port_id = cur.fetchone()[0]
    # Terminate any existing active session on this port
    cur.execute("UPDATE charging_sessions SET session_status = 'COMPLETED', end_time = NOW() WHERE port_id = %s AND session_status = 'ACTIVE';", (test_port_id,))
    cur.execute("UPDATE charging_ports SET status = 'AVAILABLE' WHERE port_id = %s;", (test_port_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"Selected Test Port ID: {test_port_id} (Reset to 'AVAILABLE')\n")
    
    results = {}
    
    # Alice starts booking and holds lock for 2 seconds
    t_alice = threading.Thread(target=book_port, args=("DRIVER_ALICE", test_port_id, 2.0, results))
    # Bob attempts to book the same port 0.3 seconds after Alice starts
    def delayed_bob():
        time.sleep(0.3)
        book_port("DRIVER_BOB", test_port_id, 0.5, results)
        
    t_bob = threading.Thread(target=delayed_bob)
    
    t_alice.start()
    t_bob.start()
    
    t_alice.join()
    t_bob.join()
    
    print("\n" + "=" * 70)
    print("CONCURRENCY TEST SUMMARY RESULTS:")
    print(f"  • Driver Alice Outcome : {results.get('DRIVER_ALICE')}")
    print(f"  • Driver Bob Outcome   : {results.get('DRIVER_BOB')}")
    print("=" * 70)
    
    # Verify no double booking in database
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM charging_sessions WHERE port_id = %s AND session_status = 'ACTIVE';", (test_port_id,))
    active_count = cur.fetchone()[0]
    print(f"Verification Check: Total active sessions on port {test_port_id} = {active_count} (Expected: EXACTLY 1)")
    if active_count == 1:
        print("[VERIFIED] Concurrency control successfully prevented race condition and double-booking!")
    else:
        print("[FAILED] Double booking occurred!")
    cur.close()
    conn.close()
    print("=" * 70)

if __name__ == '__main__':
    run_concurrency_test()
