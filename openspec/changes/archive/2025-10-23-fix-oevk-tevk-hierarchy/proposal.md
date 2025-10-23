# Proposal: Fix OEVK/TEVK Hierarchy

**Change ID:** `fix-oevk-tevk-hierarchy`  
**Status:** Proposed  
**Priority:** High  
**Effort:** Medium (~4-6 hours)  
**Breaking Change:** Yes (TEVK IDs will change, full pipeline re-run required)

## Why

The current data model incorrectly treats TEVK (SettlementIndividualElectoralDistrict) as a hierarchical subdivision of OEVK (NationalIndividualElectoralDistrict), when they are actually **parallel, independent electoral district systems**. This fundamental misunderstanding violates the real-world electoral geography of Hungary and creates data integrity issues.

### Current Incorrect Model
```
County
  └─ OEVK (National Electoral District)
      └─ TEVK (Settlement Electoral District)  ❌ WRONG
```

### Correct Model
```
County ──┬─→ OEVK (National Electoral District)
         │    Scope: County-level parliamentary districts
         │
         └─→ Settlement ──→ TEVK (Settlement Electoral District)
                            Scope: Settlement-level municipal districts
```

### Real-World Context

**Translation from Hungarian requirement:**
> "mert a tevk nem az oevk további felosztása, hanem úgy van, hogy megye -> oevk; város -> tevk"
>
> "Because TEVK is not a further subdivision of OEVK, but rather: county → OEVK; settlement → TEVK"

**Electoral Systems:**
- **OEVK**: 106 National Individual Electoral Districts for parliamentary elections, organized by **county** boundaries
- **TEVK**: ~4,677 Settlement Individual Electoral Districts for local municipal elections, organized by **settlement** boundaries
- **Independence**: TEVK boundaries are NOT constrained by OEVK boundaries; they may overlap or span across OEVK boundaries

### Impact of Current Error

1. **Incorrect Foreign Key**: Forces every TEVK to belong to exactly one OEVK, which is factually wrong
2. **Wrong ID Generation**: Includes `oevk` parameter in TEVK hash, creating artificial dependency
3. **Data Integrity Risk**: May create orphaned TEVK records if OEVK join fails during transformation
4. **Query Confusion**: Misleads developers into believing direct TEVK→OEVK relationship exists
5. **Real-World Violation**: A single TEVK can span multiple OEVKs, or multiple TEVKs can exist within one OEVK

## What Changes

This proposal removes the hierarchical dependency between TEVK and OEVK by:

### 1. Schema Changes

#### Remove OEVK Foreign Key from TEVK Table

**Before:**
```sql
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY,
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,  -- ❌ REMOVE
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID)   -- ❌ REMOVE
        REFERENCES NationalIndividualElectoralDistrict(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK, NationalIndividualElectoralDistrict_ID)
);
```

**After:**
```sql
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY,
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID TEXT NOT NULL,  -- Keep (administrative hierarchy)
    Settlement_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK)  -- ✅ No OEVK
);
```

### 2. ID Generation Changes

#### Update `hash_tevk_id()` Function

**Before:**
```python
def hash_tevk_id(county_code, settlement_code, tevk, oevk):
    # Includes oevk - WRONG
    return hash(f"{county_code}|{settlement_code}|{tevk}|{oevk}")
```

**After:**
```python
def hash_tevk_id(county_code, settlement_code, tevk):
    # Independent of OEVK - CORRECT
    return hash(f"{county_code}|{settlement_code}|{tevk}")
```

**Files Affected:**
- `src/etl/hashing.py` - Python function signature and implementation
- `src/etl/transform_optimized.py` - DuckDB macro definition (line ~50)
- `src/etl/transform.py` - DuckDB macro definition (line ~37)

### 3. Transformation Logic Changes

#### Update TEVK Transformation SQL

**Before:**
```sql
SELECT
    hash_tevk_id(county_code, settlement_code, tevk_code, oevk_code) as ID,
    o.ID as NationalIndividualElectoralDistrict_ID
FROM staging_korzet sk
JOIN NationalIndividualElectoralDistrict o  -- ❌ Incorrect JOIN
    ON sk.county_code = c.CountyCode AND sk.oevk_code = o.OEVK
```

**After:**
```sql
SELECT
    hash_tevk_id(county_code, settlement_code, tevk_code) as ID
FROM staging_korzet sk
-- No OEVK JOIN - TEVK is independent
```

**Files Affected:**
- `src/etl/transform_optimized.py:341-380`
- `src/etl/transform.py:237-280`

### 4. Downstream Reference Updates

**PollingStation Table** - References updated but no FK removed:
```python
# Before
hash_tevk_id(county_code, settlement_code, tevk, oevk)

# After  
hash_tevk_id(county_code, settlement_code, tevk)
```

**Address Table** - References updated but no FK removed:
```python
# Before
hash_tevk_id(county_code, settlement_code, tevk, oevk)

# After
hash_tevk_id(county_code, settlement_code, tevk)
```

**Note:** PollingStation and Address tables correctly maintain BOTH TEVK and OEVK foreign keys because addresses/polling stations exist in the context of both electoral systems. Only the TEVK→OEVK direct relationship is incorrect.

### 5. Export Schema Updates

**PostgreSQL Export** (`exports/schema.sql`):
- Same schema changes as DuckDB schema
- UUID v3 generation updated to exclude OEVK from TEVK IDs

## Impact

### Breaking Changes

⚠️ **This is a BREAKING CHANGE that requires full data regeneration**

1. **TEVK IDs Change**: All `SettlementIndividualElectoralDistrict.ID` values will change because OEVK is removed from hash input
2. **Schema Incompatibility**: New schema cannot load old data (column removed)
3. **Export Regeneration**: All CSV and PostgreSQL exports must be regenerated
4. **Downstream Systems**: Any systems consuming TEVK IDs must update

### Migration Required

**Migration Steps:**
1. Drop dependent tables: `Address`, `PollingStation`, `SettlementIndividualElectoralDistrict`
2. Apply new schema with updated table definitions
3. Re-run complete transformation pipeline with new logic
4. Regenerate all exports (CSV, PostgreSQL)
5. Update downstream systems consuming TEVK IDs

**No In-Place Migration Possible**: This is a logical model correction, not a data migration

### Data Integrity Improvements

**Before Fix:**
- TEVK artificially constrained to single OEVK
- May miss TEVK records if OEVK JOIN fails
- UNIQUE constraint incorrectly includes OEVK

**After Fix:**
- TEVK correctly independent of OEVK
- No missing records from failed OEVK JOINs
- UNIQUE constraint correctly based on (County, Settlement, TEVK)
- Addresses can correctly span OEVK/TEVK combinations

### Query Pattern Changes

**Incorrect Pattern (Before):**
```sql
-- Direct JOIN - WRONG
SELECT * FROM SettlementIndividualElectoralDistrict t
JOIN NationalIndividualElectoralDistrict o 
    ON t.NationalIndividualElectoralDistrict_ID = o.ID;
```

**Correct Pattern (After):**
```sql
-- Find OEVKs that overlap with TEVK via addresses - CORRECT
SELECT DISTINCT o.* 
FROM SettlementIndividualElectoralDistrict t
JOIN Address a ON a.SettlementIndividualElectoralDistrict_ID = t.ID
JOIN NationalIndividualElectoralDistrict o 
    ON a.NationalIndividualElectoralDistrict_ID = o.ID
WHERE t.ID = ?;
```

### Affected Components

**Code:**
- `src/database/schema.sql` - TEVK table definition
- `src/etl/hashing.py` - `hash_tevk_id()` function signature
- `src/etl/transform_optimized.py` - Hash macro, TEVK transformation, PollingStation/Address hash calls
- `src/etl/transform.py` - Same changes as transform_optimized.py
- `exports/schema.sql` - PostgreSQL export schema

**Tests:**
- `tests/contract/test_transform.py` - TEVK transformation tests
- `tests/integration/test_data_integrity.py` - Foreign key validation tests
- `tests/integration/test_full_cycle.py` - End-to-end pipeline tests

**Documentation:**
- `README.md` - Data model diagram
- `docs/009_FIXING_OEVK_TEVK_RELATION.md` - Problem analysis (already exists)

### Performance Impact

**Minimal Performance Change:**
- One less JOIN in TEVK transformation (slight improvement)
- One less column in TEVK table (minimal storage saving)
- Hash computation slightly faster (one less component)

### Validation Strategy

**Schema Verification:**
```sql
-- Verify TEVK has no OEVK FK
PRAGMA foreign_key_list(SettlementIndividualElectoralDistrict);
-- Should NOT show NationalIndividualElectoralDistrict_ID
```

**Data Integrity Tests:**
```sql
-- Verify TEVK independence: same TEVK may span multiple OEVKs
SELECT t.Settlement_ID, t.TEVK, 
       COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) as oevk_count
FROM SettlementIndividualElectoralDistrict t
JOIN Address a ON a.SettlementIndividualElectoralDistrict_ID = t.ID
GROUP BY t.Settlement_ID, t.TEVK
HAVING COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) > 1;
-- May return rows, proving TEVK/OEVK independence
```

**ID Generation Test:**
```python
# Verify deterministic ID without OEVK
id1 = hash_tevk_id("01", "001", "1")  # No oevk parameter
id2 = hash_tevk_id("01", "001", "1")
assert id1 == id2  # Same input -> same ID
```

## Alternatives Considered

### Alternative 1: Keep FK but make it nullable
**Rejected**: Doesn't fix the fundamental model error; still implies hierarchy

### Alternative 2: Add many-to-many junction table TEVK_OEVK
**Rejected**: Relationship already captured via Address table; adds complexity without value

### Alternative 3: Keep current model, add comments
**Rejected**: Documentation doesn't fix the data integrity issues; code still violates real-world geography

## Dependencies

**Depends On:** None (standalone change)

**Blocks:** 
- Any future features relying on correct OEVK/TEVK relationship
- Geospatial analysis requiring accurate electoral district boundaries

## Timeline

**Estimated Effort:** 4-6 hours
- Schema changes: 30 minutes
- Hash function updates: 30 minutes  
- Transformation logic: 1 hour
- Test updates: 1.5 hours
- Full pipeline test: 30 minutes
- Documentation: 30 minutes
- Review and validation: 1 hour

**Priority:** High (data model correctness issue)

**Urgency:** Should be fixed before next release to avoid propagating incorrect model

## Success Criteria

✅ TEVK table has no `NationalIndividualElectoralDistrict_ID` column  
✅ `hash_tevk_id()` accepts 3 parameters (county, settlement, tevk)  
✅ TEVK transformation has no OEVK JOIN  
✅ UNIQUE constraint is `(County_ID, Settlement_ID, TEVK)`  
✅ All hash function call sites updated (PollingStation, Address transformations)  
✅ All tests pass with new schema  
✅ Full pipeline completes successfully  
✅ Verification query shows TEVKs spanning multiple OEVKs (proves independence)  
✅ Documentation updated to reflect correct model  

## References

- **Problem Analysis:** `docs/009_FIXING_OEVK_TEVK_RELATION.md`
- **Hungarian Electoral Law:** TEVK and OEVK are separate systems for different government levels
- **Source Data:** `staging_korzet` contains both codes for polling station mapping, not hierarchy

---

**Proposed By:** AI Analysis based on Hungarian requirement  
**Date:** 2025-10-24  
**Spec Deltas:** electoral-districts (MODIFIED)  
**Related Changes:** None
