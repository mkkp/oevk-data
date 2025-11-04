<!--
DOCUMENT METADATA
=================
Title: OEVK ETL Pipeline Performance Report
Type: Analysis
Category: Performance
Status: Completed
Version: 1.0
Created: 2025-10-29
Last Updated: 2025-10-29
Author: System
Pipeline Run: 20251029013900

Related Documents:
- Performance Benchmarks (PERFORMANCE_BENCHMARKS.md)

Related Code:
- src/cli.py (ETL pipeline orchestration)
- src/etl/ingest.py (ingestion stage)
- src/etl/transform.py (transformation stage)
- src/etl/deduplicate.py (deduplication stage)
- src/etl/export.py (export stage)

Dependencies:
- DuckDB for processing
- Polars for data transformation

Keywords: performance, benchmarks, etl-pipeline, timing, throughput, deduplication, optimization

Summary:
Performance analysis report for complete ETL pipeline run processing 3.3M addresses in 19.5 minutes. Breakdown: Ingestion 17.2s (1.5%), Transformation 705.5s (60.3%), Export 446.4s (38.2%). Identifies Transform stage as bottleneck, particularly public space extraction (409.9s) and canonical formatting (235.8s). Includes detailed step-by-step timing, chunk processing rates, and optimization recommendations.

Audience:
Performance engineers, developers optimizing ETL pipeline, technical leads reviewing system performance.
-->

# OEVK ETL Pipeline - Performance Report

**Pipeline Run:** 20251029013900  
**Status:** ✓ COMPLETED SUCCESSFULLY  
**Total Duration:** 1,169.04 seconds (19.5 minutes)  
**Date:** October 29, 2025

---

## Executive Summary

The OEVK ETL pipeline successfully processed **3,336,202 addresses** in **19.5 minutes**, generating:
- 3,315,609 canonical addresses (after deduplication)
- 7,550 invalid addresses filtered (all-zero house numbers)
- 20,593 duplicates removed (0.62% deduplication rate)
- Complete exports in CSV, PostgreSQL, and database dump formats

**Key Finding:** All-zero house number filtering is working correctly ✓

---

## Step-by-Step Execution Breakdown

### 1. INGESTION STEP
**Duration:** 17.20s (1.5% of total time)

- Downloaded OEVK JSON and Korzet ZIP files
- Extracted and loaded staging data
- **Rows processed:** 3,336,202
- **Throughput:** 193,965 rows/s
- **Status:** ✓ Completed

---

### 2. TRANSFORM STEP
**Duration:** 705.49s = 11.8 min (60.3% of total time)

#### 2.1 Basic Entity Transformations (~1s)
- Counties: 20
- Settlements: 3,177
- National electoral districts: 106 (with polygon data)
- Postal codes: 3,106
- Settlement electoral districts: 4,597
- Polling stations: 8,547
- Postal code-settlement relationships: 3,684

#### 2.2 Polars Address Transformation
**Duration:** 198.0s = 3.3 min (16.9% of total)
- Processed: 3,336,202 addresses in 67 chunks of 50,000
- **Throughput:** 16,979 addresses/sec
- Chunk performance: avg 3.09s, min 2.40s, max 3.70s

#### 2.3 Invalid Address Filtering
**Duration:** <1s
- **Filtered:** 7,550 invalid addresses (all-zero house numbers)
- Valid addresses: 3,328,652
- **Filter working correctly:** "0000", "00000" → removed ✓

#### 2.4 Address Deduplication
**Duration:** 180.0s = 3.0 min (15.4% of total)
- Original addresses: 3,336,202
- Canonical addresses: 3,315,609
- **Duplicates removed:** 20,593 (0.62% deduplication rate)
- **Throughput:** ~18,423 addresses/sec

#### 2.5 Geocoding (using cache)
- Cached addresses: 2,935,674
- Skipped new addresses: 379,935 (--update-from-cache mode)
- Database updated with cached geocoding results

**Total rows processed:** 3,507,228  
**Overall throughput:** 4,971 rows/s

---

### 3. EXPORT STEP
**Duration:** 446.35s = 7.4 min (38.2% of total time)

#### 3.1 CSV Export (all entities)
- Exported 12 tables to CSV format
- Address export: 3,258,585 rows in 208.4s
  - Fetch: 21.1s @ 154,368 rows/s
  - MD5→UUID5 conversion + write: 187.3s @ ~17,400 rows/s

#### 3.2 PostgreSQL Export
- Generated optimized import script
- Split large tables into chunks (33 chunks for addresses)
- Created schema.sql with proper DDL

#### 3.3 Canonical Address Export (by settlement)
- Exported 3,315,609 canonical addresses
- Processed 3,177 settlements

#### 3.4 Database Verification & Dump
- Created PostgreSQL dump: `oevk_db_20251029013900.sql.gz`

**Total rows processed:** 3,336,202  
**Overall throughput:** 7,474 rows/s

---

## Step Execution Frequency Analysis

### Pipeline-Level Steps
Each pipeline step executes **exactly ONCE** per run:
- `ingest`: 1 execution
- `transform`: 1 execution
- `export`: 1 execution

### Transform Step Sub-Operations
- Entity transformations: 7 different entity types
- Polars chunk processing: **67 chunks** executed
- Deduplication: 1 execution
- Geocoding cache update: 1 execution

### Export Step Operations
- CSV table exports: **12 tables**
- Settlement-based exports: **3,177 settlements** processed
- PostgreSQL script generation: 1 execution

---

## Performance Bottleneck Analysis

### Time Distribution

1. **Transform step:** 705.49s (60.3%) - Largest portion
   - Deduplication: 180.0s (15.4% of total)
   - Polars processing: 198.0s (16.9% of total)
   - Other transforms: ~327s (27.9% of total)

2. **Export step:** 446.35s (38.2%)
   - Address UUID conversion: ~187s (16.0% of total)
   - Settlement exports: ~239s (20.4% of total)

3. **Ingestion step:** 17.20s (1.5%) - Very fast ✓

### Top Bottlenecks (slowest operations)

1. **Settlement-based exports:** ~239s (20.4% of total time)
2. **Polars address processing:** 198s (16.9%)
3. **UUID conversion + CSV write:** 187s (16.0%)
4. **Address deduplication:** 180s (15.4%)

---

## Key Performance Metrics

### Throughput by Step
- **Ingestion:** 193,965 rows/s (fastest)
- **Transform:** 4,971 rows/s
- **Export:** 7,474 rows/s
- **Overall:** 8,708 rows/s

### Data Quality Results
- **Invalid addresses filtered:** 7,550 (0.23% of input)
- **Duplicates removed:** 20,593 (0.62% of input)
- **Final canonical addresses:** 3,315,609 (99.4% of input)

### All-Zero House Number Fix Status
**✓ WORKING CORRECTLY**
- Addresses like "0000", "00000" properly filtered
- Leading zeros before digits preserved (e.g., "000001" → "1")

---

## Optimization Recommendations

Based on the performance analysis, here are optimization opportunities:

### 1. Settlement-based export (239s - 20.4% of time)
**Issue:** Processing settlements one-by-one  
**Recommendation:** Consider batch processing settlements  
**Potential speedup:** 2-3x faster

### 2. UUID conversion during export (187s - 16.0% of time)
**Issue:** Single-threaded UUID conversion  
**Recommendation:** Parallelize across multiple CPU cores  
**Potential speedup:** 2-4x faster on multi-core systems

### 3. Polars chunk processing (198s - 16.9% of time)
**Status:** Already well-optimized (16,979 addr/sec)  
**Assessment:** Chunk size of 50,000 appears optimal  
**Recommendation:** No immediate optimization needed

### 4. Deduplication (180s - 15.4% of time)
**Status:** Currently processing 18,423 addr/sec  
**Assessment:** Already reasonably fast  
**Recommendation:** Consider caching hash computations if running multiple times

---

## Overall Assessment

**Pipeline is well-optimized.** Total time of **19.5 minutes** for **3.3M addresses** is very reasonable. 

**Export phase** offers the most optimization potential, particularly settlement-based exports and UUID conversion which together account for **36.4%** of total execution time.

**Transform phase** is highly optimized with Polars-based processing achieving excellent throughput.

**Data quality** is excellent with proper filtering of invalid addresses and effective deduplication.

---

## Performance Tracking Tools

The following tools were created to monitor pipeline performance:

- `perf_tracker.py` - Analyzes log files and generates detailed performance reports
- `monitor_and_report.sh` - Auto-refresh monitoring (updates every 30 seconds)
- `wait_and_report.sh` - Waits for pipeline completion and generates final report

**Usage:**
```bash
# Run analysis anytime:
python perf_tracker.py

# Auto-refresh monitoring:
./monitor_and_report.sh
```

---

## Metrics Summary Table

| Metric | Value |
|--------|-------|
| Total Duration | 19.5 minutes (1,169 seconds) |
| Input Addresses | 3,336,202 |
| Output Addresses | 3,315,609 |
| Invalid Filtered | 7,550 (0.23%) |
| Duplicates Removed | 20,593 (0.62%) |
| Overall Throughput | 8,708 rows/s |
| Fastest Step | Ingestion (193,965 rows/s) |
| Slowest Operation | Settlement exports (239s) |
| Chunk Processing | 67 chunks @ 3.09s avg |
| Deduplication Rate | 0.62% |
| Success Rate | 100% ✓ |
