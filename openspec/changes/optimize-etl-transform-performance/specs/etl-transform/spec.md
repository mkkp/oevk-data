# ETL Transform Capability Specification

## MODIFIED Requirements

### Requirement: Address Transformation Performance

The system SHALL transform 3.3M+ addresses from staging to normalized format within 30 minutes to meet NFR-002 performance requirements.

#### Scenario: Sequential chunk processing performance

- **WHEN** processing addresses in sequential mode
- **THEN** the system SHALL process each 100,000-row chunk in ≤60 seconds
- **AND** achieve throughput of ≥1,850 addresses per second
- **AND** maintain peak memory usage ≤1GB per chunk
- **AND** complete full 3.3M address dataset in ≤60 minutes

#### Scenario: Parallel chunk processing performance

- **WHEN** processing addresses with 4 parallel workers
- **THEN** the system SHALL process chunks concurrently with ≤45 seconds per chunk
- **AND** maintain peak memory usage ≤2GB total (all workers combined)
- **AND** complete full 3.3M address dataset in ≤30 minutes
- **AND** meet NFR-002 performance requirement

#### Scenario: Memory-efficient batch processing

- **WHEN** processing large address datasets
- **THEN** the system SHALL use chunked iteration (not load entire dataset in memory)
- **AND** use default chunk size of 100,000 rows
- **AND** support configurable chunk size via CHUNK_SIZE environment variable
- **AND** monitor memory usage and log warnings if exceeding 1.5GB

### Requirement: Polars-Based Transformation Engine

The system SHALL use Polars DataFrame library for in-memory address transformation to achieve performance targets.

#### Scenario: Fetch staging data via Arrow

- **WHEN** fetching a chunk from staging_korzet table
- **THEN** the system SHALL use DuckDB Arrow interface for zero-copy transfer
- **AND** convert Arrow table to Polars DataFrame
- **AND** complete fetch operation in ≤5 seconds for 100k rows
- **AND** preserve all column types and NULL values

#### Scenario: Vectorized hash ID generation

- **WHEN** generating entity hash IDs
- **THEN** the system SHALL use xxhash64 algorithm (not MD5)
- **AND** apply hash functions as Polars expressions or map operations
- **AND** generate all 7+ hash IDs per row in ≤15 seconds for 100k rows
- **AND** produce identical hash IDs as legacy SQL implementation

#### Scenario: Vectorized string operations

- **WHEN** processing address string components
- **THEN** the system SHALL use Polars string expressions for trimming, concatenation, and formatting
- **AND** replace Python UDF trim_leading_zeros with Polars regex or string operations
- **AND** apply operations vectorized across entire chunk
- **AND** complete all string operations in ≤10 seconds for 100k rows

#### Scenario: Row numbering and sequencing

- **WHEN** assigning Sequence and OriginalOrder columns
- **THEN** the system SHALL use Polars .with_row_count() method
- **AND** calculate global OriginalOrder based on chunk offset
- **AND** complete row numbering in ≤2 seconds for 100k rows
- **AND** maintain deterministic ordering across runs

#### Scenario: Persist transformed data via Arrow

- **WHEN** persisting transformed chunk to DuckDB
- **THEN** the system SHALL convert Polars DataFrame to Arrow table
- **AND** register Arrow table with DuckDB
- **AND** insert via SQL using registered Arrow table
- **AND** complete persist operation in ≤10 seconds for 100k rows
- **AND** handle ON CONFLICT for idempotent updates

### Requirement: Legacy SQL Fallback Implementation

The system SHALL maintain SQL-based transformation implementation as fallback during migration period.

#### Scenario: Feature flag for implementation selection

- **WHEN** user specifies transformation implementation
- **THEN** the system SHALL default to Polars-based implementation
- **AND** support --legacy-transform CLI flag to use SQL implementation
- **AND** support USE_POLARS_TRANSFORM environment variable (default: true)
- **AND** log which implementation is being used

#### Scenario: SQL implementation availability

- **WHEN** --legacy-transform flag is set
- **THEN** the system SHALL use transform_addresses_optimized() SQL-based function
- **AND** produce identical output schema and hash IDs as Polars implementation
- **AND** log deprecation warning for SQL implementation
- **AND** continue to support SQL until 2 releases after Polars stability proven

#### Scenario: Output validation between implementations

- **WHEN** running validation mode
- **THEN** the system SHALL support --validate-implementations flag
- **AND** run both SQL and Polars implementations on same dataset
- **AND** compare hash IDs, row counts, and FK integrity
- **AND** report any differences found
- **AND** fail validation if >0.01% hash ID mismatch

### Requirement: Deterministic Hash ID Generation

The system SHALL generate deterministic hash-based entity IDs using xxhash64 algorithm to ensure idempotent processing.

#### Scenario: Hash function implementation in Polars

- **WHEN** calculating hash IDs in Polars
- **THEN** the system SHALL use same xxhash64 algorithm as SQL implementation
- **AND** apply hash functions to concatenated key components (county_code|settlement_code|...)
- **AND** encode input strings as UTF-8 before hashing
- **AND** return hexadecimal string representation of hash
- **AND** produce identical hashes as legacy SQL MD5-based macros (algorithm migration separate)

#### Scenario: Hash consistency validation

- **WHEN** processing same address multiple times
- **THEN** the system SHALL generate identical hash ID each time
- **AND** support property-based testing with 1000+ random addresses
- **AND** verify hash stability across Python restarts
- **AND** verify hash stability across different Polars versions (within minor version)

### Requirement: Progress Tracking and Logging

The system SHALL provide comprehensive progress tracking with optimized update frequency for performance.

#### Scenario: Batch progress updates

- **WHEN** processing chunks
- **THEN** the system SHALL update progress bars every chunk completion
- **AND** log detailed metrics every 10 chunks
- **AND** disable individual chunk progress bars in parallel mode (reduce overhead)
- **AND** show overall progress, chunks completed, and ETA

#### Scenario: Performance metrics logging

- **WHEN** chunk processing completes
- **THEN** the system SHALL log processing time per chunk
- **AND** log cumulative processing time and throughput
- **AND** log estimated time remaining based on average chunk time
- **AND** log memory usage if exceeding 500MB threshold

#### Scenario: Final transformation statistics

- **WHEN** transformation completes
- **THEN** the system SHALL log total addresses processed
- **AND** log total processing time and average throughput
- **AND** log memory usage statistics (peak, average)
- **AND** log transformation mode used (Polars or SQL)

## ADDED Requirements

### Requirement: Configurable Chunk Size

The system SHALL support configurable chunk size to balance memory usage and performance.

#### Scenario: Default chunk size

- **WHEN** chunk size is not specified
- **THEN** the system SHALL use default chunk size of 100,000 rows
- **AND** calculate total chunks as ceiling(total_rows / chunk_size)
- **AND** log chunk configuration at pipeline start

#### Scenario: Custom chunk size via environment variable

- **WHEN** CHUNK_SIZE environment variable is set
- **THEN** the system SHALL use specified chunk size
- **AND** validate chunk size is between 10,000 and 500,000 rows
- **AND** log warning if chunk size outside recommended range (50k-200k)
- **AND** fall back to default if invalid value provided

#### Scenario: Custom chunk size via CLI parameter

- **WHEN** user specifies --chunk-size parameter
- **THEN** the system SHALL use specified chunk size
- **AND** override environment variable if both specified
- **AND** validate chunk size range (10k-500k)
- **AND** log chunk size configuration

#### Scenario: Memory-based chunk size adjustment

- **WHEN** memory usage exceeds 1.5GB during processing
- **THEN** the system SHALL log warning about high memory usage
- **AND** suggest reducing chunk size for next run
- **AND** continue processing current run without auto-adjustment
- **AND** document recommended chunk sizes for different RAM configurations

### Requirement: Performance Benchmarking

The system SHALL provide performance benchmarking capabilities to validate optimizations and detect regressions.

#### Scenario: Benchmark mode execution

- **WHEN** user runs with --benchmark flag
- **THEN** the system SHALL process full dataset with timing instrumentation
- **AND** measure and log per-chunk processing time breakdown
- **AND** measure fetch time, transform time, persist time separately
- **AND** calculate throughput (addresses per second) for each stage
- **AND** log memory usage at each chunk completion

#### Scenario: Performance regression detection

- **WHEN** running performance regression tests
- **THEN** the system SHALL compare current run time against baseline target
- **AND** fail test if total processing time >20% slower than target (36 minutes vs 30 minute target)
- **AND** fail test if per-chunk time >20% slower than target (72 seconds vs 60 second target)
- **AND** fail test if memory usage exceeds 2GB threshold

#### Scenario: Baseline performance metrics storage

- **WHEN** benchmark completes successfully
- **THEN** the system SHALL optionally store metrics to JSON file
- **AND** include timestamp, dataset size, chunk size, total time, memory usage
- **AND** support --save-baseline flag to update baseline metrics file
- **AND** support comparison against historical baselines

### Requirement: Zero-Copy Data Transfer

The system SHALL use Apache Arrow format for efficient zero-copy data transfer between DuckDB and Polars.

#### Scenario: Arrow-based chunk fetch

- **WHEN** fetching chunk from DuckDB
- **THEN** the system SHALL use DuckDB .fetch_arrow() method
- **AND** convert Arrow Table to Polars DataFrame with .from_arrow()
- **AND** avoid intermediate copies or format conversions
- **AND** preserve column types, NULL handling, and metadata

#### Scenario: Arrow-based chunk persist

- **WHEN** persisting Polars DataFrame to DuckDB
- **THEN** the system SHALL convert DataFrame to Arrow with .to_arrow()
- **AND** register Arrow table with DuckDB .register() method
- **AND** insert via SQL referencing registered table name
- **AND** unregister temporary Arrow table after insert

#### Scenario: Memory efficiency validation

- **WHEN** transferring 100k rows via Arrow
- **THEN** the system SHALL complete transfer in <3 seconds
- **AND** avoid duplicate memory allocation for data
- **AND** maintain memory overhead <10% of payload size
