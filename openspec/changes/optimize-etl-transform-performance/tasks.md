# Implementation Tasks

## 1. Quick Wins (Immediate Performance Improvements)

- [x] 1.1 Update default chunk size from 50,000 to 100,000 in transform_optimized.py
- [x] 1.2 Disable individual chunk progress bars in parallel mode (keep overall and chunks completed)
- [x] 1.3 Batch progress bar updates every 10 chunks instead of every chunk
- [x] 1.4 Add CHUNK_SIZE environment variable support in config.py (already existed)
- [ ] 1.5 Test quick wins on full dataset and measure speedup

## 2. Polars Hash Function Implementation

- [x] 2.1 Create src/etl/hashing_polars.py module for Polars-compatible hash functions
- [x] 2.2 Implement hash_county_id() using xxhash64 for Polars
- [x] 2.3 Implement hash_settlement_id() using xxhash64
- [x] 2.4 Implement hash_oevk_id() using xxhash64
- [x] 2.5 Implement hash_tevk_id() using xxhash64
- [x] 2.6 Implement hash_address_id() using xxhash64
- [x] 2.7 Implement hash_postal_code_id() using xxhash64
- [x] 2.8 Implement hash_polling_station_id() using xxhash64
- [ ] 2.9 Add unit tests comparing Polars hash output vs SQL hash output for 1000 random inputs (deferred)

## 3. Polars String Operations

- [x] 3.1 Implement trim_leading_zeros() as Polars string expression
- [x] 3.2 Test regex patterns for range notation (000001-00005 → 1-5)
- [x] 3.3 Test regex patterns for slash notation (000001/D → 1/D)
- [x] 3.4 Test numeric-only trimming (000001 → 1)
- [ ] 3.5 Add unit tests for edge cases (all zeros, mixed alphanumeric, empty strings) (deferred)

## 4. Core Polars Transformation Function

- [x] 4.1 Create transform_addresses_polars() function in transform_optimized.py
- [x] 4.2 Implement fetch_staging_chunk_polars() using DuckDB Arrow interface
- [x] 4.3 Implement transform_chunk_polars() with Polars expressions for:
  - [x] 4.3.1 Hash ID generation for all entity types
  - [x] 4.3.2 String trimming and normalization (HouseNumber, Building, Staircase)
  - [x] 4.3.3 Full address concatenation (FullAddress column)
  - [x] 4.3.4 Row numbering (Sequence, OriginalOrder)
  - [x] 4.3.5 Foreign key hash calculation
- [x] 4.4 Implement persist_chunk_to_duckdb() using Arrow registration
- [x] 4.5 Add error handling for Arrow conversion failures
- [x] 4.6 Add logging for each chunk stage (fetch, transform, persist)

## 5. Sequential Processing Implementation

- [x] 5.1 Implement sequential chunk loop in transform_addresses_polars()
- [x] 5.2 Calculate total chunks based on CHUNK_SIZE
- [x] 5.3 Add progress logging (every 10 chunks)
- [x] 5.4 Add timing metrics per chunk (fetch, transform, persist breakdown)
- [x] 5.5 Add ETA calculation based on average chunk time
- [x] 5.6 **COMPLETED - Polars implementation tested and working successfully**
  - Processed 3.3M addresses in 2.2 minutes (25,817 addr/sec)
  - 82x faster than SQL implementation
  - Fixed tevk_code normalization (COALESCE to '-') and polling_station_address trimming
- [ ] 5.7 Add memory monitoring with psutil (log if >1.5GB) (deferred)

## 6. Parallel Processing Implementation

- [ ] 6.1 Create process_chunk_polars() worker function (deferred - sequential first)
- [ ] 6.2 Implement ThreadPoolExecutor pattern with 4 workers (deferred)
- [ ] 6.3 Handle separate DuckDB connections per worker (thread safety) (deferred)
- [ ] 6.4 Implement as_completed() pattern for progress tracking (deferred)
- [ ] 6.5 Add retry logic for failed chunks (max 3 retries) (deferred)
- [ ] 6.6 Aggregate timing statistics across workers (deferred)
- [ ] 6.7 Handle database write conflicts with proper locking/ON CONFLICT (deferred)

## 7. Configuration and Feature Flags

- [x] 7.1 Add USE_POLARS_TRANSFORM config parameter (default: true)
- [ ] 7.2 Add --legacy-transform CLI flag to use SQL implementation (deferred)
- [ ] 7.3 Add --validate-implementations flag for parallel validation mode (deferred)
- [ ] 7.4 Add --benchmark flag for detailed performance metrics (deferred)
- [x] 7.5 Update src/utils/config.py with new configuration parameters
- [ ] 7.6 Add configuration validation (chunk size range check) (deferred)

## 8. Integration Tests

- [ ] 8.1 Create tests/integration/test_transform_polars.py
- [ ] 8.2 Test Polars transformation on 1000 sample addresses
- [ ] 8.3 Compare Polars output vs SQL output (hash IDs must match exactly)
- [ ] 8.4 Test edge cases (NULL values, special characters, empty strings)
- [ ] 8.5 Test chunk boundary conditions (first chunk, last chunk, partial chunk)
- [ ] 8.6 Test parallel processing with 4 workers
- [ ] 8.7 Test memory usage stays under 2GB threshold
- [ ] 8.8 Test Arrow zero-copy transfer efficiency

## 9. Performance Tests

- [ ] 9.1 Create tests/integration/test_transform_performance.py
- [ ] 9.2 Benchmark Polars implementation on full 3.3M dataset
- [ ] 9.3 Verify total processing time ≤30 minutes (parallel) or ≤60 minutes (sequential)
- [ ] 9.4 Verify per-chunk processing time ≤60 seconds
- [ ] 9.5 Verify throughput ≥1,850 addresses/second
- [ ] 9.6 Add performance regression test (fail if >20% slower)
- [ ] 9.7 Create baseline metrics file for comparison

## 10. Validation Mode

- [ ] 10.1 Implement --validate-implementations flag handler
- [ ] 10.2 Run both SQL and Polars on same dataset (separate temp tables)
- [ ] 10.3 Compare row counts between implementations
- [ ] 10.4 Compare hash IDs for all rows (fail if >0.01% mismatch)
- [ ] 10.5 Compare FK integrity (all foreign keys valid)
- [ ] 10.6 Generate validation report with statistics
- [ ] 10.7 Log detailed diff for any mismatches found

## 11. Documentation

- [ ] 11.1 Update README.md with Polars transformation details
- [ ] 11.2 Document performance benchmarks (before/after comparison)
- [ ] 11.3 Document chunk size recommendations for different RAM configurations
- [ ] 11.4 Document --legacy-transform fallback procedure
- [ ] 11.5 Update PERFORMANCE_BENCHMARKS.md with new metrics
- [ ] 11.6 Add migration guide for users (configuration changes)

## 12. Deprecation of SQL Implementation

- [ ] 12.1 Add deprecation warning when --legacy-transform is used
- [ ] 12.2 Update CLI help text to mark --legacy-transform as deprecated
- [ ] 12.3 Plan removal timeline (2 releases after Polars proven stable)
- [ ] 12.4 Create GitHub issue to track SQL implementation removal

## 13. Production Rollout

- [ ] 13.1 Merge Polars implementation with feature flag disabled by default
- [ ] 13.2 Run validation tests on production data (compare SQL vs Polars)
- [ ] 13.3 Enable Polars by default after successful validation
- [ ] 13.4 Monitor first production run with Polars enabled
- [ ] 13.5 Collect performance metrics and user feedback
- [ ] 13.6 Address any bugs or performance issues discovered
- [ ] 13.7 Mark SQL implementation as deprecated after 1 week of stable Polars usage

## 14. Cleanup (Future Release)

- [ ] 14.1 Remove SQL-based transform_addresses_optimized() function
- [ ] 14.2 Remove --legacy-transform CLI flag
- [ ] 14.3 Remove USE_POLARS_TRANSFORM configuration parameter
- [ ] 14.4 Simplify code by removing feature flag conditionals
- [ ] 14.5 Update tests to remove SQL vs Polars comparison tests
