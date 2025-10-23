# Specification: Fix Address Deduplication Building/Staircase Field Loss

## Problem Statement

The address deduplication process correctly generates `FullAddress` strings but fails to preserve the `Building` and `Staircase` component fields in the canonical address records. This results in addresses where the full formatted address is correct (e.g., "Körtöltés utca 1/D."), but the component fields are missing (Building = NULL instead of "D").

### Observed Issue

**Example from Szeged**:
- **Expected canonical address**:
  - FullAddress: `"Körtöltés utca 1/D."`
  - HouseNumber: `"1"` (or `"000001"` with leading zeros)
  - Building: `"D"`
  - Staircase: `""` (empty)

- **Actual canonical address** (INCORRECT):
  - FullAddress: `"Körtöltés utca 1/D."` ✅ Correct
  - HouseNumber: `"1"` ✅ Correct
  - Building: `NULL` or `""` ❌ **Missing**
  - Staircase: `NULL` or `""` ✅ Correct (in this case)

### Root Cause

Located in `src/etl/deduplicate.py:684-740`, the `_create_canonical_addresses()` method:

```python
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),  # ✅ Captured
    pl.first("full_address").alias("full_address"),
]
# ❌ MISSING: building and staircase fields are NOT included
```

**Issue**: The aggregation selects fields from the first record after sorting by `structure_score`, but **only includes 5 fields**. The `building` and `staircase` columns are never extracted, so they are lost in the canonical address output.

**Impact**:
1. Canonical addresses have complete `FullAddress` strings but missing component fields
2. Downstream exports (CSV, PostgreSQL) show NULL/empty values for Building and Staircase
3. Users cannot filter or query by building number despite it appearing in the formatted address
4. Data integrity: The address string contains information that isn't available in structured fields

## Technical Analysis

### Deduplication Flow

1. **Input**: Multiple address variants for the same location
   ```
   Variant 1: HouseNumber="000001", Building="D", Staircase=""
   Variant 2: HouseNumber="000001", Building="", Staircase="D"
   Variant 3: HouseNumber="000001/D", Building="", Staircase=""
   ```

2. **Format Full Address**: All variants format to `"Körtöltés utca 1/D."` (correctly)

3. **Generate Canonical ID**: All three hash to the same ID (correctly identifying them as duplicates)

4. **Calculate Structure Score**: Assign priority scores
   - Variant 1: Score 100 (structured: plain house + building)
   - Variant 2: Score 100 (structured: plain house + staircase)
   - Variant 3: Score 50 (unstructured: slash notation)

5. **Sort and Select Best**: Sort by score (desc), select first
   - **Best variant**: Variant 1 (score 100, row_order 1)

6. **Extract Fields**: ❌ **BUG HERE**
   ```python
   pl.first("county_code").alias("county_code"),
   pl.first("settlement_name").alias("settlement_name"),
   pl.first("street_name").alias("street_name"),
   pl.first("house_number").alias("house_number"),
   pl.first("full_address").alias("full_address"),
   # Missing: building and staircase!
   ```

7. **Output Canonical Address**:
   - FullAddress: `"Körtöltés utca 1/D."` ✅
   - HouseNumber: `"1"` ✅
   - Building: `NULL` ❌ Should be `"D"`
   - Staircase: `NULL` ✅ (empty in this case)

### Why FullAddress is Correct But Fields Are Missing

- The `full_address` column is computed **before** the aggregation (in `_generate_canonical_ids()`)
- Each variant has its own formatted `full_address` value
- When `pl.first("full_address")` is called, it correctly gets the full address from the best-scored variant
- **However**, `building` and `staircase` are never extracted with `pl.first()`, so they disappear

### Affected Scenarios

This bug affects **all** deduplicated addresses where:
1. Multiple variants exist with different building/staircase placements
2. The best variant has a non-empty building or staircase field
3. Examples:
   - `"1/D"` with Building="D" → Building lost
   - `"1"` with Building="B", Staircase="III" → Both lost
   - `"1-5"` with Building="A" → Building lost

## Solution Specification

### Required Changes

**File**: `src/etl/deduplicate.py`
**Method**: `_create_canonical_addresses()` (lines 684-740)

**Change**: Add `building` and `staircase` to the aggregation columns

#### Current Code (Incorrect)

```python
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),
    pl.first("full_address").alias("full_address"),
]
```

#### Fixed Code

```python
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),
    pl.first("building").alias("building"),        # ADD THIS
    pl.first("staircase").alias("staircase"),      # ADD THIS
    pl.first("full_address").alias("full_address"),
]
```

### Justification

1. **`pl.first()`** combined with **sorting** ensures the fields come from the **best-scored variant**
   - The dataframe is sorted by `structure_score` (descending) before aggregation
   - `pl.first()` returns the value from the first row in each group (the highest-scoring variant)
   - Therefore, `pl.first("building")` and `pl.first("staircase")` will correctly get the values from the selected best variant

2. **Consistency**: All address component fields should be preserved:
   - `house_number` ✅ Already extracted
   - `building` ❌ Currently missing → FIX
   - `staircase` ❌ Currently missing → FIX

3. **Data Integrity**: The component fields should match the data used to generate `full_address`

### Expected Behavior After Fix

**Input variants**:
```
Variant 1: HouseNumber="000001", Building="D", Staircase="", score=100, row_order=1
Variant 2: HouseNumber="000001", Building="", Staircase="D", score=100, row_order=2
Variant 3: HouseNumber="000001/D", Building="", Staircase="", score=50, row_order=3
```

**After sorting and aggregation**:
```python
canonical_address = {
    "county_code": "06",                     # from Variant 1 (first)
    "settlement_name": "Szeged",             # from Variant 1 (first)
    "street_name": "Körtöltés",              # from Variant 1 (first)
    "house_number": "1",                # from Variant 1 (first) ✅
    "building": "D",                         # from Variant 1 (first) ✅ FIXED
    "staircase": "",                         # from Variant 1 (first) ✅ FIXED
    "full_address": "Körtöltés utca 1/D.",   # from Variant 1 (first) ✅
}
```

## Verification Strategy

### Test Cases

#### Test 1: Single building notation
**Input**:
```
Variant 1: house="000001", building="D", staircase=""
Variant 2: house="000001/D", building="", staircase=""
```

**Expected Canonical**:
- HouseNumber: `"000001"` or `"1"` (after trim)
- Building: `"D"`
- Staircase: `""` (empty)
- FullAddress: `"[Street] 1/D."`

#### Test 2: Building and staircase
**Input**:
```
Variant 1: house="000002", building="B", staircase="0003"
Variant 2: house="000002/B", building="", staircase="0003"
```

**Expected Canonical**:
- HouseNumber: `"000002"` or `"2"`
- Building: `"B"`
- Staircase: `"0003"` or `"III"` (Roman numeral)
- FullAddress: `"[Street] 2/B. III. lépcsőház"`

#### Test 3: Numeric building and staircase
**Input**:
```
Variant 1: house="000009", building="0001", staircase="0001"
```

**Expected Canonical**:
- HouseNumber: `"000009"` or `"9"`
- Building: `"0001"` or `"1"`
- Staircase: `"0001"` or `"I"`
- FullAddress: `"[Street] 9. 1. épület I. lépcsőház"`

#### Test 4: Staircase only
**Input**:
```
Variant 1: house="000005", building="", staircase="L"
Variant 2: house="000005/L", building="", staircase=""
```

**Expected Canonical**:
- HouseNumber: `"000005"` or `"5"`
- Building: `""` (empty)
- Staircase: `"L"`
- FullAddress: `"[Street] 5/L."`

### Integration Test

**Data Source**: Szeged addresses from `staging_korzet`

**Query** (after fix):
```sql
SELECT
    settlement_name,
    street_name,
    house_number,
    building,
    staircase,
    full_address
FROM CanonicalAddress
WHERE settlement_name = 'Szeged'
  AND street_name LIKE '%Körtöltés%'
  AND full_address LIKE '%1/D%'
```

**Expected Result**:
```
settlement_name | street_name | house_number | building | staircase | full_address
----------------|-------------|--------------|----------|-----------|-------------------
Szeged          | Körtöltés   | 000001       | D        |           | Körtöltés utca 1/D.
```

**Current Result (before fix)**:
```
settlement_name | street_name | house_number | building | staircase | full_address
----------------|-------------|--------------|----------|-----------|-------------------
Szeged          | Körtöltés   | 000001       | NULL     | NULL      | Körtöltés utca 1/D.
```

## Implementation Steps

1. **Update `_create_canonical_addresses()` method**
   - Add `pl.first("building").alias("building")` to aggregation columns
   - Add `pl.first("staircase").alias("staircase")` to aggregation columns
   - Ensure these are added **before** the accessibility_flag check

2. **Run deduplication tests**
   - Execute existing test suite: `pytest tests/contract/test_deduplication_logic.py`
   - Verify all tests still pass
   - Add new test cases for building/staircase preservation

3. **Run full pipeline**
   - Execute: `python src/cli.py run --stages transform,export`
   - Verify canonical addresses have populated building/staircase fields
   - Check PostgreSQL export includes these fields correctly

4. **Verify Szeged example**
   - Query Szeged "Körtöltés utca 1/D" address
   - Confirm Building="D" is present
   - Confirm FullAddress matches component fields

5. **Update documentation**
   - Update `docs/DEDUPLICATION_FEATURE_HISTORY.md` with bug fix entry
   - Document the field preservation behavior

## Impact Assessment

### Data Changes

**Before Fix**:
- ~3.3M addresses with FullAddress containing building/staircase info
- Building and Staircase fields mostly NULL/empty in canonical addresses
- Information loss: structured data unavailable despite being in formatted string

**After Fix**:
- Same ~3.3M addresses
- Building and Staircase fields correctly populated from best variants
- No change to FullAddress formatting or deduplication logic
- Better data quality: component fields match formatted addresses

### Performance Impact

**Negligible**: Adding two fields to the aggregation has minimal overhead
- Aggregation already processes all columns
- `pl.first()` is an O(1) operation per group
- No additional sorting or filtering required

### Breaking Changes

**None**: This is a bug fix, not a behavior change
- Deduplication logic unchanged
- FullAddress generation unchanged
- Canonical ID computation unchanged
- Only difference: previously NULL fields now populated

### Downstream Effects

**Positive improvements**:
1. **CSV Exports**: Building and Staircase columns now useful
2. **PostgreSQL**: Structured queries on building numbers now possible
3. **Data Analysis**: Can filter/group by building without parsing FullAddress
4. **Data Quality**: Improved consistency between formatted and structured data

## Testing Requirements

### Unit Tests

**File**: `tests/contract/test_deduplication_logic.py`

Add test cases:

```python
def test_canonical_address_preserves_building():
    """Verify building field is preserved in canonical address."""
    variants = [
        {"house_number": "000001", "building": "D", "staircase": ""},
        {"house_number": "000001/D", "building": "", "staircase": ""},
    ]
    canonical = deduplicate(variants)
    assert canonical["building"] == "D", "Building must be preserved from best variant"

def test_canonical_address_preserves_staircase():
    """Verify staircase field is preserved in canonical address."""
    variants = [
        {"house_number": "000002", "building": "", "staircase": "L"},
        {"house_number": "000002/L", "building": "", "staircase": ""},
    ]
    canonical = deduplicate(variants)
    assert canonical["staircase"] == "L", "Staircase must be preserved from best variant"

def test_canonical_address_preserves_both():
    """Verify both building and staircase are preserved."""
    variants = [
        {"house_number": "000003", "building": "B", "staircase": "0002"},
        {"house_number": "000003/B", "building": "", "staircase": "0002"},
    ]
    canonical = deduplicate(variants)
    assert canonical["building"] == "B"
    assert canonical["staircase"] in ["0002", "II"], "Staircase may be converted to Roman"
```

### Integration Tests

**File**: `tests/integration/test_deduplication_integration.py`

```python
def test_szeged_kortoltes_utca_building_preserved():
    """Verify real-world Szeged address has building preserved."""
    # Run full pipeline with Szeged data
    run_pipeline(settlement_filter="Szeged")

    # Query canonical address
    result = db.execute("""
        SELECT house_number, building, staircase, full_address
        FROM CanonicalAddress
        WHERE settlement_name = 'Szeged'
          AND street_name = 'Körtöltés'
          AND full_address LIKE '%1/D%'
    """).fetchone()

    assert result is not None, "Address should exist"
    assert result["full_address"] == "Körtöltés utca 1/D."
    assert result["building"] == "D", "Building D must be preserved"
```

## Success Criteria

✅ **Fix is successful when**:

1. `pl.first("building")` and `pl.first("staircase")` added to aggregation
2. All existing deduplication tests pass
3. New test cases for building/staircase preservation pass
4. Szeged "Körtöltés utca 1/D" address shows Building="D"
5. PostgreSQL export includes non-NULL building/staircase values
6. No performance regression (< 1% slowdown acceptable)
7. FullAddress formatting remains unchanged

## References

- **Code Location**: `src/etl/deduplicate.py:684-740`
- **Method**: `AddressDeduplicator._create_canonical_addresses()`
- **Related Tests**: `tests/contract/test_deduplication_logic.py`
- **Documentation**: `docs/DEDUPLICATION_FEATURE_HISTORY.md`

## Appendix: Code Diff

```diff
--- a/src/etl/deduplicate.py
+++ b/src/etl/deduplicate.py
@@ -727,6 +727,8 @@ class AddressDeduplicator:
             pl.first("settlement_name").alias("settlement_name"),
             pl.first("street_name").alias("street_name"),
             pl.first("house_number").alias("house_number"),
+            pl.first("building").alias("building"),
+            pl.first("staircase").alias("staircase"),
             pl.first("full_address").alias("full_address"),
         ]
```

**Lines changed**: 2 lines added
**Complexity**: Trivial
**Risk**: Very low (simple field extraction)
