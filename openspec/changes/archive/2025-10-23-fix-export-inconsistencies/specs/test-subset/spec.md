## ADDED Requirements

### Requirement: Generate representative test data subset

**The system SHALL provide a utility to generate a smaller, representative subset of the full OEVK database for faster testing of export/import pipelines.**

#### Scenario: Create subset with Budapest districts
- **Given** the subset generation utility is executed.
- **When** processing Budapest data.
- **Then** it should include exactly 3 selected districts from Budapest.

#### Scenario: Create subset with settlements from multiple counties
- **Given** the subset generation utility is executed.
- **When** selecting non-Budapest settlements.
- **Then** it should include 10 settlements distributed across 3 different counties.

#### Scenario: Include all addresses for selected settlements
- **Given** specific settlements have been selected for the subset.
- **When** filtering address data.
- **Then** all addresses associated with the selected settlements should be included in the subset.

#### Scenario: Preserve referential integrity in subset
- **Given** a subset database has been generated.
- **When** validating foreign key relationships.
- **Then** all foreign key constraints should be satisfied within the subset data.

### Requirement: Enable fast pipeline testing with subset

**The system SHALL enable complete export/import pipeline testing with the subset database in under 30 seconds.**

#### Scenario: Subset database processes faster than full database
- **Given** a subset database has been generated.
- **When** running the complete export/import pipeline on the subset.
- **Then** the total processing time should be under 30 seconds (vs. 2.5 minutes for full dataset).

#### Scenario: Subset includes diverse address patterns
- **Given** the subset generation process selects settlements.
- **When** analyzing address patterns in the subset.
- **Then** it should include diverse patterns (different address formats, building types, etc.) representative of the full dataset.

### Requirement: Support optional settlement limiting in loader

**The system SHALL provide an optional `--limit-settlements` parameter in the loader script for quick targeted tests.**

#### Scenario: Load limited number of settlements
- **Given** the loader script is executed with `--limit-settlements 5`.
- **When** processing settlement data.
- **Then** it should load only the first 5 settlements and their associated addresses.

#### Scenario: Full load when parameter not provided
- **Given** the loader script is executed without `--limit-settlements`.
- **When** processing data.
- **Then** it should load all settlements as normal.

### Requirement: Document subset generation process

**The system SHALL provide clear documentation on how to generate and use the test subset database.**

#### Scenario: Subset utility includes help text
- **Given** the subset generation utility is executed with `--help`.
- **When** displaying help information.
- **Then** it should explain all parameters and usage examples.

#### Scenario: Subset configuration is reproducible
- **Given** the subset generation utility is executed with specific parameters.
- **When** run multiple times with the same parameters.
- **Then** it should produce identical subset selections (deterministic).
