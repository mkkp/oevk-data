# Proposal: Add PollingStationCode Column to PostgreSQL Schema

**Change ID**: `add-polling-station-code`
**Type**: Schema Enhancement
**Impact**: Low (additive change, no breaking changes)
**Status**: Implemented

## Problem Statement

The source data (`staging_korzet` table) contains a `polling_station_code` column that uniquely identifies each polling station within its electoral context. However, this code is currently **not extracted** into the `PollingStation` table during transformation, resulting in data loss.

**Current State**:
- `staging_korzet` has `polling_station_code` column
- `PollingStation` DuckDB table has no code column
- `polling_station` PostgreSQL table has no code column
- The code is used in hash ID generation (line 67 comment in schema.sql) but not stored

**Evidence**:
```sql
-- From exports/schema.sql line 67:
id UUID PRIMARY KEY, -- md5(code|code|oevk|tevk|address)
-- But no 'code' column exists in the table
```

```python
# From src/etl/transform_optimized.py lines 433-446:
INSERT INTO PollingStation (
    ID, PollingStationAddress, SettlementIndividualElectoralDistrict_ID,
    County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID
)
-- polling_station_code is NOT selected or inserted
```

## Proposed Solution

Add `polling_station_code` column to both DuckDB and PostgreSQL `polling_station` tables to preserve this authoritative identifier from the source data.

### Changes Required

1. **DuckDB Schema**: Add `PollingStationCode VARCHAR` column
2. **PostgreSQL Schema**: Add `code TEXT NOT NULL` column
3. **Transform Logic**: Extract `polling_station_code` during transformation
4. **Export Logic**: Map `PollingStationCode` → `code` for PostgreSQL compatibility

### Naming Convention

- **DuckDB**: `PollingStationCode` (PascalCase, matches existing convention)
- **PostgreSQL**: `code` (snake_case, matches PostgreSQL naming convention from project.md)

## Benefits

1. **Data Completeness**: Preserves all source data without loss
2. **Analytical Value**: Enables queries by polling station code
3. **Referential Integrity**: Matches source system identifiers
4. **Debugging**: Facilitates data lineage tracking
5. **No Breaking Changes**: Additive-only, backward compatible

## Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing queries break | Low | Low | Column is additive, no existing columns removed |
| NULL values in data | None | N/A | Data analysis confirms 0 NULL values; NOT NULL constraint safe |
| Export performance degradation | Very Low | Very Low | Single TEXT column adds negligible overhead |

## Alternatives Considered

1. **Status Quo**: Keep current schema
   - ❌ Loses source data
   - ❌ Breaks data lineage

2. **Composite Key Instead of Code Column**: Use county+settlement+tevk+oevk as identifier
   - ❌ More complex
   - ❌ Still loses the authoritative code from source

3. **Proposed Solution**: Add code column
   - ✅ Simple and complete
   - ✅ Preserves all data
   - ✅ Backward compatible

## Data Analysis Results

Analysis of `staging_korzet.polling_station_code` (run_tag: 20251105_033400, 3.3M records):

1. **Nullability**: ✅ **RESOLVED** - NO NULL values found
   - 0 out of 3,336,202 records have NULL or empty codes (0.00%)
   - **Decision**: Use `NOT NULL` constraint safely

2. **Uniqueness**: ✅ **RESOLVED** - NOT unique globally
   - 255 distinct codes across 8,547 distinct polling stations
   - Codes are reused across different counties/settlements
   - **Decision**: Code is NOT a primary key; ID hash remains `hash_polling_station_id(county, settlement, oevk, tevk, address)`

3. **Format**: ✅ **RESOLVED** - Consistent 3-digit numeric format
   - All codes are exactly 3 characters long
   - All codes are numeric only (0-9)
   - Zero-padded format: `001`, `002`, ..., `255`
   - **Decision**: Could add `CHECK (code ~ '^[0-9]{3}$')` constraint for PostgreSQL (optional)

## Implementation Phases

1. **Phase 1**: Add column to DuckDB schema and transform logic
2. **Phase 2**: Add column to PostgreSQL export schema
3. **Phase 3**: Update export mapping logic
4. **Phase 4**: Verify data in exports and tests

## Success Criteria

- [x] `PollingStation` table in DuckDB has `PollingStationCode` column
- [x] `polling_station` table in PostgreSQL has `code` column
- [x] Transform logic extracts `polling_station_code` from staging
- [x] Export correctly maps DuckDB → PostgreSQL naming
- [x] All existing tests pass (PostgreSQL schema test updated and passing)
- [x] Verified code column in generated PostgreSQL schema

## Related Capabilities

- **Capability**: Polling Station Data Model
- **Specification**: `openspec/changes/add-polling-station-code/specs/polling-station-code/spec.md`
