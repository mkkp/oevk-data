# Data Model: Release Transformed Database

**Feature**: 002-release-transformed-database  
**Date**: 2025-09-29  
**Status**: Complete

## Core Entities

### Release Package
Represents a packaged release of transformed data ready for distribution.

**Fields**:
- `release_id` (string): Unique identifier (deterministic hash based on timestamp + content)
- `release_tag` (string): Human-readable tag (YYYYMMDD-HHMM format)
- `created_at` (datetime): Release creation timestamp
- `data_version` (string): Version identifier from transformation pipeline
- `status` (string): Release status (pending, created, failed)
- `change_summary` (string): Summary of changes since last release
- `github_release_url` (string): URL to GitHub release

**Validation Rules**:
- `release_tag` must match pattern `^\\d{8}-\\d{4}$`
- `status` must be one of: pending, created, failed
- `release_id` must be deterministic hash using xxhash64

### Release Artifact
Represents individual compressed files within a release package.

**Fields**:
- `artifact_id` (string): Unique identifier (deterministic hash)
- `release_id` (string): Foreign key to Release Package
- `artifact_type` (string): Type of artifact (csv_archive, database_archive)
- `file_path` (string): Path to compressed artifact file
- `file_size` (integer): Size in bytes
- `checksum` (string): SHA-256 checksum for integrity verification
- `created_at` (datetime): Artifact creation timestamp

**Validation Rules**:
- `artifact_type` must be one of: csv_archive, database_archive
- `file_size` must be positive integer
- `checksum` must be valid SHA-256 hash

### Release Metadata
Stores metadata about the release process and data validation.

**Fields**:
- `metadata_id` (string): Unique identifier
- `release_id` (string): Foreign key to Release Package
- `total_files` (integer): Number of files packaged
- `total_size` (integer): Total size of all artifacts in bytes
- `validation_status` (string): Data validation result (passed, failed)
- `validation_errors` (array): List of validation errors if any
- `pipeline_run_id` (string): Identifier of the transformation pipeline run

**Validation Rules**:
- `validation_status` must be one of: passed, failed
- `total_files` must be positive integer
- `total_size` must be positive integer

## Relationships

- **Release Package** 1:N **Release Artifact** (one release contains multiple artifacts)
- **Release Package** 1:1 **Release Metadata** (each release has metadata)

## State Transitions

### Release Package Status Flow
```
pending → created → [final]
pending → failed → [final]
```

**Rules**:
- Initial status is `pending` when release process starts
- Status changes to `created` when GitHub release is successfully created
- Status changes to `failed` if any step in the release process fails
- Once in `created` or `failed` state, cannot be modified

## Data Integrity Constraints

1. **Referential Integrity**: All foreign keys must reference existing entities
2. **Uniqueness**: 
   - `release_tag` must be unique across all releases
   - `release_id` must be unique
   - `artifact_id` must be unique
3. **Consistency**: 
   - All artifacts must belong to a valid release
   - Metadata must reference a valid release

## Deterministic Hash Generation

All entity IDs use xxhash64 for deterministic generation:

- **Release Package ID**: `xxhash64(release_tag + created_at.isoformat())`
- **Release Artifact ID**: `xxhash64(release_id + artifact_type + file_path)`
- **Release Metadata ID**: `xxhash64(release_id + "metadata")`

## Data Validation Rules

### Pre-release Validation
- All CSV export files must exist and be non-empty
- DuckDB database file must exist and be valid
- File sizes must be within expected ranges
- Checksums must match expected values

### Post-release Validation
- Compressed archives must be valid and extractable
- GitHub release must be accessible
- Release artifacts must match expected counts and sizes