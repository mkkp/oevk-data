# TEVK Settlement_ID Mapping Fix

**Date:** 2025-11-04  
**Issue:** Incorrect settlement mapping in SettlementIndividualElectoralDistrict (TEVK) table  
**Status:** ✅ FIXED

## Problem Description

In the TEVK table, the `settlement_id` column referenced incorrect settlements. The root cause was that `settlement_code` is only unique within a county, so settlements from different counties with the same code were randomly selected.

### Root Cause

In the `transform_settlement_individual_electoral_districts()` function (`src/etl/transform_optimized.py:404`), the JOIN with the Settlement table was incorrect:

**INCORRECT CODE:**
```sql
JOIN County c ON sk.county_code = c.CountyCode
JOIN Settlement s ON sk.county_code = c.CountyCode AND sk.settlement_code = s.SettlementCode
```

**Problem:** The second JOIN only used `settlement_code` from the Settlement table, but did not properly link the county (County_ID). Since `settlement_code` is only unique within a county, if two different counties had the same code, it randomly selected one regardless of which county it belonged to.

**Example:**
- Pest county has a settlement with code "01" (Budapest)
- Borsod county also has a settlement with code "01" (Miskolc)
- During the JOIN, it randomly selected one, regardless of which county the record was actually from

## Solution

Fixed the JOIN condition to also use `Settlement.County_ID`:

**CORRECTED CODE:**
```sql
JOIN County c ON sk.county_code = c.CountyCode
JOIN Settlement s ON s.County_ID = c.ID AND sk.settlement_code = s.SettlementCode
```

**Change:** Instead of `sk.county_code = c.CountyCode`, using `s.County_ID = c.ID` ensures that the settlement belongs to the correct county.

## Files Modified

1. **`src/etl/transform_optimized.py:404`**
   - Modified the Settlement JOIN condition

## Verification

According to the Settlement table schema (`src/database/schema.sql:23-24`):
```sql
CREATE TABLE IF NOT EXISTS Settlement (
    ID TEXT PRIMARY KEY, -- md5(CountyCode|SettlementCode)
    SettlementCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, SettlementCode)  -- SettlementCode is only unique within a county!
);
```

The `UNIQUE (County_ID, SettlementCode)` constraint confirms that `settlement_code` is indeed only unique within a county.

## Other Files Checked

✅ **`src/etl/transform.py`** - Does not use JOIN, instead uses `hash_settlement_id(county_code, settlement_code)` - CORRECT  
✅ **`src/etl/transform_optimized.py` - `transform_polling_stations()`** - Uses hash functions - CORRECT

## Impact

**Before Fix:**
- TEVK records had random settlement IDs from different counties with the same settlement_code
- Data integrity violated
- Reports and queries produced incorrect results

**After Fix:**
- TEVK records correctly reference settlements in the correct county
- Data integrity restored
- All foreign key relationships valid

## Testing

After the fix, re-run the transformation:

```bash
python src/cli.py run --force
```

This will recreate the TEVK table with correct settlement_id values.

### Verification Query

To verify the fix, run this query:

```sql
-- Verification: check if every TEVK record's settlement_id belongs to the same county as County_ID
SELECT 
    tevk.ID,
    tevk.Name,
    tevk.County_ID as TEVK_County_ID,
    s.County_ID as Settlement_County_ID,
    c1.CountyName as TEVK_County,
    c2.CountyName as Settlement_County,
    CASE 
        WHEN tevk.County_ID = s.County_ID THEN 'OK' 
        ELSE 'MISMATCH' 
    END as Status
FROM SettlementIndividualElectoralDistrict tevk
JOIN Settlement s ON tevk.Settlement_ID = s.ID
JOIN County c1 ON tevk.County_ID = c1.ID
JOIN County c2 ON s.County_ID = c2.ID
WHERE tevk.County_ID != s.County_ID;
```

**Expected:** This query should return zero rows (all County_IDs match).

## Prevention

For all JOINs with the Settlement table, always use `County_ID`, not just `SettlementCode`:

**CORRECT pattern:**
```sql
JOIN Settlement s ON s.County_ID = c.ID AND sk.settlement_code = s.SettlementCode
```

**INCORRECT pattern:**
```sql
JOIN Settlement s ON sk.settlement_code = s.SettlementCode  -- NOT sufficient!
```
