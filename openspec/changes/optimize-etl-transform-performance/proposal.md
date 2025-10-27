# ETL Transform Performance Optimization Proposal

## Why

The current address transformation process has degraded from ~45 seconds per chunk to **3 minutes per chunk**, causing the full pipeline to take 3+ hours instead of the expected 30 minutes. With 67 chunks of 50,000 addresses each (3.3M total), this creates a severe bottleneck that makes iterative development and testing impractical.

**Root Causes Identified:**
- Heavy SQL complexity with nested window functions and string operations
- Python UDF overhead (`trim_leading_zeros()`) called millions of times
- MD5 hashing performed multiple times per row in DuckDB
- Parallel processing overhead with 4 separate DB connections
- Progress bar overhead in tight processing loops
- Inefficient chunk processing pattern (pull from DB → process → write back)

**Impact:**
- Development cycles take hours instead of minutes
- Pipeline exceeds NFR-002 performance requirement (30 minutes max)
- Resource contention when multiple processes run simultaneously
- Poor developer experience with slow feedback loops

This optimization addresses the core transformation bottleneck using Polars for in-memory processing while maintaining DuckDB as the authoritative data store for downstream stages.

## What Changes

- **MODIFIED CAPABILITY**: `etl-transform` - Address transformation using Polars-based chunked processing
- Replace SQL-heavy transformation with Polars DataFrame operations
- Move hash calculations from DuckDB MD5 to Python xxhash64 (3-5x faster)
- Move string operations (`trim_leading_zeros`) from Python UDF to Polars expressions
- Implement vectorized batch processing: fetch → transform in Polars → persist to DuckDB
- Increase default chunk size from 50,000 to 100,000 rows (better memory/performance balance)
- Optimize progress bar updates (batch updates, disable individual chunk bars in parallel mode)
- Maintain DuckDB as storage layer for downstream stages (export, geocoding, deduplication)
- Add performance benchmarking and timing metrics for optimization validation

### Performance Targets

- **Chunk processing time**: 45-60 seconds per chunk (down from 180 seconds)
- **Total pipeline time**: <30 minutes for 3.3M addresses (meets NFR-002)
- **Memory usage**: <1GB peak (stable throughout processing)
- **Throughput**: >1,850 addresses/second (up from ~280 addresses/second)

### Implementation Strategy

**Quick Wins (Immediate Implementation):**
1. Increase chunk size to 100,000 rows
2. Disable individual chunk progress bars in parallel mode
3. Batch progress bar updates (every 10 chunks instead of every chunk)

**Core Optimization (Polars-based Processing):**
1. Fetch staging data chunks into Polars DataFrame
2. Apply transformations using Polars expressions (vectorized):
   - Hash ID generation with xxhash64
   - String normalization and trimming
   - Address component formatting
   - Foreign key hash calculations
3. Persist transformed DataFrame to DuckDB Address table
4. DuckDB remains source of truth for downstream stages

**Backward Compatibility:**
- Keep SQL-based implementation as fallback via `--legacy-transform` flag
- Maintain identical output schema and data quality
- No changes to downstream stages (export, geocoding, deduplication)

## Impact

### Affected Specs
- **MODIFIED**: `specs/etl-transform/spec.md` - Address transformation performance requirements
- **MODIFIED**: NFR-002 compliance (processing time targets)

### Affected Code
- `src/etl/transform_optimized.py` - MODIFIED: Replace `transform_addresses_optimized()` and `transform_addresses_parallel()` with Polars-based implementation
- `src/etl/transform_optimized.py` - MODIFIED: Update `process_chunk_parallel()` to use Polars processing
- `src/etl/hashing.py` - MODIFIED: Add Polars-compatible hash functions using xxhash64
- `src/utils/config.py` - MODIFIED: Add configuration for chunk size and processing mode
- `tests/integration/test_transform_performance.py` - NEW: Performance benchmarks and regression tests

### Performance Impact
- **First run**: 25-30 minutes for 3.3M addresses (down from 180+ minutes)
- **Memory overhead**: Minimal (<1GB peak vs current ~34MB - acceptable tradeoff)
- **Chunk size increase**: 50k → 100k rows (better batch efficiency)
- **Throughput improvement**: ~6.5x faster (280 → 1,850 addresses/second)

### Breaking Changes
None. Output schema, data quality, and deterministic hashing remain identical. Legacy SQL-based implementation available via `--legacy-transform` flag.

### Dependencies
- Polars 0.20.0+ (already in requirements)
- xxhash 3.4.0+ (already in requirements)
- No new external dependencies required

### Success Criteria
- **Performance**: Process 3.3M addresses in ≤30 minutes (NFR-002 compliance)
- **Quality**: Identical output schema and hash IDs compared to SQL implementation
- **Memory**: Peak memory usage ≤2GB during transformation
- **Reliability**: Zero data loss, 100% FK constraint satisfaction
- **Maintainability**: Code complexity reduced (fewer SQL CTEs, clearer Polars expressions)

### Migration Path
1. Implement Polars-based processing with feature flag (`--use-polars-transform`, default: true)
2. Add integration tests comparing SQL vs Polars output (hash IDs must match)
3. Run parallel validation: both implementations on same dataset
4. Enable Polars by default after validation passes
5. Deprecate SQL implementation in future release (keep for 1-2 releases)
6. Remove SQL implementation after proven stability

### Rollback Plan
- Use `--legacy-transform` flag to revert to SQL-based implementation
- No data migration required (output schema identical)
- Configuration change only (no code deployment)
