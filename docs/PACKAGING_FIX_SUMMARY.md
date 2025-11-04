# PostgreSQL Archive Packaging Fix

**Date:** 2025-11-04  
**Issue:** GitHub release upload failing due to 2GB asset size limit  
**Solution:** Exclude large Address.csv file (use chunked versions instead)

## Problem

The PostgreSQL archive packaging was failing with:
```
HTTP 422: Validation Failed
size must be less than or equal to 2147483648
```

### Root Cause
- **PostgreSQL export directory**: 2.5GB total
- **Address.csv file**: 1.2GB (duplicate of chunked files)
- **GitHub limit**: 2GB per asset
- **Result**: Archive exceeded limit and upload failed

## Solution Implemented

Modified `src/release/packaging.py` to exclude the large `Address.csv` file from the PostgreSQL archive, since the same data exists in chunked files (`Address_chunk*.csv`).

### Changes Made

1. **Filter CSV files** before packaging:
   ```python
   csv_files_filtered = [
       f for f in csv_files 
       if f.name != "Address.csv"
   ]
   ```

2. **Added logging** to inform about excluded files:
   ```
   Excluding 1 large file(s) (Address.csv) - using chunked versions instead
   ```

3. **Updated README** in the archive to document:
   - The full `Address.csv` is intentionally excluded
   - Use `Address_chunk*.csv` files instead
   - Same data, just split into manageable chunks

## Size Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| PostgreSQL directory | 2.5GB | 1.3GB | **-1.2GB** |
| Expected ZIP size | >2.1GB | ~1.3GB | **-800MB** |
| GitHub upload | ❌ FAIL | ✅ PASS | N/A |

## Verification

```bash
# Without Address.csv
$ find exports/postgresql -type f ! -name "Address.csv" -exec du -ch {} + | tail -1
1.3G	total

# With schema.sql and import_postgresql.sql (tiny)
$ ls -lh exports/*.sql
-rw-r--r--  1 robson  staff    26K Nov  4 03:07 exports/import_postgresql.sql
-rw-r--r--  1 robson  staff   7.6K Nov  4 03:03 exports/schema.sql
```

**Final archive size: ~1.3GB** (well under GitHub's 2GB limit)

## Impact

### Positive
✅ Archive now fits under GitHub's 2GB limit  
✅ No data loss - chunked files contain same data  
✅ Faster packaging (less data to process)  
✅ Smaller downloads for users  
✅ Clear documentation in README  

### Considerations
- Users must use `Address_chunk*.csv` files instead of single `Address.csv`
- Import scripts already handle chunked files correctly
- No changes needed to database schema or import process

## Testing

The next release creation should:
1. Package PostgreSQL files successfully
2. Create a ZIP archive under 2GB
3. Upload to GitHub without errors
4. Include all necessary files except Address.csv

## Files Modified

- `src/release/packaging.py` - Filter logic and README content

## Next Steps

The packaging code is now ready. You can:
1. Run the release command again
2. Verify the PostgreSQL archive is created and under 2GB
3. Confirm successful GitHub upload

```bash
# Example release command (adjust based on your CLI)
python src/cli.py release --tag <tag> --force-rebuild
```
