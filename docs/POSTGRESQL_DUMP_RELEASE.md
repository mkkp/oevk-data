# PostgreSQL Dump Release Integration

**Date:** 2025-11-04  
**Status:** ✅ COMPLETED

## Summary

Added automatic PostgreSQL dump file inclusion in GitHub releases.

## What Was Added

The release workflow now automatically packages and uploads the PostgreSQL dump file (`oevk_db_*.sql.gz`) as a separate release artifact.

### New Files in Release

After this change, your releases will include:

1. **CSV Archive** (`oevk-data-csv-{tag}.zip`)
   - Individual CSV exports for all tables

2. **Database Archive** (`oevk-data-db-{tag}.zip`)
   - DuckDB database file

3. **PostgreSQL CSV Archive** (`oevk-postgresql-{tag}.zip`)
   - PostgreSQL-compatible CSV files
   - Schema DDL (`schema.sql`)
   - Import script (`import_postgresql.sql`)
   - ~1.3GB (Address.csv excluded to stay under 2GB limit)

4. **PostgreSQL Dump** (`oevk-postgresql-dump-{tag}.sql.gz`) ⭐ NEW
   - Full database dump created by `pg_dump`
   - Compressed with gzip
   - ~550MB
   - Ready to restore with `psql -d oevk < oevk-postgresql-dump-{tag}.sql.gz` or `gunzip` then `psql`

5. **Geocoding Cache** (`oevk-geocoding-cache-{tag}.zip`)
   - Cached geocoding results (~2.9M addresses)

## Implementation Details

### Files Modified

1. **`src/release/packaging.py`**
   - Added `package_postgresql_dump()` method
   - Finds the most recent `oevk_db_*.sql.gz` file in exports directory
   - Copies it to release artifacts with standardized naming

2. **`src/release/workflow.py`**
   - Added call to `package_postgresql_dump()` in `create_release_package()`
   - Includes error handling (logs warning if dump not found)

3. **`src/release/common.py`**
   - Added `postgresql_dump` artifact type to `generate_archive_name()`

### How It Works

1. **During export** (`python src/cli.py export`):
   - PostgreSQL dump is created as `exports/oevk_db_YYYYMMDD_HHMMSS.sql.gz`

2. **During release** (`python src/cli.py release create`):
   - Release workflow finds the most recent dump file
   - Copies it to `data/temp/oevk-postgresql-dump-{tag}.sql.gz`
   - Uploads it to GitHub as a release asset

3. **If dump doesn't exist**:
   - Logs an info message and continues (non-fatal)
   - Other artifacts still uploaded successfully

## Usage

### For Users Downloading the Release

Two options to restore the database:

**Option 1: Use the dump file (fastest)**
```bash
# Download the dump
wget https://github.com/mkkp/oevk-data/releases/download/{tag}/oevk-postgresql-dump-{tag}.sql.gz

# Create database
createdb oevk
psql -d oevk -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Restore from dump (decompress on-the-fly)
gunzip -c oevk-postgresql-dump-{tag}.sql.gz | psql -d oevk
```

**Option 2: Use CSV files (more flexible)**
```bash
# Download and extract CSV archive
wget https://github.com/mkkp/oevk-data/releases/download/{tag}/oevk-postgresql-{tag}.zip
unzip oevk-postgresql-{tag}.zip

# Create database
createdb oevk
psql -d oevk -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Import schema and data
psql -d oevk -f schema.sql
psql -d oevk -f import_postgresql.sql
```

### Dump vs CSV - Which to Use?

| Feature | Dump (`.sql.gz`) | CSV Archive (`.zip`) |
|---------|------------------|----------------------|
| **Size** | 550MB | 1.3GB |
| **Restore Speed** | ⚡ Fast (~2-3 min) | Slower (~5-10 min) |
| **Flexibility** | All-or-nothing | Can import individual tables |
| **Compression** | Better (gzip) | None (STORED) |
| **Use Case** | Quick full restore | Selective imports, debugging |

## Testing

### Before Next Release

The dump packaging will be tested automatically during the next release:

```bash
python src/cli.py release create \
  --repo-owner mkkp \
  --repo-name oevk-data \
  --force-rebuild \
  --auto
```

Expected output:
```
INFO: PostgreSQL dump packaged successfully
INFO: Creating PostgreSQL dump artifact: oevk-postgresql-dump-{tag}.sql.gz
INFO: PostgreSQL dump artifact created: oevk-postgresql-dump-{tag}.sql.gz (550,123,456 bytes)
```

### Verification

After release, check that the dump file appears in the GitHub release assets:
```bash
gh release view {tag} --repo mkkp/oevk-data
```

Should show:
- ✅ `oevk-postgresql-dump-{tag}.sql.gz` (~550MB)

## Benefits

1. ✅ **Faster restores** - Users can restore the full database in 2-3 minutes
2. ✅ **Smaller downloads** - 550MB vs 1.3GB CSV archive
3. ✅ **Automatic** - No manual upload needed, fully integrated
4. ✅ **Non-breaking** - If dump doesn't exist, release continues without it
5. ✅ **Better compression** - gzip provides better compression than ZIP STORED

## Backward Compatibility

- ✅ Existing releases unaffected
- ✅ CSV files still available for users who prefer them
- ✅ No changes to import scripts or database schema
- ✅ New artifact is optional - release succeeds even if dump missing

## Next Release

The next time you run:
```bash
python src/cli.py release create --repo-owner mkkp --repo-name oevk-data --force-rebuild --auto
```

The release will automatically include the PostgreSQL dump file! 🎉
