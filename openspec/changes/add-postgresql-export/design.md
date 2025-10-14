# Design: PostgreSQL Export

## 1. Implementation Details

### 1.1. Local Development Environment

A local PostgreSQL instance can be run using Docker for development and testing.

- **Docker Command:**
  ```bash
  docker run --name oevk -e POSTGRES_PASSWORD=oevk -d -p 15432:5432 postgres
  ```
- **Connection Details:**
  - **Host:** `localhost`
  - **Port:** `15432`
  - **Database:** `oevk`
  - **User:** `oevk`
  - **Password:** `oevk`

The database name, user, and password can be customized using the `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` environment variables when starting the Docker container.

### 1.2. Configuration

The following variables need to be managed for the PostgreSQL connection:

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

These can be provided as command-line arguments or defined in a `.env` file.

## 2. Implementation Plan

### Phase 1: SQL Export and Schema Translation

1.  **Centralize UUID Conversion:**
    - In `src/etl/export.py`, add a `to_uuid3` helper function and `OEVK_NAMESPACE` constant, mirroring the implementation found in `export_canonical_v3.py`. This centralizes the conversion logic.

2.  **Translate SQLite Schema to PostgreSQL:**
    - A new function `generate_postgresql_schema()` will be created in `src/etl/export.py`.
    - This function will read `src/database/schema.sql` and perform the following type conversions:
        - **ID Columns:** All `ID` and `*_ID` columns of type `TEXT PRIMARY KEY` or `TEXT NOT NULL` will be converted to the native **`UUID`** type in PostgreSQL. This matches the final data type after the export-time UUID conversion.
        - Other types will be mapped appropriately (`TEXT` -> `TEXT`, `INTEGER` -> `INTEGER`, etc.).

3.  **Update Export Logic (`src/etl/export.py`):**
    - Modify `export_tables_to_csv` to accept the `formats` argument.
    - If `"postgresql"` is in `formats`:
        - Generate and write `exports/schema.sql`.
        - Open `exports/data.sql` for writing.
        - For each table, read the data. For each row, convert all internal `xxhash64` ID fields to `UUIDv3` strings using the `to_uuid3` function before generating the `INSERT` statement.

4.  **Update Canonical Export Logic (`src/etl/export_canonical_v3.py`):**
    - Modify `export_canonical_addresses_optimized` to accept the `formats` argument.
    - If `"postgresql"` is in `formats`:
        - **Append** `INSERT` statements to the `exports/data.sql` file created by the main export function. The existing UUID conversion logic in this script will be used.

5.  **Add Export Control Flag:**
    - Add `--skip-postgresql-export` flag to CLI (default: PostgreSQL export is enabled).
    - When flag is present, skip all PostgreSQL-related operations (SQL generation, verification, dump creation).

### Phase 2: Import Verification and Dump Creation

1.  **Docker PostgreSQL Management (`src/utils/docker_postgresql.py`):**
    - Create utility functions for Docker container lifecycle:
        - `create_temp_postgresql_container()`: Start temporary PostgreSQL container with unique name
        - `wait_for_postgresql_ready()`: Poll container until PostgreSQL accepts connections
        - `stop_and_remove_container()`: Clean up temporary container
    - Use Docker Python SDK or subprocess calls to `docker` CLI

2.  **Import Verification (`src/etl/postgresql_verify.py`):**
    - Create `verify_and_dump_postgresql()` function:
        - Start temporary PostgreSQL container using Docker utilities
        - Wait for database to be ready
        - Execute `psql` to import `schema.sql` (create tables, indexes)
        - Execute `psql` to import `data.sql` (insert data)
        - Verify import success by querying row counts
        - Execute `pg_dump` to create complete database dump
        - Compress dump using `gzip` as `oevk_db_{timestamp}.sql.gz`
        - Stop and remove temporary container
        - Log all operations with detailed error handling

3.  **Integration with Export Workflow:**
    - Call verification function after SQL files are generated
    - Only proceed if verification succeeds
    - Include gzipped dump in export artifacts

### Phase 3: Update Release Process

1.  **Add PostgreSQL Packaging (`src/release/packaging.py`):**
    - Create a new method `package_postgresql_files` in the `FilePackager` class.
    - This method will find `schema.sql`, `data.sql`, and `oevk_db_{timestamp}.sql.gz` in the `exports_dir`.
    - It will create a new ZIP archive named `oevk-postgresql-{release_tag}.zip`.
    - Include standalone loader script and requirements.txt
    - It will return an artifact dictionary, similar to the other packaging methods.

2.  **Update Release Workflow (`src/release/workflow.py`):**
    - In the `create_release_package` method of the `ReleaseWorkflow` class, add a call to the new `self.packager.package_postgresql_files` method.
    - Append the returned artifact dictionary to the `artifacts` list.

## 3. Technical Decisions

### 3.1. Why Use Temporary Docker Container for Verification?

**Decision:** Use a temporary Docker PostgreSQL container for import verification rather than requiring a pre-existing database.

**Rationale:**
- **Isolation:** Each verification runs in a clean environment, preventing contamination from previous runs
- **Consistency:** Ensures the same PostgreSQL version used across all environments
- **Automation:** No manual database setup required before running verification
- **CI/CD Friendly:** Works in automated pipelines without external dependencies

**Alternatives Considered:**
- **Manual PostgreSQL Setup:** Requires users to maintain a separate database instance (rejected - too much manual work)
- **Skip Verification:** Trust SQL generation without testing (rejected - risky for data integrity)

### 3.2. Why Create Gzipped Dump?

**Decision:** Generate `pg_dump` output as gzipped file (`oevk_db_{timestamp}.sql.gz`) in addition to raw SQL files.

**Rationale:**
- **Size Reduction:** Gzip compression typically reduces PostgreSQL dumps by 70-90%
- **Single File Distribution:** Users can import complete database with one file instead of two (schema + data)
- **Version Compatibility:** `pg_dump` format is more portable across PostgreSQL versions
- **Performance:** Faster to download and transfer compressed file

**Alternatives Considered:**
- **Only Raw SQL Files:** Larger file sizes, two files to manage (rejected - less convenient)
- **Custom Binary Format:** Requires PostgreSQL-specific tools to restore (rejected - less accessible)

### 3.3. Export Control Design

**Decision:** Enable PostgreSQL export by default with opt-out flag `--skip-postgresql-export`.

**Rationale:**
- **Progressive Enhancement:** Users get PostgreSQL support automatically
- **Backward Compatible:** Existing workflows continue to work
- **Explicit Opt-Out:** Users who don't need PostgreSQL can easily disable it

**Implementation:**
- CLI flag: `--skip-postgresql-export` (boolean, default=False)
- When enabled, skip: SQL generation, verification, dump creation, packaging
