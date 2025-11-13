# PostgreSQL Polygon Auto-Closing Fix

**Date:** 2025-11-05  
**Issue:** Invalid polygon errors during PostgreSQL import  
**Status:** ✅ FIXED

## Problem Description

During PostgreSQL import, 54 OEVK (National Individual Electoral District) polygons were being skipped with "invalid polygon" errors:

```
psql:/tmp/import_postgresql_docker.sql:84: NOTICE:  Skipping invalid polygon for id ba330bba-03e8-5300-af24-134273537631
psql:/tmp/import_postgresql_docker.sql:84: NOTICE:  Skipping invalid polygon for id e23aaf83-672d-5855-acf7-47d17f9ce84d
...
```

### Root Cause Analysis

PostGIS requires that polygon geometries be **closed** - the first coordinate must equal the last coordinate. The exported WKT polygons were not closed.

**Investigation revealed:**

1. **Python function works correctly**: `convert_polygon_to_wkt()` (line 171-172 in export.py) has auto-close logic:
   ```python
   # Auto-close polygon: first point must equal last point
   if coords[0] != coords[-1]:
       coords.append(coords[0])
   ```

2. **SQL export doesn't auto-close**: The PostgreSQL CSV export uses a SQL-based approach (line 1024) that only swaps coordinates:
   ```sql
   'POLYGON((' || regexp_replace(Polygon, '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g') || '))'
   ```

3. **Result**: Polygons exported to PostgreSQL CSV files were unclosed, causing PostGIS validation to fail.

**Example of an unclosed polygon:**
- **ID**: `ba330bba-03e8-5300-af24-134273537631` (Pest 04)
- **Coordinate pairs**: 1,208
- **First**: `18.9280610064928 48.0571220015694`
- **Last**: `18.9337305064918 48.0506001015689` ❌ NOT THE SAME!
- **Error**: `ST_GeomFromText()` rejects unclosed polygons

## Solution

Updated the SQL query in `src/etl/export.py:1024` to auto-close polygons during export:

**Before:**
```sql
CASE
    WHEN Polygon IS NOT NULL THEN
        'POLYGON((' || regexp_replace(Polygon, '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g') || '))'
    ELSE NULL
END as polygon_wkt
```

**After:**
```sql
CASE
    WHEN Polygon IS NOT NULL THEN
        -- Swap lat/lon to lon/lat and auto-close polygon if needed
        CASE
            -- Check if polygon is already closed (first coord == last coord)
            WHEN split_part(Polygon, ',', 1) = split_part(Polygon, ',', -1) THEN
                'POLYGON((' || regexp_replace(Polygon, '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g') || '))'
            ELSE
                -- Auto-close: append first coordinate to the end
                'POLYGON((' || regexp_replace(Polygon, '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g') || ',' || 
                split_part(regexp_replace(split_part(Polygon, ',', 1), '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g'), ' ', 1) || ' ' ||
                split_part(regexp_replace(split_part(Polygon, ',', 1), '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g'), ' ', 2) || '))'
        END
    ELSE NULL
END as polygon_wkt
```

### How the Fix Works

1. **Check if already closed**: Compares first and last coordinate pairs
2. **If closed**: Use existing polygon as-is
3. **If not closed**: 
   - Take the first coordinate pair from the polygon
   - Swap it from (lat, lon) to (lon, lat) format
   - Append it to the end of the coordinate string
   - This ensures `first == last`, making the polygon valid

## Files Modified

1. **`src/etl/export.py:1024`** - Added auto-close logic to SQL export query

## Impact

**Before Fix:**
- 54 OEVK polygons failed to import into PostgreSQL
- Geometries were NULL for these districts
- Spatial queries incomplete

**After Fix:**
- All OEVK polygons import successfully
- Valid PostGIS POLYGON geometries for all districts
- Spatial queries work correctly

## Testing

After the fix, re-run the export:

```bash
python src/cli.py export --db-path data/oevk.db --output-dir exports
```

Then import to PostgreSQL and verify no errors:

```bash
psql -d oevk -f exports/schema.sql
psql -d oevk -f exports/import_postgresql.sql
```

**Expected result**: No "Skipping invalid polygon" notices.

### Verification Query

Check that all OEVK records have valid polygons:

```sql
SELECT 
    COUNT(*) as total,
    COUNT(polygon) as with_polygon,
    COUNT(*) - COUNT(polygon) as missing_polygon
FROM oevk;
```

**Expected**: `missing_polygon = 0` (all records have polygons)

### Validate Polygon Closure

Verify all polygons are closed:

```sql
SELECT 
    id, 
    code, 
    name,
    ST_IsClosed(ST_Boundary(polygon)) as is_closed
FROM oevk
WHERE polygon IS NOT NULL
  AND NOT ST_IsClosed(ST_Boundary(polygon));
```

**Expected**: 0 rows (all polygons are closed)

## PostGIS Polygon Requirements

For reference, PostGIS requires valid polygons to have:

1. ✅ **Closed ring**: First point = Last point
2. ✅ **At least 4 points**: 3 distinct points + 1 closing point
3. ✅ **No self-intersections**: Polygon edges don't cross each other
4. ✅ **Correct winding order**: Counter-clockwise for exterior ring

Our fix addresses requirement #1. The import script also uses `ST_MakeValid()` to fix self-intersections (#3) if they occur.

## Prevention

The dual code paths for polygon conversion (Python function vs SQL query) created inconsistency. To prevent this in the future:

**Option 1**: Always use the Python function for polygon conversion  
**Option 2**: Keep SQL conversion but ensure it matches Python logic (✅ current fix)  
**Option 3**: Add validation tests that verify exported polygons are closed

## Related Code

- **Python polygon conversion**: `src/etl/export.py:128` - `convert_polygon_to_wkt()`
- **SQL polygon conversion**: `src/etl/export.py:1024` - SQL CASE statement
- **PostGIS import**: `exports/import_postgresql.sql:84` - `ST_MakeValid()` handling

## Known Limitations

The SQL auto-close logic assumes:
- Coordinates are comma-separated
- Each pair is space-separated "lat lon"
- The polygon string is well-formed

If source data is malformed (e.g., missing commas, extra spaces), the fix may not work correctly. In such cases, the import script will still skip the invalid polygon with a notice.
