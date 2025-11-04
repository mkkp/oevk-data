<!--
DOCUMENT METADATA
=================
Title: Allow NULL House Numbers
Type: Changelog
Category: Feature
Status: Implemented
Version: 1.0
Created: 2025-10-29
Last Updated: 2025-10-29
Author: System

Related Documents:
- Impact Analysis (HOUSE_NUMBER_NULL_IMPACT_ANALYSIS.md)
- Invalid Addresses Analysis (INVALID_ADDRESSES_ANALYSIS.md)
- House Number Fix (CHANGELOG_HOUSE_NUMBER_FIX.md)

Related Code:
- src/etl/deduplicate.py (lines 373-431: _clean_house_number)
- src/etl/deduplicate.py (lines 479-580: _format_full_address)
- src/etl/export.py (line 593: nullable house_number schema)

Dependencies:
- PostgreSQL schema changes
- Polars for data processing

Keywords: null-house-numbers, infrastructure-addresses, complex-buildings, address-validation, schema-change

Summary:
Implementation details for allowing addresses without house numbers. Retains 7,551 previously filtered addresses including infrastructure locations (railway stations, landmarks) and complex buildings identified by building/staircase only. Updates _clean_house_number() to return empty string for all-zero values, modifies formatting logic to handle 4 new address patterns, and makes PostgreSQL schema house_number field nullable.

Audience:
Developers implementing address validation logic, data quality engineers, database administrators.
-->

# Changes: Allow NULL House Numbers

**Date:** October 29, 2025  
**Status:** ✅ IMPLEMENTED AND TESTED

---

## Summary

Modified the ETL pipeline to allow addresses without house numbers. This retains **7,551 previously filtered addresses** including:
- **2,091 complex buildings** with building/staircase identifiers
- **4,660 infrastructure/area addresses** (railway stations, landmarks, farms)
- **794 special patterns** with partial information

---

## Files Modified

### 1. `src/etl/export.py` (Line 593)
**Change:** PostgreSQL schema now allows NULL house numbers

```sql
-- OLD:
house_number TEXT NOT NULL,

-- NEW:
house_number TEXT,  -- Can be NULL for infrastructure/area addresses or when building/staircase suffices
```

**Impact:** Database can now store addresses without house numbers

---

### 2. `src/etl/deduplicate.py` (Lines 373-431)
**Change:** `_clean_house_number()` returns empty string instead of None

```python
# OLD:
if not cleaned:
    return None  # Invalid

# NEW:
if not cleaned:
    return ""  # Allow empty house number
```

**Impact:** All-zero house numbers ("0000", "00000") now return `""` instead of `None`, allowing further processing

---

### 3. `src/etl/deduplicate.py` (Lines 479-580)
**Change:** `_format_full_address()` handles empty house numbers

**New Cases:**
```python
# Case 1: No house number, but has building AND staircase
if not has_house_number and has_building and has_staircase:
    return f"{street_prefix}, {building}. épület {staircase}. lépcsőház"
    # Example: "Gázgyári lakótelep, 1. épület I. lépcsőház"

# Case 2: No house number, only building
if not has_house_number and has_building:
    return f"{street_prefix}, {building}. épület"
    # Example: "Rákos MÁV telep, 5. épület"

# Case 3: No house number, only staircase
if not has_house_number and has_staircase:
    return f"{street_prefix}, {staircase}. lépcsőház"
    # Example: "Gázgyári lakótelep, I. lépcsőház"

# Case 4: No house number, no building, no staircase (infrastructure)
if not has_house_number:
    return street_prefix
    # Example: "Vasútállomás"
```

**Impact:** All addresses can now be formatted, even without house numbers

---

### 4. `src/etl/deduplicate.py` (Lines 648-675)
**Change:** Removed filtering of addresses with empty full_address

```python
# OLD:
formatted_df = formatted_df.filter(pl.col("full_address").is_not_null())
logger.info(f"Filtered out {filtered_count:,} invalid addresses...")

# NEW:
# No filtering - all addresses kept
# Log statistics about addresses without house numbers
logger.info(
    f"Addresses without house numbers: {no_house_count:,} "
    f"({with_building:,} with building/staircase, "
    f"{no_house_count - with_building:,} infrastructure/area addresses)"
)
```

**Impact:** All 7,551 addresses with empty house numbers are now retained

---

## Test Results

✅ **All tests passed** (see `test_null_house_numbers.py`)

### Test Coverage:

1. **_clean_house_number():**
   - ✓ "000000" → "" (empty string)
   - ✓ "000001" → "1" (leading zeros stripped)
   - ✓ "000000/D" → "" (all zeros with suffix)
   - ✓ "000000 5" → " 5" (space-separated preserved)
   - ✓ None → "" (null input handled)

2. **_format_full_address():**
   - ✓ "Gázgyári lakótelep 000000, Building 0001, Staircase 0001" → "Gázgyári lakótelep, 1. épület I. lépcsőház"
   - ✓ "Vasútállomás 000000" → "Vasútállomás"
   - ✓ "Fazekas utca 000000" → "Fazekas utca"
   - ✓ Normal addresses still work correctly

3. **Real-world addresses:**
   - ✓ All test cases from filtered CSV work correctly
   - ✓ Infrastructure addresses formatted properly
   - ✓ Complex buildings with building/staircase formatted correctly

---

## Expected Impact on Next Pipeline Run

### Address Statistics (Estimated):

**Current (with filtering):**
- Input: 3,336,202 addresses
- Filtered out: 7,551 (0.23%)
- Processed: 3,328,651
- Canonical: 3,315,609
- Duplicates: 20,593

**New (without filtering):**
- Input: 3,336,202 addresses
- Filtered out: 0 ✓
- Processed: **3,336,202** (+7,551)
- Canonical: **~3,323,160** (estimated, +7,551)
- Duplicates: ~20,593 (similar rate)

### Log Output Changes:

**Old Log:**
```
INFO: Filtered out 7,550 invalid addresses (house number is all zeros, e.g., '0000', '00000')
```

**New Log:**
```
INFO: Addresses without house numbers: 7,551 (2,091 with building/staircase, 5,460 infrastructure/area addresses)
```

---

## Address Format Examples

### Before (Filtered Out):
These addresses were LOST:

1. "Gázgyári lakótelep 000000, Building 0001, Staircase 0001" → ❌ Filtered
2. "Vasútállomás 000000" → ❌ Filtered
3. "Fazekas utca 000000" → ❌ Filtered

### After (Retained):
These addresses are now KEPT:

1. "Gázgyári lakótelep 000000, Building 0001, Staircase 0001" → ✅ "Gázgyári lakótelep, 1. épület I. lépcsőház"
2. "Vasútállomás 000000" → ✅ "Vasútállomás"
3. "Fazekas utca 000000" → ✅ "Fazekas utca"

---

## Database Schema Impact

### Address Table Structure:

```sql
CREATE TABLE IF NOT EXISTS address (
    id UUID PRIMARY KEY,
    house_number TEXT,  -- NOW NULLABLE ✓
    building TEXT,
    staircase TEXT,
    full_address TEXT NOT NULL,  -- Always generated, never NULL
    latitude REAL,
    longitude REAL,
    geocoding_quality TEXT,
    geocoding_source TEXT,
    county_id UUID NOT NULL,
    settlement_id UUID NOT NULL,
    public_space_name_id UUID NOT NULL,
    public_space_type_id UUID NOT NULL,
    oevk_id UUID NOT NULL,
    tevk_id UUID NOT NULL,
    postal_code_id UUID NOT NULL,
    polling_station_id UUID NOT NULL
);
```

### Query Examples:

```sql
-- Find addresses without house numbers
SELECT * FROM address WHERE house_number IS NULL OR house_number = '';

-- Find complex buildings (no house number but has building)
SELECT * FROM address 
WHERE (house_number IS NULL OR house_number = '') 
  AND (building IS NOT NULL AND building != '');

-- Find infrastructure addresses (no house, no building, no staircase)
SELECT * FROM address 
WHERE (house_number IS NULL OR house_number = '') 
  AND (building IS NULL OR building = '')
  AND (staircase IS NULL OR staircase = '');
```

---

## Deduplication Impact

### Hash Generation:
- Already handles NULL correctly: `house_number = house_number if house_number is not None else ""`
- Addresses without house numbers will hash with empty string in house number position
- Differentiation by building/staircase still works correctly

### Example Deduplication:
```
"Gázgyári lakótelep, 1. épület I. lépcsőház"  → hash(Gázgyári lakótelep + "" + 1 + I)
"Gázgyári lakótelep, 1. épület II. lépcsőház" → hash(Gázgyári lakótelep + "" + 1 + II)
"Gázgyári lakótelep, 2. épület I. lépcsőház"  → hash(Gázgyári lakótelep + "" + 2 + I)
```
All three get unique hashes ✓

---

## Geocoding Impact

### Addresses Without House Numbers:

**Strategy:** Street-level or area-level geocoding

1. **With building/staircase:** Geocode to street centroid
   - Accuracy: ±50-200 meters
   - `geocoding_quality = "street_level"`

2. **Infrastructure addresses:** Geocode by name or skip
   - Railway stations: May have known coordinates
   - Unknown landmarks: `geocoding_quality = "no_house_number"`
   - May set `latitude = NULL`, `longitude = NULL`

**Current geocoding implementation already handles this** - it attempts to geocode the full_address string, which now includes formatted addresses without house numbers.

---

## Validation Rules

### Old Validation:
```python
if house_number == "000000":
    return None  # Invalid - reject address
```

### New Validation:
```python
if house_number == "000000":
    if building or staircase:
        return format_with_building(...)  # Valid - complex building
    else:
        return format_area_address(...)   # Valid - infrastructure
```

**All addresses are now valid** - none are rejected solely due to missing house numbers.

---

## Benefits

1. **Data Completeness:** +7,551 addresses (0.23% increase)
2. **Better Real-World Representation:** Infrastructure addresses properly included
3. **Complex Buildings Retained:** 2,091 addresses with building/staircase now kept
4. **No Invalid Data:** Only truly invalid patterns still filtered (incomplete ranges like "000020-")

---

## Risks and Mitigation

### Risk 1: Geocoding Accuracy
**Issue:** Addresses without house numbers less precise  
**Mitigation:** Mark with `geocoding_quality = "street_level"` or `"no_house_number"`

### Risk 2: Deduplication Edge Cases
**Issue:** Multiple addresses at same street without house numbers might merge  
**Mitigation:** Building/staircase differentiation prevents unwanted merging

### Risk 3: Query Complexity
**Issue:** Need to handle NULL in queries  
**Mitigation:** Updated documentation with query examples

---

## Next Steps

1. ✅ Code changes completed
2. ✅ Tests passing
3. ⏳ **Run full pipeline** to verify changes in production
4. ⏳ **Review output** for 7,551 newly retained addresses
5. ⏳ **Check geocoding** results for addresses without house numbers
6. ⏳ **Validate database** constraints and queries

---

## Rollback Plan

If issues arise:

1. **Revert schema:** Add back `NOT NULL` constraint
2. **Revert deduplicate.py:** Change `return ""` back to `return None`
3. **Revert filtering:** Add back `filter(pl.col("full_address").is_not_null())`
4. **Regenerate exports:** Re-run pipeline with reverted code

All changes are localized to 3 files and can be easily reverted.

---

## Conclusion

✅ **Implementation successful**  
✅ **All tests passing**  
✅ **Ready for production run**

The ETL pipeline now properly handles addresses without house numbers, retaining 7,551 valid addresses that were previously filtered out. This improves data completeness and better reflects the real-world diversity of Hungarian addresses.
