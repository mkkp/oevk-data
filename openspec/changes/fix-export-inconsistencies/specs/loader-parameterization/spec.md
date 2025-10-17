## ADDED Requirements

### Requirement: Support database name parameter in loader script

**The system SHALL accept a `--database` command-line parameter in the `load_postgresql.py` script to specify the target database name.**

#### Scenario: Load to custom database via parameter
- **Given** the load_postgresql.py script is executed with `--database mydb`.
- **When** the script connects to PostgreSQL.
- **Then** it should connect to a database named "mydb" instead of the default.

#### Scenario: Database parameter overrides default
- **Given** the load_postgresql.py script has a default database name of "oevk".
- **And** the script is executed with `--database custom_oevk`.
- **When** the connection is established.
- **Then** it should use "custom_oevk" as the database name.

#### Scenario: Database parameter overrides environment variable
- **Given** the POSTGRES_DB environment variable is set to "env_db".
- **And** the script is executed with `--database cli_db`.
- **When** the connection is established.
- **Then** it should use "cli_db" (command-line takes precedence).

### Requirement: Maintain backward compatibility with existing parameters

**The system SHALL continue to support existing connection parameters (host, port, user, password) without breaking changes.**

#### Scenario: All parameters work together
- **Given** the script is executed with `--host localhost --port 5432 --database mydb --user admin --password secret`.
- **When** the connection is established.
- **Then** all parameters should be used correctly to connect to the specified database.

#### Scenario: Default database name when parameter not provided
- **Given** the script is executed without the `--database` parameter.
- **When** the connection is established.
- **Then** it should use the default database name "oevk" or value from POSTGRES_DB environment variable.

### Requirement: Provide clear error messages for parameter issues

**The system SHALL display informative error messages when database parameter issues occur.**

#### Scenario: Database does not exist
- **Given** the script is executed with `--database nonexistent_db`.
- **And** the database "nonexistent_db" does not exist on the PostgreSQL server.
- **When** the script attempts to connect.
- **Then** it should display a clear error message indicating the database does not exist.

#### Scenario: Invalid database name
- **Given** the script is executed with an invalid database name (e.g., containing prohibited characters).
- **When** the script attempts to use the name.
- **Then** it should display a clear error message about the invalid database name format.
