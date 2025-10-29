<!--
DOCUMENT METADATA
=================
Title: House Number Leading Zeros Fix
Type: Changelog
Category: Fix
Status: Implemented
Version: 1.0
Created: 2025-10-29
Last Updated: 2025-10-29
Author: System

Related Documents:
- Building/Staircase Fix (commit e02fc49)
- NULL House Numbers (CHANGES_NULL_HOUSE_NUMBERS.md)

Related Code:
- src/etl/deduplicate.py (lines 632-670: column cleaning)
- src/etl/deduplicate.py (lines 373-431: _clean_house_number function)

Dependencies:
- Polars for data processing

Keywords: house-number, leading-zeros, data-quality, cleaning, deduplication, fix

Summary:
Fix for house_number, building, and staircase columns containing leading zeros in exports and database dumps. The cleaning logic existed but was only used for formatting full_address. Solution adds explicit column cleaning step before formatting to store cleaned values (15 instead of 000015). Includes test verification and impact analysis.

Audience:
Developers working on data cleaning, ETL pipeline maintainers, data quality engineers.
-->

# House Number Leading Zeros Fix

## Issue

House numbers in the PostgreSQL database and CSV exports contained leading zeros (e.g., `000015`, `000068`, `000017/0002`) instead of cleaned values (e.g., `15`, `68`, `17/0002`).

**Example from database:**
```sql
SELECT house_number, full_address FROM address LIMIT 5;

 house_number |        full_address
--------------+-----------------------------
 000015       | Szőlőhegy dűlő 15.
 000068       | II. körzet tanya 68.
 000017/0002  | Bethlen utca 17/0002.
 000029/0004  | Lázár utca 29/0004.
 000004       | Báró Rudnyánszki S. utca 4.
```

## Root Cause

The `_clean_house_number()` function existed and worked correctly, but it was only being used in `_format_full_address()` to generate the formatted address string. The cleaned house number was **never stored back** to the `house_number` column in the dataframe.

**Before:**
```python
# _clean_house_number() was only called inside _format_full_address()
def _format_full_address(self, street_name, street_type, house_num, ...):
    cleaned_house = self._clean_house_number(house_num)  # Used for formatting
    # ... but original house_num with leading zeros was kept in the column

# The dataframe still had original values:
pl.first("house_number").alias("house_number")  # Still had "000015"
```

## Solution

Added an explicit cleaning step **before** the formatting step to clean the `house_number` column:

**After (deduplicate.py:632-639):**
```python
# Clean house_number column (strip leading zeros)
def clean_house_number_udf(house_num: str) -> str:
    return self._clean_house_number(house_num or "")

formatted_df = addresses_df.with_columns(
    pl.col("house_number")
    .map_elements(clean_house_number_udf, return_dtype=pl.Utf8)
    .alias("house_number")
)

# Then apply formatting to create full_address column
formatted_df = formatted_df.with_columns(
    pl.struct(["street_name", "street_type", "house_number", ...])
    .map_elements(lambda row: format_address_udf(...))
    .alias("full_address")
)
```

## Changes Made

### File: `src/etl/deduplicate.py`

**Location:** Lines 632-639 (before the full_address formatting step)

**Change:** Added `house_number` column cleaning:
```python
# Clean house_number column (strip leading zeros)
def clean_house_number_udf(house_num: str) -> str:
    return self._clean_house_number(house_num or "")

formatted_df = addresses_df.with_columns(
    pl.col("house_number")
    .map_elements(clean_house_number_udf, return_dtype=pl.Utf8)
    .alias("house_number")
)
```

## Verification

Created test script that verifies the cleaning logic:

```python
Test Cases:
✓ 000015          → 15              (simple number)
✓ 000068          → 68              (simple number)
✓ 000017/0002     → 17/0002         (slash notation)
✓ 000000          → ""              (all zeros → empty)
✓ 000000          → ""              (infrastructure address)
```

All test cases passed ✓

## Expected Results After Fix

After re-running the pipeline:

**Database:**
```sql
SELECT house_number, full_address FROM address LIMIT 5;

 house_number |        full_address
--------------+-----------------------------
 15           | Szőlőhegy dűlő 15.
 68           | II. körzet tanya 68.
 17/0002      | Bethlen utca 17/0002.
 29/0004      | Lázár utca 29/0004.
 4            | Báró Rudnyánszki S. utca 4.
```

**CSV Exports:**
```csv
id,house_number,building,staircase,full_address,...
abc123,15,,,Szőlőhegy dűlő 15.,...
def456,68,,,II. körzet tanya 68.,...
```

## Impact

- **CSV Exports:** All CSV files will have cleaned house numbers
- **PostgreSQL Dumps:** Database dumps will have cleaned values
- **Backward Compatibility:** Full addresses remain unchanged (they were already using cleaned values)
- **Data Quality:** Improved consistency and cleaner data

## Related Logic

The `_clean_house_number()` function handles these cases:

1. **Simple numbers:** `000015` → `15`
2. **Ranges:** `000001-00005` → `1-5`
3. **Slash notation:** `000001/D` → `1/D`
4. **All zeros:** `000000` → `""` (empty, for infrastructure addresses)
5. **Null/empty:** `None` or `""` → `""`

## To Apply This Fix

1. The code change is already in `src/etl/deduplicate.py`
2. Re-run the pipeline to regenerate exports:
   ```bash
   python -m src.cli run
   ```
3. Re-create PostgreSQL dump:
   ```bash
   python -m src.cli db verify
   ```
4. Load new dump to database:
   ```bash
   python scripts/load_dump_to_docker.py --drop-database
   ```

## Files Modified

- `src/etl/deduplicate.py` (lines 632-639)

## Version

- **Fixed in:** 2025-10-29
- **Issue discovered:** During PostgreSQL dump review
- **Testing:** Unit test created and passed

## Notes

- This is a data quality fix that improves the cleanliness of exported data
- The `full_address` field was already correct because it was using cleaned values
- Only the `house_number` column itself had leading zeros
- No schema changes required
- No breaking changes - only improves data quality
