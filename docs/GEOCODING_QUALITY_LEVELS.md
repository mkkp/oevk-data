# Geocoding Quality Levels

## Quality Level Definitions

The OEVK geocoding pipeline uses five quality levels to indicate coordinate precision:

| Quality | Source | Precision | Description |
|---------|--------|-----------|-------------|
| **EXACT** | Geocoding Service | Highest | House-level match directly from Nominatim or HERE API |
| **INTERPOLATED** | Calculation | High | House-level precision calculated via linear interpolation |
| **STREET** | Geocoding Service | Medium | Street-level match (street centroid) |
| **SETTLEMENT** | Geocoding Service | Low | Settlement-level match (settlement centroid) |
| **FAILED** | None | None | No match found |

## Quality Hierarchy

```
EXACT (Geocoded)     ─┐
                      ├─ High Precision (House-level)
INTERPOLATED         ─┘

STREET               ─── Medium Precision (Street-level)

SETTLEMENT           ─── Low Precision (Settlement-level)

FAILED               ─── No Coordinates
```

## Expected Distribution (OEVK Dataset)

### After All Improvements (Nominatim + Interpolation + HERE)

| Quality | Count | Percentage | Description |
|---------|-------|------------|-------------|
| **EXACT** | 126,000-166,000 | 19-25% | From Nominatim/HERE APIs |
| **INTERPOLATED** | 133,000-199,000 | 20-30% | Calculated from nearby exact matches |
| **STREET** | 232,000-299,000 | 35-45% | Street centroids |
| **SETTLEMENT** | 33,000-47,000 | 5-7% | Settlement centroids |
| **FAILED** | 665-1,329 | 0.1-0.2% | No coordinates |

**High-Precision Total (EXACT + INTERPOLATED): 45-55%**

## Usage Guidelines

### When to Use Each Quality Level

**EXACT Only:**
- Critical applications requiring geocoding-verified coordinates
- Legal or official address verification
- Navigation systems
- Emergency services

**EXACT + INTERPOLATED:**
- General mapping and visualization
- Statistical analysis
- Demographic studies
- Address geocoding for most applications

**EXACT + INTERPOLATED + STREET:**
- Approximate location needs
- Regional analysis
- Settlement-level mapping

**All Quality Levels:**
- Complete dataset analysis
- Coverage statistics
- Data quality reports

## SQL Query Examples

### Get High-Precision Addresses
```sql
-- Both geocoded and interpolated (recommended for most uses)
SELECT * FROM CanonicalAddress 
WHERE GeocodingQuality IN ('exact', 'interpolated');
```

### Get Only Geocoded Addresses
```sql
-- Only coordinates from geocoding services
SELECT * FROM CanonicalAddress 
WHERE GeocodingQuality = 'exact';
```

### Get Only Interpolated Addresses
```sql
-- Only calculated coordinates
SELECT * FROM CanonicalAddress 
WHERE GeocodingQuality = 'interpolated';
```

### Quality Distribution
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

## Source Tracking

Each quality level has associated sources:

### EXACT Sources
- `nominatim_local` - Local Nominatim instance
- `here_api` - HERE Geocoding API
- `cache` - Cached from previous geocoding

### INTERPOLATED Sources
- `interpolated (10-50)` - Linear interpolation between house numbers
- `extrapolated (nearest: 70)` - Extrapolated beyond known range

### STREET Sources
- `nominatim_local` - Nominatim street centroid
- `here_api` - HERE street-level result

### SETTLEMENT Sources
- `settlement_centroid` - Settlement centroid fallback
- `nominatim_local` - Nominatim settlement result
- `here_api` - HERE settlement result

## Quality vs Source Query

```sql
SELECT 
    GeocodingQuality,
    GeocodingSource,
    COUNT(*) as Count
FROM CanonicalAddress
GROUP BY GeocodingQuality, GeocodingSource
ORDER BY GeocodingQuality, Count DESC;
```

## Accuracy Considerations

### EXACT
- **Accuracy**: ±5-10 meters typically
- **Reliability**: Highest - verified by geocoding service
- **Coverage**: 19-25% of addresses

### INTERPOLATED
- **Accuracy**: ±10-50 meters typically
- **Reliability**: High - mathematically calculated
- **Coverage**: 20-30% of addresses
- **Note**: More accurate on straight streets, less accurate on curved streets

### STREET
- **Accuracy**: ±50-500 meters
- **Reliability**: Medium - depends on street length
- **Coverage**: 35-45% of addresses

### SETTLEMENT
- **Accuracy**: ±500-5000 meters
- **Reliability**: Low - settlement centroid only
- **Coverage**: 5-7% of addresses

## Best Practices

1. **Default to EXACT + INTERPOLATED** for most applications
2. **Use EXACT only** when you need verified coordinates
3. **Check GeocodingSource** for detailed provenance
4. **Document** which quality levels your application accepts
5. **Validate** critical addresses independently

## Migration from Old Quality Levels

If you have code or queries using the old system (where interpolated = exact):

**Old:**
```sql
-- This would include interpolated addresses
WHERE GeocodingQuality = 'exact'
```

**New:**
```sql
-- Explicitly include both
WHERE GeocodingQuality IN ('exact', 'interpolated')

-- Or only real geocoded
WHERE GeocodingQuality = 'exact' 
  AND GeocodingSource NOT LIKE 'interpolated%'
```

## See Also

- [Geocoding Improvements 2025](GEOCODING_IMPROVEMENTS_2025.md)
- [Geocoding Interpolation](GEOCODING_INTERPOLATION.md)
- [HERE Geocoding](HERE_GEOCODING.md)
- [Quality Level Change](../QUALITY_LEVEL_CHANGE.md)
