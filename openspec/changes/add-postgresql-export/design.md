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

### Phase 2: Update Release Process

1.  **Add PostgreSQL Packaging (`src/release/packaging.py`):**
    - Create a new method `package_postgresql_files` in the `FilePackager` class.
    - This method will find `schema.sql` and `data.sql` in the `exports_dir`.
    - It will create a new ZIP archive named `oevk-postgresql-{release_tag}.zip`.
    - It will return an artifact dictionary, similar to the other packaging methods.

2.  **Update Release Workflow (`src/release/workflow.py`):**
    - In the `create_release_package` method of the `ReleaseWorkflow` class, add a call to the new `self.packager.package_postgresql_files` method.
    - Append the returned artifact dictionary to the `artifacts` list.
