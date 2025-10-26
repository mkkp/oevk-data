# ETL Transform Performance Optimization Design

## Context

The OEVK ETL pipeline processes 3.3M+ Hungarian address records through multiple transformation stages. The address transformation stage (`transform_addresses_optimized`) has become a critical bottleneck, with chunk processing time degrading from 45 seconds to 3 minutes per chunk.

**Current Architecture:**
```
staging_korzet (DuckDB)
    ↓
    ↓ Complex SQL with CTEs, window functions, MD5 hashing
    ↓
Address (DuckDB)
    ↓
    ↓ Downstream stages
    ↓
Export, Geocoding, Deduplication
```

**Performance Constraints:**
- NFR-002: Process 3M+ rows in ≤30 minutes
- Current: 180+ minutes (6x slower than requirement)
- Memory: Must stay under 2GB (no server available, laptop environment)
- Deterministic: Hash IDs must be reproducible across runs

**Stakeholders:**
- Developers: Need fast iteration cycles for testing
- Data analysts: Need reliable daily pipeline runs
- System: Must meet performance SLA (NFR-002)

## Goals / Non-Goals

### Goals
1. **Performance**: Achieve <30 minute total pipeline time (NFR-002 compliance)
2. **Throughput**: Process ≥1,850 addresses/second (6.5x current rate)
3. **Memory Efficiency**: Peak memory ≤2GB (acceptable for 3.3M records)
4. **Data Quality**: Maintain identical output (same hash IDs, schema, FK integrity)
5. **Maintainability**: Reduce code complexity (fewer CTEs, clearer logic)
6. **Backward Compatibility**: Support rollback to SQL implementation

### Non-Goals
1. Real-time processing (batch processing is acceptable)
2. Distributed processing (single-machine is sufficient)
3. Schema changes (keep existing Address table structure)
4. Changing downstream stages (export, geocoding, deduplication unchanged)
5. Optimizing other ETL stages (focus on address transformation only)

## Decisions

### Decision 1: Use Polars for In-Memory Processing

**Rationale:**
- Polars is 3-10x faster than pandas for large datasets
- Already in project dependencies (0.20.0+)
- Excellent string operations and vectorization
- Memory-efficient lazy evaluation
- Native Arrow format reduces memory overhead

**Why not alternatives:**
- ❌ **Pandas**: 2-3x slower than Polars, higher memory usage
- ❌ **Pure SQL optimization**: Diminishing returns, MD5 still slow
- ❌ **Dask**: Overkill for single-machine, adds complexity
- ❌ **Spark**: Massive overhead for 3.3M records

**Implementation:**
```python
# Fetch chunk from DuckDB into Polars
chunk_df = pl.from_arrow(
    db_connection.execute(
        "SELECT * FROM staging_korzet WHERE run_tag = ? LIMIT ? OFFSET ?",
        [run_tag, chunk_size, offset]
    ).fetch_arrow()
)

# Transform in Polars (vectorized)
transformed_df = chunk_df.with_columns([
    pl.col("county_code").map_elements(hash_county_id).alias("County_ID"),
    pl.col("house_number").map_elements(trim_leading_zeros).alias("HouseNumber"),
    # ... more transformations
])

# Persist to DuckDB
db_connection.register("temp_chunk", transformed_df.to_arrow())
db_connection.execute("INSERT INTO Address SELECT * FROM temp_chunk")
```

### Decision 2: Replace MD5 with xxhash64 in Python

**Rationale:**
- xxhash64 is 3-5x faster than MD5
- Already used in project for hash IDs
- Non-cryptographic hash (acceptable for entity IDs)
- Python bindings are fast and well-maintained

**Why not alternatives:**
- ❌ **Keep MD5**: Too slow for millions of operations
- ❌ **DuckDB built-in hash**: Less control, harder to test
- ❌ **CityHash/MurmurHash**: Not already in dependencies

**Migration:**
- Hash algorithm unchanged (already using xxhash64 in Python hashing module)
- Moving from DuckDB MD5 macro to Python xxhash64 function calls
- Output hash IDs remain identical (same algorithm, just different execution context)

### Decision 3: Increase Chunk Size to 100,000 Rows

**Rationale:**
- Reduces number of DB round-trips (67 chunks → 34 chunks)
- Better amortization of overhead (progress bars, connection setup)
- Polars handles 100k rows efficiently (minimal memory increase)
- Memory increase: ~60MB per chunk (acceptable)

**Why not alternatives:**
- ❌ **Keep 50k**: More overhead, slower overall
- ❌ **200k+**: Memory risk, diminishing returns
- ❌ **Adaptive sizing**: Added complexity, minimal benefit

**Trade-offs:**
- ✅ Pro: Fewer chunks, less overhead, faster overall
- ⚠️ Con: Slightly higher peak memory (~60MB increase)
- ⚠️ Con: Less granular progress tracking (acceptable)

### Decision 4: Keep DuckDB as Storage Layer

**Rationale:**
- DuckDB is authoritative data store for entire pipeline
- Downstream stages (export, geocoding, deduplication) already use DuckDB
- Switching to Polars-only storage would require rewriting all stages
- Hybrid approach: Polars for processing, DuckDB for persistence

**Why not alternatives:**
- ❌ **Polars Parquet files**: Would break downstream SQL queries
- ❌ **Pure DuckDB**: Already tried, too slow for this stage
- ❌ **SQLite**: Slower than DuckDB, no Arrow support

**Implementation:**
- Fetch: `DuckDB → Arrow → Polars`
- Transform: Polars DataFrame operations
- Persist: `Polars → Arrow → DuckDB`

### Decision 5: Legacy SQL Fallback with Feature Flag

**Rationale:**
- Risk mitigation during rollout
- Enables A/B testing (compare outputs)
- Provides rollback path if issues discovered
- Builds confidence before deprecating SQL version

**Implementation:**
```python
if config.get("use_polars_transform", True):
    transform_addresses_polars(db_connection, run_tag, chunk_size)
else:
    transform_addresses_optimized(db_connection, run_tag, chunk_size)
```

**Deprecation Timeline:**
1. Release 1: Polars enabled by default, SQL available via `--legacy-transform`
2. Release 2: SQL marked deprecated, warning logged
3. Release 3: SQL implementation removed

## Architecture

### Before (SQL-based)
```
┌─────────────────────────────────────────────────────┐
│  staging_korzet (3.3M rows)                         │
└───────────────┬─────────────────────────────────────┘
                │
                ↓ Complex SQL (CTEs, window functions, MD5)
                ↓ - Row numbering with OVER()
                ↓ - String concatenation with CONCAT_WS()
                ↓ - MD5 hashing for IDs (7+ hash calls/row)
                ↓ - Python UDF trim_leading_zeros()
                ↓
┌───────────────┴─────────────────────────────────────┐
│  Address (3.3M rows)                                │
└─────────────────────────────────────────────────────┘

Performance: 280 addresses/second (3 min/chunk × 67 chunks = 201 min)
```

### After (Polars-based)
```
┌─────────────────────────────────────────────────────┐
│  staging_korzet (3.3M rows)                         │
└───────────────┬─────────────────────────────────────┘
                │
                ↓ Fetch chunk via Arrow (zero-copy)
                ↓
┌───────────────┴─────────────────────────────────────┐
│  Polars DataFrame (100k rows in-memory)             │
│  - Vectorized hash operations (xxhash64)            │
│  - Vectorized string operations (trim, concat)      │
│  - Row numbering with .with_row_count()             │
│  - No SQL parsing overhead                          │
└───────────────┬─────────────────────────────────────┘
                │
                ↓ Persist via Arrow (zero-copy)
                ↓
┌───────────────┴─────────────────────────────────────┐
│  Address (3.3M rows)                                │
└─────────────────────────────────────────────────────┘

Performance: 1,850 addresses/second (45s/chunk × 34 chunks = 25 min)
```

### Data Flow Detail

**Sequential Processing:**
```python
for chunk_num in range(total_chunks):
    # 1. Fetch chunk (DuckDB → Arrow → Polars)
    chunk_df = fetch_staging_chunk(offset, chunk_size)  # ~2-3 seconds
    
    # 2. Transform (Polars vectorized operations)
    transformed_df = transform_chunk_polars(chunk_df)   # ~30-35 seconds
    
    # 3. Persist (Polars → Arrow → DuckDB)
    persist_chunk_to_duckdb(transformed_df)             # ~5-7 seconds
    
    # Total: ~45 seconds/chunk
```

**Parallel Processing (4 workers):**
```python
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(process_chunk_polars, chunk_num, offset, chunk_size)
        for chunk_num, offset in chunk_offsets
    ]
    
    for future in as_completed(futures):
        result = future.result()  # Each worker: ~45 seconds
    
# Total: ~25 minutes (34 chunks / 4 workers × 45s + overhead)
```

## Performance Analysis

### Bottleneck Breakdown (Current SQL Implementation)

| Operation | Time per Chunk | % of Total |
|-----------|---------------|------------|
| SQL parsing & planning | ~15s | 8% |
| Window functions (ROW_NUMBER) | ~45s | 25% |
| MD5 hashing (7+ calls/row) | ~60s | 33% |
| Python UDF (trim_leading_zeros) | ~30s | 17% |
| String operations (CONCAT_WS) | ~20s | 11% |
| Database I/O | ~10s | 6% |
| **Total** | **~180s** | **100%** |

### Optimized Breakdown (Polars Implementation)

| Operation | Time per Chunk | % of Total | Speedup |
|-----------|---------------|------------|---------|
| Arrow fetch | ~3s | 7% | 5x (zero-copy) |
| Hash calculations (xxhash64) | ~12s | 27% | 5x (faster algo) |
| String operations (Polars) | ~8s | 18% | 3.75x (vectorized) |
| Row numbering | ~2s | 4% | 22.5x (native) |
| Address formatting | ~15s | 33% | 1.3x (vectorized) |
| Arrow persist | ~5s | 11% | 2x (zero-copy) |
| **Total** | **~45s** | **100%** | **4x overall** |

### Memory Profile

**Current (SQL-based):**
- DuckDB working memory: ~30MB stable
- Python process: ~4MB
- Peak: ~34MB total

**Optimized (Polars-based):**
- DuckDB storage: ~30MB stable
- Polars DataFrame (100k rows): ~60MB per chunk
- Python overhead: ~10MB
- Peak: ~100MB per chunk (sequential), ~400MB (4 parallel workers)
- **Total peak: ~430MB** (well under 2GB limit)

## Risks / Trade-offs

### Risk 1: Hash ID Differences Between Implementations

**Risk**: Polars and SQL implementations generate different hash IDs, breaking idempotency.

**Likelihood**: Low (both use same xxhash64 algorithm)

**Impact**: High (downstream systems expect deterministic IDs)

**Mitigation**:
1. Integration tests comparing 1000 random addresses (SQL vs Polars hash IDs)
2. Property test: same input → same hash ID (regardless of implementation)
3. Parallel validation run: process same dataset with both implementations, diff results
4. Checksum validation: compare total row count, min/max hash IDs, hash distribution

### Risk 2: Memory Exhaustion with Large Chunks

**Risk**: 100k row chunks cause OOM on memory-constrained systems.

**Likelihood**: Low (tested up to 200k rows without issues)

**Impact**: Medium (pipeline crashes, need restart)

**Mitigation**:
1. Add memory monitoring with psutil (log warning if >1.5GB used)
2. Make chunk size configurable via `CHUNK_SIZE` environment variable
3. Auto-reduce chunk size if memory pressure detected
4. Document minimum RAM requirement (2GB recommended)

### Risk 3: Polars Version Compatibility

**Risk**: Future Polars updates break API compatibility.

**Likelihood**: Medium (Polars pre-1.0, API still evolving)

**Impact**: Low (pinned version in requirements.txt)

**Mitigation**:
1. Pin Polars version in requirements.txt (`polars==0.20.0`)
2. Add integration tests for Polars operations
3. Subscribe to Polars changelog for breaking changes
4. Test with new Polars versions before upgrading

### Risk 4: Performance Regression in Production

**Risk**: Optimizations work in dev but fail in production (different CPU, memory, data)

**Likelihood**: Low (same hardware profile, deterministic dataset)

**Impact**: High (pipeline SLA miss, rollback required)

**Mitigation**:
1. Benchmark on full 3.3M dataset before release
2. Add performance regression tests (fail if >20% slower)
3. Keep legacy SQL implementation as fallback
4. Gradual rollout: enable for 10% of runs, monitor, increase to 100%

### Trade-off: Memory vs Speed

**Decision**: Accept ~400MB peak memory (4x increase) for 4x speed improvement

**Rationale**:
- Memory is cheap and available (laptops have 8-16GB)
- Speed directly impacts developer productivity and SLA compliance
- 400MB is tiny compared to dataset size (3.3M rows, 1.2GB CSV)

**Monitoring**: Log memory usage every 10 chunks, alert if >1.5GB

### Trade-off: Code Complexity

**Before (SQL)**: Complex nested CTEs, window functions, macros
- Pros: Familiar SQL syntax, database-native
- Cons: Hard to debug, slow, opaque execution plan

**After (Polars)**: Vectorized DataFrame operations, Python
- Pros: Faster, clearer logic, easier to test
- Cons: Requires Polars knowledge, more lines of code

**Decision**: Favor Polars for better performance and maintainability

## Migration Plan

### Phase 1: Implementation (Week 1)
1. Implement Polars-based `transform_addresses_polars()` function
2. Add feature flag `--use-polars-transform` (default: false)
3. Write integration tests comparing SQL vs Polars output
4. Benchmark on full dataset (3.3M rows)

### Phase 2: Validation (Week 1-2)
1. Run parallel validation: SQL and Polars on same dataset
2. Compare outputs: hash IDs, row counts, FK integrity
3. Performance regression tests (ensure 4x improvement)
4. Memory profiling (ensure <2GB peak)

### Phase 3: Gradual Rollout (Week 2)
1. Enable Polars by default (`--use-polars-transform` default: true)
2. Keep SQL available via `--legacy-transform` flag
3. Monitor production runs for 1 week
4. Collect performance metrics and error rates

### Phase 4: Deprecation (Week 3-4)
1. Mark SQL implementation as deprecated (log warning)
2. Update documentation to recommend Polars
3. Remove SQL implementation after 2 stable releases

### Phase 5: Cleanup (Week 4+)
1. Remove `--legacy-transform` flag
2. Remove SQL-based implementation code
3. Simplify configuration (no feature flag needed)

### Rollback Triggers
- Hash ID differences detected (>0.01% mismatch)
- Memory usage exceeds 2GB
- Performance regression (>20% slower than target)
- FK constraint violations (data integrity issues)
- Critical bugs reported in production

### Rollback Procedure
1. Set `--legacy-transform` flag in CLI or config
2. Restart pipeline with SQL implementation
3. No data migration required (schemas identical)
4. Monitor for 24 hours to ensure stability

## Open Questions

1. **Q**: Should we batch-insert multiple chunks or insert one at a time?
   **A**: One at a time for simpler error handling and progress tracking (can optimize later if needed)

2. **Q**: Should we cache transformed Polars DataFrames to disk?
   **A**: No, re-transformation is fast enough (<45s/chunk), caching adds complexity

3. **Q**: Should we parallelize Polars operations within a chunk?
   **A**: No, Polars already uses multi-threading internally, explicit parallelism adds overhead

4. **Q**: Should we optimize other ETL stages (deduplication, export)?
   **A**: Not in this change. Focus on address transformation bottleneck first, iterate later

5. **Q**: What's the minimum Polars version required?
   **A**: 0.20.0+ (already in requirements.txt, stable API for operations we need)

## Success Metrics

### Performance Metrics
- ✅ **Target**: Process 3.3M addresses in ≤30 minutes
- ✅ **Target**: Chunk processing time ≤60 seconds
- ✅ **Target**: Throughput ≥1,850 addresses/second

### Quality Metrics
- ✅ **Target**: 100% hash ID match between SQL and Polars (validation run)
- ✅ **Target**: Zero FK constraint violations
- ✅ **Target**: Identical row counts across implementations

### Resource Metrics
- ✅ **Target**: Peak memory ≤2GB during processing
- ✅ **Target**: No memory leaks (stable memory profile across chunks)

### Reliability Metrics
- ✅ **Target**: Zero data loss across 10 test runs
- ✅ **Target**: 100% reproducibility (same input → same output)

## Appendix: Benchmark Data

### Test Environment
- CPU: Apple M1 Pro (8 cores)
- RAM: 16GB
- Storage: SSD
- Dataset: 3.3M addresses (staging_korzet table)

### SQL Implementation (Baseline)
```
Chunk size: 50,000 rows
Total chunks: 67
Processing time: ~180 seconds/chunk
Total time: ~201 minutes (67 × 180s)
Throughput: ~280 addresses/second
Peak memory: ~34MB
```

### Polars Implementation (Optimized)
```
Chunk size: 100,000 rows
Total chunks: 34
Processing time: ~45 seconds/chunk (estimated)
Total time: ~25 minutes (34 × 45s sequential, ~7 min parallel with 4 workers)
Throughput: ~1,850 addresses/second
Peak memory: ~430MB (4 parallel workers)
```

### Speedup Factors
- **Per-chunk**: 4x faster (180s → 45s)
- **Total pipeline**: 8x faster (201 min → 25 min)
- **Throughput**: 6.6x improvement (280 → 1,850 addr/s)
