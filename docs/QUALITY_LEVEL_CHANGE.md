# Quality Level Change: INTERPOLATED

## Summary

Interpolated addresses now use a separate quality level `INTERPOLATED` instead of being upgraded to `EXACT`. This distinguishes between addresses with coordinates from geocoding services (EXACT) and calculated coordinates (INTERPOLATED).

## Change Details

### Before
```python
class GeocodingQuality(Enum):
    EXACT = "exact"       # House-level match
    STREET = "street"     # Street-level match
    SETTLEMENT = "settlement"
    FAILED = "failed"
```

Interpolated addresses were marked as `EXACT`.

### After
```python
class GeocodingQuality(Enum):
    EXACT = "exact"           # House-level match (from geocoding service)
    INTERPOLATED = "interpolated"  # House-level match (calculated via interpolation)
    STREET = "street"         # Street-level match
    SETTLEMENT = "settlement"
    FAILED = "failed"
```

Interpolated addresses are now marked as `INTERPOLATED`.

## Quality Levels Explained

| Quality | Source | Precision | Description |
|---------|--------|-----------|-------------|
| **EXACT** | Geocoding API | Highest | Direct match from Nominatim/HERE with house number |
| **INTERPOLATED** | Calculation | High | Calculated from nearby exact matches using linear interpolation |
| **STREET** | Geocoding API | Medium | Street centroid, no specific house number |
| **SETTLEMENT** | Geocoding API | Low | Settlement centroid |
| **FAILED** | - | None | No match found |

## Impact on Statistics

### Before Change
```
Quality Distribution:
  EXACT:  100% (4 exact + 11 interpolated)
  STREET:   0%
```

### After Change
```
Quality Distribution:
  EXACT:         26.7% (4 from geocoding)
  INTERPOLATED:  73.3% (11 calculated)
  STREET:         0%
```

## Impact on Real Dataset

For the full OEVK dataset (~664,600 addresses):

### Expected Distribution After Improvements

**Before Quality Change:**
- EXACT: 45-55% (includes both geocoded and interpolated)
- STREET: 35-45%
- SETTLEMENT: 5-7%
- FAILED: 0.1-0.2%

**After Quality Change:**
- **EXACT: 19-25%** (from geocoding only)
- **INTERPOLATED: 20-30%** (calculated)
- STREET: 35-45%
- SETTLEMENT: 5-7%
- FAILED: 0.1-0.2%

**Combined high-precision (EXACT + INTERPOLATED): 45-55%**

## Benefits of Separate Quality Level

1. **Transparency**: Clear distinction between geocoded and calculated coordinates
2. **Quality Assessment**: Users can evaluate precision based on source
3. **Filtering**: Easy to filter by geocoding method
4. **Validation**: Can validate interpolated coordinates separately
5. **Auditing**: Clear tracking of data sources

## Database Queries

### Count by Quality
```sql
SELECT 
    GeocodingQuality,
    COUNT(*) as Count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as Percentage
FROM CanonicalAddress
GROUP BY GeocodingQuality
ORDER BY 
    CASE GeocodingQuality
        WHEN 'exact' THEN 1
        WHEN 'interpolated' THEN 2
        WHEN 'street' THEN 3
        WHEN 'settlement' THEN 4
        WHEN 'failed' THEN 5
    END;
```

### Get Only Geocoded Addresses (not interpolated)
```sql
SELECT * FROM CanonicalAddress 
WHERE GeocodingQuality = 'exact';
```

### Get All High-Precision Addresses (geocoded + interpolated)
```sql
SELECT * FROM CanonicalAddress 
WHERE GeocodingQuality IN ('exact', 'interpolated');
```

### Get Only Interpolated Addresses
```sql
SELECT * FROM CanonicalAddress 
WHERE GeocodingQuality = 'interpolated';
```

## Source Tracking

Interpolated addresses also have distinct source values:

| Source | Description |
|--------|-------------|
| `interpolated (10-50)` | Linear interpolation between house #10 and #50 |
| `extrapolated (nearest: 70)` | Extrapolated beyond known range, nearest is #70 |

Example query:
```sql
SELECT 
    GeocodingSource,
    COUNT(*) as Count
FROM CanonicalAddress
WHERE GeocodingQuality = 'interpolated'
GROUP BY GeocodingSource
ORDER BY Count DESC
LIMIT 10;
```

## Migration Notes

### For Existing Data

If you have already run geocoding with the old code (interpolated as EXACT):

1. **Re-run geocoding** to update quality levels:
   ```bash
   python -m src.cli geocode run --force
   ```

2. **Or manually update** in database:
   ```sql
   UPDATE CanonicalAddress
   SET GeocodingQuality = 'interpolated'
   WHERE GeocodingSource LIKE 'interpolated%'
      OR GeocodingSource LIKE 'extrapolated%';
   ```

### For Applications

If your application filters by quality:

**Old code:**
```python
# Get high-precision addresses
exact_addresses = df.filter(pl.col("GeocodingQuality") == "exact")
```

**New code:**
```python
# Get high-precision addresses (both exact and interpolated)
high_precision = df.filter(
    pl.col("GeocodingQuality").is_in(["exact", "interpolated"])
)

# Or if you only want geocoded (not calculated):
exact_only = df.filter(pl.col("GeocodingQuality") == "exact")
```

## Testing

All tests updated and passing:

```bash
python test_interpolation.py
```

Output:
```
✓ All test cases passed!
Quality Distribution:
  EXACT:        26.7% (4 from geocoding)
  INTERPOLATED: 73.3% (11 calculated)
  STREET:        0%
```

## Documentation Updated

- ✅ `src/etl/geocoding.py` - Code updated
- ✅ `test_interpolation.py` - Tests updated
- ✅ `QUALITY_LEVEL_CHANGE.md` - This document (NEW)

## Backward Compatibility

⚠️ **Breaking Change**: This is a breaking change for applications that:
- Filter by `GeocodingQuality == 'exact'`
- Assume all house-level coordinates are from geocoding

**Migration**: Update filters to include `INTERPOLATED` if you want all house-level precision:
```python
high_precision = ["exact", "interpolated"]
```

## Recommendations

1. **Use EXACT + INTERPOLATED** for high-precision filtering
2. **Use EXACT only** if you need geocoding-verified coordinates
3. **Check GeocodingSource** for detailed tracking
4. **Document** which quality levels your application uses

## Questions?

- **Q: Should I trust interpolated coordinates?**
  - A: Yes! Interpolation is mathematically sound for addresses between known points. Accuracy depends on street geometry (straight streets = more accurate).

- **Q: Which is better: INTERPOLATED or STREET?**
  - A: INTERPOLATED is better. It provides house-level precision (calculated) vs street centroid.

- **Q: Can I upgrade INTERPOLATED to EXACT?**
  - A: No. EXACT should only be used for geocoding service results. INTERPOLATED indicates calculated coordinates.

- **Q: How do I get only real geocoded data?**
  - A: Filter by `GeocodingQuality = 'exact'` and `GeocodingSource IN ('nominatim_local', 'here_api', 'cache')`.
