-- ============================================================================
-- ADBMS Project: Smart EV Charging Infrastructure Database
-- File: 04_spatial_queries.sql
-- Primary Track: GIS & Spatial Database Operations
-- Target Database: ev_db
-- ============================================================================

\c ev_db;

-- Reference Location for Demonstrations:
-- Bandra Kurla Complex (BKC), Mumbai
-- Latitude:  19.065716
-- Longitude: 72.868725

-- ============================================================================
-- 1. POSTGIS SPATIAL FUNCTIONS DEMONSTRATION
-- (Requires PostGIS extension activated; see Section 2 for portable SQL fallback)
-- ============================================================================

-- QUERY 1.1: RADIUS SEARCH (Find all EV stations within 10 km of BKC, Mumbai)
-- Uses PostGIS ST_DWithin on WGS-84 geography (distance evaluated in meters)
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.address,
    s.city,
    round((ST_Distance(s.geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography) / 1000.0)::numeric, 2) AS distance_km,
    count(p.port_id) AS total_ports,
    count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports
FROM charging_stations s
LEFT JOIN charging_ports p ON s.station_id = p.station_id
WHERE s.geom IS NOT NULL 
  AND ST_DWithin(s.geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography, 10000) -- 10,000 meters = 10 km
GROUP BY s.station_id, s.station_name, s.operator_name, s.address, s.city, s.geom
ORDER BY distance_km ASC;

-- QUERY 1.2: NEAREST AVAILABLE STATION WITH CCS-2 FAST CHARGER (>= 50 kW)
-- Combines spatial distance sorting with relational availability and hardware constraints
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.address,
    p.port_id,
    p.connector_type,
    p.power_kw,
    p.status,
    round((ST_Distance(s.geom, ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography) / 1000.0)::numeric, 2) AS distance_km
FROM charging_stations s
JOIN charging_ports p ON s.station_id = p.station_id
WHERE p.status = 'AVAILABLE'
  AND p.connector_type = 'CCS-2'
  AND p.power_kw >= 50.0
  AND s.geom IS NOT NULL
ORDER BY s.geom <-> ST_SetSRID(ST_MakePoint(72.868725, 19.065716), 4326)::geography
LIMIT 5;

-- QUERY 1.3: MULTI-CRITERIA FILTER (Area + Connector + Minimum Power + Operator)
SELECT 
    s.station_name,
    s.city,
    s.operator_name,
    p.port_number,
    p.connector_type,
    p.power_kw,
    p.status
FROM charging_stations s
JOIN charging_ports p ON s.station_id = p.station_id
WHERE s.state = 'Maharashtra'
  AND p.connector_type IN ('CCS-2', 'Type 2 AC')
  AND p.power_kw >= 22.0
  AND p.status = 'AVAILABLE'
ORDER BY p.power_kw DESC, s.station_name ASC
LIMIT 15;

-- ============================================================================
-- 2. PORTABLE HAVERSINE GEODESIC QUERY (Runs on any PostgreSQL without extensions)
-- Formula: d = 2R * asin(sqrt(sin²(Δφ/2) + cos(φ1)cos(φ2)sin²(Δλ/2)))
-- Earth radius R = 6371 km
-- ============================================================================
SELECT 
    s.station_id,
    s.station_name,
    s.operator_name,
    s.city,
    s.latitude,
    s.longitude,
    round((
        6371.0 * 2.0 * asin(sqrt(
            power(sin(radians(s.latitude - 19.065716) / 2.0), 2) +
            cos(radians(19.065716)) * cos(radians(s.latitude)) *
            power(sin(radians(s.longitude - 72.868725) / 2.0), 2)
        ))
    )::numeric, 2) AS haversine_distance_km,
    count(p.port_id) AS total_ports,
    count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports
FROM charging_stations s
LEFT JOIN charging_ports p ON s.station_id = p.station_id
WHERE s.state = 'Maharashtra'
GROUP BY s.station_id, s.station_name, s.operator_name, s.city, s.latitude, s.longitude
HAVING (
    6371.0 * 2.0 * asin(sqrt(
        power(sin(radians(s.latitude - 19.065716) / 2.0), 2) +
        cos(radians(19.065716)) * cos(radians(s.latitude)) *
        power(sin(radians(s.longitude - 72.868725) / 2.0), 2)
    ))
) <= 25.0 -- 25 km radius
ORDER BY haversine_distance_km ASC;

-- ============================================================================
-- 3. EXPLAIN ANALYZE: SPATIAL QUERY PERFORMANCE
-- Comparing execution plans with and without spatial indexing
-- ============================================================================

-- Plan A: Query Plan for Radius Distance Evaluation
EXPLAIN ANALYZE
SELECT station_id, station_name, latitude, longitude
FROM charging_stations
WHERE latitude BETWEEN 18.80 AND 19.30
  AND longitude BETWEEN 72.70 AND 73.20;

-- Plan B: Join Query Plan between Stations and Available Ports
EXPLAIN ANALYZE
SELECT 
    s.station_name, 
    p.connector_type, 
    p.power_kw, 
    p.status
FROM charging_stations s
JOIN charging_ports p ON s.station_id = p.station_id
WHERE s.state = 'Maharashtra'
  AND p.status = 'AVAILABLE';
