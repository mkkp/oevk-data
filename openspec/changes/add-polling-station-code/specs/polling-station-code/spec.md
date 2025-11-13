# Specification: Polling Station Code Column

**Capability**: Polling Station Data Model
**Version**: 1.0.0
**Status**: Draft

## Overview

Add `code` column to polling station tables to preserve the authoritative polling station code from source data (`staging_korzet.polling_station_code`).

---

## ADDED Requirements

### Requirement: DuckDB Schema Extension
**ID**: REQ-PSC-001

**Priority**: High
**Category**: Data Model

The `PollingStation` table in DuckDB SHALL include a `PollingStationCode` column to store the polling station code from source data.

#### Scenario: DuckDB table includes code column

**Given** the DuckDB database schema
**When** the `PollingStation` table is created
**Then** it SHALL have a `PollingStationCode VARCHAR` column
**And** the column SHALL be positioned after the `ID` column for readability

#### Scenario: Code column preserves source data

**Given** staging data with `polling_station_code = '031'`
**When** transformation extracts polling station records
**Then** the `PollingStationCode` column SHALL contain `'031'`
**And** no data loss SHALL occur

---

### Requirement: PostgreSQL Schema Extension
**ID**: REQ-PSC-002

**Priority**: High
**Category**: Data Model

The `polling_station` table in PostgreSQL SHALL include a `code` column following PostgreSQL naming conventions.

#### Scenario: PostgreSQL table includes code column

**Given** the PostgreSQL schema SQL file
**When** the `polling_station` table is created
**Then** it SHALL have a `code TEXT NOT NULL` column
**And** the column SHALL be positioned after the `id` column for readability
**And** the column comment SHALL indicate it stores the polling station code

#### Scenario: Code column follows naming convention

**Given** PostgreSQL naming convention requires `snake_case`
**When** exporting DuckDB `PollingStationCode` to PostgreSQL
**Then** the column SHALL be named `code` (not `polling_station_code` or `PollingStationCode`)
**And** it SHALL match the pattern established in `openspec/project.md`

---

### Requirement: Transformation Logic Update
**ID**: REQ-PSC-003

**Priority**: High
**Category**: ETL

The transformation logic SHALL extract `polling_station_code` from `staging_korzet` into `PollingStation.PollingStationCode`.

#### Scenario: Transform extracts code from staging

**Given** `staging_korzet` table with populated `polling_station_code`
**When** `transform_polling_stations()` executes
**Then** the INSERT statement SHALL include `polling_station_code` in the SELECT
**And** the column SHALL be mapped to `PollingStation Code`
**And** the code SHALL be trimmed of whitespace

#### Scenario: All codes are NOT NULL

**Given** source data analysis shows 0 NULL values in 3.3M records
**When** transformation processes records
**Then** all `PollingStationCode` values SHALL be NOT NULL
**And** the DuckDB column MAY use `NOT NULL` constraint
**And** the PostgreSQL column SHALL use `NOT NULL` constraint

**Rationale**: Data analysis (run_tag 20251105_033400) confirms 100% code population; NOT NULL constraint is safe.

---

### Requirement: Export Mapping
**ID**: REQ-PSC-004

**Priority**: High
**Category**: Export

The PostgreSQL export logic SHALL map DuckDB `PollingStationCode` to PostgreSQL `code` column.

#### Scenario: DuckDB to PostgreSQL column mapping

**Given** a PollingStation record with `PollingStationCode = '031'`
**When** exporting to PostgreSQL CSV format
**Then** the value SHALL be written to the `code` column
**And** the column order SHALL match the schema definition
**And** NULL values SHALL be represented as empty strings in CSV

#### Scenario: Export includes code in schema

**Given** the PostgreSQL schema generation logic
**When** `exports/schema.sql` is created
**Then** it SHALL include the `code TEXT NOT NULL` column definition
**And** the column SHALL appear in the correct position

---

### Requirement: Data Validation
**ID**: REQ-PSC-005

**Priority**: Medium
**Category**: Testing

Tests SHALL verify the code column is correctly populated throughout the pipeline.

#### Scenario: Integration test validates code column

**Given** a test database with sample staging data
**When** the full transformation pipeline executes
**Then** the `PollingStation.PollingStationCode` column SHALL be populated
**And** the values SHALL match `staging_korzet.polling_station_code`
**And** the export SHALL include the code in PostgreSQL format

#### Scenario: PostgreSQL import verification

**Given** exported PostgreSQL schema and data files
**When** importing into a PostgreSQL database
**Then** the `polling_station.code` column SHALL exist
**And** it SHALL contain the expected values
**And** SELECT queries SHALL successfully retrieve codes

---

## MODIFIED Requirements

### Requirement: PostgreSQL Schema Generation
**ID**: REQ-PS-EXPORT-001
**Priority**: High
**Category**: Export

The PostgreSQL schema generation process SHALL include the `code TEXT NOT NULL` column in the `polling_station` table definition.

#### Scenario: Generated schema includes code column

**Given** the schema generation process
**When** `generate_postgresql_schema()` creates `exports/schema.sql`
**Then** the `polling_station` table definition SHALL include:
```sql
CREATE TABLE IF NOT EXISTS polling_station (
    id UUID PRIMARY KEY,
    code TEXT NOT NULL,
    address TEXT NOT NULL,
    -- ... rest of columns
);
```

---

## Implementation Notes

### Schema Position

The `code` column should be placed as the second column (after `id`) for the following reasons:
1. **Logical Grouping**: Primary identifier (id) followed by human-readable identifier (code)
2. **Readability**: SELECT * queries show code early
3. **Convention**: Similar to other tables where codes follow IDs

### Data Type Selection

**DuckDB**: `VARCHAR`
- Matches existing string columns
- Codes are 3-digit strings (e.g., '031', '115')

**PostgreSQL**: `TEXT NOT NULL`
- Follows PostgreSQL convention from project
- Variable length, no size limit needed
- NOT NULL if source data confirms no nulls

### Performance Considerations

- **Index**: Not needed initially; code is not a primary search key
- **Storage**: Minimal impact (~10 bytes per row × 8,547 stations = ~85 KB)
- **Query Performance**: No impact on existing queries (additive only)

### Migration Strategy

No migration needed since this is a new column in an additive change. Existing data/exports unaffected.

---

## Verification Checklist

- [ ] DuckDB schema includes `PollingStationCode VARCHAR`
- [ ] PostgreSQL schema includes `code TEXT NOT NULL`
- [ ] Transform SQL extracts `polling_station_code` from staging
- [ ] Export logic maps `PollingStationCode` → `code`
- [ ] Integration test validates end-to-end flow
- [ ] PostgreSQL import test verifies column exists and populated
- [ ] Documentation updated (if applicable)
- [ ] No regression in existing tests
