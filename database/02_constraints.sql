-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 02_constraints.sql
-- Description: Business Rules, Constraints, Integrity Checks & Demonstrations
-- Target Database: ev_db
-- ============================================================================

-- This file documents and tests the database constraints that guarantee
-- ACID integrity, prevent data corruption, and enforce business rules at the schema level.

\c ev_db;

-- ============================================================================
-- 1. REVIEW OF ACTIVE CONSTRAINTS
-- ============================================================================

-- Query PostgreSQL System Catalogs to list all active constraints on our tables:
SELECT 
    conrelid::regclass AS table_name,
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid::regclass::text IN ('charging_stations', 'charging_ports', 'charging_sessions', 'station_status_history')
ORDER BY table_name, constraint_type;

-- ============================================================================
-- 2. DEMONSTRATION TESTS FOR CONSTRAINTS (EXPECTED ERRORS)
-- Run each block to verify that PostgreSQL rejects invalid domain values.
-- ============================================================================

-- TEST 2.1: Coordinate Range Validation (chk_latitude_range)
-- Business Rule: Latitude must be between -90.0 and +90.0 degrees.
-- Expected Outcome: ERROR: new row for relation "charging_stations" violates check constraint "chk_latitude_range"
DO $$
BEGIN
    RAISE NOTICE '--- TEST 2.1: Testing invalid latitude (95.0) ---';
    BEGIN
        INSERT INTO charging_stations (station_name, operator_name, city, state, latitude, longitude)
        VALUES ('Invalid Test Station', 'Test Operator', 'Mumbai', 'Maharashtra', 95.123456, 72.877700);
        RAISE EXCEPTION 'TEST FAILED: Constraint allowed invalid latitude!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'SUCCESS: PostgreSQL rejected invalid latitude (chk_latitude_range triggered).';
    END;
END $$;

-- TEST 2.2: Connector Standard Validation (chk_connector_type)
-- Business Rule: Connectors must conform to approved standards (CCS-2, Type 2 AC, CHAdeMO, GB/T, Bharat AC-001/DC-001).
-- Expected Outcome: ERROR: violates check constraint "chk_connector_type"
DO $$
DECLARE
    v_st_id INT;
BEGIN
    RAISE NOTICE '--- TEST 2.2: Testing unapproved connector standard ---';
    -- Get or create a sample station
    SELECT station_id INTO v_st_id FROM charging_stations LIMIT 1;
    IF v_st_id IS NULL THEN
        INSERT INTO charging_stations (station_name, operator_name, city, state, latitude, longitude)
        VALUES ('Base Station', 'Tata Power', 'Mumbai', 'Maharashtra', 19.0760, 72.8777)
        RETURNING station_id INTO v_st_id;
    END IF;

    BEGIN
        INSERT INTO charging_ports (station_id, port_number, connector_type, power_kw, status)
        VALUES (v_st_id, 999, 'Proprietary-Tesla-V1', 150.0, 'AVAILABLE');
        RAISE EXCEPTION 'TEST FAILED: Constraint allowed unknown connector standard!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'SUCCESS: PostgreSQL rejected unapproved connector type (chk_connector_type triggered).';
    END;
END $$;

-- TEST 2.3: Non-Negative Power Check (chk_power_positive)
-- Business Rule: Power output rating must be strictly greater than 0 kW.
-- Expected Outcome: ERROR: violates check constraint "chk_power_positive"
DO $$
DECLARE
    v_st_id INT;
BEGIN
    RAISE NOTICE '--- TEST 2.3: Testing non-positive power output (-50 kW) ---';
    SELECT station_id INTO v_st_id FROM charging_stations LIMIT 1;
    BEGIN
        INSERT INTO charging_ports (station_id, port_number, connector_type, power_kw, status)
        VALUES (v_st_id, 998, 'CCS-2', -50.0, 'AVAILABLE');
        RAISE EXCEPTION 'TEST FAILED: Constraint allowed negative power output!';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'SUCCESS: PostgreSQL rejected negative power output (chk_power_positive triggered).';
    END;
END $$;

-- TEST 2.4: Double-Booking Safeguard (uq_active_session_per_port)
-- Business Rule: A port cannot have two concurrent ACTIVE charging sessions.
-- Expected Outcome: ERROR: duplicate key value violates unique constraint "uq_active_session_per_port"
DO $$
DECLARE
    v_port_id INT;
BEGIN
    RAISE NOTICE '--- TEST 2.4: Testing double-booking on same port ---';
    -- Ensure at least one port exists
    SELECT port_id INTO v_port_id FROM charging_ports LIMIT 1;
    IF v_port_id IS NULL THEN
        INSERT INTO charging_ports (station_id, port_number, connector_type, power_kw, status)
        SELECT station_id, 1, 'CCS-2', 60.0, 'AVAILABLE' FROM charging_stations LIMIT 1
        RETURNING port_id INTO v_port_id;
    END IF;

    -- Clean up any existing active session on this test port
    UPDATE charging_sessions SET session_status = 'COMPLETED' WHERE port_id = v_port_id AND session_status = 'ACTIVE';

    -- First user starts session:
    INSERT INTO charging_sessions (port_id, user_identifier, session_status)
    VALUES (v_port_id, 'USER_ALICE', 'ACTIVE');

    -- Second user attempts to start concurrent session on identical port:
    BEGIN
        INSERT INTO charging_sessions (port_id, user_identifier, session_status)
        VALUES (v_port_id, 'USER_BOB', 'ACTIVE');
        RAISE EXCEPTION 'TEST FAILED: Double-booking constraint failed to block second active session!';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'SUCCESS: PostgreSQL blocked concurrent active session on same port (uq_active_session_per_port).';
    END;

    -- Clean up test session
    UPDATE charging_sessions SET session_status = 'COMPLETED', end_time = NOW() 
    WHERE port_id = v_port_id AND user_identifier = 'USER_ALICE';
END $$;

-- TEST 2.5: Referential Integrity Deletion Protection
-- Business Rule: A port cannot be deleted while a session references it (ON DELETE RESTRICT).
-- Expected Outcome: ERROR: update or delete on table "charging_ports" violates foreign key constraint
DO $$
DECLARE
    v_port_id INT;
BEGIN
    RAISE NOTICE '--- TEST 2.5: Testing foreign key deletion guard (RESTRICT) ---';
    SELECT port_id INTO v_port_id FROM charging_sessions LIMIT 1;
    IF v_port_id IS NOT NULL THEN
        BEGIN
            DELETE FROM charging_ports WHERE port_id = v_port_id;
            RAISE EXCEPTION 'TEST FAILED: Port with session history was deleted!';
        EXCEPTION WHEN foreign_key_violation THEN
            RAISE NOTICE 'SUCCESS: PostgreSQL prevented deletion of port with dependent session records.';
        END;
    END IF;
END $$;

-- ============================================================================
-- SUMMARY OF CONSTRAINTS ENFORCED
-- 1. chk_latitude_range         -> Enforces coordinate bounds [-90, +90]
-- 2. chk_longitude_range        -> Enforces coordinate bounds [-180, +180]
-- 3. chk_connector_type         -> Enforces certified EV hardware connector standards
-- 4. chk_power_positive         -> Enforces realistic kW capacity (> 0)
-- 5. chk_port_status            -> Enforces valid finite state machine states
-- 6. uq_station_port_num        -> Enforces distinct port numbering per station
-- 7. chk_session_times          -> Enforces temporal sanity (end_time >= start_time)
-- 8. uq_active_session_per_port -> PARTIAL UNIQUE index preventing concurrent sessions
-- 9. FK ON DELETE RESTRICT      -> Protects audit trail & billing logs from orphaned records
-- ============================================================================
