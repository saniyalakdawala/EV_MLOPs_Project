-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 05_transactions.sql
-- Topic: Transaction Management, ACID Properties & Rollback Scenarios
-- Target Database: ev_db
-- ============================================================================

\c ev_db;

-- ============================================================================
-- SCENARIO 1: ATOMIC CHARGING SESSION START (SUCCESSFUL COMMIT)
-- Business Flow:
-- 1. Begin transaction
-- 2. Lock target port row using FOR UPDATE
-- 3. Verify port is AVAILABLE
-- 4. Transition port status to IN_USE
-- 5. Insert active charging session
-- 6. Insert status history audit record
-- 7. Commit transaction
-- ============================================================================

DO $$
DECLARE
    v_target_port_id INT;
    v_port_status VARCHAR(20);
    v_user_id VARCHAR(50) := 'USER_AKSHAY_MH01';
    v_session_id UUID;
BEGIN
    RAISE NOTICE '=======================================================';
    RAISE NOTICE 'SCENARIO 1: ATOMIC SESSION INITIATION (COMMIT)';
    RAISE NOTICE '=======================================================';

    -- Step 1: Select an AVAILABLE port and acquire ROW-LEVEL EXCLUSIVE LOCK
    SELECT port_id, status 
    INTO v_target_port_id, v_port_status
    FROM charging_ports
    WHERE status = 'AVAILABLE'
    LIMIT 1
    FOR UPDATE; -- Prevents concurrent modifications

    IF v_target_port_id IS NULL THEN
        RAISE EXCEPTION 'No AVAILABLE ports found for transaction test!';
    END IF;

    RAISE NOTICE 'Selected Port ID: %, Current Status: %', v_target_port_id, v_port_status;

    -- Step 2: Validate Availability
    IF v_port_status <> 'AVAILABLE' THEN
        RAISE EXCEPTION 'Port % is not available (Status: %)', v_target_port_id, v_port_status;
    END IF;

    -- Step 3: Transition Port Status to IN_USE
    UPDATE charging_ports
    SET status = 'IN_USE', updated_at = NOW()
    WHERE port_id = v_target_port_id;

    -- Step 4: Insert Active Charging Session
    INSERT INTO charging_sessions (
        port_id, user_identifier, start_time, session_status, energy_kwh
    ) VALUES (
        v_target_port_id, v_user_id, NOW(), 'ACTIVE', 0.0
    ) RETURNING session_id INTO v_session_id;

    -- Step 5: Insert Audit Trail Entry (also logged via trigger)
    INSERT INTO station_status_history (
        port_id, old_status, new_status, changed_at, reason
    ) VALUES (
        v_target_port_id, 'AVAILABLE', 'IN_USE', NOW(), 'Session initiated by ' || v_user_id
    );

    RAISE NOTICE 'SUCCESS: Charging session % created. Port % locked & IN_USE.', v_session_id, v_target_port_id;
    RAISE NOTICE 'Transaction COMMITTED cleanly.';
END $$;


-- ============================================================================
-- SCENARIO 2: ATOMIC CHARGING SESSION TERMINATION (SUCCESSFUL COMMIT)
-- Business Flow:
-- 1. Lock active session and associated port row
-- 2. Calculate elapsed duration and energy delivered (kWh)
-- 3. Update session end_time, energy_kwh, and session_status = 'COMPLETED'
-- 4. Transition port status back to 'AVAILABLE'
-- 5. Insert audit trail entry
-- 6. Commit transaction
-- ============================================================================

DO $$
DECLARE
    v_active_session_id UUID;
    v_port_id INT;
    v_kwh_delivered NUMERIC(8,2) := 28.45;
BEGIN
    RAISE NOTICE '=======================================================';
    RAISE NOTICE 'SCENARIO 2: ATOMIC SESSION TERMINATION (COMMIT)';
    RAISE NOTICE '=======================================================';

    -- Find an active session
    SELECT session_id, port_id 
    INTO v_active_session_id, v_port_id
    FROM charging_sessions
    WHERE session_status = 'ACTIVE'
    LIMIT 1
    FOR UPDATE;

    IF v_active_session_id IS NULL THEN
        RAISE NOTICE 'No active sessions to terminate.';
        RETURN;
    END IF;

    RAISE NOTICE 'Terminating Session: %, Port: %', v_active_session_id, v_port_id;

    -- Step 1: Lock and update port back to AVAILABLE
    UPDATE charging_ports
    SET status = 'AVAILABLE', updated_at = NOW()
    WHERE port_id = v_port_id;

    -- Step 2: Finalize session record
    UPDATE charging_sessions
    SET end_time = NOW(),
        energy_kwh = v_kwh_delivered,
        session_status = 'COMPLETED'
    WHERE session_id = v_active_session_id;

    -- Step 3: Record audit trail
    INSERT INTO station_status_history (
        port_id, old_status, new_status, changed_at, reason
    ) VALUES (
        v_port_id, 'IN_USE', 'AVAILABLE', NOW(), 'Session ' || v_active_session_id || ' completed cleanly'
    );

    RAISE NOTICE 'SUCCESS: Session finalized. Delivered % kWh. Port % released to AVAILABLE.', v_kwh_delivered, v_port_id;
END $$;


-- ============================================================================
-- SCENARIO 3: TRANSACTION FAILURE & AUTOMATIC ROLLBACK DEMONSTRATION
-- Demonstrates Atomicity & Consistency:
-- If an error occurs halfway through (e.g. invalid status or simulated hardware failure),
-- the ENTIRE transaction rolls back, leaving ZERO partial updates.
-- ============================================================================

DO $$
DECLARE
    v_test_port_id INT;
    v_initial_status VARCHAR(20);
    v_post_test_status VARCHAR(20);
    v_session_count_before INT;
    v_session_count_after INT;
BEGIN
    RAISE NOTICE '=======================================================';
    RAISE NOTICE 'SCENARIO 3: TRANSACTION ERROR & ROLLBACK PROOF';
    RAISE NOTICE '=======================================================';

    -- Pick a port for testing
    SELECT port_id, status INTO v_test_port_id, v_initial_status
    FROM charging_ports WHERE status = 'AVAILABLE' LIMIT 1;

    SELECT count(*) INTO v_session_count_before FROM charging_sessions;

    RAISE NOTICE 'BEFORE Transaction: Port % has status = ''%'' | Total sessions: %', 
                 v_test_port_id, v_initial_status, v_session_count_before;

    -- Begin simulated faulty transaction block:
    BEGIN
        -- Step 1: Update port to IN_USE
        UPDATE charging_ports SET status = 'IN_USE' WHERE port_id = v_test_port_id;

        -- Step 2: Insert charging session
        INSERT INTO charging_sessions (port_id, user_identifier, session_status)
        VALUES (v_test_port_id, 'USER_FAILURE_TEST', 'ACTIVE');

        -- Step 3: SIMULATE A FATAL RUNTIME / POWER METER HARDWARE EXCEPTION:
        RAISE EXCEPTION 'METER_HARDWARE_FAULT: Energy meter failed to communicate with dispensing unit!';

        -- Step 4: This code is never reached:
        COMMIT;

    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'CAUGHT EXCEPTION: "%"', SQLERRM;
        RAISE NOTICE 'Transaction was automatically ROLLED BACK by PostgreSQL engine.';
    END;

    -- Step 5: VERIFY ZERO RESIDUAL / DIRTY STATE
    SELECT status INTO v_post_test_status FROM charging_ports WHERE port_id = v_test_port_id;
    SELECT count(*) INTO v_session_count_after FROM charging_sessions;

    RAISE NOTICE 'AFTER Rollback: Port % status = ''%'' (Expected: ''%'')', 
                 v_test_port_id, v_post_test_status, v_initial_status;
    RAISE NOTICE 'AFTER Rollback: Total sessions = % (Expected: %)', 
                 v_session_count_after, v_session_count_before;

    IF v_post_test_status = v_initial_status AND v_session_count_before = v_session_count_after THEN
        RAISE NOTICE 'ACID ATOMICITY PROOF VERIFIED: No dirty records or partial updates remain!';
    ELSE
        RAISE EXCEPTION 'TEST FAILED: Data inconsistency detected after rollback!';
    END IF;
    RAISE NOTICE '=======================================================';
END $$;
