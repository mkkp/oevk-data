# Geocoding Cache Migration Report

**Date:** 2025-11-04  
**Status:** ✓ COMPLETED SUCCESSFULLY

## Problem Identified

The geocoding cache contained 2,872,430 geocoded addresses, but only 2,154 were being applied to the database (0.07% usage rate).

### Root Cause

The cache was built from a previous version of the data before the leading zero normalization was implemented (commit `e02fc49`). When addresses were normalized to strip leading zeros from `HouseNumber`, `Building`, and `Staircase` columns, the cache keys (based on `MD5(settlement|street|house)`) no longer matched.

**Example:**
- **Old data**: `HouseNumber = "007"` → Cache key: `MD5("Budapest|Main|007")`
- **New data**: `HouseNumber = "7"` → Cache key: `MD5("Budapest|Main|7")` ← **DIFFERENT!**

## Migration Process

### 1. Backup Created
```bash
data/geocoding_cache/geocoding_cache.db.backup_20251104_024705 (941 MB)
```

### 2. Migration Strategy
- Used DuckDB to efficiently join cache entries with current canonical addresses
- Recalculated cache keys using current address normalization
- Resolved duplicates by keeping the best quality entry

### 3. Migration Results

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total cache entries | 2,872,430 | 2,865,724 | -6,706 |
| Matched addresses | 2,154 | **2,935,660** | +2,933,506 |
| Match rate | 0.07% | **88.3%** | +88.2% |
| Migration time | - | 13.2 seconds | - |

### 4. Missing Entries Analysis

**Lost entries:** 6,706 addresses (0.23%)

These are addresses whose IDs no longer exist in the current database, likely because they were:
- Deduplicated and merged into other canonical addresses
- Removed during data cleaning
- Changed significantly during normalization

## Verification

✓ Cache join now finds **2,935,660 matches** (up from 2,154)  
✓ Cache keys correctly match current address normalization  
✓ Quality priorities preserved (exact > street > settlement)  
✓ All address IDs are valid in current database

## Next Steps

The cache is now ready to use. You can apply the migrated cache to your database by running:

```bash
# This will update ~2.9M addresses with cached geocodes
python src/cli.py geocode --update-from-cache
```

**Expected outcome:**
- 2,935,660 addresses will be geocoded from cache (88.3% of 3,322,877 total)
- Only ~387,217 addresses will need new geocoding (11.7%)
- Significant time and API cost savings

## Files Created

- `migrate_cache_fast.py` - Fast migration script using DuckDB
- `test_cache_join.py` - Verification script
- `CACHE_MIGRATION_REPORT.md` - This report

## Backup Information

**Original cache backup location:**
```
data/geocoding_cache/geocoding_cache.db.backup_20251104_024705
```

To restore the original cache if needed:
```bash
mv data/geocoding_cache/geocoding_cache.db data/geocoding_cache/geocoding_cache.db.migrated
cp data/geocoding_cache/geocoding_cache.db.backup_20251104_024705 data/geocoding_cache/geocoding_cache.db
```
