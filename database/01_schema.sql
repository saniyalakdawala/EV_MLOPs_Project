-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 01_schema.sql
-- Description: Database Schema Definition (DDL) for EV Charging Infrastructure
-- Target Database: ev_db
-- Author: B.Tech Data Science Student
-- ============================================================================

-- 1. Enable Spatial and Cryptographic Extensions
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS postgis;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'PostGIS extension not yet present in PostgreSQL directory. Run install_postgis.bat or StackBuilder to activate.';
END $$;

-- pgcrypto provides gen_random_uuid() and cryptographic functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- btree_gist enables GiST indexing for mixed spatial and scalar attributes
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Drop existing tables if rebuilding (in reverse order of foreign keys)
DROP TABLE IF EXISTS station_status_history CASCADE;
DROP TABLE IF EXISTS charging_sessions CASCADE;
DROP TABLE IF EXISTS charging_ports CASCADE;
DROP TABLE IF EXISTS charging_stations CASCADE;
DROP TABLE IF EXISTS stg_charging_stations CASCADE;

-- ============================================================================
-- Staging Table: stg_charging_stations
-- Used during ETL ingestion pipeline to safely load untrusted external feeds
-- (OpenChargeMap, NITI Aayog GeoJSON) prior to validation and normalization.
-- ============================================================================
CREATE TABLE stg_charging_stations (
    staging_id BIGSERIAL PRIMARY KEY,
    raw_station_id VARCHAR(100),
    station_name TEXT,
    operator_name TEXT,
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(50),
    latitude_raw TEXT,
    longitude_raw TEXT,
    connector_type TEXT,
    power_kw_raw TEXT,
    number_of_ports_raw TEXT,
    source_name VARCHAR(100) DEFAULT 'OpenChargeMap',
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    validation_status VARCHAR(20) DEFAULT 'PENDING',
    validation_error TEXT
);

COMMENT ON TABLE stg_charging_stations IS 'ETL Staging table for raw external EV station datasets before validation and loading into 3NF schema';

-- ============================================================================
-- Production Table 1: charging_stations
-- Normalized table storing static geographic and operator metadata.
-- Coordinates are stored both as scalar decimals (for API consumers) and
-- PostGIS geography(Point, 4326) for true geodesic distance queries.
-- ============================================================================
CREATE TABLE charging_stations (
    station_id SERIAL PRIMARY KEY,
    station_name VARCHAR(150) NOT NULL,
    operator_name VARCHAR(100) NOT NULL,
    address TEXT,
    city VARCHAR(60) NOT NULL,
    state VARCHAR(60) NOT NULL,
    postal_code VARCHAR(12),
    latitude NUMERIC(9,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    source_name VARCHAR(50) DEFAULT 'OpenChargeMap',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),

    -- Coordinate bounds validation
    CONSTRAINT chk_latitude_range CHECK (latitude >= -90.0 AND latitude <= 90.0),
    CONSTRAINT chk_longitude_range CHECK (longitude >= -180.0 AND longitude <= 180.0)
);

-- Conditionally attach PostGIS geography column if PostGIS extension is installed
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'geography') THEN
        ALTER TABLE charging_stations ADD COLUMN IF NOT EXISTS geom geography(Point, 4326);
        EXECUTE 'COMMENT ON COLUMN charging_stations.geom IS ''PostGIS spatial geography point (SRID 4326) calculated from longitude and latitude'';';
    END IF;
END $$;

COMMENT ON TABLE charging_stations IS 'Master table of EV charging stations with WGS-84 coordinates and PostGIS spatial point';

-- Trigger to automatically synchronize PostGIS geom column on INSERT or UPDATE of coordinates
CREATE OR REPLACE FUNCTION trg_sync_station_geom()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated := NOW();
    -- If PostGIS functions exist, synchronize spatial geography point
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'st_setsrid') THEN
        EXECUTE 'SELECT ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography'
        INTO NEW.geom
        USING NEW.longitude, NEW.latitude;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stations_geom_update
BEFORE INSERT OR UPDATE OF latitude, longitude ON charging_stations
FOR EACH ROW
EXECUTE FUNCTION trg_sync_station_geom();

-- ============================================================================
-- Production Table 2: charging_ports
-- Physical charging connectors / dispensers available at each station.
-- Tracks hardware connector standard, max power output, and live status.
-- ============================================================================
CREATE TABLE charging_ports (
    port_id SERIAL PRIMARY KEY,
    station_id INT NOT NULL REFERENCES charging_stations(station_id) ON DELETE CASCADE,
    port_number INT NOT NULL,
    connector_type VARCHAR(40) NOT NULL,
    power_kw NUMERIC(6,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Connector standard validation (Indian EV Standards / AIS-138)
    CONSTRAINT chk_connector_type CHECK (
        connector_type IN ('CCS-2', 'Type 2 AC', 'CHAdeMO', 'GB/T', 'Bharat AC-001', 'Bharat DC-001')
    ),
    -- Power output must be strictly positive
    CONSTRAINT chk_power_positive CHECK (power_kw > 0.0),
    -- Operational status finite state machine
    CONSTRAINT chk_port_status CHECK (
        status IN ('AVAILABLE', 'IN_USE', 'OUT_OF_SERVICE', 'MAINTENANCE')
    ),
    -- Port numbering unique per station
    CONSTRAINT uq_station_port_num UNIQUE (station_id, port_number)
);

COMMENT ON TABLE charging_ports IS 'Individual charging ports/connectors belonging to a charging station';
COMMENT ON COLUMN charging_ports.status IS 'Current operational status (AVAILABLE, IN_USE, OUT_OF_SERVICE, MAINTENANCE)';

-- ============================================================================
-- Production Table 3: charging_sessions
-- Operational charging sessions. Tracks start, end, energy consumption (kWh),
-- and status. Uses row-level transactions and locking during session lifecycle.
-- ============================================================================
CREATE TABLE charging_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    port_id INT NOT NULL REFERENCES charging_ports(port_id) ON DELETE RESTRICT,
    user_identifier VARCHAR(60) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    energy_kwh NUMERIC(8,2) DEFAULT 0.0,
    session_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',

    -- End time cannot precede start time
    CONSTRAINT chk_session_times CHECK (end_time IS NULL OR end_time >= start_time),
    -- Energy cannot be negative
    CONSTRAINT chk_energy_positive CHECK (energy_kwh >= 0.0),
    -- Finite session states
    CONSTRAINT chk_session_status CHECK (session_status IN ('ACTIVE', 'COMPLETED', 'ABORTED'))
);

COMMENT ON TABLE charging_sessions IS 'Transactional EV charging sessions with energy metering';

-- CRITICAL ADBMS CONSTRAINT:
-- Ensure that a port cannot have more than ONE active charging session simultaneously.
-- A standard unique constraint would block historical sessions; a PARTIAL unique index
-- enforces uniqueness ONLY where session_status = 'ACTIVE'.
CREATE UNIQUE INDEX uq_active_session_per_port 
ON charging_sessions (port_id) 
WHERE session_status = 'ACTIVE';

-- ============================================================================
-- Production Table 4: station_status_history
-- Temporal audit table recording every status transition of every port.
-- Preserves timestamps, previous state, and reason for complete DBA traceability.
-- ============================================================================
CREATE TABLE station_status_history (
    history_id BIGSERIAL PRIMARY KEY,
    port_id INT NOT NULL REFERENCES charging_ports(port_id) ON DELETE CASCADE,
    old_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason VARCHAR(150),

    CONSTRAINT chk_hist_new_status CHECK (
        new_status IN ('AVAILABLE', 'IN_USE', 'OUT_OF_SERVICE', 'MAINTENANCE')
    )
);

COMMENT ON TABLE station_status_history IS 'Temporal status change log for port availability tracking and SLA reporting';

-- Automated trigger to record status transitions in station_status_history
CREATE OR REPLACE FUNCTION trg_log_port_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE' AND OLD.status IS DISTINCT FROM NEW.status) THEN
        INSERT INTO station_status_history (port_id, old_status, new_status, changed_at, reason)
        VALUES (NEW.port_id, OLD.status, NEW.status, NOW(), 'Automatic trigger: port status updated');
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO station_status_history (port_id, old_status, new_status, changed_at, reason)
        VALUES (NEW.port_id, NULL, NEW.status, NOW(), 'Initial port provisioning');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ports_status_audit
AFTER INSERT OR UPDATE OF status ON charging_ports
FOR EACH ROW
EXECUTE FUNCTION trg_log_port_status_change();
