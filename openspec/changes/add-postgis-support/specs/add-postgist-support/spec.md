# Spec Delta: PostGIS Support

**Capability:** `add-postgist-support`  
**Change Type:** Feature Addition

---

## ADDED Requirements

### Requirement: Coordinate conversion functions must transform TEXT to WKT format

**The system SHALL provide conversion functions that transform TEXT-based coordinates to Well-Known Text (WKT) format for PostGIS, handling coordinate order swap, validation, and edge cases.**

**Priority:** High  
**Rationale:** Conversion functions are the bridge between DuckDB TEXT storage and PostgreSQL GEOMETRY types. Correct implementation is critical for data integrity.

#### Scenario: Center point TEXT is converted to WKT POINT with coordinate swap

**Given** OEVK center coordinates in TEXT format "47.4979 19.0402" (lat lon)  
**When** `convert_center_to_point()` is called  
**Then** the function SHALL return "POINT(19.0402 47.4979)" (lon lat)  
**And** longitude SHALL be the first coordinate  
**And** latitude SHALL be the second coordinate

**Verification:**
```python
from src.etl.export_canonical_v3 import convert_center_to_point

result = convert_center_to_point("47.4979 19.0402")
assert result == "POINT(19.0402 47.4979)"
assert result.startswith("POINT(19.0402")  # Verify lon first
```

#### Scenario: Polygon TEXT is converted to WKT POLYGON with all coordinates swapped

**Given** polygon coordinates "47.5 19.0,47.5 19.1,47.4 19.1"  
**When** `convert_polygon_to_wkt()` is called  
**Then** each coordinate pair SHALL be swapped from (lat, lon) to (lon, lat)  
**And** result SHALL be valid WKT POLYGON format

**Verification:**
```python
from src.etl.export_canonical_v3 import convert_polygon_to_wkt

result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
assert "19.0 47.5" in result  # First point swapped
assert "19.1 47.5" in result  # Second point swapped
assert result.startswith("POLYGON((")
```

#### Scenario: NULL and empty inputs return NULL without error

**Given** NULL or empty string input  
**When** conversion function is called  
**Then** the function SHALL return NULL  
**And** no exception SHALL be raised  
**And** no error SHALL be logged

**Verification:**
```python
assert convert_center_to_point(None) is None
assert convert_center_to_point("") is None
assert convert_center_to_point("   ") is None

assert convert_polygon_to_wkt(None) is None
assert convert_polygon_to_wkt("") is None
```

#### Scenario: Invalid coordinates are rejected with validation

**Given** coordinates with values out of valid range  
**When** conversion function is called  
**Then** the function SHALL return NULL  
**And** a warning SHALL be logged with the invalid values

**Verification:**
```python
# Latitude out of range (-90 to 90)
assert convert_center_to_point("91.0 19.0") is None  # lat > 90
assert convert_center_to_point("-91.0 19.0") is None  # lat < -90

# Longitude out of range (-180 to 180)
assert convert_center_to_point("47.0 181.0") is None  # lon > 180
assert convert_center_to_point("47.0 -181.0") is None  # lon < -180
```

#### Scenario: Malformed input is handled gracefully

**Given** malformed coordinate input (wrong format, non-numeric values)  
**When** conversion function is called  
**Then** the function SHALL return NULL  
**And** an error SHALL be logged describing the issue

**Verification:**
```python
assert convert_center_to_point("invalid") is None
assert convert_center_to_point("47.0") is None  # Missing lon
assert convert_center_to_point("47.0 19.0 extra") is None  # Too many parts
assert convert_center_to_point("abc def") is None  # Non-numeric
```

### Requirement: Polygons must be automatically closed during conversion

**The system SHALL ensure all polygons are closed (first point equals last point) by automatically appending the first coordinate if the polygon is not already closed.**

**Priority:** Medium  
**Rationale:** PostGIS requires closed polygons per OGC Simple Features specification. Source data may contain unclosed polygons.

#### Scenario: Unclosed polygon is automatically closed

**Given** polygon with coordinates that do not form a closed ring  
**When** `convert_polygon_to_wkt()` is called  
**Then** the first coordinate pair SHALL be automatically appended to close the polygon  
**And** the result SHALL have first point equal to last point

**Verification:**
```python
# Input: 3 points, not closed
result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")

# Output: 4 points, closed (first point added at end)
assert result.startswith("POLYGON((19.0 47.5")
assert result.endswith("19.0 47.5))")
```

#### Scenario: Already closed polygon is not modified

**Given** polygon that is already closed (first point == last point)  
**When** `convert_polygon_to_wkt()` is called  
**Then** the closing point SHALL NOT be duplicated  
**And** the first coordinate SHALL appear exactly twice (start and end)

**Verification:**
```python
# Input: Already closed
result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.0,47.5 19.0")

# Output: Should not duplicate closing point
assert result.count("19.0 47.5") == 2  # Appears at start and end only
```

#### Scenario: Polygon with less than 3 points is rejected

**Given** polygon with less than 3 coordinate pairs  
**When** `convert_polygon_to_wkt()` is called  
**Then** the function SHALL return NULL  
**And** a warning SHALL be logged

**Verification:**
```python
assert convert_polygon_to_wkt("47.0 19.0") is None  # 1 point
assert convert_polygon_to_wkt("47.0 19.0,47.1 19.1") is None  # 2 points
```

### Requirement: Export function must support PostGIS geometry generation

**The system SHALL modify the PostgreSQL export function to generate `ST_GeomFromText()` SQL statements when PostGIS is enabled, using converted WKT values.**

**Priority:** High  
**Rationale:** Integration point that connects conversion functions to PostgreSQL data generation.

#### Scenario: PostGIS enabled generates ST_GeomFromText SQL

**Given** `POSTGRESQL_USE_POSTGIS=true` configuration  
**When** exporting NationalIndividualElectoralDistrict to PostgreSQL  
**Then** INSERT statements SHALL use `ST_GeomFromText('POINT(...)', 4326)` for Center  
**And** INSERT statements SHALL use `ST_GeomFromText('POLYGON(...)', 4326)` for Polygon  
**And** SRID SHALL be 4326 for all geometries

**Verification:**
```python
# Check generated SQL contains PostGIS functions
with open('exports/data.sql', 'r') as f:
    sql = f.read()
    assert "ST_GeomFromText('POINT(" in sql
    assert "ST_GeomFromText('POLYGON((" in sql
    assert ", 4326)" in sql  # SRID specified
```

#### Scenario: PostGIS disabled generates TEXT values

**Given** `POSTGRESQL_USE_POSTGIS=false` configuration  
**When** exporting NationalIndividualElectoralDistrict to PostgreSQL  
**Then** INSERT statements SHALL use TEXT values for Center  
**And** INSERT statements SHALL use TEXT values for Polygon  
**And** no ST_GeomFromText functions SHALL be used

**Verification:**
```python
# Check generated SQL uses TEXT format
with open('exports/data.sql', 'r') as f:
    sql = f.read()
    assert "ST_GeomFromText" not in sql
    # Center and Polygon should be quoted TEXT values
```

#### Scenario: NULL geometry values are handled correctly

**Given** OEVK record with NULL Center or Polygon  
**When** exporting to PostgreSQL with PostGIS enabled  
**Then** INSERT statement SHALL use NULL for the geometry column  
**And** no ST_GeomFromText function SHALL be called for NULL values

**Verification:**
```python
# Export should handle NULL without errors
# Check SQL contains: ..., NULL, ... (not ST_GeomFromText(NULL))
```

### Requirement: Configuration option must control PostGIS behavior

**The system SHALL provide a configuration option `POSTGRESQL_USE_POSTGIS` that controls whether PostGIS geometry types or TEXT types are used in PostgreSQL exports.**

**Priority:** Medium  
**Rationale:** Enables backward compatibility and gradual migration for existing installations.

#### Scenario: POSTGRESQL_USE_POSTGIS defaults to true

**Given** no explicit configuration is set  
**When** reading configuration  
**Then** `POSTGRESQL_USE_POSTGIS` SHALL default to `true`  
**And** PostGIS geometry types SHALL be used by default

**Verification:**
```python
from src.utils.config import get_config

# With no environment variable set
config = get_config()
assert config.POSTGRESQL_USE_POSTGIS == True
```

#### Scenario: POSTGRESQL_USE_POSTGIS can be set to false

**Given** environment variable `POSTGRESQL_USE_POSTGIS=false`  
**When** reading configuration  
**Then** `POSTGRESQL_USE_POSTGIS` SHALL be `false`  
**And** TEXT types SHALL be used instead of geometry types

**Verification:**
```bash
export POSTGRESQL_USE_POSTGIS=false
# Run export
# Verify schema.sql contains: Center TEXT, Polygon TEXT
```

#### Scenario: POSTGRESQL_USE_POSTGIS accepts case-insensitive values

**Given** environment variable with mixed case ("True", "FALSE", "tRuE")  
**When** parsing configuration  
**Then** the value SHALL be normalized to boolean correctly

**Verification:**
```python
import os
from src.utils.config import get_config

os.environ['POSTGRESQL_USE_POSTGIS'] = 'True'
assert get_config().POSTGRESQL_USE_POSTGIS == True

os.environ['POSTGRESQL_USE_POSTGIS'] = 'FALSE'
assert get_config().POSTGRESQL_USE_POSTGIS == False
```

### Requirement: Docker configuration must use PostGIS image

**The system SHALL provide Docker Compose configuration using the official PostGIS image to ensure PostGIS extension availability.**

**Priority:** Medium  
**Rationale:** Simplifies setup and ensures PostGIS is pre-installed in containerized environments.

#### Scenario: Docker Compose specifies PostGIS image

**Given** `docker-compose.yml` configuration file  
**When** inspecting the PostgreSQL service definition  
**Then** the image SHALL be `postgis/postgis:15-3.3` or compatible PostGIS image  
**And** the image SHALL include PostgreSQL 12+ and PostGIS 3.0+

**Verification:**
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgis/postgis:15-3.3
```

#### Scenario: PostGIS extension is available in container

**Given** PostgreSQL container running with PostGIS image  
**When** connecting to the database  
**Then** `CREATE EXTENSION postgis` SHALL succeed  
**And** PostGIS functions SHALL be immediately available

**Verification:**
```bash
docker-compose exec postgres psql -U oevk_user -d oevk_data \
  -c "CREATE EXTENSION IF NOT EXISTS postgis; SELECT PostGIS_version();"
# Should output PostGIS version without error
```

#### Scenario: Environment variables configure database credentials

**Given** `.env` file with `POSTGRES_PASSWORD` variable  
**When** Docker Compose starts PostgreSQL service  
**Then** database SHALL be created with credentials from environment  
**And** password SHALL be read from `.env` file

**Verification:**
```bash
# .env file
POSTGRES_PASSWORD=secure_password_here

# docker-compose.yml uses ${POSTGRES_PASSWORD}
# Connection should work with the password
```

---

## Implementation Notes

### Files to Modify

1. **src/etl/export_canonical_v3.py**
   - Add `convert_center_to_point()` function
   - Add `convert_polygon_to_wkt()` function
   - Modify `export_national_individual_electoral_districts()` function
   - Add PostGIS mode check

2. **src/utils/config.py**
   - Add `POSTGRESQL_USE_POSTGIS` configuration variable

3. **exports/schema.sql**
   - Add `CREATE EXTENSION IF NOT EXISTS postgis;`
   - Change Center from TEXT to GEOMETRY(POINT, 4326)
   - Change Polygon from TEXT to GEOMETRY(POLYGON, 4326)
   - Add spatial indexes

4. **docker-compose.yml** (new or update existing)
   - Add PostgreSQL service with PostGIS image
   - Configure environment variables
   - Mount schema and data files

5. **tests/unit/test_postgis_conversion.py** (new)
   - Unit tests for conversion functions

6. **tests/integration/test_postgis_export.py** (new)
   - Integration tests for PostGIS export

### Coordinate System Details

- **SRID 4326:** WGS 84 (standard GPS coordinates)
- **Order:** PostGIS uses (longitude, latitude) per OGC specification
- **Source:** Hungarian electoral data uses (latitude, longitude)
- **Conversion:** Always swap coordinates during transformation

### Error Handling Strategy

- **NULL inputs:** Return NULL, no error
- **Invalid format:** Return NULL, log error
- **Out of range:** Return NULL, log warning
- **Malformed data:** Return NULL, log error
- **Never raise exceptions:** Graceful degradation to NULL

---

**Created:** 2025-10-24  
**Status:** Proposed  
**Related:** `docs/010_ADD_POSTGIST_SUPPORT.md`, proposal.md, design.md
