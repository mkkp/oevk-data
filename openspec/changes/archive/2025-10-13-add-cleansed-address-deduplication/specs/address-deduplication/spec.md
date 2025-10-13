# Address Deduplication Capability

## ADDED Requirements

### Requirement: Address Cleansing for Deduplication

The system SHALL apply comprehensive Hungarian address cleansing rules to all address components before generating the canonical address ID for deduplication purposes.

#### Scenario: Leading zeros removed from house numbers
- **GIVEN** an address with house number "000001"
- **WHEN** the address is cleansed
- **THEN** the house number SHALL be normalized to "1"

#### Scenario: Leading zeros removed from house number ranges
- **GIVEN** an address with house number "000001-00005"
- **WHEN** the address is cleansed
- **THEN** the house number SHALL be normalized to "1-5"

#### Scenario: Leading zeros preserved in slash notation
- **GIVEN** an address with house number "000001/D"
- **WHEN** the address is cleansed
- **THEN** the house number SHALL be normalized to "1/D" (numeric part cleaned, suffix preserved)

#### Scenario: Building field leading zeros trimmed
- **GIVEN** an address with building "0001"
- **WHEN** the address is cleansed
- **THEN** the building SHALL be normalized to "1"

#### Scenario: Numeric staircase converted to Roman numerals
- **GIVEN** an address with numeric staircase "0001"
- **WHEN** the address is cleansed
- **THEN** the staircase SHALL be normalized to "I"

#### Scenario: Numeric staircase "0005" converted to Roman "V"
- **GIVEN** an address with numeric staircase "0005"
- **WHEN** the address is cleansed
- **THEN** the staircase SHALL be normalized to "V"

#### Scenario: Alphabetic staircase preserved and uppercased
- **GIVEN** an address with alphabetic staircase "l"
- **WHEN** the address is cleansed
- **THEN** the staircase SHALL be normalized to "L"

#### Scenario: Null or empty street name handled gracefully
- **GIVEN** an address with null or empty street_name
- **WHEN** the address is cleansed
- **THEN** empty string SHALL be used for street name without error

#### Scenario: Null or empty house number handled gracefully
- **GIVEN** an address with null or empty house_number
- **WHEN** the address is cleansed
- **THEN** default value "0" SHALL be used for house number

#### Scenario: Multiple consecutive spaces collapsed in street name
- **GIVEN** an address with street name "Kossuth  Lajos" (double space)
- **WHEN** normalized for canonical ID generation
- **THEN** multiple spaces SHALL be collapsed to single space: "KOSSUTH LAJOS"

### Requirement: Full Address Formatting Rules

The system SHALL format cleansed full addresses according to Hungarian address conventions with specific rules for slash notation, ranges, and building/staircase combinations.

#### Scenario: House number with slash and no building/staircase
- **GIVEN** house number "000001/D", empty building, empty staircase
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1/D."

#### Scenario: House number without slash and building only
- **GIVEN** house number "000001", building "D", empty staircase
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1/D."

#### Scenario: House number without slash and staircase only
- **GIVEN** house number "000001", empty building, staircase "D"
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1/D."

#### Scenario: House number without slash, both building and staircase
- **GIVEN** house number "000001", building "D", staircase "L"
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1/D. L. lépcsőház"

#### Scenario: House number with slash, both building and staircase ignores slash
- **GIVEN** house number "000001/D", building "B", staircase "L"
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1. B. épület L. lépcsőház"

#### Scenario: House number with slash and only staircase preserves slash
- **GIVEN** house number "000001/D", empty building, staircase "L"
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1/D. L. lépcsőház"

#### Scenario: Range with building and staircase
- **GIVEN** house number "000001-00005", building "B", staircase "L"
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1-5. B. épület L. lépcsőház"

#### Scenario: Range with slash suffix
- **GIVEN** house number "000001-00005/D", empty building, empty staircase
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 1-5/D."

#### Scenario: Numeric building and staircase with Roman conversion
- **GIVEN** house number "000009", building "0001", staircase "0001"
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 9. 1. épület I. lépcsőház"

#### Scenario: Numeric building and staircase "0005" converts to Roman "V"
- **GIVEN** house number "000009", building "0001", staircase "0005"
- **WHEN** formatted as full address
- **THEN** result SHALL be "{Street Name} {Street Type} 9. 1. épület V. lépcsőház"

### Requirement: Duplicate Detection Using Cleansed Address

The system SHALL identify duplicate addresses by generating a deterministic canonical ID based on the cleansed full address, ensuring addresses that format to the same string are considered duplicates.

#### Scenario: Three variants of same address detected as duplicates
- **GIVEN** three address records:
  - ("000001", building="D", staircase="")
  - ("000001", building="", staircase="D")
  - ("000001/D", building="", staircase="")
- **WHEN** addresses are cleansed and canonical IDs generated
- **THEN** all three SHALL produce the same canonical ID (same cleansed address: "Körtöltés utca 1/D.")

#### Scenario: Different addresses produce different canonical IDs
- **GIVEN** two address records:
  - ("000001", building="D", staircase="L")
  - ("000001/D", building="B", staircase="L")
- **WHEN** addresses are cleansed and canonical IDs generated
- **THEN** they SHALL produce different canonical IDs (different cleansed addresses)

#### Scenario: Canonical ID computed from county, settlement, and cleansed address
- **GIVEN** an address with county_code="06", settlement_name="Szeged", cleansed_full_address="Körtöltés utca 1/D."
- **WHEN** canonical ID is generated
- **THEN** hash input SHALL be "06|SZEGED|KÖRTÖLTÉS UTCA 1/D." (normalized and uppercased)

#### Scenario: Same address in different settlements produces different canonical IDs
- **GIVEN** two addresses with identical street/number but different settlements
- **WHEN** canonical IDs are generated
- **THEN** they SHALL have different canonical IDs (settlement is part of hash input)

### Requirement: Deterministic Address Cleansing

The system SHALL apply address cleansing rules deterministically, producing identical cleansed output for identical input across all pipeline runs.

#### Scenario: Same input produces same cleansed output
- **GIVEN** address with house_number="000001", building="D", staircase=""
- **WHEN** cleansing is applied in two separate pipeline runs
- **THEN** both runs SHALL produce identical cleansed full address

#### Scenario: Whitespace variations normalized consistently
- **GIVEN** two addresses with same components but different whitespace
- **WHEN** addresses are cleansed and normalized
- **THEN** both SHALL produce identical canonical IDs after whitespace normalization

### Requirement: Settlement-Partitioned Export

The system SHALL export deduplicated canonical addresses and original addresses as separate CSV files partitioned by settlement code and name.

#### Scenario: Canonical addresses exported per settlement
- **GIVEN** canonical addresses for multiple settlements
- **WHEN** export is executed
- **THEN** one CSV file SHALL be created per settlement with naming format "Address_{code}_{name}.csv"

#### Scenario: Original addresses exported per settlement
- **GIVEN** original addresses for multiple settlements
- **WHEN** export is executed with original address flag
- **THEN** one CSV file SHALL be created per settlement with naming format "OriginalAddress_{code}_{name}.csv"

#### Scenario: Both canonical and original exports in unified directory
- **GIVEN** export is executed with both canonical and original address options
- **WHEN** export completes
- **THEN** both file types SHALL be placed in the same export directory "{run_tag}_Address/"

#### Scenario: Settlement with special characters in name
- **GIVEN** a settlement name containing spaces or special characters (e.g., "Csorna-Pusztacsalád")
- **WHEN** export filename is generated
- **THEN** special characters SHALL be handled appropriately (e.g., replaced with underscores or URL-encoded)

### Requirement: UUID v3 Export Format

The system SHALL convert all entity IDs to UUID v3 format in exported CSV files using the 'oevk.hu' DNS namespace for deterministic UUID generation.

#### Scenario: Address ID converted to UUID v3
- **GIVEN** an address with internal hash ID "a1b2c3d4e5f6"
- **WHEN** exported to CSV
- **THEN** the ID SHALL be converted to UUID v3 format using namespace 'oevk.hu'

#### Scenario: UUID v3 generation is deterministic
- **GIVEN** an entity ID that is exported multiple times
- **WHEN** UUID v3 conversion is applied in each export
- **THEN** all exports SHALL produce the same UUID v3 value

#### Scenario: All entity types use UUID v3 in exports
- **GIVEN** canonical addresses with relationships to polling stations, PIR codes, etc.
- **WHEN** exported to CSV
- **THEN** all entity IDs (address, polling station, PIR code) SHALL be in UUID v3 format

### Requirement: Relationship Preservation in Partitioned Export

The system SHALL preserve all original relationships (polling stations, PIR codes, address mappings) when exporting partitioned canonical addresses.

#### Scenario: Polling station assignments preserved in canonical export
- **GIVEN** multiple original addresses mapped to one canonical address with different polling stations
- **WHEN** canonical address is exported
- **THEN** all polling station relationships SHALL be preserved in the export

#### Scenario: PIR codes preserved in canonical export
- **GIVEN** multiple original addresses mapped to one canonical address with different PIR codes
- **WHEN** canonical address is exported
- **THEN** all PIR code relationships SHALL be preserved in the export

#### Scenario: Original address count tracked in canonical export
- **GIVEN** a canonical address created from 3 duplicate original addresses
- **WHEN** canonical address is exported
- **THEN** export SHALL include metadata indicating 3 original addresses merged

### Requirement: Deduplication Reporting

The system SHALL generate a comprehensive deduplication report containing statistics, processing metrics, and settlement-level breakdown of deduplication results.

#### Scenario: Report includes total and canonical address counts
- **GIVEN** deduplication process completes on 3,336,202 addresses
- **WHEN** deduplication report is generated
- **THEN** report SHALL include total_addresses=3,336,202 and canonical_addresses_created count

#### Scenario: Report includes deduplication rate
- **GIVEN** deduplication identifies 13,084 duplicate addresses
- **WHEN** deduplication report is generated
- **THEN** report SHALL calculate and include deduplication_rate as percentage

#### Scenario: Report includes processing time
- **GIVEN** deduplication completes in 2,500 milliseconds
- **WHEN** deduplication report is generated
- **THEN** report SHALL include processing_time_ms=2500

#### Scenario: Report includes settlement-level statistics
- **GIVEN** deduplication completes for multiple settlements
- **WHEN** deduplication report is generated
- **THEN** report SHALL include per-settlement breakdown of duplicates found

## MODIFIED Requirements

None (this is a new capability)

## REMOVED Requirements

None

## RENAMED Requirements

None
