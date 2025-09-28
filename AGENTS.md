# AGENTS.md - OEVK Data Processing Project

## Build/Lint/Test Commands
- **No build system configured yet** - Project is in specification phase
- **Test command**: `python -m pytest tests/` (when tests are implemented)
- **Single test**: `python -m pytest tests/test_file.py::test_function -v`
- **Lint**: `ruff check .` (when Python code is added)
- **Type check**: `mypy .` (when Python code is added)

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
- Modular scripts: ingest.py, transform.py, export.py
- Separate configuration from business logic
- Use environment variables for configuration