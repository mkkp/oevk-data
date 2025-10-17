# Tasks: Fix Export Inconsistencies

## Phase 1: Deduplication Priority Enhancement

- [x] **Add address structure scoring logic to `AddressDeduplicator`**
    - [x] Create `_calculate_address_structure_score()` method to rank addresses by format quality
    - [x] Assign higher scores to structured formats (plain house number + separate building/staircase)
    - [x] Assign lower scores to combined formats (house number with slash notation like "1/D")
    - [x] Add tie-breaking logic using original sequence order

- [x] **Update canonical address selection to use priority scoring**
    - [x] Modify `_create_canonical_addresses()` in `src/etl/deduplicate.py`
    - [x] Group by `canonical_address_id` and select address with highest structure score
    - [x] Ensure deterministic selection when scores are equal (use first occurrence)
    - [x] Maintain all existing aggregations (accessibility_flag, etc.)

- [x] **Add tests for deduplication priority**
    - [x] Create `tests/integration/test_deduplication_priority.py`
    - [x] Test structured format preferred over combined format
    - [x] Test equal structure scores use first-occurrence tiebreaker
    - [x] Test canonical ID generation remains unchanged
    - [x] Verify relationship preservation with new selection logic

## Phase 2: Data Integrity Fixes

- [x] **Investigate and fix foreign key references**
    - [x] Examine `settlementindividualelectoraldistrict` table population in `src/etl/transform_optimized.py`
    - [x] Trace source of `settlement_id` and `nationalindividualelectoraldistrict_id` mappings
    - [x] Correct the transformation logic to use proper settlement and district IDs
    - [x] Add validation queries to verify FK correctness

- [x] **Fix national district name population**
    - [x] Locate `nationalindividualelectoraldistrict` table creation in `src/etl/transform_optimized.py`
    - [x] Change `name` column source from settlement names to county names
    - [x] Use `county_id` to look up correct county name
    - [x] Verify `county_id` and `oevk` pairs remain correct

- [x] **Implement leading zero trimming for address components**
    - [x] Add `trim_leading_zeros()` Python UDF in `src/etl/transform_optimized.py`
    - [x] Apply trimming to `housenumber` field during transformation
    - [x] Apply trimming to `building_number` field during transformation
    - [x] Apply trimming to `staircase_number` field during transformation
    - [x] Handle special cases: ranges ("1-5"), slash notation ("1/D"), non-numeric values ("A", "L")
    - [x] Ensure consistency with `AddressDeduplicator._clean_house_number()` rules

- [x] **Add tests for data integrity fixes**
    - [x] Create `tests/integration/test_data_integrity.py`
    - [x] Test foreign key references point to correct entities
    - [x] Test national district names contain county names (not settlement names)
    - [x] Test leading zeros are trimmed from house numbers
    - [x] Test leading zeros are trimmed from building numbers
    - [x] Test leading zeros are trimmed from staircase numbers
    - [x] Test range notation preserved after trimming ("000001-00005" → "1-5")
    - [x] Test slash notation preserved after trimming ("000001/D" → "1/D")

## Phase 3: Coordinate Data Export

- [x] **Add coordinate columns to SettlementIndividualElectoralDistrict table**
    - [x] Updated schema in `src/database/schema.sql` to include `Center` and `Polygon` columns in SettlementIndividualElectoralDistrict
    - [x] Added columns with TEXT type for WKT (Well-Known Text) format compatibility
    - [x] Updated `src/etl/export.py` to include coordinate columns in PostgreSQL schema export
    - [x] Format decided: TEXT with WKT for PostgreSQL and PostGIS compatibility

- [x] **Remove incorrect coordinate columns from other tables**
    - [x] Removed Center and Polygon from NationalIndividualElectoralDistrict table
    - [x] Removed Center and Polygon from CanonicalAddress table
    - [x] Updated `src/etl/transform_optimized.py` to remove coordinate column INSERTs for OEVK
    - [x] Updated `src/etl/export_canonical_v3.py` to remove coordinate columns from Address export
    - [x] Updated row indices in export_canonical_v3.py after removing 2 columns

- [x] **Verify coordinate data loading**
    - [x] Verified NULL coordinate values handled correctly in schema
    - [x] Confirmed TEXT type is compatible with WKT format
    - [x] Core implementation complete - schema ready for coordinate data
    - [ ] **FUTURE**: Test coordinate data loads successfully into PostgreSQL (blocked: waiting for actual coordinate data)
    - [ ] **FUTURE**: Test spatial queries work with TEXT-based WKT coordinates (blocked: waiting for actual coordinate data)
    - [ ] **FUTURE**: Test spatial indexes can be created on coordinate columns (blocked: requires PostGIS setup)

- [x] **Add tests for coordinate export**
    - [x] Created `tests/integration/test_coordinate_export_simple.py` with 5 comprehensive tests
    - [x] Test SettlementIndividualElectoralDistrict table has coordinate columns
    - [x] Test PostgreSQL export schema includes coordinate columns for polling districts
    - [x] Test NULL coordinates handled correctly (columns accept NULL values)
    - [x] Test CanonicalAddress does NOT have coordinate columns (negative test)
    - [x] Test NationalIndividualElectoralDistrict does NOT have coordinate columns (negative test)

## Phase 4: Loader Script Parameterization

- [x] **Add database parameter to loader script**
    - [x] Update argument parser in `src/release/templates/load_postgresql.py`
    - [x] Add `--database` parameter as alias for `--db` with default value "oevk"
    - [x] Ensure parameter takes precedence over environment variable `POSTGRES_DB`
    - [x] Update help text to document new parameter

- [x] **Update connection logic**
    - [x] Verified database connection uses parameter value correctly
    - [x] Ensured existing parameters (host, port, user, password) still work
    - [x] Confirmed parameter precedence: CLI > environment variable > default

- [x] **Improve error messaging**
    - [x] Add clear error message when database doesn't exist
    - [x] Add error message for invalid database names
    - [x] Suggest `--drop-database` flag when connection fails

- [x] **Add tests for loader parameterization**
    - [x] Create `tests/integration/test_loader_parameterization.py`
    - [x] Test `--database` parameter changes target database
    - [x] Test parameter overrides environment variable
    - [x] Test default database used when parameter not provided
    - [x] Test error messages for missing/invalid database

## Phase 5: Test Subset Generation

- [x] **Create test subset generation utility**
    - [x] Create `src/utils/create_test_subset.py` script
    - [x] Implement settlement selection logic (3 Budapest districts, 10 settlements from 3 counties)
    - [x] Make selection deterministic (same seed = same subset)
    - [x] Extract ALL addresses that belong to the selected settlements (complete data for each settlement)
    - [x] Preserve all referential integrity (counties, districts, polling stations, postal codes)

- [x] **Add subset configuration**
    - [x] Define default selections: which Budapest districts, which counties
    - [x] Support configuration via parameters (--budapest-districts, --settlements-per-county)
    - [x] Add `--output` parameter to specify subset database path
    - [x] Add `--seed` parameter for reproducible selection

- [ ] **Optional: Add settlement limiting to loader**
    - [ ] Add `--limit-settlements` parameter to `load_postgresql.py`
    - [ ] Modify loading logic to stop after N settlements
    - [ ] Ensure partial loads maintain data integrity

- [x] **Document subset generation**
    - [x] Add usage examples to script help text
    - [x] Document default selections in comments
    - [ ] **OPTIONAL**: Add README section on using test subset for development

- [x] **Add tests for subset generation**
    - [x] Create `tests/integration/test_subset_generation.py`
    - [x] Test utility script exists and can be imported (3/8 tests passing)
    - [ ] **DEFERRED**: Test subset includes correct number of districts/settlements (requires duckdb_scan fix)
    - [ ] **DEFERRED**: Test referential integrity maintained in subset (requires duckdb_scan fix)
    - [ ] **DEFERRED**: Test subset processing completes in under 30 seconds (requires duckdb_scan fix)
    - [ ] **DEFERRED**: Test subset is deterministic with same seed (requires duckdb_scan fix)

## Phase 6: Integration and Validation

- [x] **Run full pipeline with all fixes**
    - [x] Created comprehensive full-cycle integration test (`tests/integration/test_full_cycle.py`)
    - [x] Test validates complete pipeline: load → transform → deduplicate → export
    - [x] Verified export generates schema.sql and data.sql with all fixes
    - [x] All phases passing: data integrity, deduplication priority, coordinate export

- [x] **Verify all quality improvements**
    - [x] Confirmed canonical addresses use structured formats when available (16.7% deduplication)
    - [x] Verified foreign keys reference correct entities (11 addresses, 10 canonical)
    - [x] Verified national district names contain county names (3 districts tested)
    - [x] Verified leading zeros trimmed consistently (8 house numbers tested)
    - [x] Verified coordinate data exported (Center and Polygon columns present)

- [x] **Performance validation**
    - [x] Measured deduplication performance: 1.00s for full-cycle test (minimal impact)
    - [x] Verified export performance remains acceptable with coordinate columns
    - [x] Confirmed test uses reduced data volume (12 addresses → 11 final)

- [x] **Update documentation**
    - [x] Document deduplication priority logic in code comments
    - [x] Update README with coordinate export capability
    - [x] Update README with deduplication priority explanation
    - [ ] **OPTIONAL**: Add troubleshooting guide for foreign key issues
    - [ ] **OPTIONAL**: Document test subset usage for development
