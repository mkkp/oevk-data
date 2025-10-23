# Proposal: Fix Export Inconsistencies

**Status**: ✅ IMPLEMENTED

## Why

The OEVK data export and deduplication processes have several quality and usability issues that need to be addressed:

1. **Deduplication Priority**: The current deduplication logic doesn't prioritize structured address formats (separate house number and building number) over combined formats (e.g., "1/A"). This can result in suboptimal canonical addresses.

2. **Data Integrity Issues**: 
   - Foreign key references in `settlementindividualelectoraldistrict` table point to incorrect IDs
   - The `nationalindividualelectoraldistrict.name` column contains settlement names instead of county names
   - Address components (house number, building number, staircase number) contain unnecessary leading zeros

3. **Missing Coordinate Export**: The `center` and `polygon` coordinate columns from polling district (TEVK) boundaries are not being exported to PostgreSQL, preventing geospatial analysis of electoral districts.

4. **Loader Script Limitations**: The `load_postgresql.py` script doesn't support a `--database` parameter, causing errors when users try to specify a target database.

5. **Testing Inefficiency**: Testing the full export/import pipeline with 3.3M+ addresses is time-consuming. A smaller representative subset would enable faster iteration.

## What Changes

This proposal introduces five distinct capabilities to address these issues:

### 1. Deduplication Priority Enhancement
- Modify `AddressDeduplicator._create_canonical_addresses()` to prefer structured addresses (plain house number + separate building) over combined formats (house number with slash notation)
- Add scoring/ranking logic to select the best representative from duplicate groups

### 2. Data Integrity Fixes
- Correct foreign key population in `settlementindividualelectoraldistrict` table
- Fix `nationalindividualelectoraldistrict.name` to contain county names instead of settlement names
- Apply leading zero trimming to `housenumber`, `building_number`, and `staircase_number` fields consistently with `fullAddress` generation rules

### 3. Coordinate Data Export
- Add `center` and `polygon` columns to `SettlementIndividualElectoralDistrict` table for polling district (TEVK) boundaries
- Implement proper geometric data type handling (GEOMETRY or TEXT with WKT format)
- Ensure coordinate data is correctly exported to PostgreSQL and can be loaded back for geospatial analysis

### 4. Loader Script Parameterization
- Add `--database` parameter to `load_postgresql.py` script
- Update argument parser to accept database name as command-line argument
- Ensure parameter properly overrides default database name

### 5. Test Data Subset Generation
- Create staging process to generate representative subset database
- Include data for 3 Budapest districts and 10 settlements from 3 other counties
- **Extract ALL addresses that belong to the selected settlements** - the subset must contain complete address data for each included settlement to maintain data integrity and enable realistic testing
- Preserve all referential integrity (counties, districts, polling stations, postal codes)
- Optional: Add `--limit-settlements` parameter to loader script for quick targeted tests

### 6. AddressFullView Database View
- Create a denormalized PostgreSQL view joining `Address` with all foreign key tables
- Provide both UUID foreign keys and human-readable data in a single queryable view
- Use new model naming convention (English column names) for consistency
- Include all 28 columns: primary key, 6 foreign key IDs, and 21 data columns
- Automatically created as part of schema generation and database setup

## Impact

### Affected Specs
- **MODIFIED**: `address-deduplication` - Add canonical address selection priority rules
- **NEW**: `data-integrity` - Data quality and formatting requirements
- **NEW**: `coordinate-export` - Geospatial data export capability
- **NEW**: `loader-parameterization` - PostgreSQL loader script configuration
- **NEW**: `test-subset` - Representative test data generation
- **NEW**: `address-full-view` - Denormalized database view for simplified querying

### Affected Code
- `src/etl/deduplicate.py` - Modify canonical address selection logic with priority scoring
- `src/etl/transform_optimized.py` - Apply leading zero trimming to address components, fix foreign key population
- `src/database/schema.sql` - Add coordinate columns to `SettlementIndividualElectoralDistrict` table
- `src/etl/export.py` - Include coordinate columns in PostgreSQL schema export, add AddressFullView to schema generation
- `src/release/templates/load_postgresql.py` - Add `--database` parameter
- `exports/schema.sql` - PostgreSQL DDL including AddressFullView definition
- `exports/address_view.sql` - Standalone view definition file
- `tests/integration/test_deduplication_priority.py` - New tests for priority logic
- `tests/integration/test_data_integrity.py` - New tests for data quality
- `tests/integration/test_coordinate_export_simple.py` - New tests for coordinate export schema
- `tests/integration/test_loader_parameterization.py` - New tests for loader script
- New script: `src/utils/create_test_subset.py` - Generate representative subset database

### Breaking Changes
None - All changes are backward compatible:
- Deduplication improvements produce better canonical addresses but don't change the schema
- Data integrity fixes correct existing bugs without changing interfaces
- Coordinate export adds columns without removing existing functionality
- Loader parameter is optional with sensible default
- Test subset is a new utility that doesn't affect existing workflows

## Dependencies

This proposal depends on the completed PostgreSQL export capability from the archived `add-postgresql-export` change. Specifically:
- PostgreSQL schema generation (`src/etl/export.py`)
- UUID conversion utilities
- PostgreSQL loader script structure (`src/release/templates/load_postgresql.py`)

## Success Criteria

1. **Deduplication Quality**: Structured addresses (separate building numbers) are prioritized as canonical representatives over combined formats
2. **Data Integrity**: All foreign keys reference correct entities, county names are correct, and leading zeros are consistently trimmed
3. **Coordinate Support**: Coordinate data can be exported to PostgreSQL and successfully loaded back with proper geometry types
4. **Loader Flexibility**: Users can specify custom database names via `--database` parameter without errors
5. **Testing Efficiency**: Representative subset database enables full pipeline testing in under 30 seconds (vs. 2.5 minutes for full dataset)
6. **View Accessibility**: AddressFullView is automatically created in PostgreSQL, provides all 28 columns, and simplifies queries by eliminating manual joins
