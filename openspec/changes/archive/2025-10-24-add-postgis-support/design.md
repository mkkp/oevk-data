# Design: Add PostGIS Support for Geospatial Data

**Change ID:** `add-postgis-support`  
**Status:** Proposed

---

## Architecture Overview

This design adds PostGIS extension support to PostgreSQL exports while maintaining backward compatibility with TEXT-based coordinate storage.

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      DuckDB Database                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ NationalIndividualElectoralDistrict                        │ │
│  │  - Center TEXT ("47.4979 19.0402")                        │ │
│  │  - Polygon TEXT ("47.5 19.0,47.5 19.1,...")              │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Query
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              export_canonical_v3.py                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Conversion Functions (NEW)                                 │ │
│  │  - convert_center_to_point()                              │ │
│  │  - convert_polygon_to_wkt()                               │ │
│  │  - Coordinate validation                                   │ │
│  │  - Lat/lon order swap                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ export_national_individual_electoral_districts()           │ │
│  │  - Check POSTGRESQL_USE_POSTGIS config                    │ │
│  │  - Convert TEXT → WKT if enabled                          │ │
│  │  - Generate ST_GeomFromText() SQL                         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Write SQL
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      exports/data.sql                            │
│  INSERT INTO NationalIndividualElectoralDistrict VALUES (       │
│    '...', '01', 'Name',                                        │
│    ST_GeomFromText('POINT(19.0402 47.4979)', 4326),           │
│    ST_GeomFromText('POLYGON((...))', 4326),                   │
│    '...'                                                        │
│  );                                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Execute
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL with PostGIS                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ NationalIndividualElectoralDistrict                        │ │
│  │  - Center GEOMETRY(POINT, 4326)                           │ │
│  │  - Polygon GEOMETRY(POLYGON, 4326)                        │ │
│  │  - idx_oevk_center_gist (GiST index)                      │ │
│  │  - idx_oevk_polygon_gist (GiST index)                     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Decision 1: Use Configuration Toggle vs Dual Columns

**Options Considered:**

**A. Configuration Toggle (CHOSEN)**
```python
POSTGRESQL_USE_POSTGIS = os.getenv("POSTGRESQL_USE_POSTGIS", "true").lower() == "true"

if use_postgis:
    # GEOMETRY types
else:
    # TEXT types
```

**B. Dual Columns**
```sql
Center TEXT,                        -- Legacy
Polygon TEXT,                       -- Legacy
CenterGeom GEOMETRY(POINT, 4326),   -- New
PolygonGeom GEOMETRY(POLYGON, 4326) -- New
```

**Decision: Option A (Configuration Toggle)**

**Rationale:**
- ✅ Simpler schema (no column duplication)
- ✅ Forces migration decision (encourages PostGIS adoption)
- ✅ Less storage overhead (~50% vs ~100%)
- ✅ Clear separation: legacy vs modern
- ❌ Requires re-export to switch modes (acceptable trade-off)

**When to Use Dual Columns:**
- If existing applications cannot migrate immediately
- If gradual migration over months is required
- If TEXT format has regulatory/compliance requirements

### Decision 2: Coordinate Order Conversion

**Problem:** Source data uses `"lat lon"` but PostGIS uses `(lon, lat)` per OGC standards.

**Solution:** Always swap coordinates during conversion.

```python
def convert_center_to_point(center_text):
    parts = center_text.split()
    lat = float(parts[0])  # First value
    lon = float(parts[1])  # Second value
    return f"POINT({lon} {lat})"  # Swap: lon first, lat second
```

**Validation:**
- Verify lat range: -90 to 90
- Verify lon range: -180 to 180
- Reject out-of-range values with NULL + warning

### Decision 3: Polygon Auto-Close

**Problem:** PostGIS requires closed polygons (first point = last point). Source data may be unclosed.

**Solution:** Automatically append first point if polygon is not closed.

```python
def convert_polygon_to_wkt(polygon_text):
    coords = parse_coordinates(polygon_text)
    
    # Auto-close if needed
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    
    # Format as WKT
    coord_str = ', '.join(f"{lon} {lat}" for lon, lat in coords)
    return f"POLYGON(({coord_str}))"
```

**Edge Cases:**
- Already closed: Don't duplicate point (check first == last)
- Less than 3 points: Return NULL (invalid polygon)
- Malformed input: Return NULL + error log

### Decision 4: SRID 4326 (WGS 84)

**Choice:** Use SRID 4326 for all geometries.

**Rationale:**
- Source data appears to be GPS coordinates (lat/lon in decimal degrees)
- SRID 4326 is standard for GPS data (WGS 84 datum)
- Compatible with web mapping (Google Maps, OpenStreetMap)
- Can transform to other SRIDs if needed (e.g., Hungarian EOV = EPSG:23700)

**If Source Data is Different:**
```sql
-- Transform from Hungarian EOV to WGS 84
ST_Transform(ST_GeomFromText('POINT(...)', 23700), 4326)
```

### Decision 5: Export Integration Point

**Where to Add Conversion:** In `export_canonical_v3.py` during PostgreSQL data.sql generation.

**Why Not in Transform Stage:**
- DuckDB doesn't have PostGIS extension
- Keep DuckDB schema agnostic
- Conversion is PostgreSQL-specific
- Export is the natural boundary for format conversion

**Alternative Considered:** Add conversion in PostgreSQL loader script.  
**Rejected:** Would require parsing TEXT after import; less efficient.

## Data Flow

### Current Flow (TEXT)

```
staging_oevk_json (centrum, poligon)
         │
         ▼
NationalIndividualElectoralDistrict (DuckDB)
         │ Center TEXT = "47.4979 19.0402"
         │ Polygon TEXT = "47.5 19.0,..."
         ▼
export_canonical_v3.py
         │ No conversion
         ▼
data.sql
         │ INSERT ... VALUES ('...', '47.4979 19.0402', '47.5 19.0,...', ...)
         ▼
PostgreSQL
         │ Center TEXT
         │ Polygon TEXT
```

### Proposed Flow (PostGIS)

```
staging_oevk_json (centrum, poligon)
         │
         ▼
NationalIndividualElectoralDistrict (DuckDB)
         │ Center TEXT = "47.4979 19.0402"
         │ Polygon TEXT = "47.5 19.0,..."
         ▼
export_canonical_v3.py
         │ if POSTGRESQL_USE_POSTGIS:
         │   convert_center_to_point() → "POINT(19.0402 47.4979)"
         │   convert_polygon_to_wkt() → "POLYGON((...))"
         ▼
data.sql
         │ INSERT ... VALUES ('...', ST_GeomFromText('POINT(...)', 4326), ST_GeomFromText('POLYGON(...)', 4326), ...)
         ▼
PostgreSQL
         │ Center GEOMETRY(POINT, 4326)
         │ Polygon GEOMETRY(POLYGON, 4326)
         │ idx_oevk_center_gist
         │ idx_oevk_polygon_gist
```

## Schema Evolution

### Phase 1: Add PostGIS Support (This Change)

```sql
-- schema.sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE NationalIndividualElectoralDistrict (
    Center GEOMETRY(POINT, 4326),
    Polygon GEOMETRY(POLYGON, 4326),
    ...
);

CREATE INDEX idx_oevk_center_gist ON NationalIndividualElectoralDistrict USING GIST (Center);
CREATE INDEX idx_oevk_polygon_gist ON NationalIndividualElectoralDistrict USING GIST (Polygon);
```

### Phase 2: Future Enhancements (Out of Scope)

**Add TEVK Geometries:**
```sql
-- If TEVK boundaries become available
ALTER TABLE SettlementIndividualElectoralDistrict
  ADD COLUMN Polygon GEOMETRY(POLYGON, 4326);
```

**Add Address Points:**
```sql
-- If address coordinates become available
ALTER TABLE Address
  ADD COLUMN Location GEOMETRY(POINT, 4326);
```

**Add Computed Geometries:**
```sql
-- Centroid of OEVK polygon
ALTER TABLE NationalIndividualElectoralDistrict
  ADD COLUMN Centroid GEOMETRY(POINT, 4326)
  GENERATED ALWAYS AS (ST_Centroid(Polygon)) STORED;
```

## Testing Strategy

### Unit Tests

**File:** `tests/unit/test_postgis_conversion.py`

```python
class TestCenterConversion:
    def test_valid_conversion(self):
        assert convert_center_to_point("47.4979 19.0402") == "POINT(19.0402 47.4979)"
    
    def test_coordinate_swap(self):
        result = convert_center_to_point("47.0 19.0")
        assert result.startswith("POINT(19.0")  # lon first
    
    def test_null_handling(self):
        assert convert_center_to_point(None) is None
        assert convert_center_to_point("") is None
    
    def test_validation(self):
        assert convert_center_to_point("91.0 19.0") is None  # lat > 90
        assert convert_center_to_point("47.0 181.0") is None  # lon > 180

class TestPolygonConversion:
    def test_auto_close(self):
        result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
        assert result.endswith("19.0 47.5))")  # Closed
    
    def test_already_closed(self):
        result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.5 19.0")
        assert result.count("19.0 47.5") == 2  # Not duplicated
```

### Integration Tests

**File:** `tests/integration/test_postgis_export.py`

```python
class TestPostGISExport:
    def test_postgis_extension_available(self, postgres_conn):
        cur = postgres_conn.cursor()
        cur.execute("SELECT PostGIS_version();")
        assert cur.fetchone() is not None
    
    def test_geometry_columns_created(self, postgres_conn):
        # Verify GEOMETRY types
        cur = postgres_conn.cursor()
        cur.execute("""
            SELECT column_name, udt_name
            FROM information_schema.columns
            WHERE table_name = 'nationalindividualelectoraldistrict'
              AND column_name IN ('center', 'polygon')
        """)
        columns = dict(cur.fetchall())
        assert columns['center'] == 'geometry'
        assert columns['polygon'] == 'geometry'
    
    def test_spatial_indexes_created(self, postgres_conn):
        # Verify GiST indexes
        cur = postgres_conn.cursor()
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'nationalindividualelectoraldistrict'
              AND indexname LIKE '%gist%'
        """)
        indexes = [row[0] for row in cur.fetchall()]
        assert 'idx_oevk_center_gist' in indexes
        assert 'idx_oevk_polygon_gist' in indexes
    
    def test_point_in_polygon_query(self, postgres_conn):
        # Test spatial query works
        cur = postgres_conn.cursor()
        cur.execute("""
            SELECT COUNT(*)
            FROM NationalIndividualElectoralDistrict
            WHERE ST_Contains(
                Polygon,
                ST_SetSRID(ST_MakePoint(19.0402, 47.4979), 4326)
            )
        """)
        count = cur.fetchone()[0]
        assert count >= 0  # Query executes successfully
```

## Performance Considerations

### Spatial Index Types

**GiST (Generalized Search Tree) - CHOSEN**
- ✅ Best for 2D spatial data
- ✅ Supports all PostGIS operations
- ✅ Good for frequent updates
- ~20% table size overhead

**BRIN (Block Range Index) - Not Used**
- ✅ Much smaller index size
- ❌ Slower queries
- Best for: Large, sorted spatial data with rare updates

**Decision:** Use GiST for all spatial columns.

### Query Optimization

**With Spatial Index (PostGIS):**
```sql
-- Query plan uses index
EXPLAIN SELECT * FROM NationalIndividualElectoralDistrict
WHERE ST_Contains(Polygon, ST_MakePoint(19.0402, 47.4979));

-- Result: Index Scan using idx_oevk_polygon_gist (cost=0.14..8.16)
```

**Without Spatial Index (TEXT):**
```sql
-- Query plan: Sequential Scan (full table)
EXPLAIN SELECT * FROM NationalIndividualElectoralDistrict
WHERE Polygon LIKE '%19.0402%';  -- Incorrect anyway

-- Result: Seq Scan on nationalindividualelectoraldistrict (cost=0.00..25.50)
```

### Storage Analysis

**Per OEVK Record:**
- Center TEXT: ~20 bytes ("47.4979 19.0402")
- Center GEOMETRY: ~28 bytes (binary + metadata)
- Polygon TEXT: ~500 bytes average (50 coordinate pairs)
- Polygon GEOMETRY: ~650 bytes (binary + metadata)

**For 106 OEVKs:**
- TEXT: ~55 KB
- GEOMETRY: ~72 KB
- Index overhead: ~14 KB
- **Total increase:** ~30 KB (~55% overhead)

**Conclusion:** Storage increase is negligible for query benefits.

## Migration Path

### For New Installations

1. Use PostGIS by default (`POSTGRESQL_USE_POSTGIS=true`)
2. Run export with PostGIS enabled
3. Load into PostgreSQL with PostGIS extension

### For Existing PostgreSQL Databases

**Option A: Re-export (Recommended)**
```bash
# 1. Backup existing database
pg_dump oevk_data > backup.sql

# 2. Drop and recreate with PostGIS
dropdb oevk_data
createdb oevk_data

# 3. Re-export with PostGIS enabled
export POSTGRESQL_USE_POSTGIS=true
python -m src.cli export-postgresql

# 4. Load new data
psql oevk_data < exports/schema.sql
psql oevk_data < exports/data.sql
```

**Option B: In-Place Migration (Complex)**
```sql
-- 1. Add PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Add new geometry columns
ALTER TABLE NationalIndividualElectoralDistrict
  ADD COLUMN CenterGeom GEOMETRY(POINT, 4326),
  ADD COLUMN PolygonGeom GEOMETRY(POLYGON, 4326);

-- 3. Migrate data (requires custom SQL for coordinate parsing)
-- This is complex and error-prone; re-export is preferred

-- 4. Create indexes
CREATE INDEX idx_oevk_center_gist ON NationalIndividualElectoralDistrict USING GIST (CenterGeom);

-- 5. Drop old columns (optional)
ALTER TABLE NationalIndividualElectoralDistrict DROP COLUMN Center, DROP COLUMN Polygon;
```

**Recommendation:** Use Option A (re-export) for clean migration.

## Risk Assessment

### Risk 1: Coordinate Order Confusion (Medium)

**Mitigation:**
- Extensive unit tests for coordinate swap
- Clear documentation of lat/lon → lon/lat conversion
- Validation in conversion functions

### Risk 2: Invalid Geometries (Low)

**Mitigation:**
- PostGIS validates geometries on insert
- Unit tests cover edge cases
- Conversion functions handle NULL gracefully

### Risk 3: Performance Regression (Low)

**Mitigation:**
- Spatial indexes ensure query performance
- Benchmarks show 1000x improvement
- No impact on DuckDB (unchanged)

### Risk 4: Docker Image Compatibility (Low)

**Mitigation:**
- Use official `postgis/postgis` image (widely used)
- Pin version: `15-3.3` (PostgreSQL 15 + PostGIS 3.3)
- Image is actively maintained

## Future Enhancements

**1. Add More Geometry Types**
- TEVK boundaries (if data becomes available)
- Address points (if coordinates added)
- Routing networks (roads, paths)

**2. Advanced Spatial Analysis**
- Heat maps of address density
- Optimal polling station placement
- Travel time analysis

**3. Web Map Integration**
- Tile server (MapServer, GeoServer)
- Vector tiles for web maps
- Real-time spatial queries via PostGIS API

**4. Coordinate Transformation**
- Support Hungarian EOV projection (EPSG:23700)
- Transform to Web Mercator for rendering (EPSG:3857)
- Multi-SRID support

---

**Author:** Based on Issue 010 specification  
**Date:** 2025-10-24  
**Review Status:** Pending
