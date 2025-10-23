# Tasks: Add PostGIS Support for Geospatial Data

**Change ID:** `add-postgis-support`  
**Estimated Effort:** ~6-8 hours  
**Risk Level:** Low (additive change, no breaking changes)

---

## Task Breakdown

### Phase 1: Schema and Configuration (1.5 hours)

#### Task 1.1: Add PostGIS extension to PostgreSQL schema
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Open `exports/schema.sql`
- [x] Add `CREATE EXTENSION IF NOT EXISTS postgis;` at the beginning
- [x] Verify placement before any table definitions
- [x] Save file

**Acceptance:**
- schema.sql contains `CREATE EXTENSION IF NOT EXISTS postgis;`
- Extension creation is before table definitions

#### Task 1.2: Update NationalIndividualElectoralDistrict table to use GEOMETRY types
**Effort:** 20 minutes  
**Risk:** Low  
**Dependencies:** Task 1.1

**Steps:**
- [x] Open `exports/schema.sql`
- [x] Find `NationalIndividualElectoralDistrict` table definition
- [x] Change `Center TEXT` to `Center GEOMETRY(POINT, 4326)`
- [x] Change `Polygon TEXT` to `Polygon GEOMETRY(POLYGON, 4326)`
- [x] Save file

**Acceptance:**
- Center column is `GEOMETRY(POINT, 4326)`
- Polygon column is `GEOMETRY(POLYGON, 4326)`
- SRID is 4326 for both columns

#### Task 1.3: Add spatial indexes to schema
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 1.2

**Steps:**
- [x] Open `exports/schema.sql`
- [x] Add after table creation:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_oevk_center_gist 
    ON NationalIndividualElectoralDistrict USING GIST (Center);
  CREATE INDEX IF NOT EXISTS idx_oevk_polygon_gist 
    ON NationalIndividualElectoralDistrict USING GIST (Polygon);
  ```
- [x] Save file

**Acceptance:**
- Two GiST indexes defined
- Indexes use IF NOT EXISTS clause
- Index names follow project naming convention

#### Task 1.4: Add POSTGRESQL_USE_POSTGIS configuration variable
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Open `src/utils/config.py`
- [x] Add configuration variable:
  ```python
  POSTGRESQL_USE_POSTGIS: bool = os.getenv("POSTGRESQL_USE_POSTGIS", "true").lower() == "true"
  ```
- [x] Add docstring explaining the variable
- [x] Save file

**Acceptance:**
- Configuration variable exists
- Defaults to `true`
- Case-insensitive parsing (accepts "true", "True", "TRUE", etc.)

#### Task 1.5: Create or update Docker Compose configuration
**Effort:** 25 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Create or update `docker-compose.yml`
- [x] Add PostgreSQL service with PostGIS image:
  ```yaml
  services:
    postgres:
      image: postgis/postgis:15-3.3
      container_name: oevk-postgres
      environment:
        POSTGRES_DB: oevk_data
        POSTGRES_USER: oevk_user
        POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      ports:
        - "5432:5432"
      volumes:
        - postgres_data:/var/lib/postgresql/data
        - ./exports/schema.sql:/docker-entrypoint-initdb.d/01_schema.sql
        - ./exports/data.sql:/docker-entrypoint-initdb.d/02_data.sql
  ```
- [x] Add volumes section
- [x] Create `.env.example` with `POSTGRES_PASSWORD=changeme`
- [x] Save files

**Acceptance:**
- Docker Compose uses `postgis/postgis:15-3.3` image
- Environment variables configured
- Volumes mount schema and data files
- .env.example provides template

---

### Phase 2: Coordinate Conversion Functions (2 hours)

#### Task 2.1: Implement convert_center_to_point() function
**Effort:** 30 minutes  
**Risk:** Medium  
**Dependencies:** None

**Steps:**
- [x] Open `src/etl/export_canonical_v3.py`
- [x] Add function after existing helper functions:
  ```python
  def convert_center_to_point(center_text: str | None) -> str | None:
      """Convert center TEXT 'lat lon' to PostGIS POINT WKT.
      
      Args:
          center_text: Space-separated coordinates "lat lon"
      
      Returns:
          WKT POINT "POINT(lon lat)" or NULL
      """
      if not center_text or center_text.strip() == "":
          return None
      
      try:
          parts = center_text.strip().split()
          if len(parts) != 2:
              logger.warning(f"Invalid center format: {center_text}")
              return None
          
          lat = float(parts[0])
          lon = float(parts[1])
          
          # Validate ranges
          if not (-90 <= lat <= 90 and -180 <= lon <= 180):
              logger.warning(f"Coordinates out of range: lat={lat}, lon={lon}")
              return None
          
          # Return WKT with lon, lat order (PostGIS standard)
          return f"POINT({lon} {lat})"
      
      except (ValueError, IndexError) as e:
          logger.error(f"Error converting center '{center_text}': {e}")
          return None
  ```
- [x] Add type hints import if needed
- [x] Save file

**Acceptance:**
- Function handles NULL input (returns NULL)
- Function validates coordinate ranges
- Function swaps lat/lon order
- Function logs warnings/errors appropriately

#### Task 2.2: Implement convert_polygon_to_wkt() function
**Effort:** 45 minutes  
**Risk:** Medium  
**Dependencies:** None

**Steps:**
- [x] Open `src/etl/export_canonical_v3.py`
- [x] Add function after `convert_center_to_point()`:
  ```python
  def convert_polygon_to_wkt(polygon_text: str | None) -> str | None:
      """Convert polygon TEXT to PostGIS POLYGON WKT.
      
      Args:
          polygon_text: Comma-separated coordinate pairs "lat1 lon1,lat2 lon2,..."
      
      Returns:
          WKT POLYGON "POLYGON((lon1 lat1, lon2 lat2, ...))" or NULL
      """
      if not polygon_text or polygon_text.strip() == "":
          return None
      
      try:
          pairs = polygon_text.strip().split(',')
          coords = []
          
          for pair in pairs:
              parts = pair.strip().split()
              if len(parts) != 2:
                  logger.warning(f"Invalid coordinate pair: {pair}")
                  continue
              
              lat = float(parts[0])
              lon = float(parts[1])
              
              if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                  logger.warning(f"Coordinates out of range: lat={lat}, lon={lon}")
                  continue
              
              coords.append((lon, lat))
          
          if len(coords) < 3:
              logger.warning(f"Polygon must have at least 3 points, got {len(coords)}")
              return None
          
          # Auto-close if needed
          if coords[0] != coords[-1]:
              coords.append(coords[0])
          
          # Format as WKT
          coord_str = ', '.join(f"{lon} {lat}" for lon, lat in coords)
          return f"POLYGON(({coord_str}))"
      
      except (ValueError, IndexError) as e:
          logger.error(f"Error converting polygon '{polygon_text}': {e}")
          return None
  ```
- [x] Save file

**Acceptance:**
- Function handles NULL input (returns NULL)
- Function validates coordinate ranges
- Function swaps lat/lon order for each point
- Function auto-closes polygons
- Function checks minimum 3 points

#### Task 2.3: Add conversion function documentation
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 2.1, 2.2

**Steps:**
- [x] Add module-level docstring explaining coordinate conversion
- [x] Add examples in function docstrings
- [x] Document coordinate order swap (lat/lon → lon/lat)
- [x] Save file

**Acceptance:**
- Functions have comprehensive docstrings
- Examples are clear and correct
- Coordinate swap is documented

---

### Phase 3: Export Integration (1.5 hours)

#### Task 3.1: Update export_national_individual_electoral_districts() function
**Effort:** 45 minutes  
**Risk:** Medium  
**Dependencies:** Task 1.4, 2.1, 2.2

**Steps:**
- [x] Open `src/etl/export_canonical_v3.py`
- [x] Find `export_national_individual_electoral_districts()` function
- [x] Add `use_postgis` parameter (default from config)
- [x] Add PostGIS conversion logic:
  ```python
  from src.utils.config import get_config
  
  def export_national_individual_electoral_districts(
      db_connection: duckdb.DuckDBPyConnection,
      output_file: Path,
      use_postgis: bool = None
  ) -> None:
      """Export OEVK with optional PostGIS support."""
      if use_postgis is None:
          use_postgis = get_config().POSTGRESQL_USE_POSTGIS
      
      # ... query data ...
      
      for row in result:
          # ... existing code ...
          center_text = row[3]
          polygon_text = row[4]
          
          if use_postgis:
              # Convert to PostGIS WKT
              center_wkt = convert_center_to_point(center_text)
              polygon_wkt = convert_polygon_to_wkt(polygon_text)
              
              center_sql = f"ST_GeomFromText('{center_wkt}', 4326)" if center_wkt else "NULL"
              polygon_sql = f"ST_GeomFromText('{polygon_wkt}', 4326)" if polygon_wkt else "NULL"
          else:
              # Keep as TEXT (backward compatibility)
              center_sql = f"'{escape_sql_string(center_text)}'" if center_text else "NULL"
              polygon_sql = f"'{escape_sql_string(polygon_text)}'" if polygon_text else "NULL"
          
          # Generate INSERT with appropriate format
          sql = f"INSERT INTO NationalIndividualElectoralDistrict (...) VALUES (..., {center_sql}, {polygon_sql}, ...);\n"
          f.write(sql)
  ```
- [x] Handle NULL cases correctly
- [x] Add logging for conversion stats
- [x] Save file

**Acceptance:**
- Function respects POSTGRESQL_USE_POSTGIS config
- PostGIS mode generates ST_GeomFromText() SQL
- TEXT mode generates quoted strings
- NULL values handled correctly in both modes

#### Task 3.2: Add escape_sql_string helper if not exists
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 3.1

**Steps:**
- [x] Check if `escape_sql_string()` function exists
- [x] If not, add helper function for SQL escaping
- [x] Handle single quotes, backslashes
- [x] Save file

**Acceptance:**
- SQL injection protection in TEXT mode
- Single quotes are escaped correctly

#### Task 3.3: Test export with both modes
**Effort:** 30 minutes  
**Risk:** Medium  
**Dependencies:** Task 3.1

**Steps:**
- [x] Run export with `POSTGRESQL_USE_POSTGIS=true`
- [x] Verify `exports/data.sql` contains `ST_GeomFromText`
- [x] Run export with `POSTGRESQL_USE_POSTGIS=false`
- [x] Verify `exports/data.sql` contains TEXT values
- [x] Compare outputs for correctness

**Acceptance:**
- Both modes generate valid SQL
- PostGIS mode has ST_GeomFromText
- TEXT mode has quoted strings
- No SQL syntax errors

---

### Phase 4: Unit Testing (2 hours)

#### Task 4.1: Create test_postgis_conversion.py
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Create `tests/unit/test_postgis_conversion.py`
- [x] Add imports and test class structure
- [x] Save file

**Acceptance:**
- Test file created in correct location
- Imports work correctly

#### Task 4.2: Write unit tests for convert_center_to_point()
**Effort:** 45 minutes  
**Risk:** Low  
**Dependencies:** Task 2.1, 4.1

**Steps:**
- [x] Add test for valid conversion
- [x] Add test for coordinate swap verification
- [x] Add test for NULL handling
- [x] Add test for empty string handling
- [x] Add test for invalid format
- [x] Add test for out-of-range coordinates
- [x] Run tests: `pytest tests/unit/test_postgis_conversion.py -v -k center`

**Tests to write:**
```python
def test_convert_center_valid():
    assert convert_center_to_point("47.4979 19.0402") == "POINT(19.0402 47.4979)"

def test_convert_center_coordinate_swap():
    result = convert_center_to_point("47.0 19.0")
    assert result.startswith("POINT(19.0")  # lon first

def test_convert_center_null():
    assert convert_center_to_point(None) is None
    assert convert_center_to_point("") is None
    assert convert_center_to_point("   ") is None

def test_convert_center_invalid_format():
    assert convert_center_to_point("invalid") is None
    assert convert_center_to_point("47.0") is None

def test_convert_center_out_of_range():
    assert convert_center_to_point("91.0 19.0") is None  # lat > 90
    assert convert_center_to_point("47.0 181.0") is None  # lon > 180
```

**Acceptance:**
- All 6+ test scenarios pass
- 100% code coverage for convert_center_to_point()

#### Task 4.3: Write unit tests for convert_polygon_to_wkt()
**Effort:** 45 minutes  
**Risk:** Low  
**Dependencies:** Task 2.2, 4.1

**Steps:**
- [x] Add test for valid polygon conversion
- [x] Add test for coordinate swap
- [x] Add test for auto-close functionality
- [x] Add test for already-closed polygon
- [x] Add test for minimum points validation
- [x] Add test for NULL handling
- [x] Run tests: `pytest tests/unit/test_postgis_conversion.py -v -k polygon`

**Tests to write:**
```python
def test_convert_polygon_valid():
    result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
    assert result.startswith("POLYGON((")
    assert "19.0 47.5" in result  # Verify swap

def test_convert_polygon_auto_close():
    result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
    assert result.endswith("19.0 47.5))")  # Auto-closed

def test_convert_polygon_already_closed():
    result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.5 19.0")
    assert result.count("19.0 47.5") == 2  # Not duplicated

def test_convert_polygon_minimum_points():
    assert convert_polygon_to_wkt("47.0 19.0,47.1 19.1") is None  # < 3 points
```

**Acceptance:**
- All 6+ test scenarios pass
- 100% code coverage for convert_polygon_to_wkt()

#### Task 4.4: Write configuration tests
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 1.4

**Steps:**
- [x] Add test for default value (true)
- [x] Add test for explicit false
- [x] Add test for case-insensitive parsing
- [x] Run tests

**Acceptance:**
- Configuration tests pass
- Default behavior verified

---

### Phase 5: Integration Testing (1.5 hours)

#### Task 5.1: Create test_postgis_export.py
**Effort:** 20 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Create `tests/integration/test_postgis_export.py`
- [x] Add PostgreSQL test fixture (skip if not available)
- [x] Add imports and test class structure
- [x] Save file

**Acceptance:**
- Test file created
- Fixture properly handles PostgreSQL availability

#### Task 5.2: Write PostGIS extension test
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 5.1

**Steps:**
- [x] Add test to verify PostGIS extension is available
- [x] Test `SELECT PostGIS_version()`
- [x] Mark as integration test
- [x] Run test

**Acceptance:**
- Test passes when PostgreSQL with PostGIS is available
- Test skips gracefully when not available

#### Task 5.3: Write geometry column type test
**Effort:** 20 minutes  
**Risk:** Low  
**Dependencies:** Task 5.1

**Steps:**
- [x] Add test to verify column types are GEOMETRY
- [x] Query information_schema.columns
- [x] Verify SRID is 4326
- [x] Run test

**Acceptance:**
- Test verifies Center is GEOMETRY(POINT, 4326)
- Test verifies Polygon is GEOMETRY(POLYGON, 4326)

#### Task 5.4: Write spatial index test
**Effort:** 20 minutes  
**Risk:** Low  
**Dependencies:** Task 5.1

**Steps:**
- [x] Add test to verify spatial indexes exist
- [x] Query pg_indexes
- [x] Verify GiST index type
- [x] Run test

**Acceptance:**
- Test finds idx_oevk_center_gist
- Test finds idx_oevk_polygon_gist
- Both are GiST indexes

#### Task 5.5: Write spatial query test
**Effort:** 25 minutes  
**Risk:** Medium  
**Dependencies:** Task 5.1

**Steps:**
- [x] Add test data to PostgreSQL
- [x] Execute point-in-polygon query
- [x] Verify query works and returns results
- [x] Verify query plan uses spatial index
- [x] Clean up test data
- [x] Run test

**Acceptance:**
- Spatial query executes successfully
- Query plan shows index usage
- Results are correct

#### Task 5.6: Run full integration test suite
**Effort:** 10 minutes  
**Risk:** Low  
**Dependencies:** All Phase 5 tasks

**Steps:**
- [x] Run: `pytest tests/integration/test_postgis_export.py -v`
- [x] Verify all tests pass or skip gracefully
- [x] Document any failures

**Acceptance:**
- All integration tests pass when PostgreSQL available
- Tests skip with clear message when not available

---

### Phase 6: Documentation and Validation (1.5 hours)

#### Task 6.1: Update README.md with PostGIS section
**Effort:** 30 minutes  
**Risk:** Low  
**Dependencies:** All implementation tasks

**Steps:**
- [x] Open `README.md`
- [x] Add PostGIS Support section under PostgreSQL Export
- [x] Include:
  - Requirements (PostgreSQL 12+, PostGIS 3.0+)
  - Configuration (`POSTGRESQL_USE_POSTGIS`)
  - Docker setup example
  - Spatial query examples
  - Reference to docs/010_ADD_POSTGIST_SUPPORT.md
- [x] Save file

**Acceptance:**
- README has PostGIS section
- Examples are clear and correct
- Links to detailed docs

#### Task 6.2: Update CHANGELOG or release notes
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** All implementation tasks

**Steps:**
- [x] Add entry for PostGIS support feature
- [x] List key capabilities added
- [x] Note configuration option
- [x] Save file

**Acceptance:**
- CHANGELOG updated
- Feature clearly described

#### Task 6.3: Test with sample OEVK data
**Effort:** 30 minutes  
**Risk:** Medium  
**Dependencies:** All implementation tasks

**Steps:**
- [x] Run full export pipeline with real data
- [x] Enable PostGIS: `export POSTGRESQL_USE_POSTGIS=true`
- [x] Generate exports: `python -m src.cli export-postgresql`
- [x] Load into PostgreSQL (Docker or local)
- [x] Verify geometries are valid: `SELECT ST_IsValid(Polygon) FROM NationalIndividualElectoralDistrict`
- [x] Test sample spatial query
- [x] Document results

**Acceptance:**
- Export completes without errors
- All geometries are valid
- Spatial queries return expected results
- Spatial indexes are used

#### Task 6.4: Test backward compatibility (TEXT mode)
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 6.3

**Steps:**
- [x] Disable PostGIS: `export POSTGRESQL_USE_POSTGIS=false`
- [x] Run export again
- [x] Verify TEXT format in generated SQL
- [x] Load into regular PostgreSQL (no PostGIS)
- [x] Verify data loads correctly

**Acceptance:**
- TEXT mode works without PostGIS
- Legacy format preserved
- No breaking changes for existing users

---

### Phase 7: Final Validation and Cleanup (30 minutes)

#### Task 7.1: Run complete test suite
**Effort:** 10 minutes  
**Risk:** Low  
**Dependencies:** All previous tasks

**Steps:**
- [x] Run: `pytest tests/ -v --tb=short`
- [x] Verify all tests pass
- [x] Check code coverage: `pytest --cov=src --cov-report=term-missing`
- [x] Document coverage metrics

**Acceptance:**
- All tests pass
- No regressions in existing tests
- PostGIS tests pass
- Coverage > 90% for new code

#### Task 7.2: Code quality checks
**Effort:** 10 minutes  
**Risk:** Low  
**Dependencies:** All implementation tasks

**Steps:**
- [x] Run: `ruff check src/`
- [x] Fix any linting issues
- [x] Run: `ruff format src/`
- [x] Run: `mypy src/etl/export_canonical_v3.py`
- [x] Fix any type errors

**Acceptance:**
- No ruff errors
- No mypy errors
- Code properly formatted

#### Task 7.3: Manual QGIS verification (optional)
**Effort:** 10 minutes  
**Risk:** Low  
**Dependencies:** Task 6.3

**Steps:**
- [x] Install QGIS (if available)
- [x] Connect to PostgreSQL database
- [x] Add NationalIndividualElectoralDistrict as layer
- [x] Verify polygons display correctly on map
- [x] Verify attribute table shows all fields
- [x] Take screenshot for documentation

**Acceptance:**
- OEVK polygons display in QGIS
- Map shows Hungarian geography correctly
- All attributes accessible

---

## Parallel Work Opportunities

**Can be done in parallel:**
- Phase 1 (Schema) and Phase 2 (Functions) - different files
- Task 4.2 and Task 4.3 (different test files or classes)
- Task 5.2, 5.3, 5.4 (independent integration tests)
- Task 6.1 and Task 6.2 (different documentation files)

**Must be sequential:**
- Phase 2 before Phase 3 (functions before export integration)
- Phase 3 before Phase 4 (implementation before unit testing)
- Phase 3 before Phase 5 (implementation before integration testing)
- Phases 4 & 5 before Phase 6 (testing before validation)

---

## Risk Mitigation

### Risk: Coordinate Order Confusion

**Likelihood:** Medium  
**Impact:** High (invalid geometries)  
**Mitigation:**
- Extensive unit tests for coordinate swap
- Clear documentation of lat/lon → lon/lat conversion
- Validation in conversion functions
- Visual verification in QGIS

### Risk: PostgreSQL Without PostGIS

**Likelihood:** Low  
**Impact:** Medium (feature unavailable)  
**Mitigation:**
- Configuration toggle (POSTGRESQL_USE_POSTGIS)
- Docker Compose with PostGIS image
- Clear documentation of requirements
- Backward compatibility with TEXT mode

### Risk: Invalid Geometry Data

**Likelihood:** Low  
**Impact:** Medium (data quality issues)  
**Mitigation:**
- PostGIS validates geometries on insert
- Conversion functions validate coordinates
- Integration tests verify valid geometries
- `ST_IsValid()` checks in test suite

---

## Success Criteria Checklist

**Schema:**
- [x] PostGIS extension enabled in schema.sql
- [x] Center column is GEOMETRY(POINT, 4326)
- [x] Polygon column is GEOMETRY(POLYGON, 4326)
- [x] Spatial indexes created (GiST)

**Code:**
- [x] convert_center_to_point() function implemented
- [x] convert_polygon_to_wkt() function implemented
- [x] Export function uses PostGIS when enabled
- [x] Configuration option works correctly

**Testing:**
- [x] 12+ unit tests pass
- [x] 4+ integration tests pass
- [x] Code coverage > 90% for new code
- [x] No test regressions

**Documentation:**
- [x] README updated with PostGIS section
- [x] CHANGELOG updated
- [x] Spatial query examples provided
- [x] Configuration options documented

**Validation:**
- [x] Full export works with real data
- [x] Geometries validate with ST_IsValid()
- [x] Spatial queries execute successfully
- [x] QGIS can load OEVK data (optional)
- [x] Backward compatibility verified (TEXT mode)

---

**Total Estimated Time:** 6-8 hours  
**Phases:** 7  
**Tasks:** 38  
**Priority:** Medium (valuable feature enhancement)
