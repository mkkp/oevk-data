## ADDED Requirements

### Requirement: Export polling district coordinate data to PostgreSQL

**The system SHALL export `center` and `polygon` coordinate columns for polling districts (TEVK - SettlementIndividualElectoralDistrict) to PostgreSQL schema and data files with appropriate geometric data types.**

#### Scenario: Schema includes coordinate columns for polling districts
- **Given** the PostgreSQL schema generation process is running.
- **When** the schema.sql file is created.
- **Then** the `SettlementIndividualElectoralDistrict` table should include `center` and `polygon` columns with appropriate geometric data types (GEOMETRY or TEXT).

#### Scenario: Polling district coordinate data exported in data.sql
- **Given** polling districts (TEVK) with center and polygon coordinate data exist in the source data.
- **When** the data.sql file is generated.
- **Then** INSERT statements for `SettlementIndividualElectoralDistrict` should include the coordinate values in a format compatible with PostgreSQL geometric types.

#### Scenario: Coordinate data successfully loaded into PostgreSQL
- **Given** schema.sql and data.sql files with polling district coordinate columns have been created.
- **When** the files are loaded into a PostgreSQL database using the loader script.
- **Then** the coordinate data should be successfully inserted into `SettlementIndividualElectoralDistrict` without errors.

### Requirement: Handle null coordinate values

**The system SHALL properly handle null or missing coordinate values during export and import.**

#### Scenario: Polling district with null center coordinate
- **Given** a polling district record with a null `center` value.
- **When** exporting to PostgreSQL.
- **Then** the INSERT statement for `SettlementIndividualElectoralDistrict` should use NULL for the center column.

#### Scenario: Polling district with null polygon coordinate
- **Given** a polling district record with a null `polygon` value.
- **When** exporting to PostgreSQL.
- **Then** the INSERT statement for `SettlementIndividualElectoralDistrict` should use NULL for the polygon column.

### Requirement: Support geospatial queries in PostgreSQL

**The system SHALL enable geospatial analysis by using appropriate PostgreSQL geometric types that support spatial indexing and queries.**

#### Scenario: Coordinate columns support spatial queries
- **Given** coordinate data has been loaded into PostgreSQL with GEOMETRY types.
- **When** a user executes a spatial query (e.g., ST_Distance, ST_Contains).
- **Then** the query should execute successfully using the coordinate columns.

#### Scenario: Coordinate columns can be indexed
- **Given** coordinate columns exist in the PostgreSQL database.
- **When** a GIST index is created on a coordinate column.
- **Then** the index should be created successfully and improve query performance.
