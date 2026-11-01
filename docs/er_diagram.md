# Entity-Relationship (ER) Diagram & Schema Documentation

## 1. Conceptual Model

The database is modeled around the real-world operational domain of Electric Vehicle (EV) Charging Networks in urban metropolitan areas. The schema satisfies **Third Normal Form (3NF)**:
- Every non-key attribute is non-transitively dependent on the primary key.
- Physical infrastructure (stations and hardware ports) is decoupled from operational business transactions (charging sessions) and audit logs (temporal status history).

---

## 2. Mermaid Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    charging_stations ||--o{ charging_ports : "houses (1:N)"
    charging_ports ||--o{ charging_sessions : "hosts (1:N)"
    charging_ports ||--o{ station_status_history : "logs transitions (1:N)"

    charging_stations {
        int station_id PK "SERIAL Primary Key"
        varchar station_name "Station display name"
        varchar operator_name "CPO (Tata Power, Jio-bp, Ather)"
        text address "Physical street address"
        varchar city "City name (e.g. Mumbai, Pune)"
        varchar state "State name (Maharashtra)"
        varchar postal_code "PIN code"
        numeric latitude "WGS-84 Decimal Latitude [-90, +90]"
        numeric longitude "WGS-84 Decimal Longitude [-180, +180]"
        geography geom "PostGIS Point SRID 4326"
        varchar source_name "Data source (OpenChargeMap, E-Amrit)"
        timestamptz created_at "Registration timestamp"
        timestamptz last_updated "Last modification timestamp"
    }

    charging_ports {
        int port_id PK "SERIAL Primary Key"
        int station_id FK "References charging_stations(station_id)"
        int port_number "Port index per station (1, 2, ...)"
        varchar connector_type "Standard (CCS-2, Type 2, CHAdeMO)"
        numeric power_kw "Max charging power (> 0 kW)"
        varchar status "AVAILABLE | IN_USE | OUT_OF_SERVICE"
        timestamptz updated_at "Status update timestamp"
    }

    charging_sessions {
        uuid session_id PK "gen_random_uuid() Primary Key"
        int port_id FK "References charging_ports(port_id)"
        varchar user_identifier "Customer / Vehicle ID"
        timestamptz start_time "Session initiation timestamp"
        timestamptz end_time "Session termination timestamp"
        numeric energy_kwh "Energy delivered in kWh (>= 0)"
        varchar session_status "ACTIVE | COMPLETED | ABORTED"
    }

    station_status_history {
        bigint history_id PK "BIGSERIAL Primary Key"
        int port_id FK "References charging_ports(port_id)"
        varchar old_status "Previous status"
        varchar new_status "Transitioned status"
        timestamptz changed_at "Timestamp of change"
        varchar reason "Reason / Trigger cause"
    }
```

---

## 3. Relational Cardinalities & Referential Integrity

| Relationship | Cardinality | Foreign Key Constraint | Delete Action | Business Justification |
| :--- | :--- | :--- | :--- | :--- |
| **`charging_stations` $\to$ `charging_ports`** | $1 : N$ | `charging_ports.station_id` $\to$ `charging_stations.station_id` | `ON DELETE CASCADE` | If a physical station is decommissioned, all attached hardware ports are removed. |
| **`charging_ports` $\to$ `charging_sessions`** | $1 : N$ | `charging_sessions.port_id` $\to$ `charging_ports.port_id` | `ON DELETE RESTRICT` | **Critical DBA Rule**: A port cannot be deleted if historical charging or billing session records exist. |
| **`charging_ports` $\to$ `station_status_history`** | $1 : N$ | `station_status_history.port_id` $\to$ `charging_ports.port_id` | `ON DELETE CASCADE` | Temporal telemetry records cascade if a test port is deleted. |

---

## 4. Key Constraints & DBA Safeguards

1. **Partial Unique Index (Double-Booking Prevention)**:
   ```sql
   CREATE UNIQUE INDEX uq_active_session_per_port 
   ON charging_sessions (port_id) 
   WHERE session_status = 'ACTIVE';
   ```
   *Guarantees at database engine level that no two concurrent `ACTIVE` sessions can ever be created for the same physical connector.*

2. **Domain Check Constraints**:
   - `chk_latitude_range`: `latitude BETWEEN -90.0 AND 90.0`
   - `chk_longitude_range`: `longitude BETWEEN -180.0 AND 180.0`
   - `chk_power_positive`: `power_kw > 0.0`
   - `chk_connector_type`: `connector_type IN ('CCS-2', 'Type 2 AC', 'CHAdeMO', 'GB/T', 'Bharat AC-001', 'Bharat DC-001')`
   - `chk_port_status`: `status IN ('AVAILABLE', 'IN_USE', 'OUT_OF_SERVICE', 'MAINTENANCE')`
   - `chk_session_times`: `end_time IS NULL OR end_time >= start_time`
