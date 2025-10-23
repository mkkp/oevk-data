# Spec: Electoral Districts

**Capability:** `electoral-districts`  
**Status:** New (Created for fix-oevk-tevk-hierarchy)  
**Scope:** Data model for Hungarian electoral districts (OEVK and TEVK)

---

## ADDED Requirements

### Requirement: TEVK must be independent of OEVK

**The system SHALL model TEVK (SettlementIndividualElectoralDistrict) as organizationally independent from OEVK (NationalIndividualElectoralDistrict), reflecting the real-world electoral geography where TEVK belongs to settlements and OEVK belongs to counties.**

**Context:** The Hungarian electoral system has two parallel district systems:
- OEVK: National Individual Electoral Districts (~106) for parliamentary elections, organized by county
- TEVK: Settlement Individual Electoral Districts (~4,677) for municipal elections, organized by settlement

These are NOT hierarchical (TEVK is not a subdivision of OEVK). They are parallel systems that may overlap geographically.

#### Scenario: TEVK table has no foreign key to OEVK

**Given** the SettlementIndividualElectoralDistrict table exists  
**When** I query the table's foreign key constraints  
**Then** foreign keys to County and Settlement SHALL exist  
**And** NO foreign key to NationalIndividualElectoralDistrict SHALL exist

```sql
-- Verification
PRAGMA foreign_key_list(SettlementIndividualElectoralDistrict);
-- Should return FKs to: County, Settlement
-- Should NOT return FK to: NationalIndividualElectoralDistrict
```

#### Scenario: TEVK ID is independent of OEVK

**Given** a TEVK record with county "01", settlement "001", and TEVK code "1"  
**When** I generate the TEVK ID using hash_tevk_id  
**Then** the ID SHALL be computed from (county_code, settlement_code, tevk_code) only  
**And** the ID SHALL NOT include oevk_code in the hash computation

```python
# Correct function signature
def hash_tevk_id(county_code: str, settlement_code: str, tevk: str) -> str:
    return hash(f"{county_code}|{settlement_code}|{tevk}")
```

#### Scenario: TEVK unique constraint excludes OEVK

**Given** the SettlementIndividualElectoralDistrict table  
**When** I attempt to insert two records with same County_ID, Settlement_ID, and TEVK  
**Then** a UNIQUE constraint violation SHALL occur  
**And** the UNIQUE constraint SHALL be on (County_ID, Settlement_ID, TEVK) only  
**And** the UNIQUE constraint SHALL NOT include NationalIndividualElectoralDistrict_ID

```sql
-- Unique constraint definition
UNIQUE (County_ID, Settlement_ID, TEVK)
```

#### Scenario: TEVK transformation is independent of OEVK

**Given** staging data with TEVK records  
**When** transforming to SettlementIndividualElectoralDistrict table  
**Then** NO JOIN to NationalIndividualElectoralDistrict SHALL be performed  
**And** TEVK records SHALL be created based on County and Settlement only

```sql
-- Correct transformation SQL
INSERT INTO SettlementIndividualElectoralDistrict (ID, TEVK, Name, County_ID, Settlement_ID)
SELECT
    hash_tevk_id(county_code, settlement_code, tevk_code),
    tevk_code,
    settlement_name || ' ' || tevk_code,
    County.ID,
    Settlement.ID
FROM staging_korzet
JOIN County ON ...
JOIN Settlement ON ...
-- NO JOIN to NationalIndividualElectoralDistrict
```

### Requirement: Addresses and polling stations maintain both OEVK and TEVK references

**The system SHALL maintain foreign key relationships from PollingStation and Address tables to BOTH SettlementIndividualElectoralDistrict (TEVK) and NationalIndividualElectoralDistrict (OEVK), because addresses and polling stations participate in both electoral systems.**

**Rationale:** While TEVK and OEVK are organizationally independent, physical addresses and polling stations exist in the context of both systems simultaneously. The relationship between TEVK and OEVK is discoverable via the Address table.

#### Scenario: PollingStation has FKs to both TEVK and OEVK

**Given** a PollingStation record  
**When** I query its relationships  
**Then** it SHALL have a foreign key to SettlementIndividualElectoralDistrict  
**And** it SHALL have a foreign key to NationalIndividualElectoralDistrict

```sql
-- PollingStation schema
CREATE TABLE PollingStation (
    ...
    SettlementIndividualElectoralDistrict_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) 
        REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) 
        REFERENCES NationalIndividualElectoralDistrict(ID)
);
```

#### Scenario: Address has FKs to both TEVK and OEVK

**Given** an Address record  
**When** I query its relationships  
**Then** it SHALL have a foreign key to SettlementIndividualElectoralDistrict  
**And** it SHALL have a foreign key to NationalIndividualElectoralDistrict

```sql
-- Address schema
CREATE TABLE Address (
    ...
    SettlementIndividualElectoralDistrict_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) 
        REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) 
        REFERENCES NationalIndividualElectoralDistrict(ID)
);
```

#### Scenario: TEVK-OEVK relationship discoverable via Address table

**Given** a TEVK record  
**When** I need to find which OEVKs overlap with this TEVK  
**Then** I SHALL query via the Address table join  
**And** the result MAY return multiple OEVKs (proving independence)

```sql
-- Correct pattern for discovering OEVK from TEVK
SELECT DISTINCT o.*
FROM SettlementIndividualElectoralDistrict t
JOIN Address a ON a.SettlementIndividualElectoralDistrict_ID = t.ID
JOIN NationalIndividualElectoralDistrict o 
    ON a.NationalIndividualElectoralDistrict_ID = o.ID
WHERE t.ID = ?;
```

### Requirement: TEVK ID generation must be deterministic and independent

**The system SHALL generate TEVK IDs deterministically based on (county_code, settlement_code, tevk_code) using xxhash64, ensuring idempotent processing and independence from OEVK.**

#### Scenario: Same TEVK inputs produce same ID

**Given** two calls to hash_tevk_id with county "01", settlement "001", TEVK "1"  
**When** I compare the generated IDs  
**Then** both IDs SHALL be identical  
**And** the IDs SHALL be 16-character hexadecimal strings (xxhash64 format)

```python
id1 = hash_tevk_id("01", "001", "1")
id2 = hash_tevk_id("01", "001", "1")
assert id1 == id2
assert len(id1) == 16  # xxhash64 hex digest length
```

#### Scenario: Different TEVK inputs produce different IDs

**Given** hash_tevk_id called with different parameters  
**When** I compare the generated IDs  
**Then** the IDs SHALL be different

```python
id1 = hash_tevk_id("01", "001", "1")
id2 = hash_tevk_id("01", "001", "2")  # Different TEVK
id3 = hash_tevk_id("01", "002", "1")  # Different settlement
assert id1 != id2
assert id1 != id3
assert id2 != id3
```

#### Scenario: TEVK ID excludes OEVK component

**Given** the hash_tevk_id function  
**When** I inspect its parameters  
**Then** it SHALL accept exactly 3 parameters: county_code, settlement_code, tevk  
**And** it SHALL NOT accept an oevk parameter

```python
# Correct signature (3 parameters)
def hash_tevk_id(
    county_code: str,
    settlement_code: str, 
    tevk: str
) -> str:
    pass

# Incorrect signature (4 parameters) - MUST NOT exist
# def hash_tevk_id(county_code: str, settlement_code: str, tevk: str, oevk: str) -> str:
#     pass  # ❌ Wrong
```

### Requirement: Schema must support TEVK/OEVK independence verification

**The system SHALL allow verification that TEVKs can span multiple OEVKs through data queries, proving the independence of the two electoral systems.**

#### Scenario: Query can identify TEVKs spanning multiple OEVKs

**Given** the database contains real address data  
**When** I query for TEVKs that appear in multiple OEVKs  
**Then** the query SHALL execute successfully  
**And** the query MAY return results (if such cases exist in real data)  
**And** the existence of such results proves TEVK/OEVK independence

```sql
-- Verification query
SELECT 
    t.Settlement_ID,
    t.TEVK,
    COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) as oevk_count
FROM SettlementIndividualElectoralDistrict t
JOIN Address a ON a.SettlementIndividualElectoralDistrict_ID = t.ID
GROUP BY t.Settlement_ID, t.TEVK
HAVING COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) > 1;

-- If returns rows: TEVK spans multiple OEVKs (proves independence)
-- If returns empty: All TEVKs fit within single OEVK (still valid, independence allowed)
```

#### Scenario: Schema allows TEVK to exist without OEVK constraint

**Given** a TEVK record  
**When** no addresses reference this TEVK  
**Then** the TEVK record SHALL remain valid  
**And** NO orphan check requiring OEVK SHALL fail

```sql
-- Valid TEVK with no addresses (allowed)
INSERT INTO SettlementIndividualElectoralDistrict 
    (ID, TEVK, Name, County_ID, Settlement_ID)
VALUES 
    ('abc123', '1', 'Test TEVK', 'county_id', 'settlement_id');
-- Should succeed even if no OEVK relationship exists
```

---

## ADDED Requirements

### Requirement: TEVK table schema must match organizational reality

**The system SHALL define the SettlementIndividualElectoralDistrict table with columns that reflect its organizational relationship to Settlement, not to OEVK.**

#### Scenario: TEVK table has required columns only

**Given** the SettlementIndividualElectoralDistrict table  
**When** I query its schema  
**Then** it SHALL have columns: ID, TEVK, Name, County_ID, Settlement_ID  
**And** it SHALL NOT have column: NationalIndividualElectoralDistrict_ID

```sql
PRAGMA table_info(SettlementIndividualElectoralDistrict);
-- Required columns:
-- - ID (TEXT PRIMARY KEY)
-- - TEVK (TEXT)
-- - Name (TEXT NOT NULL)
-- - County_ID (TEXT NOT NULL, FK to County)
-- - Settlement_ID (TEXT NOT NULL, FK to Settlement)

-- Forbidden columns:
-- - NationalIndividualElectoralDistrict_ID
```

#### Scenario: TEVK table has exactly 2 foreign keys

**Given** the SettlementIndividualElectoralDistrict table  
**When** I query its foreign keys  
**Then** it SHALL have exactly 2 foreign keys  
**And** one SHALL reference County(ID)  
**And** one SHALL reference Settlement(ID)

```sql
-- Foreign keys
FOREIGN KEY (County_ID) REFERENCES County(ID)
FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID)
-- Total: 2 foreign keys (NOT 3)
```

### Requirement: Hash function call sites must use correct signature

**The system SHALL call hash_tevk_id with 3 parameters (county, settlement, tevk) at all call sites throughout the transformation pipeline.**

#### Scenario: TEVK table transformation uses 3-parameter hash

**Given** the TEVK transformation SQL  
**When** creating TEVK records  
**Then** hash_tevk_id SHALL be called with 3 parameters  
**And** the parameters SHALL be: county_code, settlement_code, tevk_code

```sql
SELECT hash_tevk_id(
    sk.county_code,
    sk.settlement_code, 
    COALESCE(sk.tevk_code, '-')
) as ID
-- NO fourth parameter (oevk_code)
```

#### Scenario: PollingStation transformation uses 3-parameter TEVK hash

**Given** the PollingStation transformation SQL  
**When** setting SettlementIndividualElectoralDistrict_ID  
**Then** hash_tevk_id SHALL be called with 3 parameters

```sql
SELECT 
    hash_tevk_id(
        county_code,
        settlement_code,
        COALESCE(tevk_code, '-')
    ) as SettlementIndividualElectoralDistrict_ID
-- Correct: 3 parameters
```

#### Scenario: Address transformation uses 3-parameter TEVK hash

**Given** the Address transformation SQL (both original and canonical)  
**When** setting SettlementIndividualElectoralDistrict_ID  
**Then** hash_tevk_id SHALL be called with 3 parameters in both locations

```sql
-- Location 1: Original address transformation
SELECT hash_tevk_id(county_code, settlement_code, COALESCE(tevk_code, '-'))

-- Location 2: Canonical address transformation  
SELECT hash_tevk_id(county_code, settlement_code, COALESCE(tevk_code, '-'))
```

---

## Implementation Notes

### Files Affected

**Schema:**
- `src/database/schema.sql` - TEVK table definition
- `exports/schema.sql` - PostgreSQL export schema

**Hash Functions:**
- `src/etl/hashing.py` - `hash_tevk_id()` function signature and implementation
- `src/etl/transform_optimized.py` - DuckDB macro at line ~50
- `src/etl/transform.py` - DuckDB macro at line ~37

**Transformations:**
- `src/etl/transform_optimized.py`:
  - Line ~354: TEVK table transformation
  - Line ~403: PollingStation TEVK ID assignment
  - Line ~501: Original Address TEVK ID assignment
  - Line ~748: Canonical Address TEVK ID assignment
- `src/etl/transform.py`:
  - Line ~250: TEVK table transformation
  - Line ~296: PollingStation TEVK ID assignment
  - Line ~380: Address TEVK ID assignment

### Migration Notes

**Breaking Change:** Yes
- TEVK IDs will change (OEVK component removed from hash)
- Schema incompatible (column removed)
- Full pipeline re-run required
- All exports must be regenerated

**No Backward Compatibility:**
- Old data cannot coexist with new schema
- Old IDs cannot be preserved (they were based on incorrect model)

**Validation:**
- Schema verification: Check FK list, table columns
- ID verification: Test deterministic generation
- Independence verification: Query for TEVKs spanning multiple OEVKs

---

**Spec Version:** 1.0  
**Created:** 2025-10-24  
**Related Changes:** fix-oevk-tevk-hierarchy
