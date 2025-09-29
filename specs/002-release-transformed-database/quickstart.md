# Quickstart Guide: Release Transformed Database

**Feature**: 002-release-transformed-database  
**Date**: 2025-09-29  
**Status**: Complete

## Overview

This feature automates the release process for transformed Hungarian electoral address data. It packages CSV exports and DuckDB database into compressed archives, creates GitHub releases with unique date-based tags, and provides change summaries between releases.

## Prerequisites

- Python 3.11+
- GitHub CLI (`gh`) installed and authenticated
- Existing ETL pipeline with exported CSV files and DuckDB database
- Write access to the GitHub repository

## Quick Test

### 1. Validate Data Before Release
```bash
python -m src.cli release validate
```
**Expected Output**:
```
Data validation passed
- CSV files: 5 files found, all non-empty
- Database: Valid DuckDB file
- Total size: 245 MB
```

### 2. Create Manual Release
```bash
python -m src.cli release create --tag 20250929-1430 --repo-owner your-username --repo-name your-repo-name
```
**Expected Output**:
```
=== RELEASE CREATED SUCCESSFULLY ===
Release URL: https://github.com/your-username/your-repo-name/releases/tag/20250929-1430
Release Tag: 20250929-1430
Artifacts: 2
```

### 3. Verify Release
```bash
gh release view 20250929-1430
```
**Expected Output**:
```
20250929-1430
Title: Data Release 20250929-1430
Published: 2025-09-29T14:30:00Z

Summary of changes: Initial data release

Assets:
- oevk-data-csv-20250929-1430.zip (98.5 MB)
- oevk-data-db-20250929-1430.zip (57.5 MB)
```

## Automated Workflow

### GitHub Actions Integration

The release workflow automatically triggers when the ETL pipeline completes successfully on the main branch:

```yaml
# .github/workflows/release.yml
name: Create Data Release
on:
  workflow_run:
    workflows: ["ETL Pipeline"]
    types: [completed]
    branches: [main]

jobs:
  release:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Create Release
        run: |
          python -m src.cli release create --auto
```

### Manual Trigger

You can also manually trigger a release at any time:

```bash
# Create release with auto-generated tag
python -m src.cli release create --auto --repo-owner your-username --repo-name your-repo-name

# Create release with specific tag
python -m src.cli release create --tag 20250929-1500 --repo-owner your-username --repo-name your-repo-name
```

## Key Features

### 1. Data Validation
- Validates all CSV export files exist and are non-empty
- Verifies DuckDB database integrity
- Checks file sizes and checksums
- Prevents corrupted releases

### 2. Automated Packaging
- Creates compressed ZIP archives for CSV files
- Creates compressed ZIP archive for DuckDB database
- Generates checksums for all artifacts
- Maintains original file structure

### 3. GitHub Integration
- Creates GitHub releases with unique date-based tags
- Attaches compressed artifacts with descriptive labels
- Generates release notes with change summaries
- Supports both automated and manual releases

### 4. Change Tracking
- Summarizes changes since last release
- Includes data structure modifications
- Provides commit log summaries
- Maintains release history

## File Structure

```
releases/
├── 20250929-1430/
│   ├── oevk-data-csv-20250929-1430.zip
│   ├── oevk-data-db-20250929-1430.zip
│   └── release-metadata.json
exports/
├── addresses.csv
├── counties.csv
├── settlements.csv
└── oevk_data.db
```

## Monitoring

### Release Status
```bash
# Check specific release status
python -m src.cli release status --tag 20250929-1430 --repo-owner your-username --repo-name your-repo-name

# View release history
python -m src.cli release history --repo-owner your-username --repo-name your-repo-name
```

### Performance Metrics
- Release process completes within 15 minutes
- Compression reduces file sizes by 60-70%
- Data validation ensures 100% integrity
- Idempotent operations guarantee consistency

## Troubleshooting

### Common Issues

1. **GitHub CLI not authenticated**
   ```bash
   gh auth login
   ```

2. **Missing data files**
   ```bash
   python -m src.cli release validate
   ```

3. **Release tag already exists**
   ```bash
   # Use a different timestamp
   python -m src.cli release create --tag 20250929-1431 --repo-owner your-username --repo-name your-repo-name
   ```

### Logs and Debugging

```bash
# Enable debug logging
python -m src.cli release create --tag 20250929-1430 --repo-owner your-username --repo-name your-repo-name

# View release logs
cat logs/release.log
```

## Next Steps

After successful release:
1. Verify artifacts are downloadable from GitHub
2. Test data extraction from compressed archives
3. Update project documentation with release information
4. Notify data consumers about the new release