# Capability: OEVK Geospatial Data

## Overview

This capability enables the import, storage, and export of geospatial boundary data for National Individual Electoral Districts (OEVK). The system ingests polygon coordinates from the `oevk.json` data source and makes them available for spatial analysis in exported databases.

## ADDED Requirements

### Requirement: OEVK table SHALL include geospatial columns

The `NationalIndividualElectoralDistrict` table SHALL store center point and boundary polygon coordinates for each OEVK district.

**Rationale**: Source data (`oevk.json`) contains geospatial boundary information that enables spatial queries, mapping, and GIS analysis. Without these columns, valuable geospatial data is lost.

#### Scenario: DuckDB schema includes OEVK polygon columns

**Given** the DuckDB database schema is defined in `src/database/schema.sql`  
**When** the `NationalIndividualElectoralDistrict` table is created  
**Then** the table must include a `Center TEXT` column to store center point coordinates  
**And** the table must include a `Polygon TEXT` column to store boundary polygon coordinates  
**And** both columns must allow NULL values (for OEVKs without polygon data)

#### Scenario: PostgreSQL export schema includes OEVK polygon columns

**Given** the PostgreSQL export schema is generated in `src/etl/export.py`  
**When** the `NationalIndividualElectoralDistrict` table DDL is generated  
**Then** the table definition must include `Center TEXT` column  
**And** the table definition must include `Polygon TEXT` column  
**And** column comments must explain the coordinate format

### Requirement: System SHALL ingest OEVK JSON geospatial data

The ingestion pipeline SHALL load polygon data from the `oevk.json` file into a staging table for use during transformation.

**Rationale**: The transformation stage needs access to polygon data to populate OEVK records. A staging table provides a clean separation between raw JSON data and transformed entities.

#### Scenario: Staging table exists for OEVK JSON data

**Given** the database schema is initialized  
**When** tables are created  
**Then** a `staging_oevk_json` table must exist  
**And** the table must have columns: `maz TEXT`, `evk TEXT`, `centrum TEXT`, `poligon TEXT`, `run_tag TEXT`  
**And** the table must have a primary key on `(maz, evk)`

#### Scenario: JSON file is loaded into staging table

**Given** the `oevk.json` file exists in the staging directory  
**And** the file contains 106 OEVK records with `maz`, `evk`, `centrum`, and `poligon` fields  
**When** the ingestion pipeline calls `load_oevk_json(conn, json_path, run_tag)`  
**Then** all 106 records must be inserted into `staging_oevk_json`  
**And** the `maz` field must map to the `maz` column (county code)  
**And** the `evk` field must map to the `evk` column (OEVK code)  
**And** the `centrum` field must map to the `centrum` column (center coordinates)  
**And** the `poligon` field must map to the `poligon` column (polygon coordinates)  
**And** the current `run_tag` must be stored in the `run_tag` column

#### Scenario: JSON loading handles errors gracefully

**Given** the ingestion pipeline is running  
**When** the `oevk.json` file is missing or corrupted  
**Then** the pipeline must log a warning  
**And** the pipeline must continue execution (non-fatal error)  
**And** OEVK records must be created with NULL polygon data

### Requirement: OEVK transformation SHALL populate polygon data

The transformation stage SHALL join OEVK records with staging JSON data to populate center and polygon columns.

**Rationale**: The transformation is responsible for enriching entity data from multiple sources. Polygon data from JSON must be merged with OEVK district data from CSV.

#### Scenario: Transformation populates OEVK polygons from JSON

**Given** the `staging_oevk_json` table contains 106 OEVK polygon records  
**And** the `staging_korzet` table contains address data referencing OEVKs  
**When** `transform_national_individual_electoral_districts()` is executed  
**Then** the function must JOIN `staging_korzet` with `staging_oevk_json`  
**And** the JOIN must match on `county_code = maz` AND `oevk_code = evk` AND `run_tag`  
**And** the INSERT must include `oevk.centrum as Center` in the SELECT  
**And** the INSERT must include `oevk.poligon as Polygon` in the SELECT  
**And** the JOIN must be a LEFT JOIN (to handle missing JSON data gracefully)

#### Scenario: Transformation logs polygon data statistics

**Given** OEVK transformation has completed  
**When** counting records in `NationalIndividualElectoralDistrict`  
**Then** the log must show total number of OEVK records  
**And** the log must show count of records with non-NULL Polygon  
**And** the log format must be: `"Transformed {total} OEVK districts ({with_polygon} with polygon data)"`

### Requirement: OEVK polygon data SHALL be exported to PostgreSQL

The export pipeline SHALL include OEVK polygon columns in the PostgreSQL schema and data export.

**Rationale**: PostgreSQL users need access to polygon data for spatial analysis, mapping, and PostGIS queries.

#### Scenario: PostgreSQL dump includes OEVK polygon data

**Given** the `NationalIndividualElectoralDistrict` table has records with Center and Polygon data  
**When** the PostgreSQL dump is generated  
**Then** the `INSERT` statements must include Center column values  
**And** the `INSERT` statements must include Polygon column values  
**And** NULL values must be exported correctly

## REMOVED Requirements

### Requirement: TEVK table SHALL NOT include geospatial columns

The `SettlementIndividualElectoralDistrict` (TEVK) table currently has `Center` and `Polygon` columns but no data source exists for these fields. These columns SHALL be removed.

**Rationale**: The schema should reflect actual data availability. The Korzet CSV does not contain polygon data for TEVK districts, so these columns are misleading and waste storage.

#### Scenario: DuckDB schema removes TEVK polygon columns

**Given** the DuckDB database schema is defined in `src/database/schema.sql`  
**When** the `SettlementIndividualElectoralDistrict` table is created  
**Then** the table must NOT include a `Center` column  
**And** the table must NOT include a `Polygon` column  
**And** the schema must remain valid with all other columns intact

#### Scenario: PostgreSQL export schema removes TEVK polygon columns

**Given** the PostgreSQL export schema is generated in `src/etl/export.py`  
**When** the `SettlementIndividualElectoralDistrict` table DDL is generated  
**Then** the table definition must NOT include `Center` column  
**And** the table definition must NOT include `Polygon` column

## Data Format

### Coordinate Storage Format

**Center Coordinates**: Space-separated latitude and longitude
```
"47.490980 19.045150"
```
- Format: `"<latitude> <longitude>"`
- Example: Latitude 47.490980°, Longitude 19.045150°

**Polygon Coordinates**: Comma-separated coordinate pairs
```
"47.5146939015652 19.0436777064605,47.5147366015652 19.0434745064606,..."
```
- Format: `"<lat1> <lon1>,<lat2> <lon2>,<lat3> <lon3>,..."`
- Each pair is space-separated (lat lon)
- Pairs are comma-separated

**Future Enhancement**: Consider adding WKT (Well-Known Text) format conversion for PostGIS compatibility:
- Center: `POINT(19.045150 47.490980)` (note: longitude first in WKT)
- Polygon: `POLYGON((19.0436777064605 47.5146939015652, ...))`

## Cross-Capability Dependencies

None - This capability is self-contained within data ingestion, transformation, and export.

## Testing Requirements

### Integration Tests

1. **Schema Validation**
   - Verify `NationalIndividualElectoralDistrict` has `Center` and `Polygon` columns
   - Verify `SettlementIndividualElectoralDistrict` does NOT have these columns

2. **JSON Import**
   - Verify `staging_oevk_json` table is populated with 106 records
   - Verify field mapping is correct (`maz` → county, `evk` → OEVK)

3. **Transformation**
   - Verify 100% of OEVK records have non-NULL Polygon (assuming all JSON records match)
   - Verify LEFT JOIN handles missing JSON data (NULL polygons)

4. **Export**
   - Verify PostgreSQL schema includes OEVK polygon columns
   - Verify PostgreSQL schema does NOT include TEVK polygon columns
   - Verify data values are exported correctly

### Error Handling Tests

1. **Missing JSON File**
   - Pipeline continues with warning log
   - OEVK records created with NULL polygons

2. **Corrupt JSON File**
   - Pipeline logs error and continues
   - OEVK records created with NULL polygons

3. **JSON Missing Records**
   - OEVKs not in JSON get NULL polygons
   - No errors or crashes
