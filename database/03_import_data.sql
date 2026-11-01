-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 03_import_data.sql
-- Description: ETL Data Ingestion, Staging, Cleaning & Verification Script
-- Target Database: ev_db
-- ============================================================================

\c ev_db;

-- ============================================================================
-- 1. INSPECT STAGING TABLE (Ingested from Python pipeline)
-- ============================================================================
SELECT 
    source_name,
    validation_status,
    count(*) AS total_records
FROM stg_charging_stations
GROUP BY source_name, validation_status
ORDER BY source_name, validation_status;

-- Inspect rejected records and error causes:
SELECT 
    staging_id,
    raw_station_id,
    station_name,
    latitude_raw,
    longitude_raw,
    validation_status,
    validation_error
FROM stg_charging_stations
WHERE validation_status = 'REJECTED'
LIMIT 10;

-- ============================================================================
-- 2. VERIFY NORMALIZED PRODUCTION DATA (3NF)
-- ============================================================================

-- A. Total Stations and Geographic Spread
SELECT 
    count(*) AS total_stations,
    count(CASE WHEN state = 'Maharashtra' THEN 1 END) AS maharashtra_stations,
    count(CASE WHEN city ILIKE '%Mumbai%' OR city ILIKE '%Thane%' OR city ILIKE '%Navi Mumbai%' THEN 1 END) AS mumbai_metro_stations,
    count(DISTINCT operator_name) AS distinct_operators
FROM charging_stations;

-- B. Station Count by Top Operators
SELECT 
    operator_name,
    count(*) AS station_count,
    round(count(*) * 100.0 / sum(count(*)) over(), 2) AS percentage_share
FROM charging_stations
GROUP BY operator_name
ORDER BY station_count DESC
LIMIT 10;

-- C. Charging Port Infrastructure Breakdown by Connector Standard
SELECT 
    connector_type,
    count(*) AS port_count,
    min(power_kw) AS min_power_kw,
    max(power_kw) AS max_power_kw,
    round(avg(power_kw), 1) AS avg_power_kw
FROM charging_ports
GROUP BY connector_type
ORDER BY port_count DESC;

-- D. Current Operational Availability Breakdown
SELECT 
    status,
    count(*) AS port_count,
    round(count(*) * 100.0 / sum(count(*)) over(), 2) AS percentage
FROM charging_ports
GROUP BY status
ORDER BY port_count DESC;

-- E. Active vs Historical Sessions Summary
SELECT 
    session_status,
    count(*) AS session_count,
    round(coalesce(sum(energy_kwh), 0.0), 2) AS total_energy_delivered_kwh,
    round(coalesce(avg(energy_kwh), 0.0), 2) AS avg_energy_per_session_kwh
FROM charging_sessions
GROUP BY session_status;

-- F. Sample Audit Trail in station_status_history
SELECT 
    h.history_id,
    p.port_id,
    s.station_name,
    p.connector_type,
    h.old_status,
    h.new_status,
    h.changed_at,
    h.reason
FROM station_status_history h
JOIN charging_ports p ON h.port_id = p.port_id
JOIN charging_stations s ON p.station_id = s.station_id
ORDER BY h.history_id DESC
LIMIT 10;
