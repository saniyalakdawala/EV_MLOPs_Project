# Database Backup and Disaster Recovery Guide

## 1. Overview & DBA Strategy

In mission-critical infrastructure like an EV Charging Network, data loss results in lost revenue, inaccurate billing, and unfulfilled driver reservations. This guide establishes standard operating procedures for **Physical and Logical Backups** on PostgreSQL.

| Strategy Component | Specification |
| :--- | :--- |
| **Backup Utility** | PostgreSQL `pg_dump` |
| **Target Database** | `ev_db` |
| **Backup Format** | Custom Archive (`-Fc` / Custom Compressed) |
| **Compression** | Built-in zlib compression (drastically reduces backup size) |
| **Restoration Utility** | `pg_restore` |
| **Target Recovery Time Objective (RTO)** | $< 15\text{ minutes}$ |
| **Target Recovery Point Objective (RPO)** | $< 1\text{ hour}$ |

---

## 2. Step-by-Step Backup Execution (`pg_dump`)

### Command (Run in VS Code PowerShell or Command Prompt):

```powershell
# Set PostgreSQL bin path if not already in system PATH
$env:PATH += ";C:\Program Files\PostgreSQL\17\bin"

# Set password environment variable to avoid hardcoded credentials in scripts
$env:PGPASSWORD = "postgres"

# Execute custom format compressed backup
pg_dump -h localhost -p 5432 -U postgres -d ev_db -Fc -v -f "c:\Projects\ADBMS\data\ev_db_backup.dump"
```

### Why Custom Format (`-Fc`) is Preferred Over Plain SQL (`-Fp`):
1. **Compression**: Custom format is compressed by default, saving up to 80% disk and network I/O.
2. **Selective Restoration**: With `pg_restore`, a DBA can choose to restore only specific tables (e.g., only `charging_stations`), or only the schema without data, or only data without constraints.
3. **Parallel Restores**: Supports multi-threaded parallel restoration (`-j 4`) for rapid disaster recovery.
4. **Error Handling**: Unlike plain SQL scripts which may stop on error, `pg_restore` manages dependency order automatically (re-creating foreign keys after tables and data are loaded).

---

## 3. Step-by-Step Restoration Execution (`pg_restore`)

### Scenario A: Full Disaster Recovery into a Fresh Database

```powershell
# 1. Create a fresh target database for disaster recovery test
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE ev_db_recovery_test;"

# 2. Restore all tables, indexes, constraints, and data
pg_restore -h localhost -p 5432 -U postgres -d ev_db_recovery_test -v "c:\Projects\ADBMS\data\ev_db_backup.dump"
```

### Scenario B: Selective Table Restoration (e.g., restoring only `charging_stations`)

```powershell
pg_restore -h localhost -p 5432 -U postgres -d ev_db -t charging_stations -v "c:\Projects\ADBMS\data\ev_db_backup.dump"
```

### Scenario C: Inspecting Backup Table of Contents without Restoring

```powershell
# Lists all archived tables, triggers, and indexes contained in the dump file:
pg_restore -l "c:\Projects\ADBMS\data\ev_db_backup.dump"
```

---

## 4. Post-Restoration Integrity Verification Queries

Run these queries in pgAdmin on the restored database (`ev_db_recovery_test`) to confirm that all records and relationships survived intact:

```sql
-- 1. Verify Record Counts
SELECT 'charging_stations' AS tbl, count(*) FROM charging_stations
UNION ALL
SELECT 'charging_ports', count(*) FROM charging_ports
UNION ALL
SELECT 'charging_sessions', count(*) FROM charging_sessions
UNION ALL
SELECT 'station_status_history', count(*) FROM station_status_history;

-- 2. Verify Foreign Key Referential Integrity (Orphaned Port Check)
SELECT count(*) AS orphaned_ports
FROM charging_ports p
LEFT JOIN charging_stations s ON p.station_id = s.station_id
WHERE s.station_id IS NULL; -- Expected result: 0

-- 3. Verify Active Session Constraint Preserved
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'charging_sessions'::regclass;
```

---

## 5. Enterprise Point-In-Time Recovery (PITR) Concept

For production 24/7 networks:
1. **WAL Archiving**: PostgreSQL continuously writes all transaction logs to Write-Ahead Logging (WAL) segments in `pg_wal`.
2. **Continuous Archiving**: Setting `archive_mode = on` and `archive_command = 'copy "%p" "\\backup_server\\wal_archive\\%f"'` ships WAL segments off-site.
3. **Point-In-Time Restoration**: In the event of a catastrophic server failure at 14:32:15, the DBA can restore the base backup from 02:00:00 and replay WAL logs up to `recovery_target_time = '2026-10-15 14:32:00'`, recovering transactions up to 15 seconds before the crash.
