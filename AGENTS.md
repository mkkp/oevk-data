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
- **Verbose validation with debug logging**: `python -m src.cli --verbose release validate --staging-dir data/staging --exports-dir exports`

### Release Creation
- **Create release with auto-generated tag**: `python -m src.cli release create --repo-owner owner --repo-name repo --auto`
- **Create release with specific tag**: `python -m src.cli release create --repo-owner owner --repo-name repo --tag 20250101-1200`
- **Create draft release**: `python -m src.cli release create --repo-owner owner --repo-name repo --auto --draft`
- **Create prerelease**: `python -m src.cli release create --repo-owner owner --repo-name repo --auto --prerelease`
- **Force overwrite existing release**: `python -m src.cli release create --repo-owner owner --repo-name repo --tag existing-tag --force`
- **Create packages without upload**: `python -m src.cli release create --repo-owner owner --repo-name repo --auto --skip-upload`

### Release Management
- **Check release status**: `python -m src.cli release status --repo-owner owner --repo-name repo --tag 20250101-1200`
- **List recent releases**: `python -m src.cli release history --repo-owner owner --repo-name repo --limit 10`

### Environment Variables
- **GitHub Token**: `GITHUB_TOKEN` (required for release operations)
- **Default directories**: `STAGING_DIR=data/staging`, `EXPORTS_DIR=exports`

## Complete Data Processing Pipeline

The OEVK data processing pipeline includes the following stages:

### Pipeline Stages
1. **Ingestion**: Downloads and loads source data from valasztas.hu
2. **Transformation**: Normalizes data into 8 core tables with parallel processing
3. **Public Space Extraction**: Extracts public space entities (names and types) from addresses
4. **Export**: Creates CSV files for all tables including public space data
5. **Release**: Packages and publishes data to GitHub releases

### Public Space Extraction Features
- **Entity Recognition**: Extracts public space names and types from addresses
- **Relationship Mapping**: Creates settlement-public space relationships
- **Hash-based IDs**: Deterministic xxhash64 identifiers for all entities
- **Data Integrity**: Full validation and referential integrity
- **Export Support**: CSV export for all public space entities

### Public Space Tables
1. **PublicSpaceName**: Unique public space names extracted from addresses
2. **PublicSpaceType**: Unique public space types (utca, tér, etc.)
3. **SettlementPublicSpaces**: Many-to-many relationships between settlements and public spaces

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
- **CSV Archive**: `oevk-data-csv-{tag}.zip` - Contains all CSV files:
  - `addresses/` - Directory containing split address files by settlement (e.g., `Address_001_Budapest.csv`, `Address_002_Debrecen.csv`)
  - `settlements.csv` - Settlement reference data
  - `counties.csv` - County reference data
  - `NationalIndividualElectoralDistrict.csv` - National electoral districts
  - `PollingStation.csv` - Polling station locations
  - `PostalCode.csv` - Postal code data
  - `PostalCode_Settlement.csv` - Postal code to settlement mapping
  - `SettlementIndividualElectoralDistrict.csv` - Settlement to electoral district mapping
  - `PublicSpaceName.csv` - Unique public space names extracted from addresses
  - `PublicSpaceType.csv` - Unique public space types (utca, tér, etc.)
  - `SettlementPublicSpaces.csv` - Many-to-many relationships between settlements and public spaces
- **Database Archive**: `oevk-data-db-{tag}.zip` - Contains oevk.db (main transformed database)
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

# Create packages without uploading to GitHub (local testing)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --skip-upload

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
- **repo** (full repository access) - **REQUIRED**
- **workflow** (if using GitHub Actions)
- **read:org** (if accessing organization repositories)

**IMPORTANT**: For organization repositories, use **classic personal access tokens** instead of fine-grained tokens. Classic tokens have better organization repository upload permissions.

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

# Test GitHub connection and permissions
gh auth status
gh api repos/your-org/oevk-data
```

#### Data Validation Issues
```bash
# Run validation with verbose output
python -m src.cli --verbose release validate --staging-dir data/staging --exports-dir exports

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

# Enable verbose logging with --verbose flag
python -m src.cli --verbose release validate --staging-dir data/staging --exports-dir exports

# Dry run (validate without creating release)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --dry-run

# Test with explicit GitHub token
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --github-token $GITHUB_TOKEN
```

### Organization Repository Troubleshooting

#### Common Organization Repository Issues

**Error**: `HTTP 403: Resource not accessible by personal access token`

**Cause**: Fine-grained personal access tokens have upload permission issues with organization repositories

**Solution**: Use classic personal access tokens instead of fine-grained tokens

```bash
# 1. Regenerate GitHub token as classic token
# Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
# Create new classic token with these scopes:
# - repo (full repository access)
# - workflow (if using GitHub Actions)
# - read:org (organization read access)

# 2. Update environment variable
export GITHUB_TOKEN="your_classic_token_here"  # Should start with "gho_"

# 3. Test repository access
gh api repos/your-org/your-repo

# 4. Test release creation and upload
gh release create test-release --repo your-org/your-repo --title "Test" --notes "Testing"
echo "test file" > test_upload.txt
gh release upload test-release test_upload.txt --repo your-org/your-repo
```

#### Token Type Identification
```bash
# Check token type
export GITHUB_TOKEN="your_token_here"
gh auth status --show-token

# Fine-grained tokens start with: github_pat_...
# Classic tokens start with: gho_...
```

#### Skip-Upload Workaround

If organization permissions can't be resolved immediately, use skip-upload:
```bash
# Create packages without uploading to GitHub
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --skip-upload

# Packages will be saved to data/temp/ for manual upload
ls -la data/temp/

# Manual upload to GitHub release
gh release upload 20250101-1200 data/temp/oevk-data-csv-20250101-1200.zip data/temp/oevk-data-db-20250101-1200.zip --repo your-org/oevk-data
```

#### Verify Organization Access
```bash
# Check current token scopes
gh auth status

# Test repository permissions
gh api repos/your-org/your-repo | jq '.permissions'

# Expected output should include:
# {
#   "admin": true,
#   "maintain": true,
#   "push": true,
#   "triage": true,
#   "pull": true
# }
```

#### Skip-Upload Workaround

If organization permissions can't be resolved immediately, use skip-upload:
```bash
# Create packages without uploading to GitHub
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --skip-upload

# Packages will be saved to data/temp/ for manual upload
ls -la data/temp/

# Manual upload to GitHub release
gh release upload 20250101-1200 data/temp/oevk-data-csv-20250101-1200.zip data/temp/oevk-data-db-20250101-1200.zip --repo your-org/oevk-data
```

#### Verify Organization Access
```bash
# Check current token scopes
gh auth status

# Test repository permissions
gh api repos/your-org/your-repo | jq '.permissions'

# Expected output should include:
# {
#   "admin": true,
#   "maintain": true,
#   "push": true,
#   "triage": true,
#   "pull": true
# }
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
