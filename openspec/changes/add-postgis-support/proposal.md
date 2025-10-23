# Proposal: Add PostGIS Support for Geospatial Data

**Change ID:** `add-postgis-support`  
**Status:** Proposed  
**Priority:** Medium  
**Effort:** Medium (~6-8 hours)  
**Breaking Change:** No (additive feature, backward compatible)

## Why

Currently, OEVK (NationalIndividualElectoralDistrict) geospatial data is stored as TEXT in PostgreSQL exports:

```sql
Center TEXT,   -- "47.4979 19.0402" (space-separated lat lon)
Polygon TEXT,  -- "47.5 19.0,47.5 19.1,..." (comma-separated coordinate pairs)
```

**Problems:**
- ❌ No spatial indexing → slow spatial queries (O(n) instead of O(log n))
- ❌ No spatial operations → cannot do distance, containment, area calculations
- ❌ Manual parsing required → error-prone coordinate extraction
- ❌ No validation → invalid coordinates can be stored
- ❌ No GIS tool integration → cannot load into QGIS, ArcGIS
- ❌ Poor query performance → point-in-polygon takes seconds instead of milliseconds

**Impact:** Geospatial analysis is impractical without native geometry support.

## What Changes

Add **PostGIS extension** support to PostgreSQL exports for native GEOMETRY types with spatial indexing.

### 1. Schema Enhancement

**Before (TEXT storage):**
```sql
CREATE TABLE NationalIndividualElectoralDistrict (
    ID UUID PRIMARY KEY,
    OEVK TEXT NOT NULL,
    Name TEXT NOT NULL,
    Center TEXT,      -- "lat lon"
    Polygon TEXT,     -- "lat1 lon1,lat2 lon2,..."
    County_ID UUID NOT NULL
);
```

**After (PostGIS GEOMETRY):**
```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE NationalIndividualElectoralDistrict (
    ID UUID PRIMARY KEY,
    OEVK TEXT NOT NULL,
    Name TEXT NOT NULL,
    Center GEOMETRY(POINT, 4326),      -- Native POINT with SRID
    Polygon GEOMETRY(POLYGON, 4326),   -- Native POLYGON with SRID
    County_ID UUID NOT NULL
);

-- Spatial indexes for fast queries
CREATE INDEX idx_oevk_center_gist ON NationalIndividualElectoralDistrict USING GIST (Center);
CREATE INDEX idx_oevk_polygon_gist ON NationalIndividualElectoralDistrict USING GIST (Polygon);
```

### 2. Coordinate Conversion

**Conversion Functions:**
- `convert_center_to_point()` - TEXT "lat lon" → WKT "POINT(lon lat)"
- `convert_polygon_to_wkt()` - TEXT coordinates → WKT "POLYGON((...))"

**Key Requirements:**
- Swap lat/lon order (PostGIS uses lon/lat per OGC standard)
- Validate coordinate ranges (lat: -90 to 90, lon: -180 to 180)
- Auto-close polygons (first point = last point)
- Handle NULL/invalid inputs gracefully

**Example:**
```python
# Input: "47.4979 19.0402" (lat lon)
# Output: "POINT(19.0402 47.4979)" (lon lat)
convert_center_to_point("47.4979 19.0402")

# Input: "47.5 19.0,47.5 19.1,47.4 19.1"
# Output: "POLYGON((19.0 47.5, 19.1 47.5, 19.1 47.4, 19.0 47.5))" (auto-closed)
convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
```

### 3. Export Integration

**Updated Export Function:**
```python
def export_national_individual_electoral_districts(
    db_connection, output_file, use_postgis=True
):
    """Export OEVK with optional PostGIS geometry conversion."""
    for row in results:
        if use_postgis:
            center_wkt = convert_center_to_point(row.center)
            polygon_wkt = convert_polygon_to_wkt(row.polygon)
            
            center_sql = f"ST_GeomFromText('{center_wkt}', 4326)" if center_wkt else "NULL"
            polygon_sql = f"ST_GeomFromText('{polygon_wkt}', 4326)" if polygon_wkt else "NULL"
        else:
            # Backward compatibility: TEXT format
            center_sql = f"'{row.center}'" if row.center else "NULL"
            polygon_sql = f"'{row.polygon}'" if row.polygon else "NULL"
        
        # Generate INSERT statement...
```

### 4. Configuration

**Environment Variable:**
```bash
# Enable PostGIS (default)
export POSTGRESQL_USE_POSTGIS=true

# Disable for backward compatibility
export POSTGRESQL_USE_POSTGIS=false
```

### 5. Docker Integration

**Use Official PostGIS Image:**
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgis/postgis:15-3.3  # PostgreSQL 15 + PostGIS 3.3
    environment:
      POSTGRES_DB: oevk_data
      POSTGRES_USER: oevk_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
```

### 6. Spatial Query Capabilities

**Point-in-Polygon:**
```sql
-- Find OEVK containing GPS coordinate
SELECT OEVK, Name
FROM NationalIndividualElectoralDistrict
WHERE ST_Contains(Polygon, ST_SetSRID(ST_MakePoint(19.0402, 47.4979), 4326));
```

**Distance Calculation:**
```sql
-- Calculate distance between OEVK centers in kilometers
SELECT 
    a.OEVK, b.OEVK,
    ST_Distance(ST_Transform(a.Center, 3857), ST_Transform(b.Center, 3857)) / 1000 as km
FROM NationalIndividualElectoralDistrict a, NationalIndividualElectoralDistrict b
WHERE a.ID != b.ID;
```

**Area Calculation:**
```sql
-- Calculate OEVK area in square kilometers
SELECT OEVK, ST_Area(ST_Transform(Polygon, 3857)) / 1000000 as area_km2
FROM NationalIndividualElectoralDistrict;
```

**Adjacency Detection:**
```sql
-- Find OEVKs that share a boundary
SELECT a.OEVK, b.OEVK
FROM NationalIndividualElectoralDistrict a
CROSS JOIN NationalIndividualElectoralDistrict b
WHERE a.ID < b.ID AND ST_Touches(a.Polygon, b.Polygon);
```

## Impact

### Performance Improvements

| Query Type | Without PostGIS (TEXT) | With PostGIS (GEOMETRY + GiST) | Speedup |
|------------|------------------------|--------------------------------|---------|
| Point-in-polygon | ~5000ms (full scan) | ~5ms (indexed) | **1000x** |
| Distance calculation | ~3000ms (parse + calculate) | ~3ms (native) | **1000x** |
| Bounding box query | ~4000ms (O(n)) | ~2ms (O(log n)) | **2000x** |
| Area calculation | Manual calculation | Native function | N/A |

### Storage Impact

- **Geometry columns:** ~30% larger than TEXT (binary format with metadata)
- **Spatial indexes:** ~20% of table size
- **Total overhead:** ~50% storage increase
- **Trade-off:** Storage cost justified by massive query performance gains

### User Benefits

✅ **GIS Tool Integration:** Direct import into QGIS, ArcGIS  
✅ **Spatial Queries:** Point-in-polygon, distance, area, adjacency  
✅ **Export Formats:** GeoJSON, Shapefile, KML via PostGIS functions  
✅ **Validation:** PostGIS validates geometries on insert  
✅ **Standards Compliance:** OGC Simple Features specification  

### Backward Compatibility

**Option 1: Configuration Toggle (Recommended)**
- Use `POSTGRESQL_USE_POSTGIS` environment variable
- Default: `true` (PostGIS enabled)
- Fallback: `false` (TEXT format for legacy systems)

**Option 2: Dual Columns (Future Enhancement)**
- Keep both TEXT and GEOMETRY columns
- Populate both during export
- Applications choose which to use

**This proposal uses Option 1** for simplicity and to encourage PostGIS adoption.

## Alternatives Considered

### Alternative 1: Keep TEXT, Add Parsing Functions

**Rejected:** Functions still can't use spatial indexes; no performance gain.

### Alternative 2: Store as JSON with coordinates

**Rejected:** No spatial indexing, no GIS integration, parsing overhead.

### Alternative 3: Use separate geospatial database

**Rejected:** Adds complexity, data duplication, sync issues.

### Alternative 4: Client-side geometry handling

**Rejected:** Pushes complexity to every client, no query optimization.

## Dependencies

**Depends On:** None

**Blocks:**
- Advanced geospatial analysis features
- Web map visualization with efficient backend queries
- Electoral district boundary analysis

**External Dependencies:**
- PostGIS extension (included in `postgis/postgis` Docker image)
- PostgreSQL 12+ (already required)

## Timeline

**Estimated Effort:** 6-8 hours

- **Phase 1:** Schema updates and conversion functions (2 hours)
- **Phase 2:** Export integration and configuration (2 hours)
- **Phase 3:** Testing (unit + integration) (2 hours)
- **Phase 4:** Docker configuration and documentation (1-2 hours)

**Priority:** Medium (valuable enhancement, not blocking)

**Suggested Schedule:**
- Can be implemented in parallel with other features
- Ideal for next sprint after current work completes

## Success Criteria

✅ PostGIS extension enabled in PostgreSQL schema  
✅ OEVK Center stored as `GEOMETRY(POINT, 4326)`  
✅ OEVK Polygon stored as `GEOMETRY(POLYGON, 4326)`  
✅ Spatial indexes created and functional (GiST)  
✅ Coordinate conversion handles lat/lon swap correctly  
✅ Invalid coordinates rejected with validation  
✅ Polygons automatically closed if needed  
✅ Configuration option `POSTGRESQL_USE_POSTGIS` works  
✅ All unit tests pass (8+ test cases)  
✅ All integration tests pass (4+ scenarios)  
✅ Spatial queries execute successfully  
✅ OEVK data loads correctly in QGIS  
✅ Docker Compose uses PostGIS image  
✅ Documentation updated with examples  
✅ No regression in existing TEXT-based workflows  

## References

- **Detailed Specification:** `docs/010_ADD_POSTGIST_SUPPORT.md`
- **PostGIS Documentation:** https://postgis.net/docs/
- **PostGIS Docker Image:** https://hub.docker.com/r/postgis/postgis
- **OGC Simple Features:** https://www.ogc.org/standards/sfa
- **SRID 4326 (WGS 84):** https://epsg.io/4326

---

**Proposed By:** Based on Issue 010 specification  
**Date:** 2025-10-24  
**Spec Deltas:** add-postgist-support (ADDED requirements)  
**Related Changes:** None
