# Proposal: Fix Deduplication Field Loss

**Change ID:** `fix-deduplication-field-loss`  
**Status:** Proposed  
**Created:** 2025-10-23  
**Author:** System

## Why

The address deduplication process loses building and staircase component fields during canonical address aggregation, causing data integrity issues where formatted addresses contain information not available in structured fields.

## What Changes

This proposal fixes the field loss bug in the deduplication process by adding two missing fields to the aggregation logic:

### Code Changes
- **File**: `src/etl/deduplicate.py` (line ~727)
- **Change**: Add `building` and `staircase` to aggregation columns in `_create_canonical_addresses()` method
- **Lines added**: 2 lines
- **Risk**: Very low (simple field extraction)

### Affected Components
- **MODIFIED**: `src/etl/deduplicate.py` - Add 2 fields to aggregation
- **ADDED**: `tests/contract/test_deduplication_logic.py` - 3 new contract tests
- **ADDED**: `tests/integration/test_deduplication_integrity.py` - 2 new integration tests
- **UPDATED**: `docs/DEDUPLICATION_FEATURE_HISTORY.md` - Document bug fix

### Breaking Changes
**None** - This is a bug fix that populates previously NULL fields. No API changes, no behavior changes to existing functionality.

## Impact

### Affected Specs
- **MODIFIED**: `address-deduplication` - Field preservation requirements added
- **MODIFIED**: `canonical-address-export` - Export includes building/staircase fields

### Affected Code
- `src/etl/deduplicate.py` - 2 lines added to aggregation
- `tests/contract/test_deduplication_logic.py` - 3 new test cases
- `tests/integration/test_deduplication_integrity.py` - 2 new test cases

### Data Impact
- **Before**: Building and Staircase fields mostly NULL in canonical addresses (~3.3M addresses)
- **After**: Fields correctly populated from best-scored variants
- **No change**: FullAddress formatting, canonical IDs, deduplication detection

### Performance Impact
- **Negligible**: Adding two fields to existing aggregation (O(1) per group)
- **No additional processing**: Uses existing sorted dataframe

## Problem Statement

The address deduplication process correctly generates `FullAddress` strings but fails to preserve the `Building` and `Staircase` component fields in canonical address records. This results in a data integrity issue where:

- The formatted `FullAddress` is correct (e.g., "Körtöltés utca 1/D.")
- Component fields are missing (Building = NULL instead of "D")
- Users cannot query or filter by building/staircase despite the information being in the address string
- Downstream exports show NULL values for these fields

### Example Issue (Szeged)

**Current (Incorrect)**:
- FullAddress: `"Körtöltés utca 1/D."` ✅ Correct
- HouseNumber: `"1"` ✅ Correct
- Building: `NULL` ❌ Missing
- Staircase: `NULL` ✅ Correct (empty in this case)

**Expected**:
- FullAddress: `"Körtöltés utca 1/D."`
- HouseNumber: `"1"`
- Building: `"D"` ✅ Should be present
- Staircase: `""` (empty)

### Root Cause

In `src/etl/deduplicate.py:727`, the `_create_canonical_addresses()` method aggregates fields from the best-scored address variant but only includes 5 fields:

```python
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),
    pl.first("full_address").alias("full_address"),
]
# Missing: building and staircase!
```

The `building` and `staircase` columns exist in the input data and are used to compute `full_address`, but they are never extracted during aggregation. This causes them to be lost in the canonical output.

### Impact

- **Data Quality**: ~3.3M addresses have inconsistent data (component fields don't match formatted address)
- **Queryability**: Cannot filter/search by building or staircase in structured way
- **Downstream Systems**: CSV and PostgreSQL exports show NULL values
- **User Experience**: Address components appear in formatted string but missing in database fields

## Proposed Solution

Add `building` and `staircase` to the aggregation columns in `_create_canonical_addresses()` method.

### Code Change

**File**: `src/etl/deduplicate.py` (line 727)

**Current**:
```python
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),
    pl.first("full_address").alias("full_address"),
]
```

**Fixed**:
```python
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),
    pl.first("building").alias("building"),        # ADD
    pl.first("staircase").alias("staircase"),      # ADD
    pl.first("full_address").alias("full_address"),
]
```

### Why This Works

1. **Sorting ensures correct source**: The dataframe is sorted by `structure_score` (descending) before aggregation
2. **`pl.first()` gets best variant**: Returns the value from the first row in each group (highest-scoring variant)
3. **Consistency**: All address component fields will be from the same best-scored variant
4. **No behavior change**: Deduplication logic, canonical ID generation, and address formatting remain unchanged

## Benefits

1. **Data Integrity**: Component fields match the formatted address
2. **Queryability**: Users can filter/search by building and staircase
3. **Minimal Risk**: 2-line change, no logic modifications
4. **Performance**: Negligible overhead (pl.first() is O(1) per group)
5. **No Breaking Changes**: This is a bug fix, not a behavior change

## Impact Assessment

### Data Changes
- **Before**: Building and Staircase fields mostly NULL in canonical addresses
- **After**: Fields correctly populated from best variants
- **No change to**: FullAddress formatting, deduplication logic, canonical IDs

### Performance
- **Negligible**: Adding two fields to aggregation has minimal overhead
- **O(1) operation**: `pl.first()` per group

### Breaking Changes
- **None**: Bug fix only, no API or behavior changes

### Affected Components
- `src/etl/deduplicate.py`: 2 lines added
- `tests/contract/test_deduplication_logic.py`: New test cases
- `tests/integration/test_deduplication_integrity.py`: Verification tests
- CSV exports: Building and Staircase columns now populated
- PostgreSQL exports: Non-NULL values for these fields

## Testing Strategy

### Contract Tests (TDD)
- Verify building field preserved from best variant
- Verify staircase field preserved from best variant
- Verify both fields preserved when present
- Verify fields match full_address content

### Integration Tests
- Verify Szeged "Körtöltés utca 1/D" address has Building="D"
- Verify field preservation across full pipeline
- Verify CSV exports include populated fields
- Verify PostgreSQL exports include non-NULL values

### Regression Tests
- All existing deduplication tests must pass
- No change to canonical ID generation
- No change to FullAddress formatting
- No change to deduplication detection

## Rollout Plan

1. **Implement**: Add 2 lines to aggregation columns
2. **Test**: Run contract and integration tests
3. **Validate**: Check Szeged example in development
4. **Full Pipeline**: Run complete transform and export
5. **Verify**: Confirm building/staircase fields populated
6. **Release**: Package and deploy with next data release

## Success Criteria

✅ Fix is successful when:
1. `building` and `staircase` added to aggregation columns
2. All existing deduplication tests pass
3. New test cases pass for field preservation
4. Szeged "Körtöltés utca 1/D" shows Building="D"
5. CSV/PostgreSQL exports have non-NULL values
6. No performance regression (< 1% acceptable)
7. FullAddress formatting unchanged

## References

- **Specification**: `docs/008_FIXING_DEDUPLICATION.md`
- **Code Location**: `src/etl/deduplicate.py:684-740`
- **Related Tests**: 
  - `tests/contract/test_deduplication_logic.py`
  - `tests/integration/test_deduplication_integrity.py`
- **Related Capabilities**:
  - `address-deduplication` (modified)
  - `canonical-address-export` (affected)

## Dependencies

**Blocks**: None  
**Blocked By**: None  
**Related Changes**: 
- `fix-export-inconsistencies` (archived) - Related to leading zero trimming
- `add-cleansed-address-deduplication` (archived) - Original deduplication feature

## Open Questions

None. The fix is straightforward and well-understood.

## Alternatives Considered

### 1. Recompute building/staircase from full_address
**Rejected**: Parsing formatted addresses is error-prone and defeats the purpose of having structured fields.

### 2. Add fields in post-processing
**Rejected**: Would require duplicating the scoring logic to identify the best variant again.

### 3. Change aggregation strategy
**Rejected**: Current strategy (pl.first() with sorting) is correct; we just need to include all fields.

## Approval

- [ ] Technical Review
- [ ] Test Coverage Review
- [ ] Documentation Review
- [ ] Ready for Implementation
