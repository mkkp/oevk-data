# AGENTS.md - OEVK Data Processing Project

## Build/Lint/Test Commands
- **Test command**: `python -m pytest tests/`
- **Single test**: `python -m pytest tests/test_file.py::test_function -v`
- **Lint**: `ruff check .`
- **Type check**: `mypy .`
- **Release workflow**: `python -m src.cli release create --auto`

## Release Workflow Commands

### Data Validation
- **Validate release data**: `python -m src.cli release validate --staging-dir data/staging --exports-dir exports`
- **Validate with custom directories**: `python -m src.cli release validate --staging-dir /path/to/staging --exports-dir /path/to/exports`

### Release Creation
- **Create release with auto-generated tag**: `python -m src.cli release create --repo-owner owner --repo-name repo --auto`
- **Create release with specific tag**: `python -m src.cli release create --repo-owner owner --repo-name repo --tag 20250101-1200`
- **Create draft release**: `python -m src.cli release create --repo-owner owner --repo-name repo --auto --draft`
- **Create prerelease**: `python -m src.cli release create --repo-owner owner --repo-name repo --auto --prerelease`
- **Force overwrite existing release**: `python -m src.cli release create --repo-owner owner --repo-name repo --tag existing-tag --force`

### Release Management
- **Check release status**: `python -m src.cli release status --repo-owner owner --repo-name repo --tag 20250101-1200`
- **List recent releases**: `python -m src.cli release history --repo-owner owner --repo-name repo --limit 10`

### Environment Variables
- **GitHub Token**: `GITHUB_TOKEN` (required for release operations)
- **Default directories**: `STAGING_DIR=data/staging`, `EXPORTS_DIR=exports`

## Code Style Guidelines

### Language & Framework
- **Primary language**: Python 3.11+
- **Data processing**: Polars or DuckDB for large datasets (>3M rows)
- **Database**: SQLite/DuckDB for staging/target (single-file, zero admin)

### Imports & Structure
- Use absolute imports
- Group imports: standard library, third-party, local modules
- Follow PEP 8 for Python code
- Use type hints for all functions and variables

### Naming Conventions
- **Variables**: snake_case (`county_code`, `settlement_name`)
- **Functions**: snake_case (`load_addresses_csv`, `transform_data`)
- **Classes**: PascalCase (`CountyLoader`, `AddressTransformer`)
- **Constants**: UPPER_SNAKE_CASE (`DATA_DIR`, `CHUNK_SIZE`)

### Data Processing Patterns
- Use deterministic hash IDs for all entities (xxhash64 recommended)
- Trim whitespace, convert empty strings to `NULL`
- Preserve diacritics and original casing for Hungarian text
- Use vectorized operations, avoid Python row loops
- Process data in chunks (100k-500k rows)

### Error Handling
- Use structured logging with levels (INFO/DEBUG)
- Validate data quality with referential integrity checks
- Stage invalid rows with error codes and messages
- Make operations idempotent and restartable

### File Organization
- Keep SQL DDL in separate files
- Modular scripts: ingest.py, transform.py, export.py, release/
- Separate configuration from business logic
- Use environment variables for configuration

### Release Workflow Architecture

#### Core Modules
- **Workflow Orchestrator**: `src/release/workflow.py` - Coordinates complete release process
- **Data Validation**: `src/release/validation.py` - Pre-release integrity and quality checks
- **File Packaging**: `src/release/packaging.py` - Creates compressed ZIP archives
- **GitHub Integration**: `src/release/github.py` - GitHub CLI integration for releases
- **Data Models**: `src/release/models.py` - ReleasePackage, ReleaseArtifact, ReleaseMetadata

#### Release Artifacts
- **CSV Archive**: `oevk-data-csv-{tag}.zip` - Contains addresses.csv, settlements.csv, counties.csv
- **Database Archive**: `oevk-data-db-{tag}.zip` - Contains database.duckdb
- **Release Metadata**: JSON metadata with validation results and performance metrics

#### Release Tags
- **Format**: YYYYMMDD-HHMM (timestamp-based to prevent duplicates)
- **Auto-generation**: Uses current timestamp when not specified
- **Validation**: Ensures unique tags to prevent conflicts

#### Data Validation
- **File Existence**: Verifies all required files exist
- **File Sizes**: Ensures files have reasonable sizes
- **File Integrity**: Validates files are readable and not corrupted
- **Data Completeness**: Checks for required headers and data
- **Referential Integrity**: Validates relationships between entities
- **Data Freshness**: Ensures data is recent (≤24 hours old)

#### Performance Targets
- **Complete Workflow**: ≤15 minutes for full release process
- **Data Validation**: ≤2 minutes for comprehensive checks
- **Package Creation**: ≤5 minutes for artifact compression
- **GitHub Integration**: ≤3 minutes for release creation
- **Idempotent Operations**: Safe to retry failed operations

## Release Workflow Usage Examples

### Basic Release Creation
```bash
# Set GitHub token (required)
export GITHUB_TOKEN="ghp_your_token_here"

# Create release with auto-generated tag
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto

# Create release with specific tag
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag 20250101-1200
```

### Advanced Release Scenarios
```bash
# Create draft release for review
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --draft

# Create prerelease (beta/alpha)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --prerelease

# Force overwrite existing release
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag existing-tag --force

# Validate data before release
python -m src.cli release validate --staging-dir data/staging --exports-dir exports
```

### Release Management
```bash
# Check release status
python -m src.cli release status --repo-owner your-org --repo-name oevk-data --tag 20250101-1200

# List recent releases
python -m src.cli release history --repo-owner your-org --repo-name oevk-data --limit 10

# Get detailed release information
python -m src.cli release info --repo-owner your-org --repo-name oevk-data --tag 20250101-1200
```

## Environment Setup

### Required Environment Variables
```bash
# GitHub Personal Access Token (required for releases)
export GITHUB_TOKEN="ghp_your_token_here"

# Optional: Custom directories
export STAGING_DIR="/path/to/staging"
export EXPORTS_DIR="/path/to/exports"
```

### GitHub Token Permissions
- **repo** (full repository access)
- **workflow** (if using GitHub Actions)
- **read:org** (if accessing organization repositories)

### Prerequisites
- **Python 3.11+** with required dependencies
- **GitHub CLI (gh)** installed and authenticated
- **GitHub Personal Access Token** with appropriate permissions
- **Data processing pipeline** completed (staging and exports directories populated)

## Troubleshooting

### Common Issues

#### GitHub Authentication
```bash
# Verify GitHub CLI authentication
gh auth status

# Login if needed
gh auth login

# Set token explicitly
gh auth login --with-token <<< "$GITHUB_TOKEN"
```

#### Release Creation Failures
```bash
# Check if release already exists
gh release view 20250101-1200 --repo your-org/oevk-data

# Delete existing release if needed
gh release delete 20250101-1200 --repo your-org/oevk-data --yes

# Force recreate release
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag 20250101-1200 --force
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
head -n 5 exports/addresses.csv
```

#### Performance Issues
```bash
# Run performance tests
python -m pytest tests/performance/ -v

# Monitor system resources during release
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --monitor

# Check disk space
df -h
du -sh data/staging/ exports/
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto

# Dry run (validate without creating release)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --dry-run
```

## Performance Monitoring

### Release Performance Commands
```bash
# Run performance benchmarks
python -m pytest tests/performance/test_release_performance.py -v

# Monitor release timing
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --timing

# Generate performance report
python -m src.cli release performance --repo-owner your-org --repo-name oevk-data --tag 20250101-1200
```

### Expected Performance Metrics
- **Total Release Time**: ≤15 minutes
- **Data Validation**: ≤2 minutes  
- **Package Creation**: ≤5 minutes
- **GitHub Operations**: ≤3 minutes
- **File Compression**: ≤2 minutes

### Resource Requirements
- **Memory**: ≥4GB RAM for large datasets
- **Disk Space**: ≥2GB free space for temporary files
- **Network**: Stable internet connection for GitHub operations
- **CPU**: Multi-core processor for parallel operations
