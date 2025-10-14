## ADDED Requirements

### Requirement: Generate PostgreSQL-compatible SQL export

#### Scenario: Export with multiple formats
- **Given** the export command is run with `--formats csv,postgresql`.
- **When** the export process completes.
- **Then** it should generate both CSV files and PostgreSQL-compatible SQL files (`schema.sql` and `data.sql`).

#### Scenario: Export with only PostgreSQL format
- **Given** the export command is run with `--formats postgresql`.
- **When** the export process completes.
- **Then** it should generate only the PostgreSQL-compatible SQL files (`schema.sql` and `data.sql`).

### Requirement: Translate SQLite schema to PostgreSQL

#### Scenario: Schema translation
- **Given** the `generate_postgresql_schema` function is called.
- **When** it processes the `src/database/schema.sql` file.
- **Then** it should output a PostgreSQL-compatible schema where `TEXT PRIMARY KEY` columns are converted to `UUID` and other types are mapped appropriately.

### Requirement: Configure PostgreSQL connection

#### Scenario: Configure connection via command-line
- **Given** the application is run with PostgreSQL connection parameters in the command-line.
- **When** the application attempts to connect to the database.
- **Then** it should use the provided parameters.

#### Scenario: Configure connection via .env file
- **Given** a `.env` file with PostgreSQL connection settings exists.
- **When** the application starts.
- **Then** it should load and use the connection settings from the file.

### Requirement: Automated PostgreSQL setup

#### Scenario: Setup local database with Docker
- **Given** the CLI command `db:setup` is executed.
- **And** a `schema.sql` and `data.sql` file exist in the `exports` directory.
- **When** the command runs.
- **Then** it should start a PostgreSQL container using Docker, wait for it to be ready, and then execute the `schema.sql` and `data.sql` files to set up the database.

### Requirement: Verify PostgreSQL import and create dump

#### Scenario: Import verification with Docker PostgreSQL
- **Given** `schema.sql` and `data.sql` files have been generated in the `exports` directory.
- **When** the verification process is triggered.
- **Then** it should start a temporary Docker PostgreSQL container, import the SQL files using `psql`, and verify the import succeeded.

#### Scenario: Create gzipped database dump
- **Given** SQL files have been successfully imported into a PostgreSQL database.
- **When** the dump creation process is triggered.
- **Then** it should execute `pg_dump` to create a complete database dump and compress it as `oevk_db_{timestamp}.sql.gz` in the `exports` directory.

#### Scenario: Cleanup temporary verification container
- **Given** the import verification and dump creation are complete.
- **When** the verification process finishes.
- **Then** it should stop and remove the temporary Docker PostgreSQL container.

### Requirement: Package PostgreSQL export for release

#### Scenario: Create release with PostgreSQL artifacts
- **Given** a release is being created.
- **And** `schema.sql`, `data.sql`, and `oevk_db_{timestamp}.sql.gz` files are present in the `exports` directory.
- **When** the packaging step is executed.
- **Then** a `oevk-postgresql-{release_tag}.zip` archive containing all PostgreSQL files should be created and included in the release.

### Requirement: Control PostgreSQL export behavior

#### Scenario: PostgreSQL export enabled by default
- **Given** the export command is run without any PostgreSQL-specific flags.
- **When** the export process completes.
- **Then** it should generate PostgreSQL SQL files, perform import verification, and create the gzipped dump.

#### Scenario: Skip PostgreSQL export
- **Given** the export command is run with `--skip-postgresql-export` flag.
- **When** the export process completes.
- **Then** it should skip all PostgreSQL-related export, verification, and dump creation steps.
