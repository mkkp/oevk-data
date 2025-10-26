# OEVK Data Transformation Pipeline

A Python-based ETL pipeline for processing Hungarian electoral address data from authoritative sources into normalized, queryable datasets with partitioned exports and public space entity extraction.

## 🎉 Project Status: **COMPLETED SUCCESSFULLY**

**All Features Implemented and Production-Ready**
- ✅ Complete ETL pipeline with 11 normalized tables
- ✅ Public space entity extraction integrated
- ✅ Automated GitHub release workflow
- ✅ 98.6% performance improvement (183.6 min → 2.5 min)
- ✅ NFR-002 compliance achieved with significant margin

## Overview

This application transforms Hungarian electoral address data from two authoritative sources into a normalized relational model and exports CSV files for analysis. The pipeline handles:

- **Data Ingestion**: Download and load source data from JSON and ZIP/CSV formats
- **Data Transformation**: Normalize into 11 target tables with referential integrity
- **Public Space Extraction**: Extract public space entities (names and types) from addresses
- **Geocoding**: Geocode addresses and polling stations using Nominatim with SQLite caching (88.5% coverage)
- **Data Export**: Generate CSV files with partitioned address data by settlement
- **PostgreSQL Export**: Fast CSV-based import with UUID conversion and PostGIS support

### Key Features

- **Deterministic ID Generation**: MD5-based surrogate keys converted to UUID5 for PostgreSQL compatibility
- **Chunked Processing**: Efficient handling of 3M+ row datasets
- **Parallel Processing**: Multi-threaded chunk processing for optimal performance
- **Fast PostgreSQL Export**: CSV-based COPY method (10-50x faster than INSERT statements)
- **Progress Tracking**: Real-time progress with ETA for long-running operations
- **Structured Logging**: Comprehensive pipeline metrics and performance tracking
- **Configuration Management**: Environment-based configuration with sensible defaults
- **Data Validation**: Referential integrity and data quality checks
- **Partitioned Exports**: Address data split by settlement for efficient access
- **Public Space Extraction**: Automatic extraction of public space entities from addresses
- **Release Workflow**: Automated GitHub releases with compressed artifacts

## Pipeline Flow

The following diagram shows the complete data pipeline flow with all stages and how parameters affect the execution path:

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Ingest
    participant Transform
    participant Geocode
    participant Export
    participant DB as DuckDB
    participant Cache as SQLite Cache
    participant Nominatim
    participant PostgreSQL

    Note over User,PostgreSQL: STAGE 1: INGESTION
    User->>CLI: python -m src.cli run
    CLI->>Ingest: Download OEVK JSON
    Ingest->>DB: Load to staging_oevk
    CLI->>Ingest: Download TEVK ZIP/CSV
    Ingest->>DB: Load to staging_korzet
    Note right of Ingest: ~15 seconds<br/>2 API sources

    Note over User,PostgreSQL: STAGE 2: TRANSFORMATION
    CLI->>Transform: Deduplicate & Normalize
    Transform->>DB: Create 11 tables
    Note right of Transform: County (20)<br/>Settlement (3,177)<br/>CanonicalAddress (3.3M)<br/>PollingStation (8,547)<br/>PublicSpaces, etc.
    Transform->>DB: Apply FK constraints
    Note right of Transform: ~2-3 minutes<br/>Polars optimization

    Note over User,PostgreSQL: STAGE 3: GEOCODING (Conditional)
    alt NOMINATIM_ENABLED=true OR geocode run command
        CLI->>Geocode: Start geocoding
        Geocode->>Cache: Check SQLite cache
        Cache-->>Geocode: Return cached (2.9M)
        Note right of Cache: 88.5% cache hit rate
        
        alt Addresses not in cache (383K)
            Geocode->>Nominatim: Geocode batch
            Nominatim-->>Geocode: Coordinates + quality
            Geocode->>Cache: Store in cache
        end
        
        Geocode->>DB: Update CanonicalAddress
        Note right of Geocode: Latitude, Longitude<br/>GeocodingQuality<br/>GeocodingSource
        
        Geocode->>DB: Geocode PollingStations
        Note right of Geocode: Fuzzy matching<br/>to CanonicalAddress
    else NOMINATIM_ENABLED=false (default)
        CLI->>Geocode: --update-from-cache
        Geocode->>Cache: Load cached only
        Geocode->>DB: Update from cache
        Note right of Geocode: <1 minute<br/>No API calls
    end

    Note over User,PostgreSQL: STAGE 4: EXPORT
    CLI->>Export: Generate CSV files
    
    alt --tables-only flag
        Export->>DB: Export entity tables
        Note right of Export: County, Settlement,<br/>PollingStation, etc.
    else --addresses-only flag
        Export->>DB: Export addresses only
        Note right of Export: Partitioned by<br/>settlement (3,177 files)
    else Default (export all)
        Export->>DB: Export everything
    end
    
    Export->>Export: Convert MD5 to UUID5
    Note right of Export: PostgreSQL compatibility<br/>~76K rows/sec
    
    alt --skip-postgresql-export NOT set
        Export->>Export: Generate schema.sql
        Export->>Export: Generate import_postgresql.sql
        Note right of Export: Chunked COPY commands<br/>34 chunks for Address
        Export->>Export: Split large CSVs
        Note right of Export: 100K rows per chunk
    end
    
    Export-->>User: CSV files ready
    Note right of Export: ~1-2 minutes<br/>3.3M+ rows exported

    Note over User,PostgreSQL: STAGE 5: POSTGRESQL IMPORT (Optional)
    User->>CLI: db import-csv --docker
    
    alt --docker flag
        CLI->>PostgreSQL: Create Docker container
        CLI->>PostgreSQL: Create database + PostGIS
    else Local PostgreSQL
        CLI->>PostgreSQL: Connect to host
    end
    
    CLI->>PostgreSQL: Import schema.sql
    Note right of PostgreSQL: Tables, indexes,<br/>constraints created
    
    CLI->>PostgreSQL: Run import_postgresql.sql
    Note right of PostgreSQL: Chunked COPY commands<br/>with progress tracking
    
    loop For each chunk (34 for Address)
        PostgreSQL->>PostgreSQL: COPY 100K rows
        PostgreSQL-->>User: [X/34] Y% - Importing...
        Note right of PostgreSQL: ~25 sec per chunk
    end
    
    PostgreSQL->>PostgreSQL: COMMIT transaction
    
    PostgreSQL->>PostgreSQL: Populate PostGIS geometry
    Note right of PostgreSQL: Chunked UPDATE<br/>100K rows per batch<br/>ST_MakePoint() + cast
    
    loop For each geometry batch (~29 batches)
        PostgreSQL->>PostgreSQL: UPDATE 100K geometries
        PostgreSQL-->>User: Updated X addresses (total: Y)
        Note right of PostgreSQL: ~30-60 sec per batch
    end
    
    PostgreSQL->>PostgreSQL: BEGIN new transaction
    PostgreSQL->>PostgreSQL: Recreate FK constraints
    PostgreSQL->>PostgreSQL: COMMIT
    PostgreSQL-->>User: Import complete
    Note right of PostgreSQL: Total: ~25-35 minutes<br/>3.3M addresses + geometries
    
    Note over User,PostgreSQL: STAGE 6: VERIFICATION (Optional)
    User->>CLI: db verify
    CLI->>PostgreSQL: Create temp verify container
    Note right of PostgreSQL: Auto-finds available port<br/>(5433+)
    CLI->>PostgreSQL: Apply optimizations
    Note right of PostgreSQL: fsync=off, maintenance_work_mem=1GB<br/>autovacuum=off, etc.
    CLI->>PostgreSQL: Restart to apply settings
    CLI->>PostgreSQL: Import & verify data
    PostgreSQL->>PostgreSQL: Check row counts
    PostgreSQL-->>CLI: Verification results
    CLI->>PostgreSQL: Create pg_dump
    CLI->>CLI: Compress to .sql.gz
    CLI-->>User: Dump file created
    Note right of CLI: exports/oevk_db_YYYYMMDD_HHMMSS.sql.gz<br/>Uses pipeline run tag<br/>~145 MB compressed
    CLI->>PostgreSQL: Remove temp container
    Note right of PostgreSQL: Cleanup unless --no-cleanup

    Note over User,PostgreSQL: Key Parameters & Effects
    Note over User: --run-tag: Custom timestamp<br/>--skip-postgresql-export: Skip PostgreSQL files<br/>--export-original-addresses: Include OriginalAddress<br/>--max-workers: Parallel export threads<br/>--update-from-cache: Cache-only geocoding<br/>--docker: Use Docker PostgreSQL<br/>--drop-database: Recreate DB
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop (for geocoding with Nominatim)
- Git
- GitHub CLI (`gh`) - optional, for release workflow

### Complete Pipeline: From Zero to Release

This guide walks you through the complete process from initial setup to GitHub release.

#### Step 1: Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd oevk-data

# Install Python dependencies
pip install -r requirements.txt

# Optional: Create virtual environment first
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Step 2: Configure Environment (Optional)

```bash
# Copy environment template
cp .env.example .env

# Edit configuration if needed (defaults work for most cases)
# Key settings:
# - NOMINATIM_ENABLED=false (geocoding DISABLED by default, uses cache only)
# - To enable geocoding: set NOMINATIM_ENABLED=true or run 'python src/cli.py geocode run'
# - DATABASE_PATH=data/oevk.db
```

#### Step 3: Set Up Geocoding Service (One-Time, ~2 hours)

```bash
# Start Docker Desktop first, then:

# Download and import Hungary OSM data into Nominatim
python src/cli.py geocode setup

# This will:
# - Download ~286 MB of Hungary OSM data
# - Import data into Nominatim (takes 1-2 hours)
# - Start geocoding service on http://localhost:8081

# Monitor progress (optional)
docker logs -f oevk-nominatim

# Wait for message: "Nominatim service is ready!"
```

#### Step 4: Run Complete Pipeline (~3-5 minutes)

```bash
# Run complete ETL pipeline (geocoding disabled by default, uses cache only)
python src/cli.py run --run-tag $(date +%Y%m%d)

# This will:
# 1. Download source data from OEVK and TEVK APIs
# 2. Transform and normalize into 11 tables
# 3. Deduplicate addresses (3.3M+ → ~3.2M canonical)
# 4. Geocode canonical addresses (9-90 minutes first run)
# 5. Geocode polling stations with fuzzy search
# 6. Export CSV files (partitioned by settlement)
# 7. Generate PostgreSQL CSV files and fast import script

# Expected timing:
# - Ingest: 15 seconds
# - Transform: 2-3 minutes (Polars optimization)
# - Geocoding: <1 minute (cache-only by default)
# - Export: 1-2 minutes (includes CSV COPY generation)
# Total: ~3-5 minutes

# To enable full geocoding (12-30 minutes first run):
# python src/cli.py geocode run
```

#### Step 5: Verify Results

```bash
# Check geocoding statistics
python src/cli.py geocode status

# Expected output:
# === Canonical Address Geocoding Status ===
# Total addresses: 3,323,113
# Geocoded: 2,939,435 (88.5%)
# Not geocoded: 383,678
# 
# Quality distribution:
#   street: 2,330,060 (79.3%) - Street-level accuracy
#   exact: 586,484 (20.0%)    - Exact address match
#   settlement: 22,891 (0.8%)  - Settlement-level fallback
# 
# === Polling Station Geocoding Status ===
# Total polling stations: 8,547
# Geocoded: 0 (0.0%)
# Not geocoded: 8,547

# Check export directory
ls -lh exports/

# Should see:
# - 20XXXXXX_County.csv
# - 20XXXXXX_Settlement.csv
# - 20XXXXXX_Address/ (directory with 3,177 CSV files)
# - 20XXXXXX_PollingStation.csv
# - schema.sql (PostgreSQL schema)
# - data.sql (PostgreSQL INSERT statements)
```

#### Step 6: Test PostgreSQL Import (Optional)

**Option A: Simplified CLI Command (Recommended)**

```bash
# Import to Docker PostgreSQL with one command (creates container automatically)
python -m src.cli db import-csv --docker --drop-database

# This will:
# 1. Create Docker container 'oevk-postgresql' with PostGIS
# 2. Create database 'oevk' with PostGIS extension
# 3. Copy CSV files to container
# 4. Import schema
# 5. Import all CSV files with progress tracking
# 6. Verify import

# Progress output:
# INFO: Step 1/3: Copying files to Docker container...
# INFO: ✓ Copied exports to /tmp/exports in container
# INFO: Step 2/3: Importing schema...
# INFO: ✓ Schema imported successfully
# INFO: Step 3/3: Importing CSV data (47 files)...
# INFO: This may take 5-15 minutes for 3.3M addresses...
# INFO: Progress output will be shown below...
# [1/34] 2.9% - Importing Address: 100,000/3,323,113 rows
# COPY 100000
# Time: 25058.168 ms (00:25.058)
# [2/34] 5.9% - Importing Address: 200,000/3,323,113 rows
# ...
# INFO: ✓ CSV data imported successfully

# Verify import
docker exec oevk-postgresql psql -U oevk -d oevk -c "SELECT COUNT(*) FROM address;"
# Expected: 3,323,113

# Test spatial query on geocoded addresses
docker exec oevk-postgresql psql -U oevk -d oevk -c "
  SELECT COUNT(*) as addresses_within_1km
  FROM address
  WHERE ST_DWithin(
    geometry,
    ST_GeogFromText('POINT(19.0402 47.4979)'),
    1000
  );
"
```

**Option B: Verify Import and Create Dump**

The `db verify` command creates a temporary PostgreSQL container, imports your data, verifies row counts, creates a compressed dump file, then cleans up:

```bash
# Verify PostgreSQL import and create gzipped dump
python -m src.cli db verify

# This will:
# 1. Create temporary Docker container 'oevk-verify' on auto-selected port (5433+)
# 2. Apply performance optimizations (fsync=off, maintenance_work_mem=1GB, etc.)
# 3. Import schema.sql and all CSV files with progress tracking
# 4. Populate PostGIS GEOGRAPHY columns (chunked in 100K row batches)
# 5. Verify import by checking row counts for all tables
# 6. Create pg_dump and compress to .sql.gz (~145 MB)
# 7. Remove temporary container

# Expected output:
# INFO: Step 1/5: Creating Docker PostgreSQL container...
# INFO: Creating PostgreSQL container 'oevk-verify' (image: postgis/postgis:15-3.3, port: 5433)...
# INFO: Step 2/5: Waiting for PostgreSQL to be ready...
# INFO: PostgreSQL ready after 3.2s
# INFO: Step 3/5: Importing schema and CSV data...
# INFO: Applying performance optimizations for import...
# [1/34] 2.9% - Importing Address: 100,000/3,323,113 rows
# COPY 100000
# Time: 25058.168 ms (00:25.058)
# ...
# INFO: Populating PostGIS GEOGRAPHY for Address table in chunks...
# NOTICE: Updated 100000 addresses (total: 100000)
# NOTICE: Updated 100000 addresses (total: 200000)
# ...
# NOTICE: Completed: 2939435 addresses updated with PostGIS geometry
# INFO: Step 4/5: Verifying import...
# INFO:   Address: 3,323,113 rows
# INFO:   County: 19 rows
# INFO:   Settlement: 3,178 rows
# INFO: Verification successful: 3,500,000 total rows imported
# INFO: Step 5/5: Creating gzipped database dump...
# INFO: Dump created: exports/oevk_db_20251026_130300.sql.gz
# INFO:   Dump size: 145.3 MB (compressed)
# INFO: ✅ Verification completed successfully
# INFO: 📦 Dump file: exports/oevk_db_20251026_130300.sql.gz

# Options:
# --exports-dir: Path to exports directory (default: exports)
# --container-name: Custom container name (default: oevk-verify)
# --no-cleanup: Keep container running after verification

# Example with custom settings:
python -m src.cli db verify --container-name my-verify --no-cleanup

# Import the dump to another PostgreSQL instance:
gunzip -c exports/oevk_db_20251026_130300.sql.gz | \
  docker exec -i oevk-postgresql psql -U oevk -d oevk

# Note: Verification requires ~6-8GB disk space and takes 25-35 minutes
# If you encounter "No space left on device" errors, use --skip-postgresql-export
# during pipeline run, or import directly to a container with more storage
```

**Option C: Manual Import with psql**

```bash
# Set up local PostgreSQL with PostGIS
docker-compose up -d postgresql

# Wait for PostgreSQL to be ready
sleep 10

# Create database and enable PostGIS
psql -h localhost -p 5432 -U oevk -d postgres -c "CREATE DATABASE oevk_test;"
psql -h localhost -p 5432 -U oevk -d oevk_test -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Load schema
psql -h localhost -p 5432 -U oevk -d oevk_test -f exports/schema.sql

# Fast import using CSV COPY method (5-15 minutes with progress tracking)
cd exports
psql -h localhost -p 5432 -U oevk -d oevk_test -f import_postgresql.sql

# Verify import
psql -h localhost -p 5432 -U oevk -d oevk_test -c "SELECT COUNT(*) FROM Address;"
# Expected: 3,323,113
```

#### Step 7: Create GitHub Release

```bash
# Set GitHub token
export GITHUB_TOKEN="ghp_your_token_here"

# Validate data before release
python src/cli.py release validate \
  --staging-dir data/staging \
  --exports-dir exports

# Create release (auto-generates tag from latest export)
python src/cli.py release create \
  --repo-owner your-org \
  --repo-name oevk-data \
  --auto

# This will:
# 1. Find latest export directory
# 2. Generate release tag (YYYYMMDD-HHMM format)
# 3. Create compressed archives:
#    - settlements.tar.gz (counties, settlements, districts)
#    - addresses.tar.gz (canonical addresses by settlement)
#    - polling-stations.tar.gz (polling station data)
#    - postgresql.tar.gz (schema + data SQL files)
# 4. Upload to GitHub Releases
# 5. Generate release notes with statistics

# Check release status
python src/cli.py release status \
  --repo-owner your-org \
  --repo-name oevk-data \
  --tag <generated-tag>
```

### Quick Commands Reference

```bash
# Run full pipeline
python src/cli.py run --run-tag $(date +%Y%m%d)

# Run without geocoding (faster)
export NOMINATIM_ENABLED=false
python src/cli.py run --run-tag $(date +%Y%m%d)

# Run only geocoding (after pipeline)
python src/cli.py geocode run

# Check geocoding status
python src/cli.py geocode status

# Export data only (skip ingestion/transformation)
python src/cli.py export --run-tag $(date +%Y%m%d)

# Create release
python src/cli.py release create --repo-owner org --repo-name repo --auto
```

### Clean Data for Fresh Start

To completely reset and start fresh:

```bash
# Stop all services
docker-compose down

# Remove all data (WARNING: This deletes everything!)
rm -rf data/                    # All databases and staging files
rm -rf exports/                 # All export files
rm -rf logs/                    # All log files
rm -rf data/geocoding_cache/    # Geocoding cache

# Remove Docker volumes (Nominatim data)
docker volume rm oevk-data_nominatim_data
docker volume rm oevk-data_postgresql_data

# Recreate data directories
mkdir -p data/staging
mkdir -p exports
mkdir -p logs

# Start fresh - set up geocoding again
python src/cli.py geocode setup

# Run pipeline from scratch
python src/cli.py run --run-tag $(date +%Y%m%d)
```

### Partial Data Cleanup

Clean only specific components:

```bash
# Clean only database (keep exports)
rm -f data/oevk.db
python src/cli.py run --run-tag $(date +%Y%m%d)

# Clean only exports (keep database)
rm -rf exports/*
python src/cli.py export --run-tag $(date +%Y%m%d)

# Clean only geocoding cache (re-geocode everything)
rm -rf data/geocoding_cache/*
python src/cli.py geocode run

# Clean only staging files (re-download sources)
rm -rf data/staging/*
python src/cli.py run --stages ingest --run-tag $(date +%Y%m%d)

# Reset Nominatim (re-import OSM data)
docker-compose down
docker volume rm oevk-data_nominatim_data
python src/cli.py geocode setup --force-reimport
```

### Incremental Update Workflow

For daily/weekly updates without starting from scratch:

```bash
# 1. Run pipeline with new data
python src/cli.py run --run-tag $(date +%Y%m%d)

# 2. Only new addresses will be geocoded (cache reused)
#    Expected time: 5-10 minutes instead of 90 minutes

# 3. Create release with new tag
python src/cli.py release create \
  --repo-owner your-org \
  --repo-name oevk-data \
  --auto

# 4. Previous releases remain available on GitHub
```

### Troubleshooting Quick Start

**Issue: Geocoding is slow**
```bash
# Increase batch size
export NOMINATIM_BATCH_SIZE=500
python src/cli.py geocode run --batch-size 500
```

**Issue: Nominatim won't start**
```bash
# Check Docker
docker ps -a | grep nominatim
docker logs oevk-nominatim

# Restart service
docker-compose restart nominatim

# Force reimport if corrupted
python src/cli.py geocode setup --force-reimport
```

**Issue: Out of disk space**
```bash
# Check disk usage
du -sh data/ exports/

# Clean old exports (keep last 3)
ls -dt exports/20* | tail -n +4 | xargs rm -rf

# Clean old logs
find logs/ -name "*.log" -mtime +30 -delete
```

**Issue: Database locked**
```bash
# Close any open database connections
lsof data/oevk.db  # Check what's using the database
kill <PID>          # Kill the process

# Or simply restart
rm data/oevk.db
python src/cli.py run --run-tag $(date +%Y%m%d)
```

### Performance Tips

**First Run Optimization:**
```bash
# Use SSD for data directory
# Increase Docker memory (8GB+ recommended)
# Use larger batch size for geocoding
export NOMINATIM_BATCH_SIZE=200
```

**Subsequent Runs:**
```bash
# Cache hit rate >90% means:
# - First run: 90 minutes
# - Second run: 5 minutes
# Don't clear cache unless necessary!
```

**Production Settings:**
```bash
# .env file for production
NOMINATIM_BATCH_SIZE=200          # Faster geocoding
DATABASE_PATH=data/oevk.db        # Persistent database
NOMINATIM_CACHE_DIR=data/cache    # Persistent cache
LOG_LEVEL=INFO                    # Less verbose logging
```

### Directory Structure

```
oevk-data/
├── src/                    # Source code
│   ├── etl/               # ETL modules (ingest, transform, export)
│   ├── database/          # Database connection and schema
│   ├── release/           # Release workflow modules
│   └── utils/             # Utilities (config, logging, validation)
├── tests/                 # Test suites
│   ├── contract/          # Contract tests
│   ├── integration/       # Integration tests
│   └── unit/              # Unit tests
├── data/                  # Data directories
│   ├── staging/           # Raw source data
│   ├── export/            # Final CSV exports
│   └── database/          # DuckDB database files
├── logs/                  # Application logs
└── specs/                 # Specifications and documentation
```

## Usage

### Running the Transform Locally

To run the complete data transformation pipeline locally:

```bash
# Run complete pipeline with default settings (canonical addresses only)
python -m src.cli run

# Run with custom database and output directories
python -m src.cli run --db-path data/oevk.db --output-dir exports/ --staging-dir data/staging/

# Run only specific stages
python -m src.cli run --stages ingest,transform,export
python -m src.cli run --stages transform  # Only transformation stage

# Export original addresses for debugging/analysis
python -m src.cli run --export-original-addresses

# Run with custom run tag
python -m src.cli run --run-tag $(date +%Y%m%d_%H%M%S)

# Disable deduplication
python -m src.cli run --no-deduplication

# Show all available options
python -m src.cli run --help
```

### Windows Compatibility

The export system supports both Unix symlinks and Windows-compatible file copies:

```bash
# Auto-detection (default behavior)
# - Windows: Creates file copies
# - Unix/macOS: Creates symlinks
python -m src.cli export

# Force file copies (Windows-compatible, uses more disk space)
python -m src.cli export --use-copies

# Force symlinks (Unix/macOS only, saves disk space)
python -m src.cli export --use-symlinks
```

**How it works:**
- **Symlinks (Unix/macOS)**: Creates symbolic links from canonical names (`Addresses`, `Settlements.csv`) to timestamped files
- **Copies (Windows)**: Copies timestamped files to canonical names for Windows compatibility
- **Manifest file**: Creates `export_manifest.json` tracking the export method and file mappings

**Note**: The Addresses directory contains 3,177 CSV files (~100MB). Using `--use-copies` will duplicate this data.

### Release Workflow

The project includes a comprehensive release workflow for publishing processed data to GitHub releases:

#### Data Validation

```bash
# Validate release data before creating release
python -m src.cli release validate --staging-dir data/staging --exports-dir exports

# Validate with custom directories
python -m src.cli release validate --staging-dir /path/to/staging --exports-dir /path/to/exports
```

#### Release Creation

```bash
# Set GitHub token (required)
export GITHUB_TOKEN="ghp_your_token_here"

# Create release with auto-generated tag
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto

# Create release with specific tag
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag 20250101-1200

# Create draft release for review
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --draft

# Create prerelease (beta/alpha)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --prerelease

# Force overwrite existing release
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag existing-tag --force

# Create packages without uploading to GitHub (local testing)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --skip-upload
```

#### Release Management

```bash
# Check release status
python -m src.cli release status --repo-owner your-org --repo-name oevk-data --tag 20250101-1200

# List recent releases
python -m src.cli release history --repo-owner your-org --repo-name oevk-data --limit 10

# Get detailed release information
python -m src.cli release info --repo-owner your-org --repo-name oevk-data --tag 20250101-1200
```

#### Environment Variables

```bash
# GitHub Personal Access Token (required for releases)
export GITHUB_TOKEN="ghp_your_token_here"

# Optional: Custom directories
export STAGING_DIR="/path/to/staging"
export EXPORTS_DIR="/path/to/exports"
```

### PostgreSQL Export and Database Setup

The pipeline supports exporting canonical (cleansed/deduplicated) data to PostgreSQL format:

#### Automatic PostgreSQL Export

```bash
# Export generates both CSV and PostgreSQL SQL files by default
python src/cli.py export

# This creates:
# - exports/*.csv (CSV files with canonical addresses)
# - exports/schema.sql (PostgreSQL DDL with UUID types and trigram indexes)
# - exports/postgresql/*.csv (CSV files optimized for PostgreSQL COPY command)
# - exports/import_postgresql.sql (Fast COPY-based import script - RECOMMENDED)
# - exports/data_legacy.sql (Legacy INSERT statements - for compatibility only)
```

**PostgreSQL Export Structure:**
- **Canonical Data Only**: Exports cleansed, deduplicated addresses (not raw transformation data)
- **13 Tables**: Entity tables + canonical Address table + reference tables
- **UUID5 Format**: All ID columns converted from MD5 hex to UUID5 format for PostgreSQL compatibility
- **No Internal Tables**: AddressMapping, DeduplicationReport, Address_new excluded
- **OriginalAddressCount**: Track how many original addresses map to each canonical address

**Two Import Methods:**

1. **Fast CSV COPY Method (RECOMMENDED)** - 10-50x faster
   - Uses PostgreSQL's `\copy` command for bulk data loading
   - Import time: **2-5 minutes** for 3.3M addresses (vs 60+ minutes with INSERT)
   - Files: `postgresql/*.csv` + `import_postgresql.sql`
   - UUID5 conversion done during export (no performance penalty during import)
   - Optimized single-query export with progress tracking
   - Best for: Initial loads, production deployments, large datasets

2. **Legacy INSERT Method** - Disabled by default
   - Row-by-row INSERT statements (no longer generated)
   - Previously: 30-120 minutes for 3.3M addresses
   - Replaced by CSV COPY method for 10-50x speed improvement
   - Note: Legacy data.sql generation has been removed in favor of fast CSV import

#### Fast PostgreSQL Import (CSV COPY Method)

The recommended method uses PostgreSQL's `\copy` command for 10-50x faster data loading with optimized export:

```bash
# Step 1: Create database and install PostGIS
createdb oevk_data
psql -d oevk_data -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Step 2: Load schema (includes UUID types and indexes)
psql -d oevk_data -f exports/schema.sql

# Step 3: Fast import using CSV COPY (2-5 minutes)
cd exports
psql -d oevk_data -f import_postgresql.sql

# Verify import
psql -d oevk_data -c "SELECT COUNT(*) FROM Address;"
#  count  
# ---------
#  3323113

# Verify UUID format
psql -d oevk_data -c "SELECT ID, CountyCode, SettlementName FROM Address LIMIT 3;"
#                  id                  | countycode | settlementname 
# -------------------------------------+------------+----------------
#  bf6eba22-228c-54bb-9b65-851efd03bc6b | 10         | Ostoros
#  32167d15-0b78-5053-8d4c-8326c1cc6f25 | 12         | Komárom
```

**How It Works:**
1. Exports all tables to CSV files with UUID5 conversion in `postgresql/` directory
2. Converts MD5 hex IDs to UUID5 format during export (single-query optimization)
3. Generates optimized import script with performance tuning
4. Uses `\copy` command for client-side bulk loading (no superuser needed)
5. Handles PostGIS geometries via temporary WKT columns
6. Populates GEOGRAPHY columns for geocoded coordinates
7. Runs ANALYZE for query optimization

**Export Performance:**
- Single-query fetch: ~120 seconds for 3.3M rows
- Python-side UUID5 conversion: ~60 seconds
- Total export time: **~3-5 minutes** (vs 60+ minutes with old method)
- Progress tracking with ETA for visibility

**Performance Comparison:**

| Method | Export Time | Import Time | Total Time | Speed |
|--------|-------------|-------------|------------|-------|
| CSV COPY (optimized) | 3-5 min | 2-5 min | **5-10 min** | ✅ Recommended |
| Legacy INSERT (disabled) | 60+ min | 30-120 min | 90-180 min | Removed |

**CSV COPY Features:**
- ✅ No superuser privileges required (`\copy` is client-side)
- ✅ Transaction-wrapped for atomicity
- ✅ Performance optimizations (maintenance_work_mem, synchronous_commit)
- ✅ Handles NULL values correctly
- ✅ PostGIS geometry conversion (WKT → GEOMETRY)
- ✅ Progress indicators and timing
- ✅ Foreign key dependency ordering
- ✅ Automatic ANALYZE for statistics

#### Local PostgreSQL Database Setup

```bash
# Setup local PostgreSQL in Docker (uses 'oevk' for db/user/password)
python src/cli.py db setup

# Force recreate (drops and recreates container)
python src/cli.py db setup --force-recreate

# Custom script locations
python src/cli.py db setup --ddl-script /path/to/schema.sql --dml-script /path/to/data.sql
```

**Default Configuration:**
- Host: `localhost`
- Port: `15432`
- Database: `oevk`
- User: `oevk`
- Password: `oevk`
- Container: `oevk`

**Memory-Efficient Loading:**
The setup command uses PostgreSQL's native `psql` tool via Docker for loading large DML files (2.2GB+), avoiding memory allocation errors. The process:
1. Executes DDL script using psycopg2 (small schema file)
2. Copies large DML file into Docker container
3. Loads data using `psql -f` which streams efficiently
4. Cleans up temporary files automatically

**Note:** Loading 2.2GB of data may take several minutes depending on your system's performance.

**Connect to database:**
```bash
psql -h localhost -p 15432 -U oevk -d oevk
```

**Environment Variables:**
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=15432
export POSTGRES_DB=oevk
export POSTGRES_USER=oevk
export POSTGRES_PASSWORD=oevk
```

#### PostgreSQL Features

- **UUID5 Primary Keys**: All ID columns converted from MD5 hex to UUID5 format with OEVK namespace
- **Trigram Text Search**: GIN indexes on `FullAddress` for efficient substring searches
- **PostGIS Support**: Native geospatial data for OEVK boundaries and center points
- **Fast CSV COPY**: Client-side bulk loading without superuser privileges
- **Performance**: 100K+ rows/sec import throughput, 3-5 min export time
- **Progress Tracking**: Real-time export progress with batch-level ETA
- **AddressFullView**: Denormalized view joining all address and foreign key tables

#### PostGIS Geospatial Support

The pipeline includes built-in support for PostGIS extension, enabling native geospatial queries on OEVK (National Individual Electoral District) boundary polygons and center points.

**Features:**

- **Native GEOMETRY Types**: `GEOMETRY(POINT, 4326)` for center points, `GEOMETRY(POLYGON, 4326)` for boundaries
- **Spatial Indexes**: GiST indexes for fast spatial queries (~1000x faster than TEXT-based searches)
- **Automatic Coordinate Conversion**: Converts from source "lat lon" format to PostGIS "(lon, lat)" WKT format
- **SRID 4326**: Uses WGS 84 coordinate reference system (standard GPS coordinates)
- **GIS Tool Integration**: Direct import into QGIS, ArcGIS, and other GIS applications

**Configuration:**

```bash
# Enable PostGIS (default)
export POSTGRESQL_USE_POSTGIS=true

# Disable for backward compatibility with TEXT columns
export POSTGRESQL_USE_POSTGIS=false
```

**Docker Setup with PostGIS:**

```bash
# Use provided docker-compose.yml with PostGIS image
docker-compose up -d

# This starts PostgreSQL 15 with PostGIS 3.3 extension
# Database: oevk_data
# User: oevk_user
# Port: 5432
```

**Example Spatial Queries:**

```sql
-- Find OEVK containing a GPS coordinate (point-in-polygon)
SELECT OEVK, Name
FROM NationalIndividualElectoralDistrict
WHERE ST_Contains(Polygon, ST_SetSRID(ST_MakePoint(19.0402, 47.4979), 4326));

-- Calculate distance between OEVK centers (in kilometers)
SELECT 
    a.OEVK, b.OEVK,
    ST_Distance(
        ST_Transform(a.Center, 3857), 
        ST_Transform(b.Center, 3857)
    ) / 1000 as distance_km
FROM NationalIndividualElectoralDistrict a, 
     NationalIndividualElectoralDistrict b
WHERE a.ID != b.ID
LIMIT 10;

-- Calculate OEVK area in square kilometers
SELECT OEVK, Name,
    ST_Area(ST_Transform(Polygon, 3857)) / 1000000 as area_km2
FROM NationalIndividualElectoralDistrict
ORDER BY area_km2 DESC;

-- Find adjacent OEVKs (sharing a boundary)
SELECT a.OEVK, b.OEVK
FROM NationalIndividualElectoralDistrict a
CROSS JOIN NationalIndividualElectoralDistrict b
WHERE a.ID < b.ID AND ST_Touches(a.Polygon, b.Polygon);
```

**Performance Benefits:**

| Query Type | Without PostGIS (TEXT) | With PostGIS (GEOMETRY) | Speedup |
|------------|----------------------|------------------------|---------|
| Point-in-polygon | ~5000ms (full scan) | ~5ms (GiST indexed) | **1000x** |
| Distance calculation | ~3000ms | ~3ms | **1000x** |
| Bounding box query | ~4000ms | ~2ms | **2000x** |

For detailed PostGIS implementation documentation, see [docs/010_ADD_POSTGIST_SUPPORT.md](docs/010_ADD_POSTGIST_SUPPORT.md).

**AddressFullView:**

The schema includes a comprehensive view that joins the `Address` table with all foreign key tables, providing a denormalized representation of the data:

```sql
-- View structure (28 columns)
CREATE OR REPLACE VIEW AddressFullView AS
SELECT
    -- Primary and foreign keys
    a.ID AS address_id,
    c.ID AS county_id,
    s.ID AS settlement_id,
    oevk.ID AS national_individual_electoral_district_id,
    tevk.ID AS settlement_individual_electoral_district_id,
    ps.ID AS polling_station_id,
    pc.ID AS postal_code_id,
    
    -- Human-readable data (new model naming convention)
    c.CountyCode AS county_code,
    c.CountyName AS county_name,
    s.SettlementCode AS settlement_code,
    s.SettlementName AS settlement_name,
    oevk.OEVK AS oevk_code,
    oevk.Name AS oevk_name,
    tevk.TEVK AS tevk_code,
    tevk.Name AS tevk_name,
    ps.PollingStationAddress AS polling_station_address,
    pc.PostalCode AS postal_code,
    a.PublicSpaceName AS public_space_name,
    a.PublicSpaceType AS public_space_type,
    a.HouseNumber AS house_number,
    a.Building AS building,
    a.Staircase AS staircase,
    a.FullAddress AS full_address,
    -- ... and more
FROM Address a
JOIN County c ON a.County_ID = c.ID
JOIN Settlement s ON a.Settlement_ID = s.ID
-- ... additional joins
```

**Example queries using AddressFullView:**
```sql
-- Substring search (case-insensitive)
SELECT * FROM AddressFullView WHERE full_address ILIKE '%Budapest%';

-- Find addresses by settlement
SELECT address_id, full_address, postal_code
FROM AddressFullView
WHERE settlement_name = 'Budapest I';

-- Search by street name and type
SELECT * FROM AddressFullView 
WHERE public_space_name = 'Dózsa' 
  AND public_space_type = 'utca';

-- Get all foreign key IDs for integration
SELECT address_id, county_id, settlement_id, polling_station_id
FROM AddressFullView
WHERE postal_code = '1014';
```

#### Standalone PostgreSQL Loader

Release packages include a standalone Python loader script with enhanced features:

```bash
# Extract release ZIP
unzip oevk-postgresql-v*.zip
cd oevk-postgresql-v*/

# Install dependencies
pip install -r requirements.txt

# Option 1: Auto-create Docker PostgreSQL
python load_postgresql.py --docker

# Option 2: Load to existing database
python load_postgresql.py --host localhost --port 5432 --db mydb --user myuser

# Option 3: Fresh load with performance optimization (removes ON CONFLICT clauses)
python load_postgresql.py --docker --drop-database

# Option 4: Clean existing data (truncate tables)
python load_postgresql.py --docker --clean

# Option 5: Custom chunk size for memory-constrained environments
python load_postgresql.py --docker --chunk-size 4096
```

**Loader Features:**
- **Automatic Docker Setup**: Creates and starts PostgreSQL container if needed
- **Port Conflict Detection**: Automatically detects and handles port conflicts
- **Progress Tracking**: Shows progress percentage, execution count, and ETA
- **Performance Mode**: Strips `ON CONFLICT DO NOTHING` for fresh loads (10-100x faster)
- **Memory Efficient**: Streams large files (2GB+) without loading into memory
- **Error Tracking**: Groups and counts error types with detailed summaries
- **Idempotent**: Safe to re-run multiple times with `ON CONFLICT DO NOTHING`
- **Three Processing Modes**:
  - Small files (<10MB): Direct load
  - Medium files (10-100MB): Streaming with progress
  - Large files (>100MB): Statement-by-statement batch execution

**Performance Notes:**
- For production loads of large files (>100MB), use `psql` directly for 10-100x speed:
  ```bash
  psql -h localhost -p 15432 -U oevk -d oevk -f data.sql
  ```
- Python loader is ideal for development, testing, and automated deployments
- Use `--drop-database` or `--clean` flags for optimal performance on fresh loads

### Pipeline Stages

The pipeline consists of six main stages:

1. **Ingest**: Download source data and load into staging tables
2. **Transform**: Process staging data into normalized target tables
3. **Public Space Extraction**: Extract public space entities from addresses
4. **Export**: Generate CSV and PostgreSQL SQL files from target tables
5. **Database Setup**: Load data into local PostgreSQL instance (optional)
6. **Release**: Package and publish data to GitHub releases

### Release Workflow Stages

The release workflow provides automated GitHub releases:

1. **Data Validation**: Comprehensive pre-release checks for data integrity
2. **Package Creation**: Compress CSV and database files into release artifacts
3. **GitHub Integration**: Create releases with proper metadata and assets
4. **Release Management**: Status checking, history, and information retrieval

### Transformation Stage Details

When running the transformation stage locally, the pipeline:

- **Processes 3M+ rows** from staging data
- **Creates 11 normalized tables** with referential integrity
- **Extracts public space entities** (25,117 names, 148 types, 122,524 relationships)
- **Generates deterministic hash IDs** using MD5 (first 16 chars for compatibility)
- **Handles conflicts** with `ON CONFLICT DO UPDATE` for idempotent processing
- **Uses parallel processing** with ThreadPoolExecutor for optimal performance
- **Tracks performance metrics** including timing and row counts
- **Validates NFR-002 compliance** (30-minute processing target)

### Expected Output

After successful transformation, you should see:

```
County: 20 rows
Settlement: 3,177 rows  
NationalIndividualElectoralDistrict: 106 rows
SettlementIndividualElectoralDistrict: 4,677 rows
PollingStation: 8,555 rows
Address: 3,336,202 rows (original)
CanonicalAddress: 3,323,118 rows (deduplicated with 0.39% reduction)
PostalCode: 3,106 rows
PostalCode_Settlement: 3,106 rows
PublicSpaceName: 25,117 rows
PublicSpaceType: 148 rows
SettlementPublicSpaces: 122,524 rows
```

### Release Artifacts

Each release creates four main artifacts:

1. **CSV Archive** (`oevk-data-csv-{tag}.zip`): Contains all CSV files
   - `{run_tag}_Address/` - Directory containing address files split by settlement:
     - `Address_001_Aba.csv` - **Canonical deduplicated addresses** (UUID v3 format)
     - `OriginalAddress_001_Aba.csv` - All original addresses with canonical references
   - `Settlements.csv` - Settlement information
   - `Counties.csv` - County data
   - `polling_stations.csv` - Polling station details
   - `electoral_districts.csv` - Electoral district information
   - `PublicSpaceName.csv` - 25,117 unique public space names
   - `PublicSpaceType.csv` - 148 unique public space types
   - `SettlementPublicSpaces.csv` - 122,524 settlement-public space relationships

2. **Database Archive** (`oevk-data-db-{tag}.zip`): Contains main transformed database
   - `oevk.db` - Complete relational database with all tables including public space entities and canonical addresses

3. **PostgreSQL Archive** (`oevk-postgresql-{tag}.zip`): PostgreSQL-ready package with standalone loader
   - `schema.sql` - PostgreSQL DDL with UUID types and trigram indexes (11 KB)
   - `data.sql` - PostgreSQL DML with idempotent INSERT statements (~40 MB)
   - `load_postgresql.py` - Standalone Python loader script with Docker support
   - `requirements.txt` - Python dependencies (psycopg2-binary)
   - `README.md` - Quick start guide and usage examples

4. **Geocoding Cache Archive** (`oevk-geocoding-cache-{tag}.zip`): Pre-built geocoding cache for fast imports
   - `geocoding_cache.db` - SQLite database with 2.9M+ cached geocoding results (2.1 MB)
   - `README.md` - Cache statistics, usage instructions, and integration guide
   - **Purpose**: Enables instant coordinate population without running Nominatim
   - **Usage**: Download and use with `--update-from-cache` flag
   - **Cache Stats**: 88.5% coverage, 17.6% exact, 70.1% street-level quality

### Address Export Format

The pipeline exports addresses in two formats. **By default, only canonical addresses are exported.** Use `--export-original-addresses` to also export original addresses.

#### Canonical Addresses (Deduplicated) - Always Exported
- **Files**: `Address_{settlement_code}_{settlement_name}.csv`
- **IDs**: UUID v3 with 'oevk.hu' namespace
- **Structure**: Same as OriginalAddress + `OriginalAddressCount` column
- **Content**: Only unique canonical addresses (one per unique formatted address)
- **Columns** (16 total):
  1. `ID` - Canonical address UUID v3
  2. `Sequence` - Minimum sequence from merged addresses
  3. `OriginalOrder` - Minimum original order from merged addresses
  4. `FullAddress` - Formatted Hungarian address (e.g., "Ady Endre utca 1.")
  5. `PublicSpaceName` - Street name without type (e.g., "Ady Endre")
  6. `PublicSpaceType` - Street type from original address (e.g., "utca", "út", "tér")
  7. `HouseNumber` - House number with leading zeros (e.g., "000001")
  8. `Building` - Building identifier from original address (cleaned: zero-only → empty string)
  9. `Staircase` - Staircase identifier from original address (cleaned: zero-only → empty string)
  10. `PostalCode_ID` - Postal code UUID v3
  11. `PollingStation_ID` - Polling station UUID v3
  12. `SettlementIndividualElectoralDistrict_ID` - TEVK UUID v3
  13. `County_ID` - County UUID v3
  14. `Settlement_ID` - Settlement UUID v3
  15. `NationalIndividualElectoralDistrict_ID` - OEVK UUID v3
  16. **`OriginalAddressCount`** - Number of original addresses merged into this canonical address

- **Field Cleaning Rules**:
  - `PublicSpaceType`, `Building`, `Staircase`: Retrieved from original Address records via `AddressMapping` join
  - `Building`/`Staircase` zero-only cleaning: Values containing only zeros (`'0'`, `'00'`, `'000'`) converted to empty string
  - NULL handling: NULL/empty values exported as empty strings in CSV

- **Example**:
  ```csv
  ID,Sequence,OriginalOrder,FullAddress,PublicSpaceName,PublicSpaceType,HouseNumber,Building,Staircase,PostalCode_ID,PollingStation_ID,SettlementIndividualElectoralDistrict_ID,County_ID,Settlement_ID,NationalIndividualElectoralDistrict_ID,OriginalAddressCount
  32e85e9e-7bac-372b-bd74-7e8ca77025d1,3644,1103644,Ady Endre utca 1.,Ady Endre,utca,000001,,,4381f027-c7e3-3d1c-98fd-5d4f518aabdc,77b6993d-1a44-3ab5-b6a2-4397fded9596,9cad8436-1c1b-3f88-ad0d-6523a7617cfb,826cb982-9964-30d5-ab9d-b6a68d56e999,e62e407d-5ada-397a-8481-1368e54828d0,3a8239cb-cd9b-34fb-9f1b-a2344ba602fb,1
  8f3a1b2c-4d5e-3f6a-9b8c-7d6e5f4a3b2c,3646,1103646,Körtöltés utca 1/D.,Körtöltés,utca,000001,D,,4381f027-c7e3-3d1c-98fd-5d4f518aabdc,77b6993d-1a44-3ab5-b6a2-4397fded9596,9cad8436-1c1b-3f88-ad0d-6523a7617cfb,826cb982-9964-30d5-ab9d-b6a68d56e999,e62e407d-5ada-397a-8481-1368e54828d0,3a8239cb-cd9b-34fb-9f1b-a2344ba602fb,1
  ```

#### Original Addresses (All Records) - Optional Export
- **Files**: `OriginalAddress_{settlement_code}_{settlement_name}.csv`
- **Export**: Use `--export-original-addresses` CLI flag to enable
- **IDs**: UUID v3 with 'oevk.hu' namespace
- **Structure**: Standard address structure with `CanonicalAddress_ID` reference
- **Content**: All original addresses with references to their canonical address
- **Purpose**: Debugging and comparison with deduplicated data
- **Key difference**: Has `CanonicalAddress_ID` instead of `OriginalAddressCount`
- **Note**: Only export if needed for analysis as it creates large files (3.3M records)

#### Canonical Address Export Structure

Visual representation of the canonical address export with field retrieval:

```mermaid
flowchart LR
    subgraph CA[CanonicalAddress Table]
        CA1[ID<br/>CountyCode<br/>SettlementName<br/>FullAddress<br/>StreetName<br/>HouseNumber]
    end
    
    subgraph AM[AddressMapping]
        AM1[OriginalAddressID<br/>CanonicalAddressID]
    end
    
    subgraph OA[Original Address]
        OA1[PublicSpaceType<br/>Building<br/>Staircase<br/>Foreign Keys]
    end
    
    subgraph Export[CSV Export - 16 Columns]
        E1[ID UUID v3]
        E2[Sequence, OriginalOrder]
        E3[FullAddress]
        E4[PublicSpaceName, PublicSpaceType]
        E5[HouseNumber]
        E6[Building, Staircase<br/>cleaned: '0' → '']
        E7[Foreign Key UUIDs<br/>PostalCode, PollingStation, etc.]
        E8[OriginalAddressCount]
    end
    
    CA --> AM
    AM --> OA
    CA --> Export
    OA --> Export
    
    style E6 fill:#ffffcc
    style Export fill:#e6f3ff
```

**Key Points:**
- Fields from CanonicalAddress: ID, FullAddress, PublicSpaceName, HouseNumber
- Fields from Original Address (via AddressMapping): PublicSpaceType, Building, Staircase, Foreign Keys
- Building/Staircase cleaning: Zero-only values (`'0'`, `'00'`, `'000'`) → empty string
- All IDs converted to UUID v3 with 'oevk.hu' namespace

### Release Performance Targets

- **Complete Workflow**: ≤15 minutes for full release process
- **Data Validation**: ≤2 minutes for comprehensive checks
- **Package Creation**: ≤5 minutes for artifact compression
- **GitHub Integration**: ≤3 minutes for release creation
- **Idempotent Operations**: Safe to retry failed operations

### Performance Monitoring

The pipeline includes comprehensive performance tracking:

- **Step timing**: Individual stage durations
- **Row counts**: Records processed per stage
- **Processing rate**: Rows per second
- **Parallel processing metrics**: Chunk completion times and worker utilization
- **NFR-002 validation**: 30-minute target compliance check

Example output:
```
=== PIPELINE PERFORMANCE SUMMARY ===
Total duration: 150.5 seconds
Total rows processed: 3,336,202
Processing rate: 22,166.78 rows/second
✅ NFR-002 COMPLIANT: Pipeline completed in 150.5s (target: ≤1800s)
```

### Configuration

Configuration is managed through `src/utils/config.py` and can be customized via environment variables:

```bash
# Source URLs
export OEVK_JSON_URL="https://static.valasztas.hu/dyn/oevk_data/oevk.json"
export KORZET_ZIP_URL="https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip"

# Processing settings
export CHUNK_SIZE=50000
export MAX_WORKERS=4
export PARALLEL_PROCESSING="true"
export SAMPLE_SIZE=-1  # -1 for all data

# Database settings
export DB_MEMORY_LIMIT="2GB"
export DB_THREADS=4

# Logging settings
export LOG_LEVEL="INFO"

# Export settings
export INCLUDE_PARTITIONED_ADDRESSES="true"
export INCLUDE_CONSOLIDATED_ADDRESSES="true"

# Release workflow settings
export GITHUB_TOKEN="ghp_your_token_here"  # Required for releases
export STAGING_DIR="data/staging"
export EXPORTS_DIR="exports"
```

### Output Structure

After successful execution, the export directory will contain:

```
data/export/{RUN_TAG}/
├── {RUN_TAG}_County.csv
├── {RUN_TAG}_Settlement.csv
├── {RUN_TAG}_NationalIndividualElectoralDistrict.csv
├── {RUN_TAG}_SettlementIndividualElectoralDistrict.csv
├── {RUN_TAG}_PostalCode.csv
├── {RUN_TAG}_PostalCode_Settlement.csv
├── {RUN_TAG}_PollingStation.csv
├── {RUN_TAG}_PublicSpaceName.csv
├── {RUN_TAG}_PublicSpaceType.csv
├── {RUN_TAG}_SettlementPublicSpaces.csv
├── {RUN_TAG}_CanonicalAddress.csv (consolidated deduplicated addresses)
└── {RUN_TAG}_Address/
    ├── Address_001_Aba.csv (canonical deduplicated, UUID v3)
    ├── Address_002_Abony.csv (canonical deduplicated, UUID v3)
    ├── OriginalAddress_001_Aba.csv (all original with canonical refs, UUID v3)
    ├── OriginalAddress_002_Abony.csv (all original with canonical refs, UUID v3)
    └── ... (two files per settlement: canonical + original)
```

**Key Changes:**
- All IDs use UUID v3 format with 'oevk.hu' namespace
- Reference lists are comma-separated without brackets
- Canonical and original address files are in the same directory
- Canonical addresses show aggregated relationships (PollingStationIDs, PIRCodes)
- OriginalAddressCount shows how many duplicates were merged

## Address Geocoding

The pipeline includes geographic coordinate enrichment for addresses and polling stations using Nominatim and OpenStreetMap data. The geocoding system has been heavily optimized for performance with multi-threading, SQLite caching, and bulk database operations.

### Features

- **3.3M+ Address Geocoding**: Add latitude/longitude coordinates to all canonical addresses
- **Multi-threaded Processing**: 32 parallel workers for optimal throughput (490 addr/sec)
- **High-Performance SQLite Cache**: Single database file (2.1MB) replacing 6,381 JSON files
- **Bulk Pre-filtering**: Loads 2.9M+ cached results via SQL JOIN before geocoding
- **Smart Cache Hit Rate**: 88.5% cache efficiency on typical datasets
- **Polling Station Geocoding**: Multi-strategy fuzzy search for institutional addresses
- **Quality Classification**: Exact (17.6%), street (70.1%), settlement (0.7%), or failed (11.5%)
- **Flexible CLI Options**: Skip geocoded, update from cache, ignore failures
- **PostGIS Support**: Optional GEOGRAPHY columns with spatial indexes for PostgreSQL exports
- **Progress Tracking**: Real-time batch progress with ETA and processing rates
- **Release Integration**: Geocoding cache packaged as separate ZIP in releases

### Quick Start

#### 1. Set Up Nominatim Service

Start the local Nominatim geocoding service (one-time setup):

```bash
# Start Nominatim with Hungary OSM data
python src/cli.py geocode setup

# This will:
# - Download Hungary OSM data (~286 MB)
# - Import data into Nominatim (takes 1-2 hours)
# - Start the geocoding service on http://localhost:8081

# Monitor import progress
docker logs -f oevk-nominatim

# Force reimport (destroys existing database)
python src/cli.py geocode setup --force-reimport
```

#### 2. Run Geocoding

Geocode addresses and polling stations with optimized multi-threaded processing:

```bash
# Geocode all addresses (uses 32 workers by default)
python src/cli.py geocode run

# Skip addresses that already have successful coordinates (retry only failures)
python src/cli.py geocode run --ignore-geocoded

# Update database from cache only (no actual geocoding)
# Useful when you have a pre-built cache from another run or release package
python src/cli.py geocode run --update-from-cache

# Combine options: update from cache, then geocode missing addresses
python src/cli.py geocode run --update-from-cache
python src/cli.py geocode run --ignore-geocoded

# Geocode with custom batch size (default: 100)
python src/cli.py geocode run --batch-size 200

# Geocode with custom database path
python src/cli.py geocode run --db-path data/custom.db
```

**Performance Characteristics:**
- **First run**: 12-30 minutes for 3.3M+ addresses with 32 workers (no cache)
- **With cache**: 2-5 minutes (88.5% cache hit rate, loads 2.9M cached via SQL JOIN)
- **Update from cache only**: <1 minute (no Nominatim calls)
- **Processing rate**: ~490 addresses/sec with 32 workers
- **Cache efficiency**: Single 2.1MB SQLite database vs 25MB of JSON files

#### 3. Check Geocoding Status

View geocoding statistics and coverage:

```bash
# Show geocoding statistics
python src/cli.py geocode status

# Output example:
# === Canonical Address Geocoding Status ===
# Total addresses: 3,342,156
# Geocoded: 3,180,234 (95.2%)
# Not geocoded: 161,922
#
# Quality distribution:
#   exact: 2,456,789 (77.3%)
#   street: 623,445 (19.6%)
#   settlement: 100,000 (3.1%)
#   failed: 0 (0.0%)
```

### How It Works

#### Geocoding Workflow Architecture

The geocoding system uses a sophisticated multi-threaded architecture with SQLite caching and bulk pre-filtering:

```mermaid
flowchart TB
    Start[Start Geocoding] --> LoadDB[Load Addresses from DuckDB]
    LoadDB --> AttachCache[Attach SQLite Cache Database]
    AttachCache --> BulkJoin[Bulk SQL JOIN:<br/>Load 2.9M Cached Results]
    BulkJoin --> UpdateCached[Update DB with Cached Coordinates]
    UpdateCached --> FilterNew[Filter Non-Cached Addresses<br/>383k remaining]
    
    FilterNew --> CheckMode{Mode?}
    CheckMode -->|update-from-cache| Done[Complete]
    CheckMode -->|geocode| BatchSplit[Split into 100-addr Batches]
    
    BatchSplit --> ThreadPool[ThreadPoolExecutor<br/>32 Parallel Workers]
    
    ThreadPool --> Worker1[Worker 1]
    ThreadPool --> Worker2[Worker 2]
    ThreadPool --> Worker3[Worker N]
    
    Worker1 --> CheckCache1{Check SQLite Cache}
    Worker2 --> CheckCache2{Check SQLite Cache}
    Worker3 --> CheckCache3{Check SQLite Cache}
    
    CheckCache1 -->|Hit| Return1[Return Cached Result]
    CheckCache1 -->|Miss| Nominatim1[Query Nominatim]
    
    CheckCache2 -->|Hit| Return2[Return Cached Result]
    CheckCache2 -->|Miss| Nominatim2[Query Nominatim]
    
    CheckCache3 -->|Hit| Return3[Return Cached Result]
    CheckCache3 -->|Miss| Nominatim3[Query Nominatim]
    
    Nominatim1 --> Cache1[Store in SQLite Cache]
    Nominatim2 --> Cache2[Store in SQLite Cache]
    Nominatim3 --> Cache3[Store in SQLite Cache]
    
    Cache1 --> Return1
    Cache2 --> Return2
    Cache3 --> Return3
    
    Return1 --> Collect[Collect Results]
    Return2 --> Collect
    Return3 --> Collect
    
    Collect --> Dedup[Deduplicate Results<br/>DISTINCT ON ID]
    Dedup --> UpdateDB[Update DuckDB with Coordinates]
    UpdateDB --> Done
    
    style BulkJoin fill:#90EE90
    style ThreadPool fill:#FFD700
    style CheckCache1 fill:#87CEEB
    style CheckCache2 fill:#87CEEB
    style CheckCache3 fill:#87CEEB
    style Nominatim1 fill:#FFA07A
    style Nominatim2 fill:#FFA07A
    style Nominatim3 fill:#FFA07A
```

**Key Optimizations:**

1. **Bulk Pre-filtering (Green)**: Uses `ATTACH DATABASE` to load 2.9M cached results via SQL JOIN before geocoding starts
2. **Multi-threading (Gold)**: 32 parallel workers process 100-address batches concurrently
3. **Thread-safe Caching (Blue)**: Each worker checks SQLite cache with connection pooling
4. **Nominatim Queries (Orange)**: Only non-cached addresses query the geocoding service
5. **Deduplication**: Handles duplicate results from multi-threading with `DISTINCT ON`

**Performance Impact:**
- Bulk pre-filtering: Processes only 11.5% of addresses (383k of 3.3M)
- Multi-threading: 3.3x speed improvement (148 → 490 addr/sec)
- Cache efficiency: 88.5% hit rate reduces Nominatim load

#### Canonical Address Geocoding

Uses structured queries to Nominatim with the following parameters:
- `street`: PublicSpaceName + HouseNumber (e.g., "Andrássy út 1")
- `city`: SettlementName (e.g., "Budapest")
- `country`: hu (Hungary)

Quality determination:
- **Exact**: House-level match (OSM type: house)
- **Street**: Street-level match (OSM type: street, road)
- **Settlement**: Settlement-level match (OSM type: city, town, village)
- **Failed**: No match found

#### Polling Station Fuzzy Search

Handles composite institutional addresses with 4-strategy waterfall approach:

**Strategy 1: Exact Nominatim Match**
```
Input: "Budapest II. kerületi Polgármesteri Hivatal, Mechwart liget 1."
Query: Direct geocoding via Nominatim
```

**Strategy 2: Fuzzy Tokenization**
```
Input: "Budapest II. kerületi Polgármesteri Hivatal, Mechwart liget 1."
Extract: "Mechwart liget 1" (remove institution keywords)
Query: Geocode extracted address
```

**Strategy 3: Canonical Address Matching**
```
Input: "Budapest II. kerületi Polgármesteri Hivatal, Mechwart liget 1."
Match: Find similar addresses in canonical database using Levenshtein distance
Threshold: ≥0.6 similarity
Result: Use coordinates from matched canonical address
```

**Strategy 4: Settlement Centroid Fallback**
```
Input: Failed to match with strategies 1-3
Fallback: Use geographic center of settlement
Quality: Marked as "settlement"
```

### Configuration

All geocoding settings can be configured via environment variables in `.env`:

```bash
# Enable/disable geocoding (default: true)
NOMINATIM_ENABLED=true

# Nominatim service URL (default: http://localhost:8081)
NOMINATIM_BASE_URL=http://localhost:8081

# Batch size for geocoding (default: 100)
NOMINATIM_BATCH_SIZE=100

# Number of parallel workers for multi-threaded geocoding (default: 32)
NOMINATIM_MAX_WORKERS=32

# Rate limit in requests/second (default: 0 = no limit for local)
NOMINATIM_RATE_LIMIT=0

# SQLite cache database path (default: data/geocoding_cache.db)
NOMINATIM_CACHE_DB=data/geocoding_cache.db

# Similarity threshold for fuzzy matching (default: 0.6)
NOMINATIM_SIMILARITY_THRESHOLD=0.6

# Enable PostGIS GEOGRAPHY columns (default: true)
GEOCODING_USE_POSTGIS=true

# Timeout for geocoding requests in seconds (default: 30)
NOMINATIM_TIMEOUT=30

# Container name for Nominatim Docker service
NOMINATIM_CONTAINER_NAME=oevk-nominatim

# OSM data URL for Hungary
NOMINATIM_PBF_URL=https://download.geofabrik.de/europe/hungary-latest.osm.pbf
```

### Database Schema

Geocoding adds the following columns to tables:

#### CanonicalAddress Table
```sql
Latitude REAL,                  -- WGS 84 latitude (-90 to 90)
Longitude REAL,                 -- WGS 84 longitude (-180 to 180)
GeocodingQuality TEXT,          -- exact, street, settlement, failed
GeocodingSource TEXT,           -- nominatim_local
GeocodedAt TIMESTAMP,           -- When geocoding was performed
CreatedAt TIMESTAMP,            -- When address was created

-- Indexes for efficient coordinate queries
CREATE INDEX idx_CanonicalAddress_Coordinates ON CanonicalAddress(Latitude, Longitude);
CREATE INDEX idx_CanonicalAddress_Quality ON CanonicalAddress(GeocodingQuality);
```

#### PollingStation Table
```sql
Latitude REAL,
Longitude REAL,
GeocodingQuality TEXT,
GeocodingSource TEXT,
GeocodedAt TIMESTAMP,
MatchedAddress TEXT,            -- The matched address for fuzzy search results

CREATE INDEX idx_PollingStation_Coordinates ON PollingStation(Latitude, Longitude);
CREATE INDEX idx_PollingStation_Quality ON PollingStation(GeocodingQuality);
```

### PostGIS Spatial Queries

When `GEOCODING_USE_POSTGIS=true`, PostgreSQL exports include GEOGRAPHY columns for advanced spatial analysis:

```sql
-- PostgreSQL schema additions
ALTER TABLE CanonicalAddress ADD COLUMN Geometry GEOGRAPHY(POINT, 4326);
ALTER TABLE PollingStation ADD COLUMN Geometry GEOGRAPHY(POINT, 4326);

-- Spatial indexes for efficient queries
CREATE INDEX idx_CanonicalAddress_Geometry ON CanonicalAddress USING GIST(Geometry);
CREATE INDEX idx_PollingStation_Geometry ON PollingStation USING GIST(Geometry);
```

#### Example Spatial Queries

**Find addresses within 1km radius:**
```sql
SELECT FullAddress, Latitude, Longitude
FROM CanonicalAddress
WHERE ST_DWithin(
    Geometry,
    ST_GeogFromText('POINT(19.0402 47.4979)'),  -- Budapest coordinates
    1000  -- 1000 meters = 1km
);
```

**Find nearest polling station to an address:**
```sql
SELECT 
    ps.PollingStationAddress,
    ST_Distance(ca.Geometry, ps.Geometry) as distance_meters
FROM CanonicalAddress ca
CROSS JOIN PollingStation ps
WHERE ca.FullAddress = 'Your Address Here'
ORDER BY distance_meters
LIMIT 1;
```

**Calculate distance between two addresses:**
```sql
SELECT ST_Distance(
    (SELECT Geometry FROM CanonicalAddress WHERE FullAddress = 'Address 1'),
    (SELECT Geometry FROM CanonicalAddress WHERE FullAddress = 'Address 2')
) as distance_meters;
```

**Find all addresses within a settlement boundary:**
```sql
SELECT ca.FullAddress, ca.Latitude, ca.Longitude
FROM CanonicalAddress ca
WHERE ST_Within(
    ca.Geometry,
    (SELECT Polygon FROM NationalIndividualElectoralDistrict WHERE OEVK = '01')
);
```

### CSV Export Format

Geocoded data is included in CSV exports:

**CanonicalAddress.csv columns:**
```csv
CanonicalAddressID,CountyCode,SettlementName,FullAddress,StreetName,HouseNumber,
AccessibilityFlag,Latitude,Longitude,GeocodingQuality,GeocodingSource,GeocodedAt,
CreatedAt,PollingStationIDs,PIRCodes,OriginalAddressCount
```

**PollingStation.csv columns:**
```csv
ID,PollingStationAddress,SettlementIndividualElectoralDistrict_ID,County_ID,
Settlement_ID,NationalIndividualElectoralDistrict_ID,Latitude,Longitude,
GeocodingQuality,GeocodingSource,GeocodedAt,MatchedAddress
```

### Troubleshooting

#### Nominatim Service Won't Start

```bash
# Check if Docker is running
docker info

# Check container status
docker ps -a | grep nominatim

# View container logs
docker logs oevk-nominatim

# Restart container
docker-compose restart nominatim

# Force reimport (if data is corrupted)
python src/cli.py geocode setup --force-reimport
```

#### Slow Geocoding Performance

**First run is slow (expected):**
- Initial import: 1-2 hours (one-time)
- First geocoding: 9-90 minutes for 3.3M addresses

**Optimize performance:**
```bash
# Increase batch size (default: 100)
python src/cli.py geocode run --batch-size 500

# Check if Nominatim is responding
curl http://localhost:8081/status

# Monitor system resources
docker stats oevk-nominatim
```

#### Low Match Rate

```bash
# Check geocoding statistics
python src/cli.py geocode status

# Review failed addresses in database
sqlite3 data/oevk.db "SELECT FullAddress FROM CanonicalAddress WHERE GeocodingQuality = 'failed' LIMIT 10;"

# Check Nominatim service
curl "http://localhost:8081/search?q=Budapest&format=json"
```

#### Cache Issues

```bash
# Clear geocoding cache
rm -rf data/geocoding_cache/*

# Re-run geocoding
python src/cli.py geocode run
```

#### PostGIS Errors

```bash
# Check if PostGIS is installed
psql -U oevk -c "SELECT PostGIS_version();"

# Disable PostGIS if not available
export GEOCODING_USE_POSTGIS=false
```

### Performance Characteristics

**Storage:**
- Nominatim database: ~2-3 GB (Hungary OSM data)
- Geocoding cache: 2.1 MB SQLite database (6,381 addresses cached)
- Cache storage improvement: 12x reduction (25MB JSON files → 2.1MB SQLite)
- Coordinate columns: ~200 MB additional database size

**Processing Time:**
- OSM data import: 1-2 hours (one-time)
- First geocoding run: 12-30 minutes (3.3M addresses, 32 workers)
- With cache (88.5% hit rate): 2-5 minutes (bulk SQL JOIN + geocode 383k new)
- Update from cache only: <1 minute (no Nominatim calls)
- Incremental updates: <5 minutes (only new addresses)

**Performance Improvements:**
- Multi-threading: 3.3x speed improvement (148 → 490 addr/sec with 32 workers)
- Cache optimization: Bulk pre-filtering via SQL JOIN (process only 11.5% of addresses)
- Storage efficiency: Single SQLite database vs thousands of JSON files

**Quality Metrics (Typical Dataset):**
- Match rate: 88.5% (2,958,473 of 3,342,156 addresses)
- Exact (house-level): 17.6% (587,234 addresses)
- Street-level: 70.1% (2,341,818 addresses)
- Settlement-level: 0.7% (29,421 addresses)
- Failed: 11.5% (383,683 addresses not in OSM)

## Data Model

The pipeline processes data through multiple stages, each with its own data model:

### Staging Data Model (DuckDB)

The staging model stores raw data from source files for transformation:

**Staging Tables:**
1. **staging_oevk_json** - Raw OEVK JSON data (polygon boundaries, centers)
2. **staging_oevk** - Legacy OEVK data structure
3. **staging_korzet** - Raw Korzet CSV data (3.3M+ address records)

The staging tables are temporary and contain all source data with minimal transformations. They include the `run_tag` column to track pipeline runs.

### DuckDB Internal Data Model

After transformation and deduplication, the pipeline creates normalized tables in DuckDB:

**Core Tables (11):**
1. **County** (`megye`) - Administrative counties (20 rows)
2. **Settlement** (`település`) - Cities, towns, villages (3,177 rows)
3. **NationalIndividualElectoralDistrict** (`OEVK`) - National electoral districts (106 rows)
4. **SettlementIndividualElectoralDistrict** (`TEVK`) - Settlement-level electoral districts (4,597 rows)
5. **PostalCode** (`irányítószám`) - Postal codes (3,106 rows)
6. **PostalCode_Settlement** - Junction table for postal code-settlement relationships (3,684 rows)
7. **PollingStation** (`szavazókör`) - Voting locations (8,547 rows)
8. **Address** (`cím`) - Individual addresses with electoral assignments (3.3M original rows)
9. **CanonicalAddress** - Deduplicated unique addresses with Hungarian formatting (3.3M deduplicated rows)
10. **PublicSpaceName** - Unique public space names extracted from addresses (25,117 rows)
11. **PublicSpaceType** - Unique public space types (utca, tér, út, etc.) (148 rows)

**Deduplication Tables (4):**
12. **AddressMapping** - Mapping between original and canonical addresses (3.3M rows)
13. **AddressPollingStations** - Canonical address to polling station relationships (3.3M rows)
14. **AddressPIRCodes** - Canonical address to PIR code relationships (3.3M rows)
15. **SettlementPublicSpaces** - Many-to-many relationships between settlements and public spaces (122,524 rows)

**Internal Tables:**
- **Address_new** - Temporary table for public space extraction
- **DeduplicationReport** - Audit log of deduplication runs

### PostgreSQL/Export Data Model

The export data model is optimized for external consumption and includes only canonical (deduplicated) data:

**Exported Tables (13):**
1. County
2. Settlement  
3. NationalIndividualElectoralDistrict
4. SettlementIndividualElectoralDistrict
5. PostalCode
6. PostalCode_Settlement
7. PollingStation
8. **Address** (renamed from CanonicalAddress) - Only deduplicated addresses with UUID v5 IDs
9. PublicSpaceName
10. PublicSpaceType
11. SettlementPublicSpaces
12. AddressPollingStations (optional, for advanced use)
13. AddressPIRCodes (optional, for advanced use)

**Key Differences from DuckDB:**
- Uses **UUID v5** format instead of MD5 hex strings for all IDs
- **Address table** contains only canonical deduplicated addresses (not original duplicates)
- **No AddressMapping** table (internal deduplication tracking)
- **No DeduplicationReport** table (internal audit)
- **PostGIS GEOGRAPHY columns** for spatial queries (PostgreSQL only)
- **Trigram GIN indexes** for fast text search (PostgreSQL only)

### DuckDB Internal Model Diagram

```mermaid
erDiagram
    County ||--o{ Settlement : contains
    County ||--o{ NationalIndividualElectoralDistrict : contains
    County ||--o{ Address : contains
    County ||--o{ PollingStation : contains
    Settlement ||--o{ SettlementIndividualElectoralDistrict : contains
    Settlement ||--o{ Address : contains
    Settlement ||--o{ PollingStation : contains
    SettlementIndividualElectoralDistrict ||--o{ Address : "assigned to"
    NationalIndividualElectoralDistrict ||--o{ Address : "assigned to"
    PollingStation ||--o{ Address : contains
    PostalCode ||--o{ PostalCode_Settlement : has
    Settlement ||--o{ PostalCode_Settlement : has
    PostalCode ||--o{ Address : assigned
    Settlement ||--o{ SettlementPublicSpaces : has
    PublicSpaceName ||--o{ SettlementPublicSpaces : has
    PublicSpaceType ||--o{ SettlementPublicSpaces : has
    Address ||--|| AddressMapping : "maps to"
    CanonicalAddress ||--o{ AddressMapping : "has many"
    CanonicalAddress ||--o{ AddressPollingStations : "has"
    CanonicalAddress ||--o{ AddressPIRCodes : "has"
    
    County {
        string ID PK "md5(CountyCode)"
        string CountyCode UK
        string CountyName
    }
    Settlement {
        string ID PK "md5(CountyCode|SettlementCode)"
        string SettlementCode
        string SettlementName
        string County_ID FK
    }
    NationalIndividualElectoralDistrict {
        string ID PK "md5(CountyCode|OEVK)"
        string OEVK
        string Name
        string Center "Center point coordinates (space-separated)"
        string Polygon "Boundary polygon coordinates (comma-separated)"
        string County_ID FK
    }
    SettlementIndividualElectoralDistrict {
        string ID PK "md5(CountyCode|SettlementCode|TEVK)"
        string TEVK
        string Name
        string County_ID FK
        string Settlement_ID FK
    }
    PostalCode {
        string ID PK "md5(PostalCode)"
        string PostalCode UK
    }
    PostalCode_Settlement {
        string ID PK "md5(PostalCode_ID|Settlement_ID)"
        string PostalCode_ID FK
        string Settlement_ID FK
    }
    PollingStation {
        string ID PK "md5(CountyCode|SettlementCode|OEVK|TEVK|PollingStationAddress)"
        string PollingStationAddress
        string SettlementIndividualElectoralDistrict_ID FK
        string County_ID FK
        string Settlement_ID FK
        string NationalIndividualElectoralDistrict_ID FK
    }
    Address {
        string ID PK "md5(address components)"
        integer Sequence
        integer OriginalOrder
        string FullAddress
        string PublicSpaceName
        string PublicSpaceType
        string HouseNumber
        string Building
        string Staircase
        string PostalCode_ID FK
        string PollingStation_ID FK
        string SettlementIndividualElectoralDistrict_ID FK
        string County_ID FK
        string Settlement_ID FK
        string NationalIndividualElectoralDistrict_ID FK
    }
    PublicSpaceName {
        string ID PK "md5(PublicSpaceName)"
        string PublicSpaceName UK
    }
    PublicSpaceType {
        string ID PK "md5(PublicSpaceType)"
        string PublicSpaceType UK
    }
    SettlementPublicSpaces {
        string ID PK "md5(Settlement_ID|PublicSpaceName_ID|PublicSpaceType_ID)"
        string Settlement_ID FK
        string PublicSpaceName_ID FK
        string PublicSpaceType_ID FK
    }
    CanonicalAddress {
        string ID PK "md5(CountyCode|SettlementName|FullAddress)"
        string CountyCode "County code (text, not FK)"
        string SettlementName "Settlement name (text, not FK)"
        string StreetName
        string HouseNumber
        string Building
        string Staircase
        string FullAddress "Formatted Hungarian address"
        string AccessibilityFlag
        timestamp CreatedAt
    }
    AddressMapping {
        string ID PK "md5(OriginalAddressID|CanonicalAddressID)"
        string OriginalAddressID FK
        string CanonicalAddressID FK
    }
    AddressPollingStations {
        string ID PK "md5(CanonicalAddressID|PollingStationID)"
        string CanonicalAddressID FK
        string PollingStationID FK
    }
    AddressPIRCodes {
        string ID PK "md5(CanonicalAddressID|PIRCode)"
        string CanonicalAddressID FK
        string PIRCode FK
    }
```

**Notes:**
- **Address table** contains original addresses with all duplicates (3.3M+ rows)
- **CanonicalAddress table** contains deduplicated unique addresses (3.3M rows, ~0.4% reduction)
- **AddressMapping** links original addresses to their canonical representation
- **CanonicalAddress** stores `CountyCode` and `SettlementName` as text (not foreign keys)
- To join CanonicalAddress with Settlement: `County.CountyCode = CanonicalAddress.CountyCode AND Settlement.SettlementName = CanonicalAddress.SettlementName`

### PostgreSQL/Export Model Diagram

```mermaid
erDiagram
    County ||--o{ Settlement : contains
    County ||--o{ NationalIndividualElectoralDistrict : contains
    County ||--o{ Address : contains
    County ||--o{ PollingStation : contains
    Settlement ||--o{ SettlementIndividualElectoralDistrict : contains
    Settlement ||--o{ Address : contains
    Settlement ||--o{ PollingStation : contains
    SettlementIndividualElectoralDistrict ||--o{ Address : "assigned to"
    NationalIndividualElectoralDistrict ||--o{ Address : "assigned to"
    PollingStation ||--o{ Address : contains
    PostalCode ||--o{ PostalCode_Settlement : has
    Settlement ||--o{ PostalCode_Settlement : has
    PostalCode ||--o{ Address : assigned
    Settlement ||--o{ SettlementPublicSpaces : has
    PublicSpaceName ||--o{ SettlementPublicSpaces : has
    PublicSpaceType ||--o{ SettlementPublicSpaces : has
    Address ||--o{ AddressPollingStations : "has (optional export)"
    Address ||--o{ AddressPIRCodes : "has (optional export)"
    
    County {
        uuid ID PK "uuid5(md5(CountyCode))"
        string CountyCode UK
        string CountyName
    }
    Settlement {
        uuid ID PK "uuid5(md5(CountyCode|SettlementCode))"
        string SettlementCode
        string SettlementName
        uuid County_ID FK
    }
    NationalIndividualElectoralDistrict {
        uuid ID PK "uuid5(md5(CountyCode|OEVK))"
        string OEVK
        string Name
        string Center "PostGIS POINT or text"
        string Polygon "PostGIS POLYGON or text"
        geography Geometry "PostGIS GEOGRAPHY (PostgreSQL only)"
        uuid County_ID FK
    }
    SettlementIndividualElectoralDistrict {
        uuid ID PK "uuid5(md5(CountyCode|SettlementCode|TEVK))"
        string TEVK
        string Name
        uuid County_ID FK
        uuid Settlement_ID FK
    }
    PostalCode {
        uuid ID PK "uuid5(md5(PostalCode))"
        string PostalCode UK
    }
    PostalCode_Settlement {
        uuid ID PK "uuid5(md5(PostalCode_ID|Settlement_ID))"
        uuid PostalCode_ID FK
        uuid Settlement_ID FK
    }
    PollingStation {
        uuid ID PK "uuid5(md5(...))"
        string PollingStationAddress
        real Latitude
        real Longitude
        geography Geometry "PostGIS GEOGRAPHY (PostgreSQL only)"
        string GeocodingQuality
        uuid SettlementIndividualElectoralDistrict_ID FK
        uuid County_ID FK
        uuid Settlement_ID FK
        uuid NationalIndividualElectoralDistrict_ID FK
    }
    Address {
        uuid ID PK "uuid5(md5(...))"
        integer Sequence
        integer OriginalOrder
        string FullAddress
        string PublicSpaceName
        string PublicSpaceType
        string HouseNumber
        string Building
        string Staircase
        string CountyCode "Text (for join to County)"
        string SettlementName "Text (for join to Settlement)"
        real Latitude
        real Longitude
        geography Geometry "PostGIS GEOGRAPHY (PostgreSQL only)"
        string GeocodingQuality
        string AccessibilityFlag
        integer OriginalAddressCount "Number of duplicates merged"
        uuid PostalCode_ID FK
        uuid PollingStation_ID FK
        uuid SettlementIndividualElectoralDistrict_ID FK
        uuid County_ID FK
        uuid Settlement_ID FK
        uuid NationalIndividualElectoralDistrict_ID FK
    }
    PublicSpaceName {
        uuid ID PK "uuid5(md5(PublicSpaceName))"
        string PublicSpaceName UK
    }
    PublicSpaceType {
        uuid ID PK "uuid5(md5(PublicSpaceType))"
        string PublicSpaceType UK
    }
    SettlementPublicSpaces {
        uuid ID PK "uuid5(md5(...))"
        uuid Settlement_ID FK
        uuid PublicSpaceName_ID FK
        uuid PublicSpaceType_ID FK
    }
    AddressPollingStations {
        uuid ID PK "uuid5(md5(AddressID|PollingStationID))"
        uuid AddressID FK
        uuid PollingStationID FK
    }
    AddressPIRCodes {
        uuid ID PK "uuid5(md5(AddressID|PIRCode))"
        uuid AddressID FK
        string PIRCode
    }
```

**Key Differences from DuckDB Model:**
- **Address** table contains only **canonical deduplicated addresses** (renamed from CanonicalAddress)
- All IDs use **UUID v5 format** instead of MD5 hex strings
- **PostGIS GEOGRAPHY columns** for spatial queries (Latitude/Longitude also preserved as REAL)
- Address table includes `CountyCode` and `SettlementName` as text fields AND proper foreign keys (`County_ID`, `Settlement_ID`)
- `OriginalAddressCount` shows how many duplicate addresses were merged
- **No AddressMapping table** (internal tracking, not exported)
- **No original Address table** (duplicates not exported by default)
- AddressPollingStations and AddressPIRCodes are **optional exports** (for advanced use cases)
```

**Note on TEVK and OEVK Relationship:**  
TEVK (SettlementIndividualElectoralDistrict) and OEVK (NationalIndividualElectoralDistrict) are **parallel, independent electoral systems**, not hierarchical. TEVK is for settlement-level municipal elections organized by settlement boundaries, while OEVK is for national parliamentary elections organized by county boundaries. Addresses maintain references to both systems independently via the Address table.

### Transformation Flow

```mermaid
flowchart TD
    A[Source Data] --> B[Ingestion]
    B --> C[Staging Tables]
    C --> D[Transformation]
    D --> E[Public Space Extraction]
    E --> F[Address Deduplication]
    F --> G[Normalized Tables]
    G --> H[Export]
    H --> I[CSV Files]
    
    subgraph A [Source Data]
        A1[oevk.json<br/>OEVK boundaries]
        A2[Korzet_allomany_orszagos.zip<br/>Address data]
    end
    
    subgraph B [Ingestion]
        B1[Download Sources]
        B2[Extract & Load]
        B3[Create Staging Tables]
    end
    
    subgraph C [Staging Tables]
        C1[staging_korzet<br/>Raw address data]
        C2[staging_oevk<br/>OEVK boundaries]
    end
    
    subgraph D [Transformation]
        D1[County & Settlement]
        D2[OEVK & TEVK]
        D3[Postal Codes]
        D4[Polling Stations]
        D5[Addresses]
        D6[Relationships]
    end
    
    subgraph E [Public Space Extraction]
        E1[Extract Public Space Names]
        E2[Extract Public Space Types]
        E3[Create Settlement Relationships]
    end
    
    subgraph F [Address Deduplication]
        F1[Format Addresses<br/>Hungarian conventions]
        F2[Generate Canonical IDs<br/>md5]
        F3[Create Canonical Addresses<br/>0.39% reduction]
        F4[Preserve Relationships<br/>Polling Stations, PIR Codes]
    end
    
    subgraph G [Normalized Tables]
        G1[County]
        G2[Settlement]
        G3[NationalIndividualElectoralDistrict]
        G4[SettlementIndividualElectoralDistrict]
        G5[PostalCode]
        G6[PostalCode_Settlement]
        G7[PollingStation]
        G8[Address Original]
        G9[CanonicalAddress]
        G10[AddressMapping]
        G11[AddressPollingStations]
        G12[AddressPIRCodes]
        G13[PublicSpaceName]
        G14[PublicSpaceType]
        G15[SettlementPublicSpaces]
    end
    
    subgraph H [Export]
        H1[Consolidated CSVs]
        H2[Canonical Addresses<br/>UUID v3]
        H3[Original Addresses<br/>UUID v3]
    end
    
    subgraph I [CSV Files]
        I1["Entity CSVs<br/>County, Settlement, etc."]
        I2["Address files<br/>Canonical deduplicated"]
        I3["OriginalAddress files<br/>With canonical refs"]
        I4["Public Space CSVs<br/>Names, Types, Relationships"]
    end
    
    D1 --> G1
    D1 --> G2
    D2 --> G3
    D2 --> G4
    D3 --> G5
    D6 --> G6
    D4 --> G7
    D5 --> G8
    
    E1 --> G13
    E2 --> G14
    E3 --> G15
    
    F1 --> F2
    F2 --> F3
    F3 --> F4
    F4 --> G9
    F4 --> G10
    F4 --> G11
    F4 --> G12
    
    G1 --> H1
    G2 --> H1
    G3 --> H1
    G4 --> H1
    G5 --> H1
    G6 --> H1
    G7 --> H1
    G9 --> H2
    G8 --> H3
    G13 --> H1
    G14 --> H1
    G15 --> H1
    
    H1 --> I1
    H2 --> I2
    H3 --> I3
    H1 --> I4
```

### Key Relationships

- Each address belongs to exactly one polling station
- Each address is assigned to both one TEVK and one OEVK (parallel systems)
- Each TEVK belongs to exactly one settlement
- Each OEVK belongs to exactly one county
- Each settlement belongs to exactly one county
- Postal codes can span multiple settlements
- Public spaces are extracted from addresses and linked to settlements

**Note:** TEVK and OEVK are independent electoral systems. TEVK is NOT subordinate to OEVK.
- Each public space has a name and type (utca, tér, etc.)
- Settlements can have multiple public spaces, and public spaces can appear in multiple settlements

## CSV Column Mapping

This section shows how source CSV columns map to database tables and columns.

### Source Data Files

1. **oevk.json** - OEVK boundary data (108 records)
2. **Korzet_allomany_orszagos.zip** → CSV file - Address data (3.3M+ records)

### CSV Column to Database Table Mapping

#### From oevk.json

| Source Field | Target Table | Target Column | Transformation |
|--------------|--------------|---------------|----------------|
| `maz` | County | CountyCode | Direct mapping |
| `maz` | NationalIndividualElectoralDistrict | County_ID | md5(maz) |
| `evk` | NationalIndividualElectoralDistrict | OEVK | Direct mapping |
| `centrum` | NationalIndividualElectoralDistrict | Center | Direct mapping (stored as text "lat lon") |
| `poligon` | NationalIndividualElectoralDistrict | Polygon | Direct mapping (stored as text coordinates) |
| `maz` + `evk` | NationalIndividualElectoralDistrict | ID | md5(maz\|evk) |

#### From Korzet_allomany_orszagos.csv

| Hungarian Column Name | English Translation | Target Table(s) | Target Column | Transformation |
|----------------------|---------------------|-----------------|---------------|----------------|
| **County & Settlement** | | | | |
| Vármegye kód | CountyCode | County | CountyCode | Direct mapping |
| Vármegye kód | CountyCode | County | ID | md5(CountyCode) |
| Vármegye | CountyName | County | CountyName | Direct mapping |
| Település kód | SettlementCode | Settlement | SettlementCode | Direct mapping |
| Település kód | SettlementCode | Settlement | ID | md5(CountyCode\|SettlementCode) |
| Település | SettlementName | Settlement | SettlementName | Direct mapping |
| Vármegye kód | CountyCode | Settlement | County_ID | md5(CountyCode) |
| **Electoral Districts** | | | | |
| OEVK | OEVK Code | NationalIndividualElectoralDistrict | OEVK | Direct mapping |
| OEVK | OEVK Code | NationalIndividualElectoralDistrict | Name | Derived: Settlement.SettlementName + " " + OEVK |
| TEVK | TEVK Code | SettlementIndividualElectoralDistrict | TEVK | Direct mapping (can be NULL) |
| TEVK | TEVK Code | SettlementIndividualElectoralDistrict | Name | Derived: Settlement.SettlementName [+ " " + TEVK if not NULL] |
| OEVK + TEVK | - | SettlementIndividualElectoralDistrict | ID | md5(CountyCode\|SettlementCode\|COALESCE(TEVK,'-')\|OEVK) |
| **Polling Stations** | | | | |
| Szavazókör | PollingStationCode | PollingStation | - | Technical ID (not stored) |
| Szavazókör cím | PollingStationAddress | PollingStation | PollingStationAddress | Direct mapping |
| Szavazókör cím | PollingStationAddress | PollingStation | ID | md5(CountyCode\|SettlementCode\|OEVK\|COALESCE(TEVK,'-')\|PollingStationAddress) |
| Számlálásra kijelölt | CountingFlag | - | - | Audit only (not stored in target) |
| Akadálymentesített | AccessibilityFlag | CanonicalAddress | AccessibilityFlag | Used in deduplication (TRUE prioritized) |
| **Postal Codes** | | | | |
| PIR | PostalCode | PostalCode | PostalCode | Direct mapping |
| PIR | PostalCode | PostalCode | ID | md5(PostalCode) |
| PIR | PostalCode | PostalCode_Settlement | PostalCode_ID | md5(PostalCode) |
| PIR | PostalCode | Address | PostalCode_ID | md5(PostalCode) |
| **Address Components** | | | | |
| Közterület név | PublicSpaceName | PublicSpaceName | PublicSpaceName | Extracted and normalized (uppercase) |
| Közterület név | PublicSpaceName | PublicSpaceName | ID | md5(PublicSpaceName) |
| Közterület név | PublicSpaceName | Address | PublicSpaceName | Direct mapping |
| Közterület név | PublicSpaceName | CanonicalAddress | StreetName | Used in canonical ID generation |
| Közterület jelleg | PublicSpaceType | PublicSpaceType | PublicSpaceType | Extracted and normalized (e.g., "utca", "tér", "út") |
| Közterület jelleg | PublicSpaceType | PublicSpaceType | ID | md5(PublicSpaceType) |
| Közterület jelleg | PublicSpaceType | Address | PublicSpaceType | Direct mapping |
| Házszám | HouseNumber | Address | HouseNumber | Direct mapping with leading zeros |
| Házszám | HouseNumber | CanonicalAddress | HouseNumber | Cleaned: leading zeros removed, ranges preserved |
| Épület | Building | Address | Building | Direct mapping |
| Épület | Building | CanonicalAddress | - | Used in FullAddress formatting |
| Lépcsőház | Staircase | Address | Staircase | Direct mapping |
| Lépcsőház | Staircase | CanonicalAddress | - | Used in FullAddress formatting (numeric → Roman) |
| Kapukód | GateCode | - | - | Excluded from deduplication and canonical address |
| **Derived Fields** | | | | |
| Multiple columns | - | Address | FullAddress | Concatenated: PublicSpaceName + PublicSpaceType + HouseNumber + Building + Staircase |
| Multiple columns | - | Address | Sequence | Row number within polling station |
| Multiple columns | - | Address | OriginalOrder | Global loading order from source CSV |
| Multiple columns | - | Address | ID | md5(all address components) |
| Multiple columns | - | CanonicalAddress | FullAddress | Formatted Hungarian address (e.g., "Körtöltés utca 1/D.") |
| Multiple columns | - | CanonicalAddress | ID | md5(CountyCode\|SettlementName\|FullAddress) |

### Junction/Relationship Tables

| Table | Source Columns | Mapping Logic |
|-------|----------------|---------------|
| **PostalCode_Settlement** | PIR + Település kód | Links postal codes to settlements (n:m relationship) |
| **SettlementPublicSpaces** | Település kód + Közterület név + Közterület jelleg | Links settlements to public spaces (n:m relationship) |
| **AddressMapping** | Address.ID + CanonicalAddress.ID | Maps original addresses to canonical deduplicated addresses |
| **AddressPollingStations** | CanonicalAddress.ID + PollingStation.ID | Preserves all polling station assignments for canonical addresses |
| **AddressPIRCodes** | CanonicalAddress.ID + PIR | Preserves all postal codes for canonical addresses |

### Deduplication Process

The deduplication process identifies duplicate addresses based on formatted Hungarian addresses:

1. **Input**: Raw address components (Közterület név, Közterület jelleg, Házszám, Épület, Lépcsőház)
2. **Formatting Rules**:
   - Remove leading zeros from house numbers: `"000001"` → `"1"`
   - Handle ranges: `"000001-00005"` → `"1-5"`
   - Convert numeric staircases to Roman numerals: `"0001"` → `"I"`
   - Apply Hungarian address format: `"{Street Name} {Street Type} {House Number}. {Building}. épület {Staircase}. lépcsőház"`
3. **Canonical ID**: md5(CountyCode | SettlementName | FullAddress)
4. **Relationship Preservation**: All polling stations and PIR codes are preserved through junction tables

**Example**:
- Input: `"Körtöltés", "utca", "000001", "D", ""`
- Formatted: `"Körtöltés utca 1/D."`
- These three source records become ONE canonical address:
  - House: `"000001"`, Building: `"D"`, Staircase: `""` ← **Selected as canonical (structured format)**
  - House: `"000001"`, Building: `""`, Staircase: `"D"`
  - House: `"000001/D"`, Building: `""`, Staircase: `""`

**Deduplication Priority** (new in v1.4):
When multiple addresses map to the same canonical ID, the pipeline prioritizes **structured formats**:
- **High Priority** (Score 100-120): Plain house number with separate building/staircase fields
  - Example: House="1", Building="D" (score 110)
- **Low Priority** (Score 50-65): Combined slash notation in house number field
  - Example: House="1/D", Building="" (score 50)

This ensures the canonical address uses the highest quality data structure available, improving data consistency and usability.

### Coordinate Export (new in v1.4)

Polling district boundaries (TEVK - SettlementIndividualElectoralDistrict) include coordinate columns:
- **Center**: Coordinate center point (WKT POINT format)
- **Polygon**: Coordinate polygon (WKT POLYGON format)

These columns are exported to PostgreSQL and CSV formats, enabling geospatial analysis of electoral districts. The columns accept NULL values until actual coordinate data becomes available.

### ID Generation Strategy

All IDs use **MD5 hashing** (first 16 characters) for deterministic, collision-resistant identifiers:

| Table | ID Components | Example |
|-------|--------------|---------|
| County | CountyCode | md5("01") |
| Settlement | CountyCode \| SettlementCode | md5("01\|001") |
| NationalIndividualElectoralDistrict | CountyCode \| OEVK | md5("01\|01") |
| SettlementIndividualElectoralDistrict | CountyCode \| SettlementCode \| TEVK \| OEVK | md5("01\|001\|-\|01") |
| PostalCode | PostalCode | md5("1014") |
| PollingStation | CountyCode \| SettlementCode \| OEVK \| TEVK \| Address | md5("01\|001\|01\|-\|Úri utca 38...") |
| Address | All address components | md5(CountyCode\|SettlementCode\|...\|HouseNumber\|Building\|Staircase) |
| CanonicalAddress | CountyCode \| SettlementName \| FullAddress | md5("01\|Budapest I\|Anna utca 1.") |
| PublicSpaceName | PublicSpaceName | md5("Kossuth Lajos") |
| PublicSpaceType | PublicSpaceType | md5("utca") |

**Note**: NULL values in TEVK are replaced with `"-"` for consistent hashing.

### Export Format

Exported CSV files use **UUID v3** with 'oevk.hu' namespace for global uniqueness:

```python
OEVK_NAMESPACE = uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")
exported_id = uuid.uuid5(OEVK_NAMESPACE, internal_md5_id)
```

This ensures:
- ✅ Global uniqueness across systems
- ✅ Deterministic conversion (same input → same UUID)
- ✅ Standard UUID format compatibility

### Deduplication Relationships

- Each original **Address** maps to exactly one **CanonicalAddress** through **AddressMapping**
- Each **CanonicalAddress** can have many original addresses (13,084 duplicates merged)
- **AddressPollingStations** preserves all polling station assignments for canonical addresses
- **AddressPIRCodes** preserves all PIR codes for canonical addresses
- Canonical IDs are deterministic: same formatted address → same canonical ID
- Export uses UUID v3 with 'oevk.hu' namespace for global uniqueness

### Field Descriptions

- **Sequence**: Logical ordering of addresses within their polling station
- **OriginalOrder**: Preserves the original loading order from source CSV for data lineage

## Development

### Testing

Run the complete test suite:

```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/contract/
python -m pytest tests/performance/

# Run public space specific tests
python -m pytest tests/contract/test_transform_public_spaces.py tests/contract/test_export_public_spaces.py

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy .

# Formatting
ruff format .
```

### Public Space Extraction

The pipeline automatically extracts public space entities from addresses:

- **Entity Recognition**: Extracts public space names and types from address strings
- **Relationship Mapping**: Creates many-to-many relationships between settlements and public spaces
- **Hash-based IDs**: Deterministic MD5 identifiers for all entities
- **Data Integrity**: Full validation and referential integrity
- **Export Support**: CSV export for all public space entities

#### Public Space Data Extracted:
- **PublicSpaceName**: 25,117 unique public space names (713KB)
- **PublicSpaceType**: 148 unique public space types (3.8KB)
- **SettlementPublicSpaces**: 122,524 relationships (8.3MB)

### Adding New Features

1. Follow the existing patterns in the codebase
2. Add appropriate tests
3. Update documentation
4. Run linting and type checking

## Performance

### ETL Pipeline Performance

- **Target Performance**: Process 3M+ rows in under 30 minutes (NFR-002)
- **Achieved Performance**: ~2.5 minutes for 3.34M records with parallel processing
- **Performance Improvement**: 98.6% reduction from baseline (183.6 minutes → 2.5 minutes)
- **Memory Usage**: Stable at ~34 MB throughout processing
- **Parallel Processing**: 4 worker threads with ThreadPoolExecutor
- **Chunked Processing**: Process data in 50K record chunks
- **Public Space Extraction**: Integrated into main pipeline without performance impact

### CSV Export Performance

- **Export Optimization**: Single-query approach with Python partitioning
- **Achieved Performance**: ~2.6 minutes for 3.3M addresses across 3,177 settlements
- **Performance Improvement**: ~17x faster than per-settlement query approach
- **Processing Rate**: ~21,000 addresses/second
- **Query Time**: 24 seconds to fetch all addresses
- **Write Time**: 2.2 minutes to write 3,177 CSV files
- **Memory Efficient**: Streaming write approach, minimal memory footprint
- **Automatic Cleanup**: Removes old export files before creating new ones

**Export Approach:**
- Single complex query fetches all 3.3M addresses with JOINs
- Python partitions data by settlement in memory
- Sequential CSV writes for each settlement
- Much faster than 3,177 separate database queries

### Release Workflow Performance

- **Complete Workflow**: ≤15 minutes for full release process
- **Data Validation**: ≤2 minutes for comprehensive checks
- **Package Creation**: ≤5 minutes for artifact compression
- **GitHub Integration**: ≤3 minutes for release creation
- **Idempotent Operations**: Safe to retry failed operations

### Performance Benchmarks

- **Baseline Processing**: 3 hours 3 minutes (sequential processing)
- **Optimized Processing**: ~2.5 minutes (parallel processing)
- **Processing Rate**: ~22,000 rows/second
- **Memory Usage**: ~34 MB (stable throughout processing)
- **NFR-002 Compliance**: ✅ Achieved with significant margin
- **Public Space Data**: 25,117 names, 148 types, 122,524 relationships extracted
- **Export Performance**: 2.6 minutes for 3.3M addresses (17x faster than baseline)

See [PERFORMANCE_BENCHMARKS.md](docs/PERFORMANCE_BENCHMARKS.md) for detailed performance analysis.

### PostgreSQL Import Performance

The PostgreSQL import process has been optimized for handling 3.3M+ rows with geocoded coordinates and PostGIS geometry columns:

**Import Optimization Techniques:**

1. **Chunked CSV COPY (Data Import)**
   - Address table split into 34 chunks of 100K rows
   - Uses PostgreSQL's `\copy` command (10-50x faster than INSERT)
   - Progress tracking: `[X/34] Y% - Importing Address: Z/3,323,113 rows`
   - Performance: ~25-30 seconds per 100K chunk
   - Total data import time: ~14-15 minutes

2. **Chunked PostGIS Geometry Population**
   - Updates 2.9M geocoded addresses in batches of 100K rows
   - Uses optimized `ST_SetSRID(ST_MakePoint(Longitude, Latitude), 4326)::geography`
   - 3-5x faster than `ST_GeogFromText()` with string concatenation
   - Commits between batches to reduce transaction log size
   - Progress tracking: `NOTICE: Updated X addresses (total: Y)`
   - Performance: ~30-60 seconds per 100K batch
   - Total geometry population time: ~15-20 minutes

3. **Transaction Management**
   - Main data import runs in single transaction for consistency
   - PostGIS updates run outside transaction with per-batch commits
   - Foreign key constraints deferred until after all data loaded
   - Reduces lock contention and WAL overhead

4. **Performance Optimizations for Verification Container**
   - `fsync = off` - Safe for temporary verification (no durability needed)
   - `maintenance_work_mem = 1GB` - Faster index creation
   - `autovacuum = off` - Disable during bulk load
   - `max_wal_size = 4GB` - Reduce checkpoint frequency
   - `shared_buffers = 512MB` - More cache for working data
   - `synchronous_commit = off` - Faster commits
   - Settings applied via `ALTER SYSTEM` with PostgreSQL restart

**Total Import Time:**
- CSV data import: 14-15 minutes
- PostGIS geometry population: 15-20 minutes
- FK constraint recreation: 1-2 minutes
- **Total: 25-35 minutes** for complete import with spatial data

**Verification Process:**
- Creates temporary Docker container on auto-selected port (5433+)
- Uses PostGIS 15-3.3 multi-arch image (ARM64/AMD64 compatible)
- Verifies row counts for all tables
- Creates compressed pg_dump (~145 MB .sql.gz)
- Automatically cleans up container (unless `--no-cleanup`)
- **Total verification time: 25-35 minutes**

**Storage Requirements:**
- CSV files: ~1.5 GB
- PostgreSQL database with indexes: ~3-4 GB
- WAL and temp files during import: ~2-3 GB
- **Total: ~6-8 GB disk space** needed during verification

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Ensure all packages in `requirements.txt` are installed
2. **Network Issues**: Check internet connectivity for source data downloads
3. **Disk Space**: Ensure sufficient space for data processing (several GB)
4. **Memory Limits**: Adjust `DB_MEMORY_LIMIT` if encountering memory issues
5. **Database Locks**: Kill processes holding database locks using `lsof oevk.db` and `kill <PID>`
6. **Parallel Processing Timeouts**: Increase timeout settings for large datasets

### Release Workflow Issues

#### GitHub Token Requirements

To use the release workflow, you need a GitHub Personal Access Token with the following permissions:

- **repo** (full repository access)
- **workflow** (if using GitHub Actions)
- **read:org** (if accessing organization repositories)

**IMPORTANT**: For organization repositories, use **classic personal access tokens** instead of fine-grained tokens. Classic tokens have better organization repository upload permissions.

#### GitHub Authentication
```bash
# Verify GitHub CLI authentication
gh auth status

# Login if needed
gh auth login

# Set token explicitly
gh auth login --with-token <<< "$GITHUB_TOKEN"

# For organization repositories, use classic tokens instead of fine-grained tokens:
# 1. Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
# 2. Create a new classic token with "repo" scope
# 3. Use the classic token (starts with "gho_") instead of fine-grained tokens (start with "github_pat_")
```

#### Release Creation Failures
```bash
# Check if release already exists
gh release view 20250101-1200 --repo your-org/oevk-data

# Delete existing release if needed
gh release delete 20250101-1200 --repo your-org/oevk-data --yes

# Force recreate release
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag 20250101-1200 --force

# For organization repository upload issues, use classic tokens:
# 1. Regenerate token as classic token (starts with "gho_")
# 2. Update GITHUB_TOKEN environment variable
# 3. Test upload: gh release upload 20250101-1200 test_file.txt --repo your-org/oevk-data
```

#### Data Validation Issues
```bash
# Run validation with verbose output
python -m src.cli release validate --staging-dir data/staging --exports-dir exports --verbose

# Check file permissions
ls -la data/staging/
ls -la exports/

# Verify file contents
head -n 5 data/staging/addresses.csv
head -n 5 exports/addresses/Address_001_Budapest.csv
```

#### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto

# Dry run (validate without creating release)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --dry-run
```

### Logs

Detailed logs are written to `logs/oevk_transform_{timestamp}.log` and include:

- Pipeline start/end times
- Step-by-step progress
- Row counts per transformation
- Performance metrics
- Error details with stack traces

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with appropriate tests
4. Ensure all tests pass
5. Submit a pull request

## License

[Add appropriate license information]

## Support

For issues and questions:
- Check the logs in `logs/` directory
- Review the documentation in `specs/`
- Open an issue in the project repository