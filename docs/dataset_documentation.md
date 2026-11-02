# Dataset Documentation, Data Lineage & Geographic Coverage Audit

## 1. Overview & Provenance

This database integrates real-world EV charging station location and infrastructure datasets for India, with special emphasis on the **Mumbai Metropolitan Region (MMR)** and **Maharashtra State**.

| Dataset Attribute | Value |
| :--- | :--- |
| **Multi-Source Lineage** | Bureau of Energy Efficiency (BEE), OpenChargeMap (OCM), NITI Aayog / E-Amrit, OpenStreetMap (OSM) |
| **BEE Ministry of Power Source** | Official Census till 26th October 2025 (`data/raw/bee_india_ev_charging_stations.json`) |
| **OpenChargeMap Source** | Dataset export (`data/raw/ocm_all_india.json`) |
| **NITI Aayog / E-Amrit Source** | Official National Portal GeoJSON (`data/raw/indian_ev_charging_stations.geojson`) |
| **OpenStreetMap Source** | Overpass API Live Extract (`data/raw/osm_mmr_overpass_raw.json`) |
| **Total Evaluated Raw Records** | **31,335 raw records** preserved in `data/raw/` |
| **National Master Staging Records** | **30,263 validated records** in `stg_national_master_ev_stations` (947 inside MMR, 29,316 outside MMR) |
| **Quarantined / Review Records** | **1,072 records** in `data/review/pending_stations.csv` (11 MMR proximity pairs, 2 generic OSM, 1,059 national pairs) |
| **Confirmed Rejections / Out-of-Bounds** | **0 records** (100% possess valid WGS-84 coordinates) |
| **Production MMR Stations (`ev_db`)** | **952 charging stations** (strictly within official MMR boundary polygon; 936 BEE, 8 OCM, 8 OSM) |
| **Production MMR Ports (`ev_db`)** | **2,026 operational hardware ports** |
| **Official MMR Boundary Source** | OpenStreetMap / Nominatim (OSM Relation ID: 13312356, ODbL 1.0, EPSG:4326) |

---

## 2. Ingestion & Validation Pipeline Architecture

```
[Raw Sources]
  ├── ocm_all_india.json (1,982 records)
  └── indian_ev_charging_stations.geojson (159 records)
           │
           ▼
[Staging Layer: stg_charging_stations]
  └── Stores unconstrained raw text attributes (latitude_raw, power_kw_raw, etc.)
           │
           ▼
[Python Cleaning & Validation Engine: scripts/ingest_pipeline.py]
  ├── Rule 1: Check required attributes (Station Name, Coordinates, City, State)
  ├── Rule 2: WGS-84 Decimal coordinate bounds check (Lat: [-90, +90], Lon: [-180, +180])
  ├── Rule 3: Subcontinent geographical bounds check (Lat: [6, 38], Lon: [68, 98])
  ├── Rule 4: Haversine spatial deduplication (< 30 meters threshold)
  ├── Rule 5: Strict MMR Coordinate Bounding: (Lat: [18.6, 19.6], Lon: [72.6, 73.3])
  └── Rule 6: Connector standard mapping & capacity assignment (CCS-2, Type 2, etc.)
           │
           ▼
[Production 3NF Schema: PostgreSQL ev_db]
  ├── charging_stations (952 rows)
  ├── charging_ports (2,026 rows)
  ├── charging_sessions (13 operational rows)
  └── station_status_history (2,027 initial & operational audit rows)
```

---

## 3. Data Dictionary

### Table: `charging_stations`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `station_id` | `SERIAL` | `PRIMARY KEY` | Auto-incrementing unique station identifier |
| `station_name` | `VARCHAR(150)` | `NOT NULL` | Registered station name |
| `operator_name` | `VARCHAR(100)` | `NOT NULL` | Charge Point Operator (Tata Power, Jio-bp, Statiq, Ather, MobiLane) |
| `address` | `TEXT` | `NULLABLE` | Street address or landmark description |
| `city` | `VARCHAR(60)` | `NOT NULL` | City name (strict MMR check applied) |
| `state` | `VARCHAR(60)` | `NOT NULL` | State name |
| `postal_code` | `VARCHAR(12)` | `NULLABLE` | Postal PIN code |
| `latitude` | `NUMERIC(9,6)` | `NOT NULL, CHECK [-90, +90]` | WGS-84 decimal latitude |
| `longitude` | `NUMERIC(9,6)` | `NOT NULL, CHECK [-180, +180]` | WGS-84 decimal longitude |
| `geom` | `geography(Point, 4326)` | `SPATIAL` | PostGIS spatial point for geodesic distance |
| `source_name` | `VARCHAR(50)` | `DEFAULT 'OpenChargeMap'` | Origin source of the station record |

### Table: `charging_ports`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `port_id` | `SERIAL` | `PRIMARY KEY` | Unique port identifier |
| `station_id` | `INT` | `FK -> charging_stations(station_id) ON DELETE CASCADE` | Associated parent station |
| `port_number` | `INT` | `NOT NULL` | Port dispenser number (1, 2, ...) |
| `connector_type` | `VARCHAR(40)` | `CHECK IN ('CCS-2', 'Type 2 AC', 'CHAdeMO', 'GB/T', 'Bharat AC-001', 'Bharat DC-001')` | Standard hardware plug type |
| `power_kw` | `NUMERIC(6,2)` | `CHECK > 0.0` | Maximum rated power output in kilowatts |
| `status` | `VARCHAR(20)` | `CHECK IN ('AVAILABLE', 'IN_USE', 'OUT_OF_SERVICE', 'MAINTENANCE')` | Live operational availability |

---

## 4. Tardeo & South Mumbai Geographic Coverage Audit

### Root Cause Analysis: Why Searching Tardeo Returned Kurla
During thorough codebase and data auditing, the root cause was traced to two key factors:
1. **Raw Dataset Coverage Gap in South Mumbai**:
   - Inspection of `data/raw/ocm_all_india.json` and `data/raw/indian_ev_charging_stations.geojson` revealed that the raw datasets contain **zero** charging stations south of latitude `19.07° N`.
   - The southernmost authentic station in the database was `MobiLane Equinox Business Park` (station_id: 70) in **Kurla West** at latitude `19.071566`, longitude `72.877213`.
   - When a user searched for "Tardeo, Mumbai" (lat: `18.9749`, lon: `72.8134`), the previous default search radius of 15 km captured Kurla West at **12.67 km away**, returning it as the "nearest" station because no closer station existed in the raw dataset.
2. **City Normalization Pipeline Bug**:
   - In `scripts/ingest_pipeline.py` (line 206), the code used `city_clean = city.title().strip() if city else 'Mumbai'`.
   - This caused 349 stations across India (which had null city in the Kaggle/OCM raw dump) to be falsely stamped with `city = 'Mumbai'`, contaminating non-MMR queries.

### Resolution & System Behavior
1. **Pipeline & Database Correction**:
   - `scripts/ingest_pipeline.py` was corrected so that records are only assigned `city = 'Mumbai'` if their coordinates strictly fall within the Mumbai Metropolitan Region bounding box (`18.6 <= lat <= 19.6` and `72.6 <= lon <= 73.3`).
   - A database cleanup was executed to reclassify all 349 non-MMR stations from `city = 'Mumbai'` to `city = 'Unknown'`.
2. **Investigation of Candidate Records (Adani, Jio-bp, Tata Power in Tardeo)**:
   - Queries for candidate names ("Adani Charging Station", "Jio-bp pulse", "Tata Power Charging Station") near Tardeo, Tulsiwadi, Arya Nagar, and Bane Compound confirmed they do **not** exist in the imported raw datasets.
   - In strict compliance with academic and engineering integrity standards, no artificial or guessed stations were hardcoded into Tardeo.
3. **Honest Empty State**:
   - When searching "Tardeo, Mumbai" at a realistic local radius of 3.0 km or 5.0 km, the API and Streamlit dashboard return **0 stations** honestly and present a clear notice:
     `"No charging stations found within 3 km of Tardeo, Mumbai. Try expanding your search radius."`
   - Kurla West is strictly excluded at <= 5 km and is only returned when the user deliberately expands their radius to >= 13 km, where it is transparently identified as an outlying station at 12.67 km in Kurla West.

---

## 5. Academic Honesty Disclosure

- **Authentic Data**: Station geographic coordinates, physical addresses, operator brands, connector specifications, and rated kilowatt power outputs are 100% sourced from real-world open datasets.
- **Simulated Operational Data**: Real-time slot availability, live energy consumption telemetry (kWh), and user charging session histories are simulated using realistic urban charging usage patterns as required by the ADBMS project rubric.
- **Clear UI Separation**: The user interface clearly demarcates authentic physical station metadata from simulated charging sessions and hardware telemetry.
