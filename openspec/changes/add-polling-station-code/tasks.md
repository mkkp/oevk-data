# Implementation Tasks: Add Polling Station Code Column

**Change ID**: `add-polling-station-code`
**Estimated Effort**: 2-3 hours
**Dependencies**: None (additive change)

---

## Task Sequence

### 1. Update DuckDB Schema (Foundation)
**Effort**: 15 min | **Status**: Pending

Add `PollingStationCode VARCHAR` column to DuckDB `PollingStation` table.

**Files**:
- `src/database/schema.py` (or wherever DuckDB schema is defined)

**Actions**:
- Locate `PollingStation` table creation
- Add `PollingStationCode VARCHAR` after `ID` column
- Verify schema creation succeeds with new column

**Validation**:
```bash
python -c "import duckdb; conn=duckdb.connect('data/oevk.db'); print(conn.execute('DESCRIBE PollingStation').fetchall())"
# Should show PollingStationCode column
```

**Dependencies**: None

---

### 2. Update Transformation Logic (Extract Code)
**Effort**: 20 min | **Status**: Pending

Extract `polling_station_code` from `staging_korzet` during transformation.

**Files**:
- `src/etl/transform_optimized.py` (line ~433-453)

**Actions**:
- Update `INSERT INTO PollingStation` statement to include `PollingStationCode`
- Add `TRIM(polling_station_code) as PollingStationCode` to SELECT clause
- Place after `ID` in both INSERT and SELECT

**Example**:
```python
INSERT INTO PollingStation (
    ID, PollingStationCode, PollingStationAddress, ...
)
SELECT
    hash_polling_station_id(...) as ID,
    TRIM(polling_station_code) as PollingStationCode,
    TRIM(polling_station_address) as PollingStationAddress,
    ...
```

**Validation**:
```bash
python -m src.cli run --run-tag test_code
# Check PollingStation table has populated codes
```

**Dependencies**: Task 1

---

### 3. Update PostgreSQL Schema (Export Target)
**Effort**: 15 min | **Status**: Pending

Add `code TEXT NOT NULL` column to PostgreSQL `polling_station` table schema.

**Files**:
- Schema template/generation logic (find where `CREATE TABLE polling_station` is defined)
- Likely: `src/etl/export.py` or template file

**Actions**:
- Locate PostgreSQL schema generation for `polling_station` table
- Add `code TEXT NOT NULL` after `id UUID PRIMARY KEY`
- Update schema comment to reflect code column
- Regenerate `exports/schema.sql`

**Example**:
```sql
CREATE TABLE IF NOT EXISTS polling_station (
    id UUID PRIMARY KEY,
    code TEXT NOT NULL,
    address TEXT NOT NULL,
    -- ...
);
```

**Validation**:
```bash
grep "code TEXT NOT NULL" exports/schema.sql
# Should find the line
```

**Dependencies**: Task 2 (to ensure DuckDB has data to export)

---

### 4. Update Export Mapping Logic (Column Mapping)
**Effort**: 30 min | **Status**: Pending

Map DuckDB `PollingStationCode` to PostgreSQL `code` in export logic.

**Files**:
- `src/etl/export.py` (find PollingStation export logic)

**Actions**:
- Locate where `PollingStation` table is exported to CSV
- Add column mapping: `PollingStationCode` → `code`
- Ensure column order matches schema (code after id)
- Handle NULL values if present

**Search hints**:
```bash
rg "PollingStation|polling_station" src/etl/export.py
```

**Validation**:
```bash
python -m src.cli export --run-tag test_code
head -5 exports/*_PollingStation.csv
# Should show 'code' column with values like '031', '115', etc.
```

**Dependencies**: Task 3

---

### 5. Add Integration Test (Verification)
**Effort**: 45 min | **Status**: Pending

Create test to verify code column throughout pipeline.

**Files**:
- `tests/integration/test_polling_station_code.py` (new file)

**Actions**:
- Create test that runs mini-pipeline with sample data
- Insert staging data with known `polling_station_code` values
- Run transformation
- Assert `PollingStation.PollingStationCode` contains expected values
- Assert PostgreSQL export includes `code` column
- Verify CSV output has correct values

**Test Structure**:
```python
def test_polling_station_code_preserved():
    # Setup: Create test DB with staging data
    # Act: Run transformation
    # Assert: Code column exists and populated
    # Assert: Export includes code
```

**Validation**:
```bash
pytest tests/integration/test_polling_station_code.py -v
```

**Dependencies**: Tasks 1-4

---

### 6. Update PostgreSQL Import Test (End-to-End)
**Effort**: 30 min | **Status**: Pending

Verify code column works in PostgreSQL import.

**Files**:
- `tests/integration/test_db_setup.py` or similar

**Actions**:
- Add assertion to verify `polling_station.code` column exists in PostgreSQL
- Verify sample records have non-NULL codes
- Test SELECT queries retrieve codes correctly

**Example**:
```python
result = conn.execute("SELECT id, code, address FROM polling_station LIMIT 5")
assert all(row['code'] is not None for row in result)
```

**Validation**:
```bash
pytest tests/integration/test_db_setup.py::test_polling_station_code -v
```

**Dependencies**: Task 5

---

### 7. Run Full Pipeline Test (Regression Check)
**Effort**: 15 min | **Status**: Pending

Verify entire pipeline works with new column.

**Actions**:
- Delete test database: `rm data/oevk.db`
- Run full pipeline: `python -m src.cli run --run-tag $(date +%Y%m%d)`
- Verify all stages complete successfully
- Check exports include code column
- Verify PostgreSQL schema.sql has code column

**Validation**:
```bash
# Check DuckDB
python -c "import duckdb; conn=duckdb.connect('data/oevk.db'); print(conn.execute('SELECT PollingStationCode FROM PollingStation LIMIT 5').fetchdf())"

# Check PostgreSQL schema
grep "code TEXT NOT NULL" exports/schema.sql

# Check CSV export
head -2 exports/*_PollingStation.csv | grep code
```

**Dependencies**: Tasks 1-6

---

### 8. Update Documentation (Optional but Recommended)
**Effort**: 20 min | **Status**: Pending

Document the new column in relevant places.

**Files**:
- `docs/POSTGRESQL_FINAL_SCHEMA.md` (if exists)
- `README.md` (if it documents schema)
- Database ERD or schema docs

**Actions**:
- Add `code` column to polling_station table documentation
- Update any schema diagrams or ERDs
- Add note about the column's purpose and source

**Validation**:
Manual review of documentation

**Dependencies**: Task 7

---

## Parallel Work Opportunities

Tasks 1-2 can be done sequentially (must be in order).
Tasks 3-4 can be done in parallel after Task 2.
Tasks 5-6 can be done in parallel after Task 4.

## Success Criteria Summary

✅ **Done when**:
1. DuckDB `PollingStation` has `PollingStationCode` column
2. PostgreSQL `polling_station` has `code` column
3. Transformation extracts code from staging
4. Export maps code correctly
5. All tests pass (including new integration tests)
6. Full pipeline run produces exports with code column
7. `exports/schema.sql` includes `code TEXT NOT NULL`

## Rollback Plan

If issues arise:
1. Revert changes to transformation logic (Task 2)
2. Revert schema changes (Tasks 1, 3)
3. Remove test files (Tasks 5-6)
4. Schema is backward compatible (only adds column)
