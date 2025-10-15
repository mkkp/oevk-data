# Tasks: Add PostgreSQL Export

- [x] **Phase 1: SQL Export and Schema Translation** (COMPLETED)
    - [x] Centralize UUID Conversion in `src/etl/export.py` (`to_uuid3()`, `OEVK_NAMESPACE`).
    - [x] Create `generate_postgresql_schema()` in `src/etl/export.py` to translate SQLite schema to PostgreSQL.
    - [x] Update `export_tables_to_csv` in `src/etl/export.py` to handle PostgreSQL format.
    - [x] Update `export_canonical_addresses_optimized` in `src/etl/export_canonical_v3.py` to handle PostgreSQL format.
    - [x] Add `--skip-postgresql-export` flag to CLI to control export behavior (default: enabled).

- [x] **Phase 2: Import Verification and Dump Creation** (COMPLETED)
    - [x] Create `src/utils/docker_postgresql.py` for Docker PostgreSQL management utilities (209 lines, 6.4 KB).
    - [x] Implement `DockerPostgreSQLManager` class with methods: `create_container()`, `wait_for_ready()`, `stop_and_remove_container()`, `get_connection_info()`.
    - [x] Create `src/etl/postgresql_verify.py` for import verification logic (290 lines).
    - [x] Implement Docker container creation with temporary PostgreSQL instance (postgres:16-alpine).
    - [x] Implement SQL import using `psql` command with error handling and timeout support.
    - [x] Implement `pg_dump` execution to create gzipped database dump (`oevk_db_{timestamp}.sql.gz`).
    - [x] Implement cleanup of temporary Docker container after verification.
    - [x] Add verification step to main export workflow (triggered after SQL generation in `src/cli.py:616-630`).

- [x] **Phase 3: Update Release Process** (COMPLETED)
    - [x] Create `package_postgresql_files` method in `src/release/packaging.py`.
    - [x] Update `create_release_package` in `src/release/workflow.py` to include PostgreSQL packaging.
    - [x] Update `package_postgresql_files` to include SQL files and gzipped dump in ZIP.
    - [x] Create standalone Python loader script `src/release/templates/load_postgresql.py`.
    - [x] Create Python requirements file `src/release/templates/requirements.txt`.
    - [x] Update `package_postgresql_files` to include loader script and requirements in ZIP.
    - [x] Add streaming support to loader script for large files (>10MB).
    - [x] Add `ON CONFLICT DO NOTHING` to all INSERT statements for idempotent loading.

- [x] **Phase 4: Testing** (COMPLETED)
    - [x] Add integration tests for the `db:setup` command (`tests/integration/test_db_setup.py`).
    - [x] Add integration tests for the end-to-end export for both CSV and PostgreSQL formats (`tests/integration/test_postgresql_export.py`).
    - [x] Add unit tests for the `xxhash64` to `UUIDv3` conversion (in integration tests).
    - [x] Add integration tests for import verification with Docker PostgreSQL (`tests/integration/test_postgresql_verify.py`).
    - [x] Add integration tests for gzipped dump creation (`tests/integration/test_postgresql_verify.py`).
    - [x] Add tests to verify the release process creates the PostgreSQL ZIP archive with all files (`tests/unit/test_packaging.py`).
    - [x] Add tests for `--skip-postgresql-export` flag behavior (`tests/integration/test_skip_postgresql_flag.py`).
    - [x] Add performance tests (`tests/performance/test_postgresql_export_performance.py`).

- [x] **Phase 5: Documentation** (COMPLETED)
    - [x] Update `README.md` with PostgreSQL export details.
    - [x] Update `.claude/commands/release.md` to document new release artifacts.
    - [x] Create `.claude/commands/export.md` (replaced csv.md).
    - [x] Create `.claude/commands/database.md` with setup and usage.
    - [x] Document `--skip-postgresql-export` flag in CLI help and documentation.
