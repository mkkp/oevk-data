## MODIFIED Requirements

### Requirement: Prioritize structured address formats in deduplication

**The system SHALL prioritize addresses with structured formats (separate house number and building fields) over combined formats when selecting canonical representatives from duplicate groups.**

#### Scenario: Prefer structured address over combined format
- **Given** two duplicate addresses exist for the same location:
  - Address A: house_number="1", building="D", staircase=""
  - Address B: house_number="1/D", building="", staircase=""
- **When** the deduplication process selects the canonical address.
- **Then** it should select Address A (structured format) as the canonical representative.

#### Scenario: Prefer plain house number with building over slash notation
- **Given** multiple duplicate addresses with different formatting:
  - Address A: house_number="9", building="1", staircase="1" (structured)
  - Address B: house_number="9/1", building="", staircase="1" (combined)
- **When** canonical address selection occurs.
- **Then** Address A should be selected as it has a plain house number with separate building field.

#### Scenario: All addresses have same structure priority
- **Given** duplicate addresses all use the same format structure (all structured or all combined).
- **When** selecting the canonical address.
- **Then** the system should use the existing first-occurrence selection as a tiebreaker.

### Requirement: Maintain deterministic canonical ID generation

**The system SHALL continue to generate canonical IDs based on the formatted full address string to ensure duplicate detection remains consistent.**

#### Scenario: Canonical ID unchanged for duplicate detection
- **Given** addresses format to the same full address string.
- **When** canonical IDs are generated.
- **Then** all addresses should receive the same canonical ID regardless of internal field structure.

#### Scenario: Different structures with same formatted address
- **Given** Address A (house_number="1", building="D") and Address B (house_number="1/D") both format to "Körtöltés utca 1/D."
- **When** canonical IDs are computed.
- **Then** both addresses should have identical canonical IDs (they are duplicates).
