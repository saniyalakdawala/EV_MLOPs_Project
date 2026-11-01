"""
Stations API Router
GIS-based spatial search, nearby station radius queries, and multi-criteria filters.
Supports both MMR (default) and All-India National scope without modifying production tables.
"""
from typing import List, Optional, Union
import math
from fastapi import APIRouter, HTTPException, Query
from app.database import get_db_connection
from app.models import StationSummary, StationDetail, PortSchema, OverviewStats

router = APIRouter(prefix="/api/stations", tags=["Stations"])

@router.get("/overview", response_model=OverviewStats)
def get_overview_statistics():
    """Returns top-level operational and infrastructure statistics."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Station counts
            cur.execute("""
            SELECT 
                count(*) AS total_stations,
                count(CASE WHEN state = 'Maharashtra' THEN 1 END) AS maharashtra_stations,
                count(CASE WHEN city ILIKE '%Mumbai%' OR city ILIKE '%Thane%' OR city ILIKE '%Navi Mumbai%' THEN 1 END) AS mumbai_metro_stations
            FROM charging_stations;
            """)
            st_stats = cur.fetchone()

            # Port counts
            cur.execute("""
            SELECT 
                count(*) AS total_ports,
                count(CASE WHEN status = 'AVAILABLE' THEN 1 END) AS available_ports,
                count(CASE WHEN status = 'IN_USE' THEN 1 END) AS in_use_ports,
                count(CASE WHEN status IN ('OUT_OF_SERVICE', 'MAINTENANCE') THEN 1 END) AS out_of_service_ports
            FROM charging_ports;
            """)
            port_stats = cur.fetchone()

            # Session stats
            cur.execute("""
            SELECT 
                count(CASE WHEN session_status = 'ACTIVE' THEN 1 END) AS active_sessions,
                coalesce(sum(energy_kwh), 0.0) AS total_energy
            FROM charging_sessions;
            """)
            session_stats = cur.fetchone()

            # National staging count
            cur.execute("""
                SELECT count(*) AS tbl_cnt FROM information_schema.tables 
                WHERE table_name = 'stg_national_master_ev_stations';
            """)
            has_national = cur.fetchone()['tbl_cnt'] > 0
            national_count = 0
            if has_national:
                cur.execute("SELECT count(*) AS nat_cnt FROM stg_national_master_ev_stations;")
                national_count = cur.fetchone()['nat_cnt']

            return OverviewStats(
                total_stations=st_stats['total_stations'],
                maharashtra_stations=st_stats['maharashtra_stations'],
                mumbai_metro_stations=st_stats['mumbai_metro_stations'],
                total_national_stations=national_count,
                total_ports=port_stats['total_ports'],
                available_ports=port_stats['available_ports'],
                in_use_ports=port_stats['in_use_ports'],
                out_of_service_ports=port_stats['out_of_service_ports'],
                active_sessions=session_stats['active_sessions'],
                total_energy_delivered_kwh=round(float(session_stats['total_energy']), 2)
            )

@router.get("/nearby", response_model=List[StationSummary])
def find_nearby_stations(
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="User Latitude (e.g. 19.0760 for Mumbai)"),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="User Longitude (e.g. 72.8777 for Mumbai)"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Alias for lat"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Alias for lon"),
    radius_km: float = Query(15.0, gt=0, le=2000.0, description="Search radius in kilometers"),
    connector_type: Optional[str] = Query(None, description="Optional connector filter (e.g. CCS-2)"),
    min_power_kw: Optional[float] = Query(None, ge=0.0, description="Minimum power in kW"),
    scope: str = Query('mmr', description="Scope filter: 'mmr' (default) or 'all' (National)"),
    limit: int = Query(50, ge=1, le=500)
):
    """
    GIS Spatial Query: Finds EV charging stations within a specified radius (km) of user coordinates.
    Calculates exact geodesic distance using PostGIS / spatial GiST indexing and spherical trigonometry.
    Supports 'scope=mmr' (default: 16 verified MMR stations) and 'scope=all' (National master dataset).
    """
    eff_lat = lat if lat is not None else latitude
    eff_lon = lon if lon is not None else longitude
    if eff_lat is None or eff_lon is None:
        raise HTTPException(status_code=422, detail="Both latitude ('lat' or 'latitude') and longitude ('lon' or 'longitude') are required.")
    lat, lon = eff_lat, eff_lon

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if scope.lower() == 'all':
                # Query from national staging table
                query = """
                SELECT 
                    s.station_id,
                    s.station_name,
                    coalesce(s.operator, 'unknown') AS operator_name,
                    s.address,
                    s.city,
                    s.state,
                    '' AS postal_code,
                    s.latitude::float,
                    s.longitude::float,
                    coalesce(array_length(string_to_array(s.connector_types, '; '), 1), 1) AS total_ports,
                    0 AS available_ports,
                    FALSE AS has_live_status,
                    string_to_array(s.connector_types, '; ') AS connector_types,
                    ARRAY[]::float[] AS power_outputs,
                    NULL::float AS max_power_kw,
                    s.is_inside_mmr,
                    round((
                        6371.0 * 2.0 * asin(sqrt(
                            power(sin(radians(s.latitude - %s) / 2.0), 2) +
                            cos(radians(%s)) * cos(radians(s.latitude)) *
                            power(sin(radians(s.longitude - %s) / 2.0), 2)
                        ))
                    )::numeric, 2) AS distance_km
                FROM stg_national_master_ev_stations s
                WHERE 1=1
                """
                params = [lat, lat, lon]
                if connector_type:
                    query += " AND s.connector_types ILIKE %s"
                    params.append(f"%{connector_type}%")

                query += """
                ORDER BY distance_km ASC
                LIMIT %s;
                """
                params.append(limit)

                cur.execute(query, params)
                rows = cur.fetchall()
                results = []
                for r in rows:
                    rd = dict(r)
                    if rd['distance_km'] is not None and float(rd['distance_km']) <= radius_km:
                        results.append(StationSummary(**rd))
                return results

            # Default: MMR production table
            cur.execute("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'charging_stations' AND column_name = 'geom'
            """)
            has_geom = cur.fetchone() is not None

            dlat = radius_km / 111.32
            cos_lat = max(0.01, math.cos(math.radians(lat)))
            dlon = radius_km / (111.32 * cos_lat)
            min_lat, max_lat = lat - dlat, lat + dlat
            min_lon, max_lon = lon - dlon, lon + dlon

            if has_geom:
                query = """
                SELECT 
                    s.station_id,
                    s.station_name,
                    s.operator_name,
                    s.address,
                    s.city,
                    s.state,
                    s.postal_code,
                    s.latitude,
                    s.longitude,
                    count(p.port_id) AS total_ports,
                    count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports,
                    FALSE AS has_live_status,
                    array_remove(array_agg(DISTINCT p.connector_type), NULL) AS connector_types,
                    array_remove(array_agg(DISTINCT p.power_kw::float), NULL) AS power_outputs,
                    max(p.power_kw::float) AS max_power_kw,
                    TRUE AS is_inside_mmr,
                    round((ST_Distance(s.geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) / 1000.0)::numeric, 2) AS distance_km
                FROM charging_stations s
                JOIN charging_ports p ON s.station_id = p.station_id
                WHERE s.geom IS NOT NULL
                  AND ST_DWithin(s.geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s * 1000.0)
                """
                params = [lon, lat, lon, lat, radius_km]
                if connector_type:
                    query += " AND p.connector_type = %s"
                    params.append(connector_type)
                if min_power_kw is not None:
                    query += " AND p.power_kw >= %s"
                    params.append(min_power_kw)

                query += """
                GROUP BY s.station_id, s.station_name, s.operator_name, s.address, s.city, s.state, s.postal_code, s.latitude, s.longitude, s.geom
                ORDER BY distance_km ASC
                LIMIT %s;
                """
                params.append(limit)
            else:
                query = """
                SELECT 
                    s.station_id,
                    s.station_name,
                    s.operator_name,
                    s.address,
                    s.city,
                    s.state,
                    s.postal_code,
                    s.latitude,
                    s.longitude,
                    count(p.port_id) AS total_ports,
                    count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports,
                    FALSE AS has_live_status,
                    array_remove(array_agg(DISTINCT p.connector_type), NULL) AS connector_types,
                    array_remove(array_agg(DISTINCT p.power_kw::float), NULL) AS power_outputs,
                    max(p.power_kw::float) AS max_power_kw,
                    TRUE AS is_inside_mmr,
                    round((
                        6371.0 * 2.0 * asin(sqrt(
                            power(sin(radians(s.latitude - %s) / 2.0), 2) +
                            cos(radians(%s)) * cos(radians(s.latitude)) *
                            power(sin(radians(s.longitude - %s) / 2.0), 2)
                        ))
                    )::numeric, 2) AS distance_km
                FROM charging_stations s
                JOIN charging_ports p ON s.station_id = p.station_id
                WHERE point(s.longitude, s.latitude) <@ box(point(%s, %s), point(%s, %s))
                """
                params = [lat, lat, lon, min_lon, min_lat, max_lon, max_lat]
                if connector_type:
                    query += " AND p.connector_type = %s"
                    params.append(connector_type)
                if min_power_kw is not None:
                    query += " AND p.power_kw >= %s"
                    params.append(min_power_kw)

                query += """
                GROUP BY s.station_id, s.station_name, s.operator_name, s.address, s.city, s.state, s.postal_code, s.latitude, s.longitude
                HAVING (
                    6371.0 * 2.0 * asin(sqrt(
                        power(sin(radians(s.latitude - %s) / 2.0), 2) +
                        cos(radians(%s)) * cos(radians(s.latitude)) *
                        power(sin(radians(s.longitude - %s) / 2.0), 2)
                    ))
                ) <= %s
                ORDER BY distance_km ASC
                LIMIT %s;
                """
                params.extend([lat, lat, lon, radius_km, limit])

            cur.execute(query, params)
            rows = cur.fetchall()
            return [StationSummary(**dict(r)) for r in rows]

@router.get("", response_model=List[StationSummary])
def search_stations(
    search: Optional[str] = Query(None, description="Search term for station name, operator, or address"),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    connector_type: Optional[str] = Query(None, description="Filter by connector standard"),
    min_power_kw: Optional[float] = Query(None, ge=0.0, description="Minimum power rating in kW"),
    available_only: bool = Query(False, description="Filter for stations having at least 1 AVAILABLE port"),
    scope: str = Query('mmr', description="Scope filter: 'mmr' (default) or 'all' (National)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Search and filter charging stations across cities, operators, and connector capacities.
    Supports 'scope=mmr' (default: 16 MMR stations) and 'scope=all' (National master dataset).
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if scope.lower() == 'all':
                query = """
                SELECT 
                    s.station_id,
                    s.station_name,
                    coalesce(s.operator, 'unknown') AS operator_name,
                    s.address,
                    s.city,
                    s.state,
                    '' AS postal_code,
                    s.latitude::float,
                    s.longitude::float,
                    coalesce(array_length(string_to_array(s.connector_types, '; '), 1), 1) AS total_ports,
                    0 AS available_ports,
                    FALSE AS has_live_status,
                    string_to_array(s.connector_types, '; ') AS connector_types,
                    ARRAY[]::float[] AS power_outputs,
                    NULL::float AS max_power_kw,
                    s.is_inside_mmr
                FROM stg_national_master_ev_stations s
                WHERE 1=1
                """
                params = []
                if search:
                    query += " AND (s.station_name ILIKE %s OR s.address ILIKE %s OR s.operator ILIKE %s)"
                    term = f"%{search}%"
                    params.extend([term, term, term])
                if city:
                    query += " AND s.city ILIKE %s"
                    params.append(f"%{city}%")
                if state:
                    query += " AND s.state ILIKE %s"
                    params.append(f"%{state}%")
                if connector_type:
                    query += " AND s.connector_types ILIKE %s"
                    params.append(f"%{connector_type}%")

                query += " ORDER BY s.is_inside_mmr DESC, s.station_name ASC LIMIT %s OFFSET %s;"
                params.extend([limit, offset])

                cur.execute(query, params)
                rows = cur.fetchall()
                return [StationSummary(**dict(r)) for r in rows]

            # Default: MMR production table
            query = """
            SELECT 
                s.station_id,
                s.station_name,
                s.operator_name,
                s.address,
                s.city,
                s.state,
                s.postal_code,
                s.latitude,
                s.longitude,
                count(p.port_id) AS total_ports,
                count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) AS available_ports,
                FALSE AS has_live_status,
                array_remove(array_agg(DISTINCT p.connector_type), NULL) AS connector_types,
                array_remove(array_agg(DISTINCT p.power_kw::float), NULL) AS power_outputs,
                max(p.power_kw::float) AS max_power_kw,
                TRUE AS is_inside_mmr
            FROM charging_stations s
            JOIN charging_ports p ON s.station_id = p.station_id
            WHERE 1=1
            """
            params = []

            if search:
                query += " AND (s.station_name ILIKE %s OR s.address ILIKE %s OR s.operator_name ILIKE %s)"
                term = f"%{search}%"
                params.extend([term, term, term])

            if city:
                query += " AND s.city ILIKE %s"
                params.append(f"%{city}%")

            if state:
                query += " AND s.state ILIKE %s"
                params.append(f"%{state}%")

            if connector_type:
                query += " AND p.connector_type = %s"
                params.append(connector_type)

            if min_power_kw is not None:
                query += " AND p.power_kw >= %s"
                params.append(min_power_kw)

            query += """
            GROUP BY s.station_id, s.station_name, s.operator_name, s.address, s.city, s.state, s.postal_code, s.latitude, s.longitude
            """

            if available_only:
                query += " HAVING count(CASE WHEN p.status = 'AVAILABLE' THEN 1 END) > 0"

            query += " ORDER BY s.station_name ASC LIMIT %s OFFSET %s;"
            params.extend([limit, offset])

            cur.execute(query, params)
            rows = cur.fetchall()
            return [StationSummary(**dict(r)) for r in rows]

@router.get("/{station_id}", response_model=StationDetail)
def get_station_detail(station_id: Union[int, str]):
    """
    Returns full details for a single station, including all attached ports and live availability.
    Checks production charging_stations first; falls back to stg_national_master_ev_stations.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            is_int_id = False
            int_id = None
            try:
                int_id = int(station_id)
                is_int_id = True
            except ValueError:
                pass

            if is_int_id:
                cur.execute("""
                SELECT 
                    station_id, station_name, operator_name, address, city, state, postal_code, latitude, longitude
                FROM charging_stations
                WHERE station_id = %s;
                """, (int_id,))
                st = cur.fetchone()

                if st:
                    cur.execute("""
                    SELECT 
                        port_id, station_id, port_number, connector_type, power_kw, status, updated_at
                    FROM charging_ports
                    WHERE station_id = %s
                    ORDER BY port_number ASC;
                    """, (int_id,))
                    ports_data = cur.fetchall()

                    ports = [PortSchema(**dict(p)) for p in ports_data]
                    avail = sum(1 for p in ports if p.status == 'AVAILABLE')

                    return StationDetail(
                        station_id=st['station_id'],
                        station_name=st['station_name'],
                        operator_name=st['operator_name'],
                        address=st['address'],
                        city=st['city'],
                        state=st['state'],
                        postal_code=st['postal_code'],
                        latitude=float(st['latitude']),
                        longitude=float(st['longitude']),
                        total_ports=len(ports),
                        available_ports=avail,
                        has_live_status=False,
                        is_inside_mmr=True,
                        ports=ports
                    )

            # Check national staging table
            cur.execute("""
            SELECT 
                station_id, station_name, operator, address, city, state, latitude, longitude,
                connector_types, is_inside_mmr
            FROM stg_national_master_ev_stations
            WHERE station_id = %s;
            """, (str(station_id),))
            nat_st = cur.fetchone()

            if not nat_st:
                raise HTTPException(status_code=404, detail=f"Charging Station with ID {station_id} not found")

            # Parse recorded connectors for national staging records
            conns = [c.strip() for c in (nat_st['connector_types'] or '').split('; ') if c.strip()]
            if not conns:
                conns = ['Standard Connector']
            stg_ports = []
            for p_idx, c_type in enumerate(conns, 1):
                stg_ports.append(PortSchema(
                    port_id=p_idx,
                    station_id=nat_st['station_id'],
                    port_number=p_idx,
                    connector_type=c_type,
                    power_kw=0.0,
                    status='STATUS_UNVERIFIED'
                ))

            return StationDetail(
                station_id=nat_st['station_id'],
                station_name=nat_st['station_name'],
                operator_name=nat_st['operator'] or 'unknown',
                address=nat_st['address'],
                city=nat_st['city'],
                state=nat_st['state'],
                postal_code='',
                latitude=float(nat_st['latitude']),
                longitude=float(nat_st['longitude']),
                total_ports=len(stg_ports),
                available_ports=0,
                has_live_status=False,
                is_inside_mmr=nat_st['is_inside_mmr'],
                ports=stg_ports
            )

