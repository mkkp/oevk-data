<!--
DOCUMENT METADATA
=================
Title: Invalid Addresses Analysis - Data Format Consistency
Type: Specification
Category: Feature
Status: Implemented
Version: 1.0
Created: 2024-10-01
Last Updated: 2024-10-15
Author: System
Change ID: N/A

Related Documents:
- README.md

Related Code:
- src/etl/

Dependencies:
- DuckDB
- Polars

Keywords: change-specification, feature, implementation

Summary:
Change specification document for feature implementation.

Audience:
Developers, technical leads.
-->

# Invalid Addresses Analysis - Data Format Consistency

**Date:** October 29, 2025  
**Issue Reported:** Inconsistency between address details and full address

---

## Summary

The invalid addresses CSV is **CORRECT**. The apparent inconsistency is due to **two different address encoding formats** in the source data, both of which are handled correctly by the filtering logic.

---

## The Two Address Formats

The Hungarian electoral database uses **two different ways** to encode addresses without street-level house numbers:

### Format 1: Using Building/Staircase Fields (INVALID - correctly filtered)
**House Number:** `000000` (all zeros - invalid)  
**Building:** `0001`, `0002`, etc.  
**Staircase:** `0001`, `0002`, etc.

**Example:**
```
Settlement: Budapest III
Street: Gázgyári lakótelep
House Number: 000000
Building: 0001
Staircase: 0001
```

**Status:** ✓ Correctly included in invalid addresses CSV (house number is all zeros)

---

### Format 2: Using Space-Separated House Numbers (VALID - correctly kept)
**House Number:** `000000 5`, `000000 812`, etc. (zeros + space + actual number)  
**Building:** empty  
**Staircase:** empty

**Example:**
```
Settlement: Budapest X
Street: Rákos MÁV telep
House Number: 000000 5
Building: (empty)
Staircase: (empty)
```

**Status:** ✓ Correctly NOT in invalid addresses CSV (actual house number exists after the space)

---

## Why The Filtering Logic Is Correct

### Test Cases

The `_clean_house_number()` function correctly handles both formats:

| Input | Output | Reason |
|-------|--------|--------|
| `"000000"` | `None` | All zeros → invalid ✓ |
| `"000000 5"` | `" 5"` | Space + number → valid (keeps " 5") ✓ |
| `"000000 812"` | `" 812"` | Space + number → valid ✓ |
| `"000001"` | `"1"` | Leading zeros stripped → valid ✓ |

The logic strips leading zeros with `lstrip("0")`:
- `"000000"` → strips all zeros → `""` → empty string → **None (invalid)** ✓
- `"000000 5"` → strips leading zeros → `" 5"` → has content → **valid** ✓

---

## Verified Examples

### Invalid Addresses (In CSV - Correctly Filtered)

All 7,551 addresses have purely all-zero house numbers:

```csv
Budapest III, Gázgyári lakótelep, 000000, Building: 0001, Staircase: 0001
Budapest III, Gázgyári lakótelep, 000000, Building: 0001, Staircase: 0002
József Attila utca, 000000, (no building/staircase)
```

### Valid Addresses (NOT in CSV - Correctly Kept)

These 502 addresses have numbers after spaces and were correctly processed:

```
Budapest X, Rákos MÁV telep, 000000 5
Budapest X, Rákos MÁV telep, 000000 812
Budapest XI, Örsöddűlő út, 000000 1118
Budapest I, Attila út, 000000 0002
```

**Verification:**
```bash
# None of these are in the invalid addresses CSV
grep "000000 5" invalid_addresses_all_zero_house_numbers.csv → NOT FOUND ✓
grep "000000 812" invalid_addresses_all_zero_house_numbers.csv → NOT FOUND ✓
grep "000000 1118" invalid_addresses_all_zero_house_numbers.csv → NOT FOUND ✓
```

---

## Source Data Statistics

| Pattern | Count | Status | In Invalid CSV? |
|---------|-------|--------|-----------------|
| `000000` (pure) | 7,093 | Invalid | ✓ Yes |
| `000000` + Building/Staircase | 458 | Invalid | ✓ Yes |
| `000000 [digit]` (space-separated) | 502 | Valid | ✗ No |
| `000001` and similar (leading zeros) | 3,328,149 | Valid | ✗ No |

---

## Why This Appears Inconsistent

When viewing the CSV, you might see:

**Row 1:**
- **Polling Station Address:** "Gázgyári lakótelepi Óvoda"
- **Voter Address:** "Gázgyári lakótelep 000000, Building 0001, Staircase 0001"

This looks odd because:
1. The **Polling Station Address** (Szavazókör cím) is where the voter goes to vote
2. The **Voter Address** (street + house number) is where they live
3. These are **always different fields** in the source data

**This is NOT a bug** - it's how the Hungarian electoral system works. Voters go to a polling station that may be at a different address than where they live.

---

## Real-World Examples

### Example 1: Gázgyári lakótelep (Complex in Budapest III)

**Voter lives at:**
- Gázgyári lakótelep 000000, Building 0001, Staircase 0001-0011
- House number: all zeros → invalid address (no street-level house number)

**Voter votes at:**
- Gázgyári lakótelepi Óvoda (kindergarten)
- This is the polling station location

**Status:** Correctly filtered out (invalid house number)

---

### Example 2: Rákos MÁV telep (Railway settlement in Budapest X)

**Voter lives at:**
- Rákos MÁV telep "000000 5"
- House number contains actual number after space → valid

**Voter votes at:**
- Keresztúri út 7-9. (school)

**Status:** Correctly kept (valid house number)

---

## Conclusion

✅ **The invalid addresses CSV is correct and consistent.**

The filtering logic properly distinguishes between:

1. **Invalid:** Pure all-zero house numbers (`000000`) with or without building/staircase
   - Represents absence of street-level address
   - 7,551 cases filtered out

2. **Valid:** House numbers with actual digits after spaces (`000000 5`)
   - Represents valid addresses with non-standard formatting
   - 502 cases correctly kept in the database

The apparent inconsistency you observed is actually **correct data** reflecting two different address encoding methods in the Hungarian electoral system.

---

## Recommendations

1. **No code changes needed** - the filtering logic is working correctly
2. The CSV accurately represents truly invalid addresses
3. The 502 space-separated addresses were correctly processed and are in the final database
4. Consider documenting these two formats in the data dictionary for future reference

---

## Files for Verification

- **Invalid addresses:** `exports/invalid_addresses/invalid_addresses_all_zero_house_numbers.csv` (7,551 addresses)
- **Source data:** `data/staging/korzet_extracted/Korzet_levalogatas20250702__ORSZAGOS.csv` (3,336,202 addresses)
- **Filtering logic:** `src/etl/deduplicate.py` lines 373-428
