# Design: Cleansed Full Address Deduplication

## Context

The OEVK data processing pipeline currently implements basic address deduplication using the `AddressDeduplicator` class in `src/etl/deduplicate.py`. However, the document `docs/004_REMOVE_DUPLICATED_ADDRESSES.md` specifies comprehensive cleansing rules that must be applied consistently to ensure accurate duplicate detection.

### Current Implementation State

**What exists:**
- `AddressDeduplicator` class with `_format_full_address()`, `_clean_house_number()`, `_to_roman_numeral()` methods (deduplicate.py:440-530)
- Canonical ID generation based on formatted full address (deduplicate.py:507-530)
- Database schema with deduplication tables: `CanonicalAddress`, `AddressMapping`, `AddressPollingStations`, `AddressPIRCodes`, `DeduplicationReport`
- UUID v3 export infrastructure with `OEVK_NAMESPACE` (export.py, export_canonical_v2.py)
- Data models for deduplication entities (models.py)

**What needs enhancement:**
- Verification that all cleansing rules from `004_REMOVE_DUPLICATED_ADDRESSES.md` are correctly implemented
- Settlement-partitioned export for both canonical and original addresses
- Comprehensive deduplication reporting with settlement-level breakdown
- Contract tests to validate cleansing rule correctness

### Stakeholders

- **Data Engineers**: Need reliable, deterministic deduplication
- **Analysts**: Need settlement-partitioned exports for regional analysis
- **QA/Auditors**: Need comprehensive deduplication reports for verification
- **Downstream Systems**: Need UUID v3 deterministic identifiers for data integration

## Goals / Non-Goals

### Goals

1. **Accurate Deduplication**: Apply all Hungarian address formatting rules consistently to detect true duplicates
2. **Settlement Partitioning**: Enable efficient regional analysis with per-settlement export files
3. **Deterministic IDs**: Use UUID v3 for reproducible entity identification across pipeline runs
4. **Comprehensive Reporting**: Provide detailed deduplication statistics for audit and verification
5. **Performance**: Maintain NFR-002 compliance (< 30 minutes for 3M+ addresses)

### Non-Goals

1. **Fuzzy Matching**: No probabilistic or similarity-based duplicate detection (exact match only)
2. **Manual Overrides**: No user interface for manual duplicate resolution (future enhancement)
3. **Address Geocoding**: No geospatial validation or coordinate generation
4. **Schema Changes**: Database schema already supports deduplication (no modifications needed)

## Decisions

### Decision 1: Cleansing Before Hashing Strategy

**Choice**: Apply cleansing transformations to create `full_address` field, then hash the normalized uppercase version for canonical ID generation.

**Rationale**:
- **Determinism**: Same input components → same cleansed address → same canonical ID
- **Visibility**: `full_address` field stores human-readable formatted address for debugging
- **Separation of Concerns**: Cleansing logic isolated in formatting methods, hashing logic in ID generation

**Implementation**:
```python
# In _generate_canonical_ids():
formatted_df = addresses_df.with_columns(
    pl.struct(["street_name", "street_type", "house_number", "building", "staircase"])
    .map_elements(lambda row: format_address_udf(...), return_dtype=pl.Utf8)
    .alias("full_address")
)

# Hash normalized full address: county_code | settlement_name | FULL_ADDRESS (uppercased)
canonical_id = hash(county_code + "|" + settlement_name + "|" + full_address.upper())
```

**Component Exclusions**:
- **Gate Code ("Kapukód")**: The source data contains a gate code column. Per document requirements (`004_REMOVE_DUPLICATED_ADDRESSES.md`), only street name, street type, house number, building, and staircase are used for deduplication. Gate codes are preserved in the database but do not affect canonical ID generation.

**Edge Case Handling**:
- **Range with slash** (e.g., "000001-00005/D"): The `_clean_house_number()` method splits on "-" first, producing ["000001", "00005/D"], then cleans each part to ["1", "5/D"], and rejoins to "1-5/D". This correctly preserves the slash as part of the second range value.

**Alternatives Considered**:
- ❌ **Hash raw components separately**: Would miss duplicates with different component distributions (e.g., "000001/D" vs "000001" + building="D")
- ❌ **Hash before cleansing**: Would treat "000001" and "1" as different addresses
- ❌ **Include gate code in hash**: Would incorrectly treat same address with different gate codes as separate addresses

### Decision 2: Settlement-Partitioned Export Architecture

**Choice**: Create unified directory structure with both canonical and original addresses partitioned by settlement.

**Structure**:
```
{export_dir}/
└── {run_tag}_Address/
    ├── Address_001_Budapest.csv           (canonical addresses)
    ├── Address_051_Szeged.csv              (canonical addresses)
    ├── OriginalAddress_001_Budapest.csv    (original addresses)
    └── OriginalAddress_051_Szeged.csv      (original addresses)
```

**Rationale**:
- **Unified Location**: Both file types in same directory simplifies access and distribution
- **Clear Naming**: `Address_` vs `OriginalAddress_` prefix makes file type obvious
- **Settlement Grouping**: Enables efficient regional analysis (e.g., analyze only Budapest)
- **Consistent Pattern**: Matches existing export conventions in codebase

**Implementation**:
```python
# In export_canonical_v2.py:
address_dir = os.path.join(export_dir, f"{run_tag}_Address")

# Canonical addresses
filename = f"Address_{settlement_code}_{safe_name}.csv"

# Original addresses (separate export function)
filename = f"OriginalAddress_{settlement_code}_{safe_name}.csv"
```

**Alternatives Considered**:
- ❌ **Separate directories**: `{run_tag}_CanonicalAddress/` and `{run_tag}_OriginalAddress/` - More complex distribution
- ❌ **Single file per settlement**: Combine canonical and original in one CSV - Harder to compare and analyze
- ❌ **No partitioning**: Single large file - Inefficient for regional analysis (3.3M+ rows)

### Decision 3: UUID v3 Namespace Strategy

**Choice**: Use `uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")` as namespace for all entity UUIDs.

**Rationale**:
- **DNS Namespace**: Standard UUID v3 approach for domain-based namespaces
- **Determinism**: Same entity ID → same UUID v3 across exports
- **Global Uniqueness**: `oevk.hu` domain provides collision avoidance
- **Consistency**: Already implemented in `export.py` and `export_canonical_v2.py`

**Implementation**:
```python
OEVK_NAMESPACE = uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")

def to_uuid3(value):
    """Convert internal hash ID to UUID v3."""
    if value is None or value == "":
        return None
    return str(uuid.uuid3(OEVK_NAMESPACE, str(value)))
```

**Alternatives Considered**:
- ❌ **UUID v4 (random)**: Non-deterministic, breaks idempotency requirement
- ❌ **UUID v5 (SHA-1)**: SHA-1 deprecation concerns, v3 (MD5) sufficient for non-cryptographic use
- ❌ **Custom namespace UUID**: Less standard, harder to document and explain

### Decision 4: Deduplication Reporting Granularity

**Choice**: Generate both pipeline-level summary and settlement-level breakdown in deduplication report.

**Report Structure**:
```json
{
  "id": "dedup_20250113_1430",
  "run_id": "20250113-1430",
  "total_addresses": 3336202,
  "duplicates_found": 13084,
  "canonical_addresses_created": 3323118,
  "deduplication_rate": 0.39,
  "processing_time_ms": 2500,
  "status": "completed",
  "settlement_breakdown": [
    {
      "settlement_code": "001",
      "settlement_name": "Budapest",
      "original_addresses": 450000,
      "canonical_addresses": 448500,
      "duplicates_found": 1500,
      "deduplication_rate": 0.33
    }
  ]
}
```

**Rationale**:
- **Audit Trail**: Pipeline-level metrics for overall verification
- **Regional Insights**: Settlement-level data helps identify data quality issues in specific regions
- **Performance Tracking**: Processing time enables optimization monitoring
- **Error Handling**: Status field captures partial failures for debugging

**Implementation**:
```python
# In generate_deduplication_report():
# 1. Calculate pipeline-level metrics
total_addresses = len(addresses_df)
canonical_count = len(canonical_addresses)
deduplication_rate = (duplicates_found / total_addresses) * 100

# 2. Calculate settlement-level breakdown
settlement_stats = addresses_df.group_by("settlement_code", "settlement_name").agg([
    pl.count().alias("original_addresses"),
    pl.col("canonical_address_id").n_unique().alias("canonical_addresses")
])
```

**Alternatives Considered**:
- ❌ **Pipeline-level only**: Loses regional insights, harder to debug data quality issues
- ❌ **Street-level breakdown**: Too granular (122K+ public spaces), unwieldy report size
- ❌ **No reporting**: Loses audit trail and verification capability

### Decision 5: Validation Strategy

**Choice**: Three-tier validation approach: Contract tests → Integration tests → Data quality checks.

**Tier 1 - Contract Tests** (TDD, run first):
```python
def test_cleansing_deterministic():
    """Same input → same cleansed output."""
    address = create_address("000001", "D", "")
    result1 = cleanse(address)
    result2 = cleanse(address)
    assert result1 == result2

def test_duplicate_detection_example_from_doc():
    """Körtöltés utca examples from 004_REMOVE_DUPLICATED_ADDRESSES.md."""
    addresses = [
        ("000001", "D", ""),
        ("000001", "", "D"),
        ("000001/D", "", "")
    ]
    canonical_ids = [get_canonical_id(a) for a in addresses]
    assert len(set(canonical_ids)) == 1  # All same canonical ID
```

**Tier 2 - Integration Tests**:
```python
def test_end_to_end_deduplication(temp_db):
    """Full deduplication pipeline with sample data."""
    # Insert sample data
    # Run deduplication
    # Verify relationships preserved
    # Check export files generated
```

**Tier 3 - Data Quality Checks**:
```python
def validate_deduplication_results(report):
    """Post-processing validation."""
    assert report.deduplication_rate < 5.0  # < 5% duplicates expected
    assert report.status == "completed"
    assert all_relationships_preserved()
```

**Rationale**:
- **TDD Approach**: Contract tests define behavior before implementation
- **Incremental Validation**: Catch issues at appropriate levels (unit → integration → system)
- **Example-Driven**: Use real examples from documentation as test fixtures
- **Performance Baseline**: Integration tests establish performance benchmarks

## Risks / Trade-offs

### Risk 1: Cleansing Rule Complexity

**Risk**: Hungarian address formatting has many edge cases (ranges, slashes, buildings, staircases) - risk of missing rules or incorrect implementation.

**Mitigation**:
- Extract all examples from `004_REMOVE_DUPLICATED_ADDRESSES.md` as contract test fixtures
- Create exhaustive test matrix covering all combinations:
  - House number types: simple, range, slash
  - Component presence: no building/staircase, building only, staircase only, both
  - Value types: numeric, alphabetic, mixed
- Manual verification of formatted addresses against document examples
- Code review with domain experts familiar with Hungarian addresses

**Residual Risk**: Low (extensive testing and examples)

### Risk 2: Performance Degradation

**Risk**: Additional cleansing steps and settlement-partitioned export might increase processing time beyond NFR-002 threshold (30 minutes).

**Current Baseline**: ~2.5 minutes for 3.3M addresses (92% faster than requirement)

**Mitigation**:
- Cleansing already implemented in `_format_full_address()` (no additional overhead)
- Settlement partitioning uses `GROUP BY` (efficient in DuckDB)
- Parallel processing with chunking already in place (100K rows/chunk, 4 workers)
- Export I/O can be parallelized per settlement if needed

**Residual Risk**: Very Low (significant performance margin, no algorithmic changes)

### Risk 3: UUID v3 Namespace Collision

**Risk**: Using DNS namespace with "oevk.hu" could theoretically collide with other systems using the same namespace and entity IDs.

**Mitigation**:
- Collision probability is cryptographically low (2^-64 for MD5-based UUID v3)
- OEVK domain is specific to Hungarian electoral data (unlikely external usage)
- Entity IDs are already xxhash64 (64-bit), providing strong uniqueness
- Export UUIDs are for external consumption only (internal system uses hash IDs)

**Residual Risk**: Negligible (standard UUID v3 usage, domain-specific namespace)

### Trade-off 1: Storage vs Query Performance

**Choice**: Store both `full_address` (formatted string) and components (street_name, house_number, etc.) in `CanonicalAddress` table.

**Pros**:
- Formatted address readily available for exports (no runtime formatting)
- Components available for filtering and analysis queries
- Debugging easier (can see both formats)

**Cons**:
- Slight storage increase (~50 bytes/row × 3.3M rows ≈ 165MB)
- Redundancy between components and formatted string

**Decision**: Accept storage trade-off for query performance and debugging clarity (165MB is negligible on modern systems).

### Trade-off 2: Aggregated Relationships vs Junction Tables

**Choice**: Store polling stations and PIR codes as comma-separated lists in canonical address export instead of separate relationship files.

**Pros**:
- Single CSV file per settlement (simpler distribution)
- Easier for analysts to work with (no JOIN required)
- Matches existing export patterns in codebase

**Cons**:
- Not normalized (violates 1NF)
- Harder to query individual relationships
- Larger file sizes if many relationships per address

**Decision**: Use aggregated format for exports (analyst convenience), but maintain normalized junction tables in database (AddressPollingStations, AddressPIRCodes) for internal use.

## Migration Plan

### Phase 1: Validation (No Code Changes)

1. Run contract tests against existing `_format_full_address()` implementation
2. Compare test results with examples in `004_REMOVE_DUPLICATED_ADDRESSES.md`
3. Document any discrepancies or missing test coverage
4. **Gate**: All contract tests pass or issues documented

### Phase 2: Cleansing Enhancement (If Needed)

1. Fix any cleansing rule discrepancies found in Phase 1
2. Add missing edge case handling (e.g., special characters in settlement names)
3. Run full test suite (contract + integration tests)
4. **Gate**: 100% contract test pass rate

### Phase 3: Settlement-Partitioned Export

1. Extend `export_canonical_v2.py` to support settlement partitioning
2. Add original address export function with same partitioning logic
3. Update CLI to expose export options (`--export-original-addresses` flag)
4. Test with sample data (1-2 settlements)
5. **Gate**: Both canonical and original exports generated correctly

### Phase 4: Deduplication Reporting Enhancement

1. Extend `generate_deduplication_report()` to calculate settlement breakdown
2. Add JSON export function for report serialization
3. Integrate report generation into pipeline
4. **Gate**: Report generated with all required metrics

### Phase 5: Full Pipeline Integration

1. Run complete ETL pipeline with deduplication enabled on full dataset
2. Verify performance meets NFR-002 (< 30 minutes)
3. Validate exports (file counts, sizes, UUID formats)
4. Compare deduplication rate with expected value (~0.39% from docs)
5. **Gate**: Full pipeline completes successfully with valid outputs

### Rollback Plan

If issues arise in production:

1. **Immediate**: Disable deduplication with `--no-deduplication` CLI flag
2. **Fallback**: Revert to previous pipeline version (no schema changes required)
3. **Investigation**: Analyze deduplication report and export files to identify root cause
4. **Fix-Forward**: Apply fixes in development environment, re-run validation phases

**Risk**: Low (additive functionality, no breaking changes, deduplication can be disabled)

## Open Questions

### Q1: Settlement Name Sanitization for Filenames

**Question**: How should special characters in settlement names be handled for filename generation?

**Options**:
- Replace spaces/slashes with underscores: `Csorna-Pusztacsalád` → `Csorna-Pusztacsalád` (keep hyphen), `Aba/Kerülés` → `Aba_Kerülés` (replace slash)
- URL encoding: `Aba/Kerülés` → `Aba%2FKerülés`
- Transliteration: Convert Hungarian characters to ASCII

**Recommendation**: Replace slashes and backslashes with underscores, preserve hyphens and Hungarian characters (UTF-8 filenames supported on modern systems).

**Implementation**:
```python
safe_name = settlement_name.replace("/", "_").replace("\\", "_")
```

**Status**: ✅ Already implemented in `export_canonical_v2.py:83`

### Q2: Deduplication Rate Variance Threshold

**Question**: What variance in deduplication rate should trigger a warning or error?

**Context**: Document mentions ~0.39% deduplication rate (13,084 duplicates from 3,336,202 addresses). What if actual rate differs significantly?

**Recommendation**: Add validation check with thresholds:
- **Expected**: 0.2% - 1.0% (normal variance)
- **Warning**: 1.0% - 3.0% (investigate potential data quality issues)
- **Error**: > 3.0% (likely implementation bug or data corruption)

**Implementation**:
```python
if deduplication_rate > 3.0:
    raise DataValidationError(f"Deduplication rate {deduplication_rate}% exceeds threshold")
elif deduplication_rate > 1.0:
    logger.warning(f"Deduplication rate {deduplication_rate}% higher than expected")
```

**Status**: ⏳ Needs decision before implementation

### Q3: Export File Size Limits

**Question**: Should large settlement exports be split into multiple files?

**Context**: Budapest has ~450K addresses. Single CSV would be ~50MB (manageable). But should we set a limit?

**Recommendation**: No splitting needed (50MB is acceptable for modern systems). Re-evaluate if any settlement exceeds 100MB (~1M addresses).

**Status**: ⏳ Monitor in production, no immediate action required

## Success Metrics

### Functional Metrics

- ✅ **Cleansing Accuracy**: 100% of contract tests pass
- ✅ **Duplicate Detection**: Expected duplicates from `004_REMOVE_DUPLICATED_ADDRESSES.md` correctly identified
- ✅ **Export Completeness**: All settlements have both canonical and original CSV files
- ✅ **UUID Determinism**: Same entity ID produces same UUID v3 across exports
- ✅ **Relationship Preservation**: 100% of polling stations and PIR codes preserved

### Performance Metrics

- ✅ **Processing Time**: < 30 minutes for 3.3M addresses (NFR-002)
- ✅ **Memory Usage**: Stable throughout pipeline (< 2GB)
- ✅ **Export Time**: < 5 minutes for all settlement partitions

### Quality Metrics

- ✅ **Deduplication Rate**: 0.2% - 1.0% (within expected range)
- ✅ **Data Integrity**: 100% referential integrity in database
- ✅ **Report Accuracy**: All metrics match validation queries

## References

- `docs/004_REMOVE_DUPLICATED_ADDRESSES.md` - Original requirements document
- `src/etl/deduplicate.py:440-530` - Current cleansing implementation
- `src/etl/export_canonical_v2.py` - UUID v3 export infrastructure
- `src/database/schema.sql` - Deduplication table definitions
- `openspec/project.md` - Project conventions and patterns
