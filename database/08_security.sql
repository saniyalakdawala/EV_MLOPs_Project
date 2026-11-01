-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 08_security.sql
-- Topic: Role-Based Access Control (RBAC), Least Privilege & Security Audit
-- Target Database: ev_db
-- ============================================================================

\c ev_db;

-- Revoke public permissions by default (hardening database):
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO PUBLIC;

-- ============================================================================
-- 1. ROLE DEFINITIONS
-- ============================================================================

-- Role 1: Database Administrator (ev_admin)
-- Scope: Full administrative authority over EV schema, DDL, maintenance, and backups
DROP ROLE IF EXISTS ev_admin;
CREATE ROLE ev_admin WITH 
    LOGIN 
    NOSUPERUSER 
    CREATEDB 
    NOCREATEROLE 
    INHERIT 
    PASSWORD 'AdminSecure2026!';

GRANT ALL PRIVILEGES ON SCHEMA public TO ev_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ev_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ev_admin;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ev_admin;

-- Role 2: Application Service User (ev_app_user)
-- Scope: Used by FastAPI backend for CRUD operations; NO DDL / DROP permissions
DROP ROLE IF EXISTS ev_app_user;
CREATE ROLE ev_app_user WITH 
    LOGIN 
    NOSUPERUSER 
    NOCREATEDB 
    NOCREATEROLE 
    NOINHERIT 
    PASSWORD 'AppServicePass2026!';

GRANT USAGE ON SCHEMA public TO ev_app_user;
-- Grant DML on operational tables only:
GRANT SELECT, INSERT, UPDATE, DELETE ON charging_stations, charging_ports, charging_sessions, station_status_history TO ev_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ev_app_user;
-- Explicitly deny DDL or staging table modification:
REVOKE ALL ON stg_charging_stations FROM ev_app_user;

-- Role 3: Read-Only Data Analyst (ev_analyst)
-- Scope: BI reporting, statistical queries, and dashboards; READ-ONLY (SELECT)
DROP ROLE IF EXISTS ev_analyst;
CREATE ROLE ev_analyst WITH 
    LOGIN 
    NOSUPERUSER 
    NOCREATEDB 
    NOCREATEROLE 
    NOINHERIT 
    PASSWORD 'AnalystReadOnly2026!';

GRANT USAGE ON SCHEMA public TO ev_analyst;
-- Read-only access to master data and analytics:
GRANT SELECT ON charging_stations, charging_ports, charging_sessions, station_status_history TO ev_analyst;
-- Explicitly ensure analyst cannot write or update:
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM ev_analyst;

-- Ensure future tables respect least-privilege defaults:
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ev_analyst;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ev_app_user;

-- ============================================================================
-- 2. VERIFICATION TESTS: LEAST PRIVILEGE ENFORCEMENT
-- ============================================================================

-- Review effective table privileges across roles:
SELECT 
    grantee, 
    table_name, 
    privilege_type
FROM information_schema.role_table_grants 
WHERE table_name IN ('charging_stations', 'charging_ports', 'charging_sessions', 'stg_charging_stations')
  AND grantee IN ('ev_admin', 'ev_app_user', 'ev_analyst')
ORDER BY grantee, table_name, privilege_type;

-- ----------------------------------------------------------------------------
-- DEMO TEST 1: Analyst can successfully SELECT data
-- ----------------------------------------------------------------------------
SET ROLE ev_analyst;
SELECT count(*) AS analyst_visible_stations FROM charging_stations;

-- ----------------------------------------------------------------------------
-- DEMO TEST 2: Analyst is BLOCKED from modifying data (EXPECTED ERROR)
-- Expected Outcome: ERROR: permission denied for table charging_ports
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    BEGIN
        UPDATE charging_ports SET status = 'AVAILABLE' WHERE port_id = 1;
        RAISE EXCEPTION 'SECURITY BREACH: Analyst was able to execute UPDATE!';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'SUCCESS: PostgreSQL correctly denied UPDATE permission to ev_analyst.';
    END;
END $$;

-- Reset session authorization to superuser:
RESET ROLE;
