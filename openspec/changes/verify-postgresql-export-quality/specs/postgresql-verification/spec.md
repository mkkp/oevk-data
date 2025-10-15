## ADDED Requirements

### Requirement: Verify zero skipped records in PostgreSQL load

**The system SHALL complete PostgreSQL data loading with zero skipped records when using --drop-database or --clean flags.**

#### Scenario: Fresh database load with performance mode
- **Given** a PostgreSQL database is freshly created or cleaned
- **And** the loader is run with `--drop-database` flag
- **When** the data loading completes for 2.2GB data.sql file
- **Then** the final output MUST show "0 skipped" records
- **And** no error messages should appear in the output
- **And** the success message "✓ Loaded successfully" should be displayed

#### Scenario: Load verification with error tracking
- **Given** the loader has error tracking enabled
- **And** the load runs in performance mode (ON CONFLICT stripped)
- **When** the data loading completes
- **Then** the error summary MUST be empty
- **And** no "⚠ New error type" messages should appear
- **And** the warning about skipped records MUST NOT appear

### Requirement: Validate data integrity in loaded database

**The system SHALL ensure all loaded data maintains referential integrity and constraint compliance.**

#### Scenario: Record count validation
- **Given** the PostgreSQL database has been loaded
- **When** querying `SELECT COUNT(*) FROM Address`
- **Then** the result MUST be approximately 3,323,113 records (±1%)
- **And** all entity tables MUST contain their expected record counts

#### Scenario: NULL constraint validation
- **Given** the Address table has NOT NULL constraints on required columns
- **When** querying for NULL values in NOT NULL columns
- **Then** no NULL values MUST exist in PublicSpaceType, FullAddress, PublicSpaceName, or HouseNumber
- **And** no NULL values MUST exist in any foreign key columns (PostalCode_ID, PollingStation_ID, etc.)

#### Scenario: Foreign key integrity validation
- **Given** the Address table has foreign key constraints to reference tables
- **When** validating foreign key relationships
- **Then** all PostalCode_ID values MUST exist in PostalCode table
- **And** all PollingStation_ID values MUST exist in PollingStation table
- **And** all other foreign key references MUST be valid
- **And** no orphaned records MUST exist in reference tables

#### Scenario: OriginalAddressCount validation
- **Given** the Address table has OriginalAddressCount column
- **When** querying OriginalAddressCount values
- **Then** all records MUST have OriginalAddressCount ≥ 1
- **And** some records MUST have OriginalAddressCount > 1 (showing deduplication occurred)
- **And** the sum of all OriginalAddressCount values should match total original addresses

### Requirement: Verify PostgreSQL performance optimizations

**The system SHALL provide acceptable performance for data loading and querying operations.**

#### Scenario: Data loading performance with Python loader
- **Given** a 2.2GB data.sql file is ready to load
- **When** loading with `--drop-database` flag (performance mode)
- **Then** the load MUST complete in less than 15 minutes
- **And** progress tracking MUST show ETA updates every 5%
- **And** memory usage MUST remain under 500MB

#### Scenario: Text search performance with trigram indexes
- **Given** the database has trigram indexes on Address.FullAddress
- **When** executing `SELECT * FROM Address WHERE FullAddress ILIKE '%utca%' LIMIT 100`
- **Then** the query MUST complete in less than 1 second
- **And** the query plan MUST show GIN index usage
- **And** substring searches with leading wildcards MUST be efficient

#### Scenario: Performance comparison with psql
- **Given** the same data.sql file can be loaded with psql
- **When** comparing load times between Python loader and psql
- **Then** psql MUST be at least 5x faster than Python loader
- **And** both methods MUST produce identical results
- **And** documentation MUST recommend psql for production loads >100MB

### Requirement: Validate loader error handling and reporting

**The system SHALL provide detailed error tracking and reporting during data loading operations.**

#### Scenario: Error grouping and counting
- **Given** the loader encounters errors during loading
- **When** multiple errors of the same type occur
- **Then** errors MUST be grouped by type with counts
- **And** the first occurrence of each error type MUST be logged
- **And** an error summary MUST be displayed at completion

#### Scenario: Progress tracking accuracy
- **Given** the loader is processing a large data file
- **When** displaying progress updates
- **Then** progress percentage MUST be accurate based on bytes read
- **And** ETA calculation MUST be based on current throughput
- **And** executed and skipped counts MUST be accurate
- **And** progress MUST update every 5% of file processed

### Requirement: Verify documentation accuracy

**The system SHALL ensure all documentation accurately reflects verified behavior and capabilities.**

#### Scenario: SQL query examples verification
- **Given** documentation contains SQL query examples
- **When** executing each documented query
- **Then** all queries MUST execute without errors
- **And** results MUST match documented descriptions
- **And** performance MUST match documented expectations

#### Scenario: Loader usage examples verification
- **Given** documentation contains loader usage examples
- **When** executing each documented command
- **Then** all commands MUST execute successfully
- **And** behavior MUST match documented descriptions
- **And** all flags and options MUST work as documented

#### Scenario: Schema structure verification
- **Given** documentation describes 13-table schema structure
- **When** inspecting the actual loaded database
- **Then** exactly 13 tables MUST exist
- **And** no internal tables (AddressMapping, DeduplicationReport, Address_new) MUST exist
- **And** Address table structure MUST match documented DDL
- **And** all documented indexes MUST exist
