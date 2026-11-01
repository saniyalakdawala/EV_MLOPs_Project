"""
PostGIS Activation and Spatial Indexing Script
Target Database: ev_db
"""
import psycopg2

DB_CONFIG = {
    'dbname': 'ev_db',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': 5432
}

def activate_postgis():
    print("=" * 60)
    print("ACTIVATING POSTGIS EXTENSION & SPATIAL GEOMETRY")
    print("=" * 60)
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # 1. Enable extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        conn.commit()
        print("[SUCCESS] PostGIS extension enabled in ev_db!")
        
        # 2. Check version
        cur.execute("SELECT PostGIS_Version();")
        version = cur.fetchone()[0]
        print(f"[VERSION] PostGIS Version: {version}")
        
        # 3. Add geom geography column if missing
        cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='charging_stations' AND column_name='geom'
            ) THEN
                ALTER TABLE charging_stations ADD COLUMN geom geography(Point, 4326);
            END IF;
        END $$;
        """)
        conn.commit()
        print("[SUCCESS] Column 'geom geography(Point, 4326)' verified on charging_stations.")
        
        # 4. Populate geometry from longitude and latitude
        print("Populating PostGIS geography points for all stations...")
        cur.execute("""
        UPDATE charging_stations 
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        WHERE geom IS NULL;
        """)
        updated_count = cur.rowcount
        conn.commit()
        print(f"[SUCCESS] Populated {updated_count} spatial geography points.")
        
        # 5. Build Spatial GiST Index
        print("Building spatial GiST index (idx_stations_spatial_gist)...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stations_spatial_gist ON charging_stations USING GIST (geom);")
        conn.commit()
        print("[SUCCESS] Spatial GiST index created!")
        
        # 6. Verify Sample Spatial Query (Distance from Gateway of India, Mumbai)
        cur.execute("""
        SELECT 
            station_name, 
            city,
            round((ST_Distance(geom, ST_SetSRID(ST_MakePoint(72.8347, 18.9220), 4326)::geography) / 1000.0)::numeric, 2) AS distance_km
        FROM charging_stations
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(72.8347, 18.9220), 4326)::geography
        LIMIT 5;
        """)
        nearest = cur.fetchall()
        print("\nVerification Test: 5 Nearest EV Stations to Gateway of India, Mumbai:")
        for idx, (name, city, dist) in enumerate(nearest, 1):
            print(f"  {idx}. {name} ({city}) — {dist} km away")
            
        print("=" * 60)
        print("POSTGIS SETUP COMPLETE AND OPERATIONAL!")
        print("=" * 60)
        return True
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] PostGIS activation: {e}")
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    activate_postgis()
