## ADDED Requirements

### Requirement: Correct foreign key references in electoral district tables

**The system SHALL populate foreign key columns in electoral district tables with correct entity IDs based on proper data source mappings.**

#### Scenario: Settlement individual electoral district references correct settlement
- **Given** a settlement individual electoral district record is being created.
- **When** the `settlement_id` column is populated.
- **Then** it should reference the correct settlement entity ID based on the settlement code from the source data.

#### Scenario: National individual electoral district references correct county
- **Given** a national individual electoral district record is being created.
- **When** the `nationalindividualelectoraldistrict_id` column is populated in related tables.
- **Then** it should reference the correct national district entity ID based on the OEVK code from source data.

### Requirement: Populate district names with correct geographic entity

**The system SHALL populate the `name` column in `nationalindividualelectoraldistrict` table with county names, not settlement names.**

#### Scenario: National district name contains county name
- **Given** a national individual electoral district record with a valid `county_id` and `oevk` pair.
- **When** the `name` column is populated.
- **Then** it should contain the county name corresponding to the `county_id`, not a settlement name.

#### Scenario: Verify county_id and OEVK pair correctness
- **Given** national individual electoral district records exist.
- **When** validating data integrity.
- **Then** each record's `county_id` and `oevk` pair should correctly identify the electoral district.

### Requirement: Trim leading zeros from address components

**The system SHALL remove leading zeros from house numbers, building numbers, and staircase numbers consistently with the rules used for full address formatting.**

#### Scenario: House number leading zeros removed
- **Given** an address with house_number="000001".
- **When** the address is processed for export.
- **Then** the housenumber field should contain "1" with leading zeros removed.

#### Scenario: Building number leading zeros removed
- **Given** an address with building="0001".
- **When** the address is processed for export.
- **Then** the building_number field should contain "1" with leading zeros removed.

#### Scenario: Staircase number leading zeros removed
- **Given** an address with staircase="001".
- **When** the address is processed for export.
- **Then** the staircase_number field should contain "1" with leading zeros removed.

#### Scenario: Numeric staircase converted to Roman numeral
- **Given** an address with staircase="001" (leading zeros trimmed to "1").
- **When** formatting for full address.
- **Then** the staircase should be formatted as "I." (Roman numeral).

#### Scenario: Non-numeric values preserved
- **Given** an address with building="A" or staircase="L".
- **When** trimming is applied.
- **Then** the alphabetic values should be preserved without modification (except uppercasing).

#### Scenario: Range notation preserved
- **Given** an address with house_number="000001-00005".
- **When** leading zeros are trimmed.
- **Then** the result should be "1-5" with both parts trimmed.

#### Scenario: Slash notation preserved
- **Given** an address with house_number="000001/D".
- **When** leading zeros are trimmed.
- **Then** the result should be "1/D" with the numeric part trimmed.
