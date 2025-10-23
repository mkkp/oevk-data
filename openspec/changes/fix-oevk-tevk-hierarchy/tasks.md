# Tasks: Fix OEVK/TEVK Hierarchy

**Change ID:** `fix-oevk-tevk-hierarchy`  
**Estimated Effort:** ~4-6 hours  
**Risk Level:** Medium (breaking change, data regeneration required)

---

## Task Breakdown

### Phase 1: Schema Updates (30 minutes)

#### Task 1.1: Update DuckDB schema - Remove OEVK FK from TEVK table
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Open `src/database/schema.sql`
- [x] Locate `SettlementIndividualElectoralDistrict` table (line ~34)
- [x] Remove line: `NationalIndividualElectoralDistrict_ID TEXT NOT NULL,`
- [x] Remove line: `FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID),`
- [x] Update UNIQUE constraint from:
  ```sql
  UNIQUE (County_ID, Settlement_ID, TEVK, NationalIndividualElectoralDistrict_ID)
  ```
  To:
  ```sql
  UNIQUE (County_ID, Settlement_ID, TEVK)
  ```
- [x] Update comment for ID field from:
  ```sql
  ID TEXT PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode|TEVK|OEVK)
  ```
  To:
  ```sql
  ID TEXT PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode|TEVK)
  ```
- [x] Save file

**Acceptance:**
- SettlementIndividualElectoralDistrict table has 5 columns (not 6)
- No FOREIGN KEY to NationalIndividualElectoralDistrict
- UNIQUE constraint on 3 fields (County_ID, Settlement_ID, TEVK)

#### Task 1.2: Update PostgreSQL export schema
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 1.1

**Steps:**
- [x] Open `exports/schema.sql`
- [x] Find SettlementIndividualElectoralDistrict table definition
- [x] Apply same changes as Task 1.1 (remove OEVK column and FK)
- [x] Verify UUID type consistency (PostgreSQL uses UUID, not TEXT)
- [x] Save file

**Acceptance:**
- PostgreSQL schema matches DuckDB schema structure
- TEVK table has no NationalIndividualElectoralDistrict_ID column
- UUID types correctly applied

---

### Phase 2: Hash Function Updates (45 minutes)

#### Task 2.1: Update hash_tevk_id Python function
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Open `src/etl/hashing.py`
- [x] Locate `hash_tevk_id()` function (line ~47)
- [x] Update function signature from:
  ```python
  def hash_tevk_id(county_code: str, settlement_code: str, tevk: str, oevk: str) -> str:
  ```
  To:
  ```python
  def hash_tevk_id(county_code: str, settlement_code: str, tevk: str) -> str:
  ```
- [x] Update docstring to remove `oevk` parameter documentation
- [x] Update hash data from:
  ```python
  data = f"{county_code}|{settlement_code}|{tevk_str}|{oevk}".encode("utf-8")
  ```
  To:
  ```python
  data = f"{county_code}|{settlement_code}|{tevk_str}".encode("utf-8")
  ```
- [x] Save file

**Acceptance:**
- Function accepts 3 parameters (not 4)
- Hash computed from county|settlement|tevk only
- Docstring accurate

#### Task 2.2: Update hash_tevk_id DuckDB macro in transform_optimized.py
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 2.1

**Steps:**
- [x] Open `src/etl/transform_optimized.py`
- [x] Locate macro definition (line ~50)
- [x] Update from:
  ```python
  CREATE OR REPLACE MACRO hash_tevk_id(county_code, settlement_code, tevk, oevk) 
  AS lower(substring(md5(county_code || '|' || settlement_code || '|' || COALESCE(tevk, '-') || '|' || oevk), 1, 16))
  ```
  To:
  ```python
  CREATE OR REPLACE MACRO hash_tevk_id(county_code, settlement_code, tevk) 
  AS lower(substring(md5(county_code || '|' || settlement_code || '|' || COALESCE(tevk, '-')), 1, 16))
  ```
- [x] Save file

**Acceptance:**
- Macro accepts 3 parameters
- MD5 hash excludes oevk component

#### Task 2.3: Update hash_tevk_id DuckDB macro in transform.py
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 2.1

**Steps:**
- [x] Open `src/etl/transform.py`
- [x] Locate macro definition (line ~37)
- [x] Apply same change as Task 2.2
- [x] Save file

**Acceptance:**
- Macro signature matches transform_optimized.py
- Consistent across both transformation implementations

---

### Phase 3: TEVK Transformation Logic (30 minutes)

#### Task 3.1: Update TEVK table transformation in transform_optimized.py
**Effort:** 15 minutes  
**Risk:** Medium  
**Dependencies:** Task 2.2

**Steps:**
- [x] Open `src/etl/transform_optimized.py`
- [x] Locate `transform_settlement_individual_electoral_districts()` function (line ~341)
- [x] Update INSERT statement:
  - Remove `NationalIndividualElectoralDistrict_ID` from column list
  - Update hash_tevk_id call to use 3 parameters (remove `sk.oevk_code`)
  - Remove `o.ID as NationalIndividualElectoralDistrict_ID` from SELECT
  - Remove JOIN to NationalIndividualElectoralDistrict table
  - Remove `o.ID` from GROUP BY clause
- [x] Before:
  ```sql
  INSERT INTO SettlementIndividualElectoralDistrict (
      ID, TEVK, Name, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID
  )
  SELECT
      hash_tevk_id(sk.county_code, sk.settlement_code, COALESCE(sk.tevk_code, '-'), sk.oevk_code),
      ...
      o.ID as NationalIndividualElectoralDistrict_ID
  FROM staging_korzet sk
  JOIN County c ON ...
  JOIN Settlement s ON ...
  JOIN NationalIndividualElectoralDistrict o ON ...
  GROUP BY ..., o.ID
  ```
- [x] After:
  ```sql
  INSERT INTO SettlementIndividualElectoralDistrict (
      ID, TEVK, Name, County_ID, Settlement_ID
  )
  SELECT
      hash_tevk_id(sk.county_code, sk.settlement_code, COALESCE(sk.tevk_code, '-')),
      ...
  FROM staging_korzet sk
  JOIN County c ON ...
  JOIN Settlement s ON ...
  GROUP BY sk.county_code, sk.settlement_code, sk.tevk_code, c.ID, s.ID
  ```
- [x] Save file

**Acceptance:**
- No JOIN to NationalIndividualElectoralDistrict
- No OEVK column in INSERT
- hash_tevk_id called with 3 parameters
- GROUP BY excludes o.ID

#### Task 3.2: Update TEVK table transformation in transform.py
**Effort:** 15 minutes  
**Risk:** Medium  
**Dependencies:** Task 2.3

**Steps:**
- [x] Open `src/etl/transform.py`
- [x] Locate `transform_settlement_individual_electoral_districts()` function (line ~237)
- [x] Apply same changes as Task 3.1
- [x] Ensure consistency with transform_optimized.py
- [x] Save file

**Acceptance:**
- Transformation logic matches transform_optimized.py
- Consistent behavior across implementations

---

### Phase 4: PollingStation and Address Hash Call Updates (45 minutes)

#### Task 4.1: Update PollingStation transformation in transform_optimized.py
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 2.2

**Steps:**
- [x] Open `src/etl/transform_optimized.py`
- [x] Locate `transform_polling_stations()` function (line ~392)
- [x] Find hash_tevk_id call for SettlementIndividualElectoralDistrict_ID (line ~403)
- [x] Update from:
  ```sql
  hash_tevk_id(county_code, settlement_code, COALESCE(tevk_code, '-'), oevk_code)
  ```
  To:
  ```sql
  hash_tevk_id(county_code, settlement_code, COALESCE(tevk_code, '-'))
  ```
- [x] Note: Keep NationalIndividualElectoralDistrict_ID column (PollingStation needs both FKs)
- [x] Save file

**Acceptance:**
- hash_tevk_id called with 3 parameters
- PollingStation still has both TEVK and OEVK FKs (correct)

#### Task 4.2: Update original Address transformation in transform_optimized.py
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 2.2

**Steps:**
- [x] Open `src/etl/transform_optimized.py`
- [x] Locate address transformation in `transform_addresses()` (line ~478)
- [x] Find hash_tevk_id call (line ~501)
- [x] Update to 3-parameter call
- [x] Note: Keep NationalIndividualElectoralDistrict_ID column (Address needs both FKs)
- [x] Save file

**Acceptance:**
- hash_tevk_id called with 3 parameters
- Address still has both TEVK and OEVK FKs (correct)

#### Task 4.3: Update canonical Address transformation in transform_optimized.py
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** Task 2.2

**Steps:**
- [x] Open `src/etl/transform_optimized.py`
- [x] Locate canonical address chunk processing (line ~724)
- [x] Find hash_tevk_id call (line ~748)
- [x] Update to 3-parameter call
- [x] Save file

**Acceptance:**
- hash_tevk_id called with 3 parameters in canonical address processing
- All address transformation call sites updated

#### Task 4.4: Update Address transformation in transform.py
**Effort:** 10 minutes  
**Risk:** Low  
**Dependencies:** Task 2.3

**Steps:**
- [x] Open `src/etl/transform.py`
- [x] Locate `transform_addresses()` function
- [x] Find hash_tevk_id call (line ~380)
- [x] Update to 3-parameter call
- [x] Save file

**Acceptance:**
- transform.py hash calls match transform_optimized.py
- Consistent across both implementations

---

### Phase 5: Testing (90 minutes)

#### Task 5.1: Update unit tests for hash_tevk_id
**Effort:** 20 minutes  
**Risk:** Low  
**Dependencies:** Task 2.1

**Steps:**
- [x] Search for tests of `hash_tevk_id` in `tests/unit/`
- [x] Update test calls to use 3 parameters (remove oevk)
- [x] Add new test: verify same inputs produce same ID
- [x] Add new test: verify different inputs produce different IDs
- [x] Run: `pytest tests/unit/test_hashing.py -v`

**Acceptance:**
- All hash function unit tests pass
- Tests verify 3-parameter signature
- Deterministic behavior validated

#### Task 5.2: Update contract tests for TEVK transformation
**Effort:** 25 minutes  
**Risk:** Medium  
**Dependencies:** Task 3.1, 3.2

**Steps:**
- [x] Open `tests/contract/test_transform.py`
- [x] Find TEVK transformation tests
- [x] Update assertions to expect no OEVK FK in TEVK table
- [x] Add test: verify TEVK table has 2 FKs (County, Settlement) not 3
- [x] Add test: verify TEVK UNIQUE constraint on 3 fields
- [x] Run: `pytest tests/contract/test_transform.py -v -k tevk`

**Acceptance:**
- TEVK contract tests pass
- Schema validation confirms correct structure

#### Task 5.3: Update integration tests for data integrity
**Effort:** 25 minutes  
**Risk:** Medium  
**Dependencies:** Phase 1-4 complete

**Steps:**
- [x] Open `tests/integration/test_data_integrity.py`
- [x] Find foreign key validation tests
- [x] Update to expect no TEVK→OEVK FK
- [x] Add test: verify TEVK/OEVK independence (query for TEVKs spanning multiple OEVKs)
- [x] Run: `pytest tests/integration/test_data_integrity.py -v`

**Acceptance:**
- Data integrity tests pass
- FK validation confirms correct relationships

#### Task 5.4: Run full pipeline test
**Effort:** 20 minutes  
**Risk:** High  
**Dependencies:** Phase 1-4 complete

**Steps:**
- [x] Clean test database: `rm -f data/test.db`
- [x] Run full pipeline: `pytest tests/integration/test_full_cycle.py -v`
- [x] Verify TEVK count matches expected (~4,677)
- [x] Verify Address count matches expected (~3.3M)
- [x] Check logs for transformation completion messages

**Acceptance:**
- Full pipeline test passes
- All tables populated
- No foreign key violations
- Performance within acceptable range

---

### Phase 6: Documentation (30 minutes)

#### Task 6.1: Update README.md data model diagram
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** None

**Steps:**
- [x] Open `README.md`
- [x] Find data model diagram (likely Mermaid ERD or ASCII art)
- [x] Update to show TEVK under Settlement, not under OEVK
- [x] Add note: "TEVK and OEVK are parallel systems, related via Address table"
- [x] Update relationship arrows to show correct hierarchy
- [x] Save file

**Acceptance:**
- Diagram shows correct organizational structure
- Notes clarify TEVK/OEVK independence

#### Task 6.2: Update docs/009_FIXING_OEVK_TEVK_RELATION.md status
**Effort:** 10 minutes  
**Risk:** Low  
**Dependencies:** All phases complete

**Steps:**
- [x] Open `docs/009_FIXING_OEVK_TEVK_RELATION.md`
- [x] Update **Status:** from "Identified" to "Implemented"
- [x] Add "Implementation" section with:
  - Completion date
  - OpenSpec change ID
  - Validation results
  - Breaking changes summary
- [x] Save file

**Acceptance:**
- Status updated to reflect implementation
- Implementation details documented

#### Task 6.3: Create migration guide
**Effort:** 5 minutes  
**Risk:** Low  
**Dependencies:** All phases complete

**Steps:**
- [x] Create `docs/MIGRATION_TEVK_FIX.md` with:
  - Breaking changes summary
  - Migration steps (backup, re-run pipeline, verify)
  - Downstream system impact
  - Rollback procedure
- [x] Save file

**Acceptance:**
- Migration guide available for users
- Clear instructions for upgrade path

---

### Phase 7: Validation and Cleanup (30 minutes)

#### Task 7.1: Manual schema verification
**Effort:** 15 minutes  
**Risk:** Low  
**Dependencies:** All phases complete

**Steps:**
- [x] Run DuckDB CLI: `duckdb data/oevk.db`
- [x] Execute: `PRAGMA foreign_key_list(SettlementIndividualElectoralDistrict);`
- [x] Verify output shows FKs to County and Settlement only
- [x] Execute: `PRAGMA table_info(SettlementIndividualElectoralDistrict);`
- [x] Verify no NationalIndividualElectoralDistrict_ID column
- [x] Execute independence verification query:
  ```sql
  SELECT t.TEVK, COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) as oevk_count
  FROM SettlementIndividualElectoralDistrict t
  JOIN Address a ON a.SettlementIndividualElectoralDistrict_ID = t.ID
  GROUP BY t.TEVK
  HAVING COUNT(DISTINCT a.NationalIndividualElectoralDistrict_ID) > 1;
  ```
- [x] Document results (even if empty, shows model allows independence)

**Acceptance:**
- Schema matches specification
- Independence verification query executes
- Results documented

#### Task 7.2: Code quality checks
**Effort:** 10 minutes  
**Risk:** Low  
**Dependencies:** All code changes complete

**Steps:**
- [x] Run: `ruff check src/`
- [x] Fix any linting issues
- [x] Run: `ruff format src/`
- [x] Run: `mypy src/etl/hashing.py src/etl/transform_optimized.py src/etl/transform.py`
- [x] Fix any type errors

**Acceptance:**
- No ruff errors
- No mypy errors
- Code properly formatted

#### Task 7.3: Final test suite run
**Effort:** 5 minutes  
**Risk:** Low  
**Dependencies:** All changes complete

**Steps:**
- [x] Run: `pytest tests/ -v --tb=short`
- [x] Verify all tests pass
- [x] Check test coverage: `pytest tests/ --cov=src --cov-report=term-missing`
- [x] Document any test coverage gaps

**Acceptance:**
- All tests pass
- No regressions
- Coverage maintained or improved

---

## Parallel Work Opportunities

**Can be done in parallel:**
- Task 1.1 and Task 1.2 (schema updates)
- Task 2.1, 2.2, 2.3 (hash function updates - different files)
- Task 4.1, 4.2, 4.3, 4.4 (hash call site updates - independent locations)
- Task 6.1, 6.2, 6.3 (documentation - different files)

**Must be sequential:**
- Phase 2 before Phase 3 (hash functions before transformations)
- Phase 3 before Phase 4 (TEVK transformation before downstream updates)
- Phases 1-4 before Phase 5 (implementation before testing)
- Phase 5 before Phase 7 (testing before validation)

---

## Risk Mitigation

### High-Risk Tasks

**Task 5.4: Full pipeline test**
- **Risk:** May reveal integration issues
- **Mitigation:** Test on copy of database first, have rollback plan ready

**Task 3.1, 3.2: TEVK transformation updates**
- **Risk:** Incorrect SQL could lose data
- **Mitigation:** Review SQL carefully, test with small dataset first

### Rollback Plan

If critical issues found during Phase 5 or 7:
1. Revert all code changes: `git revert <commit-range>`
2. Restore database backup (if any)
3. Document issues found
4. Re-plan fix

---

## Success Criteria Checklist

**Schema:**
- [x] TEVK table has 5 columns (not 6)
- [x] TEVK table has 2 FKs (County, Settlement)
- [x] UNIQUE constraint on (County_ID, Settlement_ID, TEVK)

**Code:**
- [x] hash_tevk_id accepts 3 parameters
- [x] All call sites use 3-parameter signature
- [x] No JOIN to OEVK in TEVK transformation

**Tests:**
- [x] All unit tests pass
- [x] All contract tests pass
- [x] All integration tests pass
- [x] Full pipeline test completes successfully

**Documentation:**
- [x] README.md diagram updated
- [x] Migration guide created
- [x] Issue doc updated

**Validation:**
- [x] Schema verification confirms correct structure
- [x] Independence query executes successfully
- [x] No ruff/mypy errors
- [x] Test coverage maintained

---

**Total Estimated Time:** 4-6 hours  
**Phases:** 7  
**Tasks:** 23  
**Priority:** High (data model correctness)
