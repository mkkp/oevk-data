# Spec Delta: Address Deduplication Field Preservation

**Capability:** `address-deduplication`  
**Change Type:** Bug Fix (Field Preservation)

## MODIFIED Requirements

### Requirement: Preserve all address component fields in canonical aggregation

**The system SHALL extract building and staircase fields along with other address components when creating canonical addresses from sorted variants.**

**Status:** Modified  
**Priority:** High  
**Rationale:** Canonical addresses must include all structured address components (county, settlement, street, house_number, building, staircase, full_address) to maintain data integrity and enable structured querying. Previously, building and staircase fields were lost during aggregation.

#### Scenario: Canonical address includes building field from best variant

**Given** multiple address variants with different building notations:
- Variant 1: house_number="000001", building="D", staircase="" (structured, score=100)
- Variant 2: house_number="000001/D", building="", staircase="" (slash notation, score=50)

**When** creating canonical addresses with structure score sorting

**Then** the canonical address:
- SHALL select Variant 1 as best (highest structure score)
- SHALL preserve building="D" from Variant 1
- SHALL include full_address="[Street] 1/D." (correctly formatted)
- SHALL NOT have NULL or empty building when source variant has value

**Verification**:
```python
canonical = deduplicator._create_canonical_addresses(variants_df)
assert canonical["building"][0] == "D"
assert canonical["full_address"][0].endswith("1/D.")
```

#### Scenario: Canonical address includes staircase field from best variant

**Given** multiple address variants with different staircase notations:
- Variant 1: house_number="000002", building="", staircase="L" (structured, score=100)
- Variant 2: house_number="000002/L", building="", staircase="" (slash notation, score=50)

**When** creating canonical addresses with structure score sorting

**Then** the canonical address:
- SHALL select Variant 1 as best (highest structure score)
- SHALL preserve staircase="L" from Variant 1
- SHALL include full_address="[Street] 2/L." (correctly formatted)
- SHALL NOT have NULL or empty staircase when source variant has value

**Verification**:
```python
canonical = deduplicator._create_canonical_addresses(variants_df)
assert canonical["staircase"][0] == "L"
assert canonical["full_address"][0].endswith("2/L.")
```

#### Scenario: Canonical address preserves both building and staircase together

**Given** address variants with building and staircase:
- Variant 1: house_number="000003", building="B", staircase="0002" (structured, score=100)
- Variant 2: house_number="000003/B", building="", staircase="0002" (mixed, score=75)

**When** creating canonical addresses

**Then** the canonical address:
- SHALL preserve building="B" from best variant
- SHALL preserve staircase="0002" from best variant
- SHALL preserve both fields from same source variant
- SHALL include full_address="[Street] 3/B. II. lépcsőház"

**Verification**:
```python
canonical = deduplicator._create_canonical_addresses(variants_df)
assert canonical["building"][0] == "B"
assert canonical["staircase"][0] == "0002"
# Both from same best variant (Variant 1)
```

#### Scenario: Component fields match formatted full_address content

**Given** a canonical address with building in full_address

**When** querying the canonical address record

**Then**:
- IF full_address contains "/D" notation
- THEN building field SHALL be "D" (not NULL)
- AND IF full_address contains "lépcsőház" (staircase)
- THEN staircase field SHALL be populated (not NULL)
- Data integrity: structured fields match formatted string

**Verification**:
```sql
SELECT building, full_address 
FROM CanonicalAddress 
WHERE full_address LIKE '%/D.%'
  AND (building IS NULL OR building = '')
-- Should return 0 rows (no mismatches)
```

#### Scenario: Aggregation uses pl.first() to extract fields from sorted variants

**Given** variants sorted by structure_score (descending) and row_order (ascending)

**When** aggregating to create canonical addresses

**Then** the aggregation:
- SHALL use `pl.first("building").alias("building")` to extract building
- SHALL use `pl.first("staircase").alias("staircase")` to extract staircase
- SHALL extract these fields after structure score sorting
- SHALL ensure all component fields come from same best variant

**Implementation**:
```python
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),
    pl.first("building").alias("building"),        # REQUIRED
    pl.first("staircase").alias("staircase"),      # REQUIRED
    pl.first("full_address").alias("full_address"),
]
```

### Requirement: Populate building and staircase fields in CSV exports

**CSV exports SHALL include non-NULL building and staircase values when these components exist in the canonical address.**

**Status:** Modified  
**Priority:** Medium  
**Rationale:** CSV exports must reflect the correct canonical address data with all component fields populated for downstream analysis and querying.

#### Scenario: CSV export includes building column with values

**Given** canonical addresses with building field populated

**When** exporting to CSV format

**Then** the CSV:
- SHALL include Building column
- SHALL contain non-NULL values where building exists in full_address
- SHALL match building values to full_address content
- SHALL NOT show NULL for addresses like "Körtöltés utca 1/D."

**Verification**:
```bash
# Check CSV for Szeged address
grep "Körtöltés utca 1/D" Address_06_Szeged.csv
# Should show Building column = "D"
```

#### Scenario: CSV export includes staircase column with values

**Given** canonical addresses with staircase field populated

**When** exporting to CSV format

**Then** the CSV:
- SHALL include Staircase column
- SHALL contain non-NULL values where staircase exists in full_address
- SHALL match staircase values to full_address content (may be Roman numeral)
- SHALL support querying/filtering by staircase value

**Verification**:
```bash
# Count addresses with staircase in CSV
awk -F',' '$7 != "" && $7 != "NULL"' Address_*.csv | wc -l
# Should be > 0
```

### Requirement: Include building and staircase in PostgreSQL exports

**PostgreSQL INSERT statements SHALL include building and staircase column values to enable structured SQL queries.**

**Status:** Modified  
**Priority:** Medium  
**Rationale:** PostgreSQL database must have complete structured address data for SQL querying by building and staircase.

#### Scenario: PostgreSQL data.sql includes building values

**Given** canonical addresses exported to PostgreSQL format

**When** generating INSERT statements in data.sql

**Then** the statements:
- SHALL include building column in INSERT
- SHALL include building values (not NULL where applicable)
- SHALL allow PostgreSQL queries filtering by building
- SHALL support geospatial analysis by building

**Verification**:
```sql
-- After import, query should work
SELECT * FROM CanonicalAddress 
WHERE building = 'D' 
  AND settlement_name = 'Szeged';
-- Should return results including Körtöltés utca 1/D
```

#### Scenario: PostgreSQL supports structured queries on building and staircase

**Given** PostgreSQL database loaded with canonical addresses

**When** querying by building or staircase

**Then** the database:
- SHALL support WHERE building = 'X' queries
- SHALL support WHERE staircase = 'Y' queries
- SHALL return correct results without parsing full_address
- SHALL enable efficient filtering and aggregation

**Verification**:
```sql
-- Count addresses by building
SELECT building, COUNT(*) 
FROM CanonicalAddress 
WHERE building IS NOT NULL 
GROUP BY building 
ORDER BY COUNT(*) DESC;
-- Should return distribution of buildings (A, B, C, D, etc.)
```

## ADDED Requirements

### Requirement: Verify field preservation with contract tests

**Contract tests MUST validate that building and staircase fields are correctly preserved from the best-scored address variant during canonical aggregation.**

**Status:** Added  
**Priority:** High  
**Rationale:** Test-driven development requires contract tests that verify the core invariant: component fields must be preserved from the best-scored variant.

#### Scenario: Test building field preserved from structured variant

**Given** test case with structured and slash notation variants

**When** running `test_canonical_address_preserves_building`

**Then** the test:
- SHALL create variants with building in different forms
- SHALL call `_create_canonical_addresses()`
- SHALL assert building field equals expected value from best variant
- SHALL fail if building field is NULL or incorrect

**Test Location**: `tests/contract/test_deduplication_logic.py`

#### Scenario: Test staircase field preserved from structured variant

**Given** test case with staircase in different notations

**When** running `test_canonical_address_preserves_staircase`

**Then** the test:
- SHALL create variants with staircase in different forms
- SHALL assert staircase field equals expected value
- SHALL verify correct variant selected based on structure score

**Test Location**: `tests/contract/test_deduplication_logic.py`

#### Scenario: Test both fields preserved together

**Given** test case with both building and staircase

**When** running `test_canonical_address_preserves_both_fields`

**Then** the test:
- SHALL verify building preserved
- SHALL verify staircase preserved
- SHALL verify both fields from same best variant
- SHALL ensure no mixing of fields from different variants

**Test Location**: `tests/contract/test_deduplication_logic.py`

### Requirement: Validate end-to-end field preservation with integration tests

**Integration tests MUST verify that building and staircase fields are correctly preserved through the complete deduplication pipeline with real address data.**

**Status:** Added  
**Priority:** High  
**Rationale:** Integration tests verify that the fix works correctly in the full pipeline with real data.

#### Scenario: Szeged real-world address verification

**Given** Szeged test data with "Körtöltés utca 1/D" address

**When** running full deduplication pipeline

**Then** the database:
- SHALL contain canonical address for this location
- SHALL show Building="D" in the record
- SHALL show full_address="Körtöltés utca 1/D."
- SHALL demonstrate real-world bug fix

**Test Location**: `tests/integration/test_deduplication_integrity.py`

#### Scenario: Field population rate verification

**Given** full canonical address dataset

**When** querying addresses with slash notation in full_address

**Then** the statistics:
- SHALL show > 0 addresses with populated building
- SHALL show > 0 addresses with populated staircase
- SHALL show > 50% of slash-notation addresses have structured building
- SHALL verify data quality improvement

**Test Location**: `tests/integration/test_deduplication_integrity.py`

## Implementation Notes

### Code Changes

**File**: `src/etl/deduplicate.py`  
**Method**: `_create_canonical_addresses()` (line ~727)  
**Change**: Add 2 lines to aggregation_columns list

```python
# Before (incorrect):
aggregation_columns = [
    pl.first("county_code").alias("county_code"),
    pl.first("settlement_name").alias("settlement_name"),
    pl.first("street_name").alias("street_name"),
    pl.first("house_number").alias("house_number"),
    pl.first("full_address").alias("full_address"),
]

# After (correct):
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

### Why This Fix Works

1. **Pre-sorted data**: Variants already sorted by structure_score (desc) before aggregation
2. **pl.first() semantics**: Returns value from first row in each group (best variant)
3. **Consistency**: All fields extracted from same best variant
4. **No side effects**: No change to sorting, scoring, or canonical ID logic

### Performance Impact

- **Negligible**: Adding fields to existing aggregation
- **O(1) per group**: pl.first() is constant time
- **No additional sorts**: Uses existing sorted dataframe
- **Memory**: Minimal (two additional columns in result)

### Testing Strategy

1. **Contract Tests**: Verify core invariant (fields preserved)
2. **Integration Tests**: Verify with real data and full pipeline
3. **Regression Tests**: Ensure existing tests still pass
4. **Manual Verification**: Check Szeged example in database

### Success Criteria

- [ ] All 5 new test scenarios pass
- [ ] All existing deduplication tests pass
- [ ] Szeged address shows Building="D"
- [ ] CSV exports have populated fields
- [ ] PostgreSQL exports support structured queries
- [ ] No performance regression

### Related Capabilities

- **canonical-address-export**: Affected by this change (exports now include fields)
- **address-formatting**: Not affected (formatting logic unchanged)
- **canonical-id-generation**: Not affected (ID generation unchanged)

### Migration Impact

**No migration required**:
- This is a bug fix, not a schema change
- Existing data can be re-exported with fix applied
- No backwards compatibility concerns
- Safe to deploy in next release

### Documentation Updates

- `docs/008_FIXING_DEDUPLICATION.md`: Already exists with full specification
- `docs/DEDUPLICATION_FEATURE_HISTORY.md`: Add entry for fix
- Code comments: Add note about field preservation in `_create_canonical_addresses()`
