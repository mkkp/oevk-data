# Tasks: Add OEVK Polygon Data

## Implementation Tasks

### Phase 1: Schema Updates (Breaking Changes)

- [ ] **Update DuckDB schema for OEVK table**
  - File: `src/database/schema.sql`
  - Add `Center TEXT` column to `NationalIndividualElectoralDistrict` table (after `Name` column)
  - Add `Polygon TEXT` column to `NationalIndividualElectoralDistrict` table (after `Center` column)
  - Add comments explaining coordinate format expectations

- [ ] **Remove TEVK polygon columns from DuckDB schema**
  - File: `src/database/schema.sql`
  - Remove `Center TEXT` column from `SettlementIndividualElectoralDistrict` table
  - Remove `Polygon TEXT` column from `SettlementIndividualElectoralDistrict` table

- [ ] **Add staging table for OEVK JSON**
  - File: `src/database/schema.sql`
  - Create `staging_oevk_json` table with columns: `maz TEXT`, `evk TEXT`, `centrum TEXT`, `poligon TEXT`, `run_tag TEXT`
  - Add primary key constraint on `(maz, evk)`

### Phase 2: Data Ingestion

- [ ] **Implement JSON loading function**
  - File: `src/etl/ingest.py`
  - Create `load_oevk_json(conn, json_path, run_tag)` function
  - Parse JSON file with `json.load()`
  - Insert records into `staging_oevk_json` using `executemany()` with UPSERT logic
  - Log count of records loaded
  - Handle file not found and JSON parsing errors gracefully

- [ ] **Integrate JSON loading into ingestion pipeline**
  - File: `src/etl/ingest.py`
  - Call `load_oevk_json()` in `load_staging_data()` after CSV loading
  - Pass `oevk.json` path from staging directory
  - Ensure error doesn't block rest of pipeline (non-fatal)

### Phase 3: Transformation Updates

- [ ] **Update OEVK transformation to include polygon data**
  - File: `src/etl/transform_optimized.py`
  - Modify `transform_national_individual_electoral_districts()` function
  - Add `Center` and `Polygon` to SELECT clause
  - Add LEFT JOIN to `staging_oevk_json` table matching on `county_code = maz` AND `oevk_code = evk`
  - Add JOIN condition for `run_tag`
  - Update GROUP BY to include `oevk.centrum, oevk.poligon`

- [ ] **Add polygon data logging**
  - File: `src/etl/transform_optimized.py`
  - Query count of OEVKs with non-NULL Polygon after transformation
  - Log: `"Transformed {total} OEVK districts ({with_polygon} with polygon data)"`

### Phase 4: Export Schema Updates

- [ ] **Update PostgreSQL export schema for OEVK**
  - File: `src/etl/export.py`
  - Add `Center TEXT` column to `NationalIndividualElectoralDistrict` table DDL
  - Add `Polygon TEXT` column to `NationalIndividualElectoralDistrict` table DDL
  - Update column comments

- [ ] **Update PostgreSQL export schema for TEVK**
  - File: `src/etl/export.py`
  - Remove `Center TEXT` column from `SettlementIndividualElectoralDistrict` table DDL
  - Remove `Polygon TEXT` column from `SettlementIndividualElectoralDistrict` table DDL

- [ ] **Update static PostgreSQL schema file**
  - File: `exports/schema.sql`
  - Apply same changes as above (add OEVK columns, remove TEVK columns)
  - Ensure view definitions are updated if they reference these columns

### Phase 5: Testing

- [ ] **Create integration test for OEVK polygon import**
  - File: `tests/integration/test_oevk_polygons.py`
  - Test 1: Verify `staging_oevk_json` table is created
  - Test 2: Verify `load_oevk_json()` successfully loads JSON data
  - Test 3: Verify OEVK records have non-NULL Center and Polygon after transformation
  - Test 4: Verify count of OEVKs with polygon data matches JSON record count
  - Test 5: Verify PostgreSQL export includes OEVK polygon columns

- [ ] **Add schema validation test**
  - File: `tests/integration/test_schema.py` (or new file)
  - Verify `NationalIndividualElectoralDistrict` has `Center` and `Polygon` columns
  - Verify `SettlementIndividualElectoralDistrict` does NOT have `Center` or `Polygon` columns

- [ ] **Run full pipeline test**
  - Execute complete pipeline with real data
  - Verify no errors during ingestion, transformation, or export
  - Check log output for polygon count statistics

### Phase 6: Documentation

- [ ] **Update functional requirements**
  - File: `docs/FUNCTIONAL_REQUIREMENTS.md` (if exists)
  - Document OEVK `Center` and `Polygon` columns
  - Note TEVK does NOT have polygon columns

- [ ] **Update README data model section**
  - File: `README.md`
  - Update `NationalIndividualElectoralDistrict` table description
  - Update `SettlementIndividualElectoralDistrict` table description

- [ ] **Document coordinate formats**
  - Add note on coordinate format (space-separated vs comma-separated)
  - Mention future enhancement possibility for WKT conversion

## Validation Checklist

- [ ] All tests pass (`pytest`)
- [ ] Schema changes applied cleanly to fresh database
- [ ] OEVK records have polygon data populated (verify count)
- [ ] PostgreSQL export includes OEVK polygons
- [ ] No references to TEVK polygons in export schema
- [ ] Logs show polygon data statistics
- [ ] No breaking changes to existing functionality (except schema migration)

## Dependencies

No external dependencies - all work is within the codebase.

## Estimated Effort

- Schema updates: 1 hour
- Ingestion implementation: 2 hours
- Transformation updates: 1 hour
- Export schema updates: 1 hour
- Testing: 2 hours
- Documentation: 1 hour

**Total: ~8 hours**

## Deployment Notes

**Database Migration Required**: Existing databases need to be rebuilt or migrated:

1. **Development**: Drop and recreate database with new schema
2. **Production** (if applicable): 
   ```sql
   -- Add OEVK columns
   ALTER TABLE NationalIndividualElectoralDistrict 
     ADD COLUMN Center TEXT,
     ADD COLUMN Polygon TEXT;
   
   -- Remove TEVK columns
   ALTER TABLE SettlementIndividualElectoralDistrict 
     DROP COLUMN Center,
     DROP COLUMN Polygon;
   ```

3. **Re-run pipeline** to populate OEVK polygon data from `oevk.json`
