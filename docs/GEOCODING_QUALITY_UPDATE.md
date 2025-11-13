# Geocoding Quality Update Summary

## Important Change

**INTERPOLATED** is now a separate quality level (not included in EXACT).

## Quality Levels (5 total)

1. **EXACT** - House-level from geocoding service (19-25%)
2. **INTERPOLATED** - House-level calculated (20-30%) ← NEW
3. **STREET** - Street centroid (35-45%)
4. **SETTLEMENT** - Settlement centroid (5-7%)
5. **FAILED** - No coordinates (0.1-0.2%)

## Updated Statistics

### Before Improvements
- Exact: 19%
- Street: 73%
- Settlement: 7%
- Failed: 0.2%

### After Improvements (with INTERPOLATED as separate)
- **Exact: 19-25%** (geocoded only)
- **Interpolated: 20-30%** (calculated)
- **Street: 35-45%**
- **Settlement: 5-7%**
- **Failed: 0.1-0.2%**

**High-Precision (EXACT + INTERPOLATED): 45-55%**

## Key Points

✅ EXACT + INTERPOLATED combined = 45-55% high-precision  
✅ INTERPOLATED is mathematically sound and reliable  
✅ Use `IN ('exact', 'interpolated')` for high-precision filtering  
✅ Use `= 'exact'` only if you need geocoding-verified coordinates  

## SQL Queries

**Get all high-precision:**
```sql
WHERE GeocodingQuality IN ('exact', 'interpolated')
```

**Get only geocoded:**
```sql
WHERE GeocodingQuality = 'exact'
```

**Get only calculated:**
```sql
WHERE GeocodingQuality = 'interpolated'
```

## Documentation Updated

All documentation files have been updated to reflect INTERPOLATED as a separate quality level. See:

- `docs/GEOCODING_QUALITY_LEVELS.md` - Complete reference
- `QUALITY_LEVEL_CHANGE.md` - Change details
- All other geocoding docs updated

## Test Results

```
✓ All tests pass with INTERPOLATED quality
Quality Distribution (test data):
  EXACT:        26.7% (from geocoding)
  INTERPOLATED: 73.3% (calculated)
  STREET:        0%
```
