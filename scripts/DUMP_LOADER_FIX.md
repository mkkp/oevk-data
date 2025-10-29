<!--
DOCUMENT METADATA
=================
Title: Dump Loader Memory Issue Fix
Type: Changelog
Category: Fix
Status: Implemented
Version: 1.0
Created: 2025-10-29
Last Updated: 2025-10-29
Author: System

Related Documents:
- Script Documentation (scripts/README.md)
- Main README (../README.md - Option C: Load Latest Dump)

Related Code:
- scripts/load_dump_to_docker.py (load_dump function: streaming implementation)
- scripts/load_dump_to_docker.py (optimize_postgresql function)

Dependencies:
- Docker
- PostgreSQL/PostGIS Docker image
- Python 3.9+
- gunzip command-line tool

Keywords: dump-loader, memory-issue, oom, postgresql, streaming, optimization, docker, fix

Summary:
Fix documentation for load_dump_to_docker.py memory issues when importing large PostgreSQL dumps (554MB compressed). Root causes: loading entire file into memory with f.read(), default PostgreSQL settings not optimized for bulk imports. Solutions: implemented streaming via shell pipeline (gunzip | docker exec psql), added PostgreSQL performance optimizations (shared_buffers, work_mem, fsync=off). Results: successful import of 3.3M addresses in 2-5 minutes.

Audience:
Developers maintaining the dump loader script, DevOps engineers troubleshooting import issues.
-->

# Dump Loader Memory Issue Fix

## Problem

The initial version of `load_dump_to_docker.py` was failing during import of large dump files (554 MB compressed) with the following error:

```
ERROR: Import failed with exit code 2
STDERR: FATAL:  terminating connection due to administrator command
server closed the connection unexpectedly
	This probably means the server terminated abnormally
	before or while processing the request.
connection to server was lost
```

**Root Cause**: PostgreSQL was running out of memory (OOM) during the import process.

## Issues Identified

1. **Memory Loading**: The script was loading the entire decompressed dump file into memory using `f.read()` before sending it to PostgreSQL
   - 554 MB compressed → ~2-3 GB decompressed
   - This caused Python to consume excessive memory

2. **Default PostgreSQL Settings**: PostgreSQL was running with default Docker settings
   - Limited `shared_buffers`, `work_mem`, and `maintenance_work_mem`
   - Not optimized for large bulk imports

3. **Process Communication**: Using `subprocess.communicate(input=f.read())` loads entire content into memory

## Solutions Implemented

### 1. Streaming Data Import

**Before** (memory-intensive):
```python
with gzip.open(dump_file, "rb") as f:
    process = subprocess.Popen([...], stdin=subprocess.PIPE, ...)
    stdout, stderr = process.communicate(input=f.read())  # Loads entire file
```

**After** (streaming):
```python
import shlex

cmd = f"gunzip -c {shlex.quote(str(dump_file))} | docker exec -i {container} psql -U oevk -d {db}"

process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, ...)

# Read output line by line to avoid memory issues
for line in process.stdout:
    last_line = line.strip()
```

**Benefits**:
- Data streams directly from gunzip to PostgreSQL
- Python process uses minimal memory
- No intermediate buffering in memory

### 2. PostgreSQL Performance Optimizations

Added `optimize_postgresql()` function that applies these settings:

```python
optimizations = [
    "ALTER SYSTEM SET shared_buffers = '256MB';",
    "ALTER SYSTEM SET work_mem = '64MB';",
    "ALTER SYSTEM SET maintenance_work_mem = '256MB';",
    "ALTER SYSTEM SET effective_cache_size = '1GB';",
    "ALTER SYSTEM SET checkpoint_completion_target = 0.9;",
    "ALTER SYSTEM SET wal_buffers = '16MB';",
    "ALTER SYSTEM SET max_wal_size = '2GB';",
    "ALTER SYSTEM SET fsync = off;",  # Unsafe but faster for initial load
    "ALTER SYSTEM SET full_page_writes = off;",  # Unsafe but faster
]
```

**Note**: `fsync=off` and `full_page_writes=off` are unsafe for production but acceptable for initial data loads in Docker containers.

### 3. Updated Process Flow

**New steps** (7 total, was 6):
1. Check Docker
2. Find dump file
3. Setup container
4. Wait for PostgreSQL
5. **Optimize PostgreSQL settings** (NEW)
6. Create database
7. Load dump (streaming)
8. Verify import

## Results

### Before Fix
- ❌ Import failed with OOM error
- ❌ 554 MB dump could not be imported
- ❌ PostgreSQL crashed during import

### After Fix
- ✅ Import completed successfully
- ✅ 554 MB dump imported in ~2-5 minutes
- ✅ 3,264,270 addresses imported
- ✅ Total 3,309,094 rows across all tables
- ✅ All verification checks passed

### Performance Metrics

```
Import Statistics:
- Dump size: 554.3 MB (compressed)
- Import time: ~2-5 minutes
- Memory usage: Minimal (streaming)
- Success rate: 100%

Table Counts:
- address:         3,264,270 rows
- county:                 21 rows
- settlement:          3,178 rows
- oevk:                  107 rows
- tevk:                4,598 rows
- postal_code:         3,107 rows
- polling_station:     8,548 rows
- public_space_name:  25,117 rows
- public_space_type:     148 rows
Total:             3,309,094 rows
```

## Testing

Verified with actual dump file:
```bash
python scripts/load_dump_to_docker.py
```

Output:
```
=== Step 6/7: Loading dump ===
INFO: Importing data (this may take several minutes)...
✓ Dump loaded successfully

=== Step 7/7: Verifying import ===
✓ address                         3,264,270 rows
✓ Import verification passed
✓ Import completed successfully!
```

## Files Modified

1. **scripts/load_dump_to_docker.py**
   - Added `optimize_postgresql()` function
   - Changed `load_dump()` to use shell pipeline streaming
   - Updated step count from 6 to 7
   - Added PostgreSQL performance optimizations

2. **README.md**
   - Updated expected output to reflect 7 steps
   - Updated dump size from 145 MB to 554 MB
   - Added optimization step documentation

3. **scripts/README.md**
   - Updated performance metrics
   - Documented streaming approach
   - Updated memory requirements

## Lessons Learned

1. **Always stream large files** - Never load entire files into memory when processing large datasets
2. **Optimize database settings** - Default settings are rarely optimal for bulk operations
3. **Use shell pipelines** - Shell pipelines are efficient for streaming data between processes
4. **Test with actual data** - Always test with production-sized datasets

## Future Improvements

Potential enhancements:
1. Add progress indicator during import (currently silent during load)
2. Make optimization settings configurable via CLI arguments
3. Add option to skip optimizations for production imports
4. Implement retry logic for transient failures
5. Add dump file validation before import

## Related Issues

- PostgreSQL OOM during large imports
- Docker container memory constraints
- Python subprocess memory usage
- Streaming vs buffering trade-offs
