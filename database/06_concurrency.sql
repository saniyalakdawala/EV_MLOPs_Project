-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 06_concurrency.sql
-- Topic: Concurrency Control, Row-Level Locking (SELECT ... FOR UPDATE) & Isolation
-- Target Database: ev_db
-- ============================================================================

\c ev_db;

-- ============================================================================
-- THEORETICAL CONTEXT: LOST UPDATES & RACE CONDITIONS
-- In an EV charging network, if two drivers arrive at a single charging port 
-- and both tap "Start Charging" on their mobile app at the same millisecond:
-- Without concurrency control:
--   - Driver A reads status = 'AVAILABLE'
--   - Driver B reads status = 'AVAILABLE'
--   - Driver A updates status = 'IN_USE' and inserts active session
--   - Driver B updates status = 'IN_USE' and inserts active session
-- Result: Lost update / Double-booked port / Conflicting physical power allocation.
--
-- DBA SOLUTION: Pessimistic Row-Level Locking (SELECT ... FOR UPDATE)
-- When a user attempts to book a port, PostgreSQL acquires an EXCLUSIVE row lock
-- on that tuple in charging_ports. The second transaction BLOCKS until the first
-- commits or aborts. When unblocked, the second transaction sees the updated status
-- ('IN_USE') and safely rejects the duplicate request.
-- In addition, the partial unique index (uq_active_session_per_port) acts as an
-- immutable database engine safeguard.
-- ============================================================================

-- ============================================================================
-- MANUAL pgAdmin CONCURRENCY DEMONSTRATION STEPS
-- Open TWO separate Query Tool tabs in pgAdmin to simulate concurrent connections:
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TAB 1: CONNECTION 1 (Driver Alice)
-- ----------------------------------------------------------------------------
/*
BEGIN;

-- Alice selects port 5 and locks the row exclusively:
SELECT port_id, status, connector_type 
FROM charging_ports 
WHERE port_id = 5 
FOR UPDATE;

-- Simulate driver Alice plugging in the charging cable (take 10 seconds before committing):
SELECT pg_sleep(10);

-- Alice transitions port to IN_USE and inserts session:
UPDATE charging_ports SET status = 'IN_USE' WHERE port_id = 5;

INSERT INTO charging_sessions (port_id, user_identifier, session_status)
VALUES (5, 'DRIVER_ALICE', 'ACTIVE');

COMMIT;
*/

-- ----------------------------------------------------------------------------
-- TAB 2: CONNECTION 2 (Driver Bob) - Run immediately after Tab 1!
-- ----------------------------------------------------------------------------
/*
BEGIN;

-- Bob attempts to select the SAME port 5 with FOR UPDATE:
-- OBSERVATION: Query will HANG / WAIT until Tab 1 (Alice) finishes!
SELECT port_id, status, connector_type 
FROM charging_ports 
WHERE port_id = 5 
FOR UPDATE;

-- Once Alice commits, Bob's query returns: status = 'IN_USE'!
-- Bob's application logic inspects status:
DO $$
DECLARE
    v_status VARCHAR(20);
BEGIN
    SELECT status INTO v_status FROM charging_ports WHERE port_id = 5;
    IF v_status <> 'AVAILABLE' THEN
        RAISE EXCEPTION 'PORT_BUSY_CONFLICT: Port 5 is already IN_USE by another driver!';
    END IF;
END $$;

ROLLBACK;
*/

-- ============================================================================
-- AUTOMATED STORED PROCEDURE: Safe Transactional Session Initiation
-- Uses NOWAIT or SKIP LOCKED or standard blocking FOR UPDATE
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_start_charging_session(
    p_port_id INT,
    p_user_id VARCHAR(60)
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    session_id UUID
) AS $$
DECLARE
    v_status VARCHAR(20);
    v_new_session_id UUID;
BEGIN
    -- Acquire exclusive row lock on target port:
    -- Using FOR UPDATE NOWAIT immediately returns an error if another user is currently locking the row
    SELECT status INTO v_status
    FROM charging_ports
    WHERE port_id = p_port_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Port ID does not exist'::TEXT, NULL::UUID;
        RETURN;
    END IF;

    -- Verify Availability
    IF v_status <> 'AVAILABLE' THEN
        RETURN QUERY SELECT FALSE, ('Port is currently ' || v_status || '. Booking rejected.')::TEXT, NULL::UUID;
        RETURN;
    END IF;

    -- Transition port status
    UPDATE charging_ports
    SET status = 'IN_USE', updated_at = NOW()
    WHERE port_id = p_port_id;

    -- Create session record
    INSERT INTO charging_sessions (port_id, user_identifier, session_status)
    VALUES (p_port_id, p_user_id, 'ACTIVE')
    RETURNING charging_sessions.session_id INTO v_new_session_id;

    -- Return success
    RETURN QUERY SELECT TRUE, 'Charging session initiated successfully'::TEXT, v_new_session_id;
END;
$$ LANGUAGE plpgsql;

-- Test the procedure:
-- SELECT * FROM sp_start_charging_session(1, 'TEST_USER');
