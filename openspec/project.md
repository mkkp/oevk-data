# Project Context: OEVK Data Processing

## Purpose

Transform Hungarian electoral address data from authoritative government sources into normalized, queryable datasets with comprehensive data quality features. The pipeline processes 3.3+ million address records, extracts public space entities, performs address deduplication, and exports partitioned CSV files optimized for analysis.

### Core Objectives

1. **Data Normalization**: Transform raw electoral data into 14 normalized relational tables
2. **Entity Extraction**: Identify and extract public space entities (names, types) from address strings
3. **Address Deduplication**: Merge duplicate addresses using Hungarian address formatting rules
4. **Multi-Format Export**: Generate settlement-based exports in CSV and PostgreSQL formats
5. **PostgreSQL Integration**: Automated schema translation, UUID conversion, and Docker-based verification
6. **Release Automation**: Package and publish processed data to GitHub releases with multiple formats

### Business Value

- **Data Quality**: Deduplicated, normalized data with 100% referential integrity
- **Performance**: 98.6% improvement (183.6 min → 2.5 min) through parallel processing
- **Accessibility**: Settlement-partitioned exports enable efficient regional analysis
- **Database Flexibility**: Export to both CSV and PostgreSQL with automated verification
- **Traceability**: Deterministic hash IDs (xxhash64) and UUID v3 ensure idempotent, reproducible processing
- **Public Space Analysis**: Extracted entities enable geospatial and urban planning research
- **Docker Integration**: Automated PostgreSQL setup and verification with containerization

## Tech Stack

### Core Technologies

- **Language**: Python 3.12.6
- **Data Processing**: Polars 0.20.0+ (high-performance DataFrame library)
- **Databases**: 
  - DuckDB 0.10.0+ (embedded analytical database)
  - PostgreSQL 16+ (production database export target)
- **Hashing**: xxhash 3.4.0+ (deterministic ID generation)
- **UUID**: UUID v3 with DNS namespace `oevk.hu` for PostgreSQL exports
- **HTTP**: requests 2.31.0+ (source data downloads)
- **PostgreSQL Driver**: psycopg2-binary 2.9.0+ (PostgreSQL connectivity)

### Development Tools

- **Linting**: ruff 0.3.0+ (fast Python linter and formatter)
- **Code Quality**: mypy (static type checking)
- **Testing**: pytest (unit, integration, contract tests)
- **Performance**: psutil 5.9.0+ (resource monitoring)
- **Containerization**: Docker (PostgreSQL verification and setup)

### Release Tools

- **GitHub Integration**: PyGithub 2.0.0+ (GitHub API)
- **Serialization**: pyarrow 14.0.0+ (efficient data formats)
- **CLI**: GitHub CLI (gh) for release management

### External Dependencies

- **Source Data**: 
  - OEVK JSON: `https://static.valasztas.hu/dyn/oevk_data/oevk.json` (108 records)
  - Korzet ZIP: `https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip` (3.3M+ records)
- **GitHub**: Release artifact hosting and distribution

## Project Conventions

### Code Style

#### Import Organization
```python
# Standard library imports (alphabetical)
import datetime
import os
import sys
from pathlib import Path

# Third-party imports (alphabetical)
import duckdb
import polars as pl
import requests
import xxhash

# Local imports (relative)
from src.database.connection import get_database_connection
from src.utils.config import Config
from src.utils.pipeline_logging import get_logger
```

#### Naming Conventions

**Variables and Functions**: `snake_case`
```python
county_code = "01"
settlement_name = "Budapest"
def transform_addresses(db_connection, run_tag):
    pass
```

**Classes**: `PascalCase`
```python
class AddressDeduplicator:
    pass

class ReleaseWorkflow:
    pass
```

**Constants**: `UPPER_SNAKE_CASE`
```python
CHUNK_SIZE = 100000
MAX_WORKERS = 4
DEFAULT_HASH_SEED = 20241012
```

**Private Members**: Leading underscore
```python
def _format_full_address(self, components):
    pass

self._canonical_addresses = {}
```

#### Type Hints

All functions and methods must include type hints:
```python
def hash_county_id(county_code: str) -> str:
    """Generate deterministic hash for county ID."""
    return hex_digest(county_code)

def transform_addresses(
    db_connection: duckdb.DuckDBPyConnection, 
    run_tag: str
) -> None:
    """Transform staging addresses to normalized format."""
    pass
```

#### Docstrings

Use Google-style docstrings:
```python
def hash_settlement_id(county_code: str, settlement_code: str) -> str:
    """Generate deterministic hash for settlement ID.
    
    Args:
        county_code: Two-digit county code
        settlement_code: Three-digit settlement code
        
    Returns:
        Hexadecimal string representation of hash
        
    Example:
        >>> hash_settlement_id("01", "001")
        'a1b2c3d4e5f6'
    """
    pass
```

### Architecture Patterns

#### 1. ETL Pipeline Pattern

**Structure**: Separate modules for Ingest → Transform → Export

```python
# src/etl/ingest.py
def download_sources() -> None:
    """Download source data from authoritative URLs."""
    
def load_staging_data(db_connection, staging_dir) -> None:
    """Load source files into staging tables."""

# src/etl/transform_optimized.py
def transform_all_optimized(db_connection, run_tag, enable_deduplication) -> None:
    """Transform staging to normalized tables with parallel processing."""

# src/etl/export.py
def export_tables_to_csv(db_connection, output_dir, run_tag, formats=["csv"]) -> None:
    """Export normalized tables to CSV and/or PostgreSQL formats."""
    
def generate_postgresql_schema() -> str:
    """Translate SQLite schema to PostgreSQL with UUID types."""
```

**Benefits**:
- Clear separation of concerns
- Independent testing of each stage
- Flexible execution (run only specific stages)

#### 2. Deterministic ID Generation Pattern

**All entity IDs use xxhash64 for idempotency**:

```python
def hash_settlement_id(county_code: str, settlement_code: str) -> str:
    """Deterministic hash: county_code | settlement_code."""
    key = f"{county_code}|{settlement_code}"
    return xxhash.xxh64(key.encode('utf-8')).hexdigest()
```

**Key Principle**: Same input → Same ID (across runs)

**Benefits**:
- Idempotent processing (safe to re-run)
- No auto-increment dependencies
- Reproducible datasets
- Consistent cross-references

#### 3. Chunked Parallel Processing Pattern

**Process large datasets in chunks with ThreadPoolExecutor**:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_chunks_parallel(data, chunk_size=100000, max_workers=4):
    """Process data in parallel chunks for optimal performance."""
    chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_chunk, chunk): i 
                   for i, chunk in enumerate(chunks)}
        
        for future in as_completed(futures):
            chunk_id = futures[future]
            result = future.result()
            yield chunk_id, result
```

**Benefits**:
- Efficient memory usage
- Parallelism for CPU-bound tasks
- Progress tracking per chunk
- Graceful error handling

#### 4. Configuration Management Pattern

**Centralized configuration with environment overrides**:

```python
# src/utils/config.py
class Config:
    def __init__(self):
        self._config = {
            "processing": {
                "chunk_size": 100000,
                "max_workers": 4,
            }
        }
        self._load_environment_variables()
    
    def _load_environment_variables(self):
        """Override defaults with environment variables."""
        if chunk_size := os.getenv("CHUNK_SIZE"):
            self._config["processing"]["chunk_size"] = int(chunk_size)
```

**Usage**:
```bash
# Override via environment
export CHUNK_SIZE=50000
export MAX_WORKERS=8
python src/cli.py run
```

**Benefits**:
- Sensible defaults
- Environment-specific overrides
- No hardcoded values
- Easy testing configuration

#### 5. Structured Logging Pattern

**Pipeline-wide logging with metrics tracking**:

```python
# src/utils/pipeline_logging.py
class PipelineMetrics:
    def __init__(self):
        self.start_time = time.time()
        self.steps = []
    
    def log_step(self, step_name, row_count):
        duration = time.time() - self.start_time
        self.steps.append({
            "name": step_name,
            "rows": row_count,
            "duration": duration
        })
        logger.info(f"{step_name}: {row_count:,} rows in {duration:.2f}s")
```

**Log Levels**:
- `DEBUG`: Detailed technical information
- `INFO`: Pipeline progress and metrics (default)
- `WARNING`: Potential issues (missing data, etc.)
- `ERROR`: Failures requiring attention

#### 6. Database Connection Pattern

**Centralized connection management with context managers**:

```python
# src/database/connection.py
def get_database_connection(db_path="data/oevk.db"):
    """Get DuckDB connection with configuration."""
    conn = duckdb.connect(db_path)
    conn.execute("SET memory_limit='2GB'")
    conn.execute("SET threads=4")
    return conn

# Usage
with get_database_connection() as conn:
    transform_all_optimized(conn, run_tag)
```

**Benefits**:
- Consistent configuration
- Automatic cleanup
- Connection pooling
- Easy testing with temporary databases

#### 7. Hungarian Address Formatting Pattern

**Domain-specific formatting rules**:

```python
class AddressDeduplicator:
    def _format_full_address(self, components) -> str:
        """Format address per Hungarian conventions.
        
        Rules:
        1. Remove leading zeros from house numbers
        2. Use 'épület' for building, 'lépcsőház' for staircase
        3. Convert numeric staircases to Roman numerals
        4. End with period
        
        Examples:
            "Körtöltés utca 1/D."
            "Körtöltés utca 1-5. B. épület L. lépcsőház"
            "Berényi utca 9. 1. épület I. lépcsőház"
        """
        pass
```

**Benefits**:
- Consistent formatting across dataset
- Culturally appropriate representation
- Deduplication accuracy
- User-friendly exports

### Testing Strategy

#### Test Hierarchy

1. **Contract Tests** (`tests/contract/`)
   - Validate core invariants
   - Run before implementation
   - TDD mandatory

2. **Integration Tests** (`tests/integration/`)
   - End-to-end workflows
   - Database operations
   - Data quality checks

3. **Unit Tests** (`tests/unit/`)
   - Individual functions
   - Edge cases
   - Performance benchmarks

#### Test Structure

```python
# tests/contract/test_deduplication.py
def test_deduplication_deterministic():
    """Contract: Same addresses → Same canonical ID."""
    address1 = create_address("Kossuth tér 1")
    address2 = create_address("Kossuth tér 1")
    
    canonical_id1 = deduplicate([address1])
    canonical_id2 = deduplicate([address2])
    
    assert canonical_id1 == canonical_id2

def test_deduplication_preserves_relationships():
    """Contract: All polling stations preserved after deduplication."""
    addresses = create_addresses_with_polling_stations(count=100)
    original_stations = extract_polling_stations(addresses)
    
    canonical = deduplicate(addresses)
    preserved_stations = extract_polling_stations(canonical)
    
    assert set(original_stations) == set(preserved_stations)
```

#### Running Tests

```bash
# All tests
pytest tests/

# Specific category
pytest tests/contract/
pytest tests/integration/
pytest tests/unit/

# With coverage
pytest tests/ --cov=src --cov-report=html

# Verbose output
pytest tests/ -v

# Specific test
pytest tests/contract/test_deduplication.py::test_deterministic -v
```

#### Test Fixtures

**Use shared fixtures for common test data**:

```python
# tests/conftest.py
import pytest
import duckdb

@pytest.fixture
def temp_db():
    """Temporary database for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()

@pytest.fixture
def sample_addresses():
    """Sample address data for testing."""
    return [
        {"street": "Kossuth tér", "number": "1"},
        {"street": "Petőfi utca", "number": "10"},
    ]
```

### Git Workflow

#### Branch Strategy

**Feature-Based Branching**:
```
main
  ├── 001-initial-oevk-transformation
  ├── 002-release-transformed-database
  ├── 003-extract-publicspacename-and
  └── 004-cleanup-duplicated-addresses
```

**Branch Naming**: `###-feature-description`
- Example: `004-cleanup-duplicated-addresses`
- Leading zeros for sorting
- Lowercase with hyphens

#### Commit Conventions

**Format**: `<type>(<scope>): <subject>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no code change
- `refactor`: Code restructuring
- `perf`: Performance improvement
- `test`: Adding tests
- `chore`: Maintenance

**Examples**:
```bash
git commit -m "feat(deduplication): implement Hungarian address formatting"
git commit -m "fix(export): correct UUID v3 namespace for addresses"
git commit -m "perf(transform): add parallel processing with ThreadPoolExecutor"
git commit -m "test(deduplication): add contract tests for deterministic IDs"
git commit -m "docs(readme): update release workflow instructions"
```

#### Pull Request Process

1. **Create feature branch**: `git checkout -b 005-new-feature`
2. **Implement with tests**: TDD approach (tests first)
3. **Run quality checks**:
   ```bash
   ruff check .
   ruff format .
   mypy .
   pytest tests/
   ```
4. **Commit frequently**: Small, logical commits
5. **Push and create PR**: Link to specification in `specs/`
6. **Review and merge**: Squash or merge based on commit quality

#### Tag Strategy

**Release Tags**: `YYYYMMDD-HHMM`
- Example: `20250113-1430`
- ISO date format for sorting
- Time for uniqueness
- Automatically generated by release workflow

## Domain Context

### Hungarian Electoral System

**Key Entities**:

1. **Vármegye (County)**: Top-level administrative unit (20 counties)
2. **Település (Settlement)**: City, town, or village (3,177 settlements)
3. **OEVK (National Electoral District)**: Parliamentary constituency (106 districts)
4. **TEVK (Settlement Electoral District)**: Local constituency within settlement (4,677 districts)
5. **Szavazókör (Polling Station)**: Physical voting location (8,555 stations)

**Data Relationships**:
```
County (20)
  └─ Settlement (3,177)
      ├─ TEVK (4,677)
      │   └─ Polling Station (8,555)
      │       └─ Address (3.3M original → 3.32M canonical)
      └─ Public Space (25,117 names × 148 types = 122,524 relationships)
```

### Hungarian Address Format

**Components**:
- **PublicSpaceName**: Street name without type (e.g., "Kossuth Lajos")
- **PublicSpaceType**: Street type (e.g., "tér", "utca", "út", "köz")
- **HouseNumber**: Building number (may include ranges: "1-5")
- **Building**: Building letter or number (e.g., "A", "B", "1")
- **Staircase**: Entrance/staircase identifier (e.g., "L", "1" → "I.")

**Formatting Rules**:
1. Remove leading zeros from house numbers
2. Use "épület" (building) and "lépcsőház" (staircase) suffixes
3. Convert numeric staircases to Roman numerals (1 → I., 5 → V.)
4. End all addresses with period
5. Format ranges differently from simple numbers when building+staircase present

**Examples**:
- `"Kossuth Lajos tér 1."` (simple address)
- `"Kossuth Lajos tér 1/D."` (with building)
- `"Kossuth Lajos tér 1-5. B. épület L. lépcsőház"` (range with building and staircase)
- `"Berényi utca 9. 1. épület I. lépcsőház"` (Roman numeral staircase)

### Deduplication Logic

**Duplicate Detection**: Hash-based on formatted full address
- Hash components: `county_code | settlement_name | full_address`
- Deduplication rate: 0.39% (13,084 duplicates from 3,336,202 addresses)
- Formatting ensures correct duplicate detection

**Relationship Preservation**:
- Polling stations: Aggregated as comma-separated UUID v3 list
- PIR codes: Aggregated as comma-separated UUID v3 list
- Accessibility flag: Maximum value (prioritize accessible)
- Original address count: Tracked for transparency

### Export Formats

**CSV Export (DuckDB format)**:
- ID Format: xxhash64 hexadecimal strings
- Deterministic hash-based IDs for idempotency
- Settlement-partitioned files for efficient access
- UTF-8 encoding with proper Hungarian character support

**PostgreSQL Export**:
- ID Format: UUID v3 (DNS namespace: `oevk.hu`)
- Schema Translation: TEXT PRIMARY KEY → UUID PRIMARY KEY
- Files Generated:
  - `schema.sql` - PostgreSQL DDL with UUID types and trigram indexes
  - `data.sql` - INSERT statements with UUID v3 IDs and ON CONFLICT DO NOTHING
  - `oevk_db_{timestamp}.sql.gz` - Compressed pg_dump for production deployment
- Trigram GIN indexes on FullAddress for efficient text search
- Idempotent loading with conflict resolution

**PostgreSQL Naming Conventions**:
- **Table Names**: `snake_case` without prefixes (e.g., `address`, `polling_station`, `public_space_name`)
- **Column Names**: `snake_case` without table name prefixes (e.g., `id`, `county_id`, `settlement_id`, not `Address_ID` or `address_county_id`)
- **Foreign Keys**: Column name matches referenced column with `_id` suffix (e.g., `county_id` references `county(id)`)
- **Special Column Names** (Hungarian domain-specific abbreviations):
  - `NationalIndividualElectoralDistrict` tables/columns must use `oevk` (not `national_individual_electoral_district`)
  - `SettlementIndividualElectoralDistrict` tables/columns must use `tevk` (not `settlement_individual_electoral_district`)
  - Examples: `oevk_id` references `oevk(id)`, `tevk_id` references `tevk(id)`
- **Constraint Names**: Generated with pattern `{table}_{column}_{type}` (e.g., `address_county_id_fkey`, `address_oevk_id_fkey`)
- **Index Names**: Pattern `idx_{table}_{column(s)}` (e.g., `idx_address_county_id`, `idx_address_oevk_id`)
- All PostgreSQL CSV exports and database dumps must comply with these naming conventions

**UUID v3 Standard**:
- Namespace: `uuid.uuid3(uuid.NAMESPACE_DNS, 'oevk.hu')`
- All entity IDs converted to UUID v3 format for PostgreSQL
- Deterministic: Same input → Same UUID across runs
- Example: `32e85e9e-7bac-372b-bd74-7e8ca77025d1`

**Settlement Partitioning** (CSV only):
- Canonical addresses: `Address_{code}_{name}.csv` (1,341 files)
- Original addresses: `OriginalAddress_{code}_{name}.csv` (1,341 files)
- Unified directory: Both types in `{run_tag}_Address/` directory
- Benefits: Regional analysis, reduced file sizes, parallel processing

## PostgreSQL Integration

### Schema Translation

**Automated SQLite to PostgreSQL Conversion**:
- TEXT PRIMARY KEY → UUID PRIMARY KEY
- xxhash64 IDs → UUID v3 format
- Foreign key relationships preserved
- Trigram extensions for text search

**Generated Files**:
1. `schema.sql` - PostgreSQL DDL
2. `data.sql` - INSERT statements with ON CONFLICT DO NOTHING
3. `oevk_db_{timestamp}.sql.gz` - Compressed pg_dump

### Docker-Based Verification

**Automated Import Verification**:
```python
# Workflow:
1. Create temporary PostgreSQL container (postgres:16-alpine)
2. Import schema.sql using psql
3. Import data.sql using psql
4. Verify row counts match expectations
5. Create pg_dump with --clean --if-exists flags
6. Compress dump with gzip
7. Cleanup temporary container
```

**Docker Container Management**:
- `DockerPostgreSQLManager` class in `src/utils/docker_postgresql.py`
- Automatic container lifecycle (create, wait for ready, cleanup)
- Configurable ports and credentials
- Health check polling until PostgreSQL accepts connections

### Standalone Loader Script

**Features** (`src/release/templates/load_postgresql.py`):
- Automatic Docker PostgreSQL setup with `--docker` flag
- External database connection support
- Streaming for large files (>10MB) with progress indicators
- Environment variable configuration
- `--database` parameter for target database selection
- `--clean` option to truncate tables before loading
- `--drop-database` option for fresh start
- Idempotent loading with ON CONFLICT DO NOTHING

**Usage Examples**:
```bash
# Auto-create Docker database
python load_postgresql.py --docker

# Connect to existing database
python load_postgresql.py --host localhost --port 5432 --database oevk

# Fresh load with database recreation
python load_postgresql.py --docker --drop-database

# Clean load (truncate tables, keep schema)
python load_postgresql.py --docker --clean
```

### CLI Commands

**Database Setup** (`db setup`):
```bash
# Create Docker PostgreSQL and load data
python src/cli.py db setup

# Custom configuration
python src/cli.py db setup --container-name my-oevk --port 15432
```

**Export Control**:
```bash
# Export both CSV and PostgreSQL (default)
python src/cli.py run

# Skip PostgreSQL export (CSV only)
python src/cli.py run --skip-postgresql-export
```

## Important Constraints

### Performance Requirements

**NFR-002 Compliance**: Process 3M+ rows in under 30 minutes
- **Target**: ≤ 1,800 seconds (30 minutes)
- **Achieved**: ~150 seconds (2.5 minutes)
- **Margin**: 92% faster than requirement

**Memory Constraints**:
- DuckDB memory limit: 2GB (configurable)
- Stable memory usage: ~34MB throughout processing
- Chunked processing prevents memory spikes

**Parallel Processing**:
- Default: 4 worker threads
- Configurable via `MAX_WORKERS` environment variable
- Chunk size: 100,000 rows (configurable)

### Data Quality Requirements

**Referential Integrity**: 100% FK constraint satisfaction
- All foreign key relationships validated
- No orphaned records
- Cross-table consistency checks

**Idempotency**: Same input → Same output
- Deterministic hash IDs (xxhash64)
- Reproducible across runs
- Safe to re-run pipeline

**Data Preservation**:
- Hungarian diacritics preserved (UTF-8 encoding)
- Original casing maintained
- Empty strings converted to NULL
- Leading/trailing whitespace trimmed

### Technical Constraints

**Python Version**: 3.11+ (3.12.6 in use)
- Type hints required
- f-strings preferred for formatting
- Dataclasses for structured data

**Database**: DuckDB (embedded)
- Single-file storage
- Zero configuration
- ACID transactions
- Efficient analytical queries

**File Formats**:
- Input: JSON, CSV (UTF-8)
- Output: CSV (UTF-8, comma-delimited)
- Archives: ZIP compression

### Regulatory Constraints

**Data Source Authority**: Hungarian National Election Office
- Official source URLs (static.valasztas.hu)
- No modifications to source data
- Traceability via `Sequence` and `OriginalOrder` fields

**Data Privacy**: Public electoral data
- No personal information (only addresses)
- Publicly accessible data
- No GDPR concerns for address data

## External Dependencies

### Source Data APIs

**OEVK JSON** (National Electoral Districts):
- URL: `https://static.valasztas.hu/dyn/oevk_data/oevk.json`
- Format: JSON array of objects
- Size: ~108 records
- Fields: `maz` (county), `evk` (district), `centrum`, `poligon`
- Update frequency: Per election cycle

**Korzet ZIP** (Address Data):
- URL: `https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip`
- Format: ZIP containing single CSV file
- Size: ~3.3M records
- Encoding: UTF-8 with BOM
- Delimiter: Semicolon (`;`)
- Update frequency: Per election cycle

### GitHub Integration

**Release Workflow**:
- GitHub API via PyGithub 2.0.0+
- GitHub CLI (`gh`) for artifact uploads
- Authentication: Personal Access Token (classic tokens recommended)
- Permissions: `repo`, `workflow`, `read:org`

**Release Artifacts**:
1. CSV Archive (`oevk-data-csv-{tag}.zip`): All CSV files partitioned by settlement
2. Database Archive (`oevk-data-db-{tag}.zip`): Complete DuckDB database
3. PostgreSQL Archive (`oevk-postgresql-{tag}.zip`): PostgreSQL-compatible SQL files, gzipped dump, and loader script
4. Metadata: JSON with validation results and metrics

### Configuration Management

**Environment Variables** (Optional):
```bash
# Source URLs (defaults provided)
export OEVK_JSON_URL="https://static.valasztas.hu/dyn/oevk_data/oevk.json"
export KORZET_ZIP_URL="https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip"

# Processing (defaults: 100000, 4, true, -1)
export CHUNK_SIZE=50000
export MAX_WORKERS=8
export PARALLEL_PROCESSING="true"
export SAMPLE_SIZE=-1

# Database (defaults: 2GB, 4)
export DB_MEMORY_LIMIT="4GB"
export DB_THREADS=8

# Logging (default: INFO)
export LOG_LEVEL="DEBUG"

# GitHub (required for releases)
export GITHUB_TOKEN="ghp_your_classic_token_here"
```

**Sensible Defaults**: All settings have defaults, environment vars are optional overrides

---

## Quick Reference

### Common Commands

```bash
# Complete pipeline (CSV + PostgreSQL, default)
python src/cli.py run

# CSV export only (skip PostgreSQL)
python src/cli.py run --skip-postgresql-export

# Include original addresses in export
python src/cli.py run --export-original-addresses

# Disable deduplication
python src/cli.py run --no-deduplication

# Custom database and output
python src/cli.py run --db-path custom.db --output-dir exports/

# Specific stages only
python src/cli.py run --stages transform,export

# PostgreSQL database setup
python src/cli.py db setup --container-name oevk-postgres --port 15432

# Release workflow
export GITHUB_TOKEN="ghp_your_token"
python src/cli.py release create --repo-owner org --repo-name repo --auto

# Run tests (including PostgreSQL integration tests)
pytest tests/
pytest tests/contract/
pytest tests/integration/
pytest tests/integration/test_postgresql_export.py

# Code quality
ruff check .
ruff format .
mypy .
```

### Key Files

- `src/cli.py` - Command-line interface entry point
- `src/etl/transform_optimized.py` - Main transformation logic
- `src/etl/deduplicate.py` - Address deduplication
- `src/etl/export.py` - Multi-format export (CSV, PostgreSQL)
- `src/etl/export_canonical_v3.py` - UUID v3 canonical export with PostgreSQL support
- `src/etl/postgresql_verify.py` - PostgreSQL import verification
- `src/utils/docker_postgresql.py` - Docker PostgreSQL container management
- `src/utils/config.py` - Configuration management
- `src/release/workflow.py` - Release workflow orchestration
- `src/release/packaging.py` - Multi-format packaging (CSV, DB, PostgreSQL)
- `src/release/templates/load_postgresql.py` - Standalone PostgreSQL loader script
- `tests/contract/` - Contract tests (TDD)
- `tests/integration/` - Integration tests (including PostgreSQL)

### Architecture Diagram

```
┌─────────────────┐
│  Source Data    │ (JSON, ZIP/CSV)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Ingestion     │ (download, load staging)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Transformation  │ (normalize, deduplicate)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Public Spaces   │ (extract entities)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│           Export                    │
│  ┌─────────────┐  ┌───────────────┐│
│  │     CSV     │  │  PostgreSQL   ││
│  │  (xxhash64) │  │  (UUID v3)    ││
│  └─────────────┘  └───────────────┘│
└────────┬────────────────┬───────────┘
         │                │
         │                ▼
         │       ┌─────────────────┐
         │       │  Docker Verify  │ (psql import)
         │       └────────┬────────┘
         │                │
         │                ▼
         │       ┌─────────────────┐
         │       │   pg_dump.gz    │ (gzipped dump)
         │       └────────┬────────┘
         │                │
         ▼                ▼
┌─────────────────────────────────────┐
│            Release                  │
│  - CSV Archive (partitioned)        │
│  - DuckDB Archive                   │
│  - PostgreSQL Archive (SQL + dump)  │
└─────────────────────────────────────┘
```

---

**End of Project Context**
