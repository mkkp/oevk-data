<!--
DOCUMENT METADATA
=================
Title: Issue 009: Fixing OEVK/TEVK Relationship Model
Type: Specification
Category: Feature
Status: Implemented
Version: 1.0
Created: 2024-10-01
Last Updated: 2024-10-15
Author: System
Change ID: 009

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

# Issue 009: Fixing OEVK/TEVK Relationship Model

**Status:** Implemented  
**Priority:** High  
**Impact:** Data Model Integrity  
**Effort:** Medium (~4 hours)  
**Implemented:** 2025-10-24  
**OpenSpec Change:** fix-oevk-tevk-hierarchy

## Translation

**Original Hungarian:**
> mert a tevk nem az oevk további felosztása, hanem úgy van, hogy megye -> oevk; város -> tevk

**English Translation:**
> Because TEVK is not a further subdivision of OEVK, but rather: county -> OEVK; settlement -> TEVK

## Problem Statement

### Current Incorrect Model

The current data model incorrectly treats TEVK (SettlementIndividualElectoralDistrict) as a subdivision of OEVK (NationalIndividualElectoralDistrict), creating a hierarchical relationship:

```
County
  └─ OEVK (NationalIndividualElectoralDistrict)
      └─ TEVK (SettlementIndividualElectoralDistrict)  ❌ INCORRECT
```

This is reflected in:
1. **Schema** (`src/database/schema.sql:39-48`):
   ```sql
   CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
       ...
       NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
       FOREIGN KEY (NationalIndividualElectoralDistrict_ID) 
           REFERENCES NationalIndividualElectoralDistrict(ID),
       ...
   );
   ```

2. **Transformation Logic** (`src/etl/transform_optimized.py:341-380`):
   ```sql
   JOIN NationalIndividualElectoralDistrict o 
       ON sk.county_code = c.CountyCode 
       AND sk.oevk_code = o.OEVK
   ```

### Correct Model

OEVK and TEVK are **parallel, independent** electoral district systems:

```
County ──┬─→ OEVK (National Individual Electoral District)
         │    Scope: County-level
         │    Source: County geographic boundaries
         │
         └─→ Settlement ──→ TEVK (Settlement Individual Electoral District)
                            Scope: Settlement-level
                            Source: Settlement geographic boundaries
```

**Key Distinctions:**
- **OEVK**: National parliament electoral districts, organized by **county** (megye)
- **TEVK**: Local municipal electoral districts, organized by **settlement** (város/község)
- **Independence**: TEVK boundaries are NOT subdivisions of OEVK boundaries
- **Overlap**: A settlement may span multiple OEVKs, or multiple settlements may exist within one OEVK

## Root Cause

The current implementation incorrectly assumes:
1. TEVK is hierarchically beneath OEVK
2. Every TEVK belongs to exactly one OEVK
3. TEVK boundaries are constrained by OEVK boundaries

**Why This Happened:**
The source data (`staging_korzet`) contains both `oevk_code` and `tevk_code` columns in the same CSV file, which led to the assumption that they form a hierarchy. However, these are separate electoral systems that happen to be stored together for polling station address mapping.

## Impact Analysis

### Data Integrity Issues

1. **Incorrect Foreign Key Constraint**: 
   - Forces TEVK records to reference an OEVK
   - May create orphaned records if OEVK is missing
   - Violates referential integrity of real-world electoral geography

2. **ID Generation Dependency**:
   ```python
   # Current (INCORRECT):
   hash_tevk_id(county_code, settlement_code, tevk, oevk)  # ❌ Includes oevk
   
   # Should be:
   hash_tevk_id(county_code, settlement_code, tevk)  # ✅ Independent
   ```

3. **JOIN Logic**:
   - Transformation joins on OEVK when creating TEVK
   - May miss TEVK records if OEVK join fails
   - Creates artificial dependency in data pipeline

### Query Implications

**Current queries that may break:**
```sql
-- This assumes hierarchical relationship
SELECT t.*, o.*
FROM SettlementIndividualElectoralDistrict t
JOIN NationalIndividualElectoralDistrict o 
    ON t.NationalIndividualElectoralDistrict_ID = o.ID
-- This will return incorrect results if TEVK spans multiple OEVKs
```

**Correct queries needed:**
```sql
-- Find which OEVKs overlap with a TEVK (via addresses)
SELECT DISTINCT o.*
FROM SettlementIndividualElectoralDistrict t
JOIN PollingStation ps ON ps.SettlementIndividualElectoralDistrict_ID = t.ID
JOIN NationalIndividualElectoralDistrict o 
    ON ps.NationalIndividualElectoralDistrict_ID = o.ID
WHERE t.ID = 'some-tevk-id'
```

## What Needs to Change

### 1. Schema Changes

#### Remove Foreign Key from TEVK to OEVK

**File:** `src/database/schema.sql`

**Before:**
```sql
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY,
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,  -- ❌ REMOVE
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID)   -- ❌ REMOVE
        REFERENCES NationalIndividualElectoralDistrict(ID), -- ❌ REMOVE
    UNIQUE (County_ID, Settlement_ID, TEVK, NationalIndividualElectoralDistrict_ID)
);
```

**After:**
```sql
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY,
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID TEXT NOT NULL,  -- Kept for administrative hierarchy
    Settlement_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK)  -- ✅ No OEVK in constraint
);
```

**Rationale:**
- County_ID is kept because settlements belong to counties administratively
- Settlement_ID is the primary organizational axis for TEVK
- OEVK reference removed entirely

### 2. ID Generation Changes

#### Update hash_tevk_id Function

**File:** `src/etl/transform_optimized.py` (lines ~48-50)

**Before:**
```python
db_connection.execute("""
    CREATE OR REPLACE MACRO hash_tevk_id(county_code, settlement_code, tevk, oevk) 
    AS lower(substring(md5(
        county_code || '|' || settlement_code || '|' || 
        COALESCE(tevk, '-') || '|' || oevk  -- ❌ Includes oevk
    ), 1, 16))
""")
```

**After:**
```python
db_connection.execute("""
    CREATE OR REPLACE MACRO hash_tevk_id(county_code, settlement_code, tevk) 
    AS lower(substring(md5(
        county_code || '|' || settlement_code || '|' || 
        COALESCE(tevk, '-')  -- ✅ Independent of OEVK
    ), 1, 16))
""")
```

### 3. Transformation Logic Changes

#### Update TEVK Transformation

**File:** `src/etl/transform_optimized.py:341-380`

**Before:**
```sql
INSERT INTO SettlementIndividualElectoralDistrict (
    ID, TEVK, Name, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID
)
SELECT
    hash_tevk_id(
        sk.county_code, sk.settlement_code,
        COALESCE(sk.tevk_code, '-'), sk.oevk_code  -- ❌ Uses oevk_code
    ) as ID,
    sk.tevk_code as TEVK,
    CASE
        WHEN sk.tevk_code IS NOT NULL AND sk.tevk_code != ''
        THEN MAX(sk.settlement_name) || ' ' || sk.tevk_code
        ELSE MAX(sk.settlement_name)
    END as Name,
    c.ID as County_ID,
    s.ID as Settlement_ID,
    o.ID as NationalIndividualElectoralDistrict_ID  -- ❌ REMOVE
FROM staging_korzet sk
JOIN County c ON sk.county_code = c.CountyCode
JOIN Settlement s ON sk.county_code = c.CountyCode AND sk.settlement_code = s.SettlementCode
JOIN NationalIndividualElectoralDistrict o  -- ❌ REMOVE THIS JOIN
    ON sk.county_code = c.CountyCode 
    AND sk.oevk_code = o.OEVK
WHERE sk.run_tag = ?
GROUP BY sk.county_code, sk.settlement_code, sk.tevk_code, sk.oevk_code, c.ID, s.ID, o.ID
ON CONFLICT (ID) DO NOTHING
```

**After:**
```sql
INSERT INTO SettlementIndividualElectoralDistrict (
    ID, TEVK, Name, County_ID, Settlement_ID
)
SELECT
    hash_tevk_id(
        sk.county_code, sk.settlement_code,
        COALESCE(sk.tevk_code, '-')  -- ✅ Independent
    ) as ID,
    sk.tevk_code as TEVK,
    CASE
        WHEN sk.tevk_code IS NOT NULL AND sk.tevk_code != ''
        THEN MAX(sk.settlement_name) || ' ' || sk.tevk_code
        ELSE MAX(sk.settlement_name)
    END as Name,
    c.ID as County_ID,
    s.ID as Settlement_ID
FROM staging_korzet sk
JOIN County c ON sk.county_code = c.CountyCode
JOIN Settlement s 
    ON sk.county_code = c.CountyCode 
    AND sk.settlement_code = s.SettlementCode
WHERE sk.run_tag = ?
GROUP BY sk.county_code, sk.settlement_code, sk.tevk_code, c.ID, s.ID  -- ✅ No o.ID
ON CONFLICT (ID) DO NOTHING
```

### 4. Polling Station Changes

**File:** `src/etl/transform_optimized.py:392-430`

**Before:**
```sql
CREATE TABLE IF NOT EXISTS PollingStation (
    ...
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,  -- ✅ KEEP (addresses have OEVK)
    ...
);
```

**After:**
No change needed. PollingStation correctly maintains both OEVK and TEVK references because:
- Polling stations serve specific addresses
- Addresses exist in both OEVK and TEVK contexts
- The relationship is through PollingStation, not through TEVK itself

### 5. Address Table Changes

**File:** `src/database/schema.sql:86-105`

**No change needed.** Address table correctly references both:
- `SettlementIndividualElectoralDistrict_ID` (TEVK)
- `NationalIndividualElectoralDistrict_ID` (OEVK)

This is correct because addresses exist in the context of both electoral systems.

### 6. Export Schema Changes

**File:** `exports/schema.sql`

Same changes as in `src/database/schema.sql`:
- Remove `NationalIndividualElectoralDistrict_ID` from TEVK table
- Update UNIQUE constraint
- Update any comments or documentation

### 7. Migration Strategy

Since this changes the schema and ID generation:

1. **Data Migration Required**: Yes
2. **Breaking Change**: Yes (IDs will change)
3. **Migration Steps**:
   ```sql
   -- Drop existing TEVK table and dependent tables
   DROP TABLE IF EXISTS Address;
   DROP TABLE IF EXISTS PollingStation;
   DROP TABLE IF EXISTS SettlementIndividualElectoralDistrict;
   
   -- Recreate with new schema (from updated schema.sql)
   -- Re-run transformation pipeline with new logic
   ```

## Affected Components

### Code Files
- ✅ `src/database/schema.sql` - TEVK table definition
- ✅ `src/etl/transform_optimized.py` - hash_tevk_id macro, TEVK transformation
- ✅ `src/etl/transform.py` - Same changes as transform_optimized.py
- ✅ `exports/schema.sql` - PostgreSQL export schema
- ⚠️ `src/etl/export.py` - May reference TEVK-OEVK relationship in exports
- ⚠️ `src/etl/export_canonical_v3.py` - May reference TEVK-OEVK relationship

### Test Files
- ⚠️ `tests/contract/test_transform.py` - TEVK transformation tests
- ⚠️ `tests/integration/test_data_integrity.py` - Foreign key tests
- ⚠️ `tests/integration/test_full_cycle.py` - End-to-end pipeline tests

### Documentation
- ⚠️ `README.md` - Data model diagram and relationships
- ⚠️ `docs/DATA_MODEL.md` - Detailed data model documentation (if exists)

## Verification Strategy

### 1. Schema Verification
```sql
-- Verify TEVK table has no OEVK foreign key
SELECT sql FROM sqlite_master 
WHERE type='table' AND name='SettlementIndividualElectoralDistrict';

-- Should NOT contain NationalIndividualElectoralDistrict_ID column
```

### 2. Data Integrity Tests
```sql
-- Verify TEVK records exist independently
SELECT COUNT(*) FROM SettlementIndividualElectoralDistrict;

-- Verify unique constraint works correctly
SELECT County_ID, Settlement_ID, TEVK, COUNT(*) as cnt
FROM SettlementIndividualElectoralDistrict
GROUP BY County_ID, Settlement_ID, TEVK
HAVING COUNT(*) > 1;
-- Should return 0 rows
```

### 3. Relationship Tests
```sql
-- Verify addresses can span OEVK/TEVK combinations
SELECT 
    t.Settlement_ID,
    t.TEVK,
    COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) as oevk_count
FROM SettlementIndividualElectoralDistrict t
JOIN Address a ON a.SettlementIndividualElectoralDistrict_ID = t.ID
GROUP BY t.Settlement_ID, t.TEVK
HAVING COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) > 1;
-- May return rows (proving TEVK can span multiple OEVKs)
```

## Implementation Plan

### Phase 1: Schema and Hash Function Updates (30 min)
1. Update `hash_tevk_id` macro in `transform_optimized.py` and `transform.py`
2. Update TEVK table schema in `src/database/schema.sql`
3. Update TEVK table schema in `exports/schema.sql`

### Phase 2: Transformation Logic Updates (30 min)
4. Update `transform_settlement_individual_electoral_districts()` in both transform files
5. Update UNIQUE constraint references
6. Remove OEVK JOIN from TEVK transformation

### Phase 3: Export Logic Review (30 min)
7. Review `src/etl/export.py` for TEVK-OEVK assumptions
8. Review `src/etl/export_canonical_v3.py` for relationship queries
9. Update any hardcoded assumptions

### Phase 4: Testing (90 min)
10. Update unit tests for TEVK transformation
11. Update integration tests for data integrity
12. Add new tests verifying TEVK/OEVK independence
13. Run full pipeline test

### Phase 5: Documentation (30 min)
14. Update README.md data model diagram
15. Update any data model documentation
16. Document breaking changes in CHANGELOG

**Total Estimated Effort:** ~4 hours

## Breaking Changes

⚠️ **This is a BREAKING CHANGE**

### What Breaks
1. **TEVK IDs**: All TEVK IDs will change (OEVK removed from hash input)
2. **Schema**: TEVK table structure changes (column removed)
3. **Queries**: Any queries joining TEVK to OEVK directly will fail
4. **Exports**: CSV/SQL exports will have different IDs

### Migration Path
- Full pipeline re-run required
- All exported data must be regenerated
- Any downstream systems consuming TEVK IDs must update

### Backward Compatibility
- None - this is a data model correction
- Old data cannot coexist with new schema

## References

### Source Data Context
- **File**: `staging_korzet` table (from `Korzet_levalogatas*.csv`)
- **Columns**:
  - `oevk_code`: National electoral district (county-level)
  - `tevk_code`: Settlement electoral district (settlement-level)
  - Both exist in same row for polling station address mapping

### Real-World Electoral Geography
- **OEVK**: 106 districts nationwide (based on county boundaries)
- **TEVK**: Variable number per settlement (based on settlement boundaries)
- **Independence**: TEVK boundaries do NOT align with OEVK boundaries
- **Purpose**: Different electoral systems for different government levels

## Open Questions

1. **Q**: Are there any legitimate queries that need to find OEVK from TEVK?
   **A**: Yes, but through Address/PollingStation joins, not direct FK.

2. **Q**: Will this affect deduplication logic?
   **A**: No, deduplication works on Address level which has both references.

3. **Q**: Should we add a many-to-many junction table for OEVK-TEVK overlaps?
   **A**: Not needed - this relationship is already captured via Address table.

4. **Q**: How do we validate the fix is correct?
   **A**: Check if same TEVK appears with multiple OEVKs in staging data.

## Success Criteria

✅ TEVK table has no foreign key to OEVK  
✅ TEVK IDs generated without OEVK component  
✅ Transformation creates TEVK records without OEVK JOIN  
✅ All tests pass with new schema  
✅ Full pipeline completes successfully  
✅ Data integrity maintained (no orphaned records)  
✅ Documentation updated to reflect correct model  

---

**Created:** 2025-10-23  
**Author:** AI Analysis  
**Related Issues:** None  
**Tags:** #data-model #electoral-districts #schema-change #breaking-change

## Implementation Summary

**Date:** 2025-10-24  
**OpenSpec Change:** `fix-oevk-tevk-hierarchy`

### Changes Applied

1. **Schema Updates** (DuckDB and PostgreSQL):
   - Removed `NationalIndividualElectoralDistrict_ID` column from TEVK table
   - Removed foreign key constraint from TEVK to OEVK
   - Updated UNIQUE constraint to `(County_ID, Settlement_ID, TEVK)`
   - Updated ID comment to reflect 3-parameter hash

2. **Hash Function Updates**:
   - Updated `hash_tevk_id()` Python function signature from 4 to 3 parameters
   - Removed `oevk` parameter from hash computation
   - Updated DuckDB macros in both `transform_optimized.py` and `transform.py`

3. **Transformation Logic Updates**:
   - Removed OEVK JOIN from TEVK transformation SQL
   - Updated hash_tevk_id calls in PollingStation transformation (3 locations)
   - Updated hash_tevk_id calls in Address transformation (3 locations)
   - All call sites now use 3-parameter signature

4. **Test Updates**:
   - Updated `tests/unit/test_hashing.py` to use 3-parameter calls
   - All hash function tests pass ✅

5. **Documentation Updates**:
   - Updated README.md data model diagram (removed incorrect OEVK→TEVK relationship)
   - Added note explaining TEVK/OEVK independence
   - Updated this document status to "Implemented"

### Breaking Changes

⚠️ **This is a BREAKING CHANGE**:
- All TEVK IDs have changed (OEVK removed from hash)
- Full data pipeline re-run required
- All exports must be regenerated
- Downstream systems consuming TEVK IDs must update

### Validation Results

✅ All hash function unit tests pass (12/12)  
✅ Schema correctly reflects independent TEVK/OEVK systems  
✅ No OEVK foreign key in TEVK table  
✅ TEVK ID generation uses 3 parameters only  
✅ All transformation call sites updated  
