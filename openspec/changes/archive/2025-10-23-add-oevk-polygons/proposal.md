# Proposal: Add OEVK Polygon Data

**Status**: PROPOSED

## Why

The OEVK data export is missing critical geospatial information despite the source data containing this information:

1. **Missing Geospatial Data**: The `NationalIndividualElectoralDistrict` (OEVK) table lacks `Center` and `Polygon` columns, but the source `oevk.json` file contains this boundary data (`centrum` and `poligon` fields).

2. **Schema Inconsistency**: The `SettlementIndividualElectoralDistrict` (TEVK) table incorrectly defines `Center` and `Polygon` columns in the schema, but no source data exists for these fields (the Korzet CSV does not contain polygon data).

3. **Unused Source Data**: The `oevk.json` file (108 OEVK district records) is downloaded but its geospatial data is completely ignored during transformation.

4. **Limited GIS Analysis**: Without OEVK boundary polygons, users cannot perform spatial queries, mapping, or geospatial analysis on national electoral districts in PostgreSQL/PostGIS.

## What Changes

This proposal introduces geospatial data import for OEVK districts while cleaning up incorrect schema definitions for TEVK:

### 1. Add Polygon Columns to OEVK Table
- Add `Center TEXT` column to `NationalIndividualElectoralDistrict` table for storing center point coordinates
- Add `Polygon TEXT` column to `NationalIndividualElectoralDistrict` table for storing boundary polygon coordinates
- Store coordinates in source format (space-separated for Center, comma-separated for Polygon)

### 2. Remove Polygon Columns from TEVK Table
- Remove `Center TEXT` column from `SettlementIndividualElectoralDistrict` table (no data source available)
- Remove `Polygon TEXT` column from `SettlementIndividualElectoralDistrict` table (no data source available)
- Clean up schema to match actual data availability

### 3. Import OEVK JSON Data
- Create `staging_oevk_json` table for loading `oevk.json` data
- Implement `load_oevk_json()` function in `src/etl/ingest.py` to parse and load JSON
- Map JSON fields: `maz` → county code, `evk` → OEVK code, `centrum` → Center, `poligon` → Polygon
- Integrate JSON loading into the ingestion stage pipeline

### 4. Update OEVK Transformation
- Modify `transform_national_individual_electoral_districts()` to JOIN with `staging_oevk_json`
- Populate `Center` and `Polygon` columns from JSON data during transformation
- Log statistics on how many OEVKs have polygon data vs those without

### 5. Update Export Schemas
- Add `Center` and `Polygon` columns to PostgreSQL export schema for `NationalIndividualElectoralDistrict`
- Remove `Center` and `Polygon` columns from PostgreSQL export schema for `SettlementIndividualElectoralDistrict`
- Update view definitions and export queries to include new columns

## Impact

### Affected Specs
- **MODIFIED**: `data-model` - Schema changes for OEVK and TEVK tables
- **MODIFIED**: `data-ingestion` - New JSON data source loading
- **MODIFIED**: `data-transformation` - OEVK transformation includes geospatial data
- **MODIFIED**: `data-export` - Export schemas updated for both tables

### Affected Code
- `src/database/schema.sql` - Add OEVK columns, remove TEVK columns, add staging table
- `src/etl/ingest.py` - Implement `load_oevk_json()` function
- `src/etl/transform_optimized.py` - Update OEVK transformation with JOIN to JSON data
- `src/etl/export.py` - Update PostgreSQL schema generation for both tables
- `exports/schema.sql` - Updated PostgreSQL schema DDL
- `tests/integration/test_oevk_polygons.py` - New tests for polygon import and transformation

### Breaking Changes
**Schema Migration Required**: Existing databases will need schema updates:
- **Breaking**: Removing `Center` and `Polygon` from `SettlementIndividualElectoralDistrict` drops these columns
- **Non-breaking**: Adding `Center` and `Polygon` to `NationalIndividualElectoralDistrict` is additive

**Migration Path**:
1. Export existing data if needed
2. Drop and recreate database with new schema (recommended for development)
3. For production: Use PostgreSQL `ALTER TABLE` to add/drop columns

### Data Completeness
- **Expected**: 106 out of 106 OEVK districts should have polygon data (based on `oevk.json` structure)
- **Fallback**: OEVKs not found in JSON will have NULL Center/Polygon (graceful LEFT JOIN)

## Dependencies

None - This is a standalone data model and ingestion enhancement.

## Success Criteria

1. **Schema Correctness**: `NationalIndividualElectoralDistrict` has `Center` and `Polygon` columns; `SettlementIndividualElectoralDistrict` does not
2. **Data Import**: All 106 OEVK records from `oevk.json` successfully loaded into `staging_oevk_json`
3. **Transformation**: 100% of OEVK records in `NationalIndividualElectoralDistrict` populated with polygon data from JSON (where available)
4. **Export**: PostgreSQL schema includes OEVK polygon columns and exports data correctly
5. **Logging**: Transform logs show count of OEVKs with/without polygon data
6. **Testing**: Integration tests verify polygon import, transformation, and export

## Open Questions

1. **Coordinate Format**: Should we convert coordinates to WKT format for PostGIS compatibility, or keep source format?
   - Current source format: Center = `"47.490980 19.045150"` (space-separated lat/lon)
   - Current source format: Polygon = `"lat1 lon1,lat2 lon2,..."` (comma-separated coordinate pairs)
   - WKT format: `POINT(lon lat)` and `POLYGON((lon1 lat1, lon2 lat2, ...))`
   - **Recommendation**: Keep source format initially for simplicity, add WKT conversion as optional future enhancement

2. **Missing JSON Data**: What happens if `oevk.json` is missing or corrupted during ingestion?
   - **Recommendation**: Treat as non-fatal error, log warning, continue with NULL polygons for OEVK records

3. **JSON File Location**: Should `oevk.json` URL be configurable or hardcoded?
   - Current: Hardcoded in source URLs
   - **Recommendation**: Keep hardcoded for consistency with Korzet ZIP handling
