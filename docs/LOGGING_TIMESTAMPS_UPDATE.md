# Logging Timestamps Update

**Date:** 2025-11-04  
**Status:** ✅ COMPLETED

## Summary

Updated the logging system to include timestamps in all log formatters, including console output.

## Changes Made

### File Modified: `src/utils/pipeline_logging.py`

**Before:**
```python
"simple": {"format": "%(levelname)s: %(message)s"},
```

**After:**
```python
"simple": {
    "format": "%(asctime)s - %(levelname)s: %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
},
```

## Logging Configuration Overview

The application now uses three formatters, all with timestamps:

### 1. **Detailed Formatter** (File Logging)
```
Format: %(asctime)s - %(name)s - %(levelname)s - %(message)s
Example: 2025-11-04 12:34:56 - src.etl.transform - INFO - Transforming data
```

### 2. **Simple Formatter** (Console Output) - ⭐ UPDATED
```
Format: %(asctime)s - %(levelname)s: %(message)s
Example: 2025-11-04 12:34:56 - INFO: Transforming data
```

### 3. **Pipeline Formatter** (Pipeline Logging)
```
Format: %(asctime)s - %(levelname)s - [%(name)s] %(message)s
Example: 2025-11-04 12:34:56 - INFO - [pipeline.etl] Transforming data
```

## Timestamp Format

All formatters use the same timestamp format:
- **Format:** `%Y-%m-%d %H:%M:%S`
- **Example:** `2025-11-04 12:34:56`
- **Precision:** Seconds (not milliseconds)

## Benefits

✅ **Consistent timestamps** across all log outputs  
✅ **Console logs now timestamped** - easier to track timing of operations  
✅ **File logs remain detailed** with module names  
✅ **Pipeline logs maintain structured format** with component tracking  

## Impact

### Before
Console output had no timestamps:
```
INFO: Starting transformation
INFO: Completed transformation
```

### After
Console output now includes timestamps:
```
2025-11-04 12:34:56 - INFO: Starting transformation
2025-11-04 12:37:23 - INFO: Completed transformation
```

## Logging System Architecture

The application uses Python's `logging` module with:

1. **Rotating File Handler**
   - Log files: `logs/oevk_transform_YYYYMMDD_HHMMSS.log`
   - Max size: 10MB (configurable)
   - Backup count: 5 files (configurable)
   - Format: Detailed formatter

2. **Console Handler** (stdout)
   - Format: Simple formatter (**now with timestamps**)
   - Level: INFO (always)

3. **Specialized Loggers**
   - `PipelineLogger` - Structured logging for ETL operations
   - `PipelineMetrics` - Performance metrics tracking
   - `PublicSpaceExtractionMetrics` - Entity extraction metrics

## Files Using Logging

All 20 Python modules in `src/` use the centralized logging system:

- ✅ `src/etl/*.py` (8 files) - ETL transformations
- ✅ `src/release/*.py` (3 files) - Release management
- ✅ `src/database/*.py` (2 files) - Database operations
- ✅ `src/utils/*.py` (4 files) - Utilities
- ✅ `src/cli.py` (1 file) - CLI interface

**Note:** `cli.py` uses `print()` statements for user-facing output (release status, etc.), which is appropriate and not logging.

## Configuration

Logging can be configured via `setup_logging()` parameters:

```python
setup_logging(
    log_dir="logs",              # Log directory
    log_level="INFO",             # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_format="detailed",        # simple, detailed, pipeline
    max_file_size="10MB",         # Max log file size
    backup_count=5,               # Number of backup files
)
```

## Testing

To verify timestamps appear in console output:

```bash
python src/cli.py run
```

You should now see timestamps in all console log messages:
```
2025-11-04 12:34:56 - INFO: Logging system initialized
2025-11-04 12:34:56 - INFO: Log file: logs/oevk_transform_20251104_123456.log
2025-11-04 12:34:57 - INFO: Starting data ingestion
...
```

## Backward Compatibility

✅ **No breaking changes**  
✅ **All existing logs still work**  
✅ **File logs unchanged** (already had timestamps)  
✅ **Only console output enhanced** with timestamps  

## Future Enhancements

Potential improvements (not implemented):

- Add millisecond precision: `datefmt="%Y-%m-%d %H:%M:%S.%f"`
- Add timezone information: `datefmt="%Y-%m-%d %H:%M:%S %Z"`
- Add colored console output for different log levels
- Add JSON formatter for machine-readable logs
- Add log aggregation (e.g., to Elasticsearch, CloudWatch)
