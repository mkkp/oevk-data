# Tasks: Add PostgreSQL Export

- [x] **Phase 1: SQL Export and Schema Translation**
    - [x] Centralize UUID Conversion in `src/etl/export.py`.
    - [x] Create `generate_postgresql_schema()` in `src/etl/export.py` to translate SQLite schema to PostgreSQL.
    - [x] Update `export_tables_to_csv` in `src/etl/export.py` to handle PostgreSQL format.
    - [x] Update `export_canonical_addresses_optimized` in `src/etl/export_canonical_v3.py` to handle PostgreSQL format.

- [x] **Phase 2: Update Release Process**
    - [x] Create `package_postgresql_files` method in `src/release/packaging.py`.
    - [x] Update `create_release_package` in `src/release/workflow.py` to include PostgreSQL packaging.
    - [x] Create standalone Python loader script `src/release/templates/load_postgresql.py`.
    - [x] Create Python requirements file `src/release/templates/requirements.txt`.
    - [x] Update `package_postgresql_files` to include loader script and requirements in ZIP.
    - [x] Add streaming support to loader script for large files (>10MB).
    - [x] Add `ON CONFLICT DO NOTHING` to all INSERT statements for idempotent loading.

- [x] **Phase 3: Testing**
    - [x] Add integration tests for the `db:setup` command (8/9 tests passing).
    - [x] Add integration tests for the end-to-end export for both CSV and PostgreSQL formats.
    - [x] Add unit tests for the `xxhash64` to `UUIDv3` conversion (10/10 tests passing).
    - [x] Add a test to verify the release process creates the PostgreSQL ZIP archive (5/5 tests passing).

- [x] **Phase 4: Documentation**
    - [x] Update `README.md` and other relevant documentation.
    - [x] Update `.claude/commands/release.md`.
    - [x] Rename `.claude/commands/csv.md` to `export.md` and update its content.
    - [x] Create `.claude/commands/database.md`.
