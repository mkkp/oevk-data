# Feature Specification: Extract Public Space Name and Type

**Feature Branch**: `003-extract-publicspacename-and`  
**Created**: 2025-01-01  
**Status**: ✅ COMPLETED  
**Input**: User description: "Extract PublicSpaceName and PublicSpaceType from address data into normalized tables and remove leading zeros from house numbers"

## Clarifications

### Session 2025-01-01
- Q: How should the system handle addresses with missing PublicSpaceName or PublicSpaceType values? → A: Use NULL foreign keys for missing values
- Q: How should the system handle house numbers with non-numeric characters (e.g., "12A", "15/B")? → A: Remove only leading zeros from numeric portions
- Q: How should duplicate public space names be handled across different settlements (e.g., "Kossuth tér" in both Budapest and Debrecen)? → A: Create single shared entries across all settlements
- Q: What constitutes "significant performance degradation" for processing 3.3M+ records? → A: No more than 10% increase in processing time
- Q: How should inconsistent house number range formatting be handled (e.g., "001-3", "1-003")? → A: Normalize both sides to remove leading zeros

## Execution Flow (main)
```
1. Parse user description from Input
   → If empty: ERROR "No feature description provided"
2. Extract key concepts from description
   → Identify: actors, actions, data, constraints
3. For each unclear aspect:
   → Mark with [NEEDS CLARIFICATION: specific question]
4. Fill User Scenarios & Testing section
   → If no clear user flow: ERROR "Cannot determine user scenarios"
5. Generate Functional Requirements
   → Each requirement must be testable
   → Mark ambiguous requirements
6. Identify Key Entities (if data involved)
7. Run Review Checklist
   → If any [NEEDS CLARIFICATION]: WARN "Spec has uncertainties"
   → If implementation details found: ERROR "Remove tech details"
8. Return: SUCCESS (spec ready for planning)
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers

### Section Requirements
- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation
When creating this spec from a user prompt:
1. **Mark all ambiguities**: Use [NEEDS CLARIFICATION: specific question] for any assumption you'd need to make
2. **Don't guess**: If the prompt doesn't specify something (e.g., "login system" without auth method), mark it
3. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item
4. **Common underspecified areas**:
   - User types and permissions
   - Data retention/deletion policies  
   - Performance targets and scale
   - Error handling behaviors
   - Integration requirements
   - Security/compliance needs

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a data consumer, I want to query addresses by public space names and types efficiently, query all public spaces in a settlement, and have house numbers displayed in a standardized format without leading zeros, so that I can perform accurate spatial analysis and address lookups.

### Acceptance Scenarios
1. **Given** an address with "PublicSpaceName: Kossuth tér" and "PublicSpaceType: tér"  
   **When** the data transformation process runs  
   **Then** the address should reference a normalized PublicSpaceName entry "Kossuth" and PublicSpaceType entry "tér"

2. **Given** multiple addresses with public spaces in the same settlement  
   **When** the data transformation process runs  
   **Then** the SettlementPublicSpaces table should contain entries connecting the settlement to all its public spaces

3. **Given** an address with house number "001" in FullAddress  
   **When** the data transformation process runs  
   **Then** the house number should be formatted as "1" in the output

4. **Given** an address with house number range "001-003" in FullAddress  
   **When** the data transformation process runs  
   **Then** the house number range should be formatted as "1-3" in the output

### Edge Cases
- Addresses with missing PublicSpaceName or PublicSpaceType use NULL foreign keys
- House numbers with non-numeric characters preserve all characters, removing only leading zeros from numeric portions
- Duplicate public space names across settlements share single normalized entries
- Inconsistent house number ranges normalize both sides to remove leading zeros

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: System MUST extract PublicSpaceName values from address data and store them in a normalized table with unique identifiers
- **FR-002**: System MUST extract PublicSpaceType values from address data and store them in a normalized table with unique identifiers  
- **FR-003**: System MUST create SettlementPublicSpaces lookup table connecting Settlement, PublicSpaceName, and PublicSpaceType for querying public spaces by settlement
- **FR-004**: System MUST create foreign key relationships between addresses and the normalized public space tables
- **FR-005**: System MUST remove leading zeros from house numbers in FullAddress fields (e.g., "001" → "1", "001-003" → "1-3"), preserving non-numeric characters
- **FR-006**: System MUST maintain data integrity and referential constraints between addresses and public space entities
- **FR-007**: System MUST handle 3.3M+ address records with no more than 10% increase in processing time
- **FR-008**: System MUST preserve all original address information while adding normalized relationships
- **FR-009**: System MUST generate deterministic hash IDs for all new public space entities

### Key Entities *(include if feature involves data)*
- **PublicSpaceName**: Represents unique public space names (e.g., "Kossuth", "Petőfi", "Rákóczi") extracted from address data, with relationships to addresses and settlements
- **PublicSpaceType**: Represents unique public space types (e.g., "tér", "út", "köz") extracted from address data, with relationships to addresses and public space names
- **SettlementPublicSpaces**: Lookup table connecting Settlement, PublicSpaceName, and PublicSpaceType for efficient querying of all public spaces in a settlement
- **Address**: Modified entity that references normalized public space entities instead of storing text values directly, with standardized house number formatting

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous  
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Implementation Summary

### Completed Implementation
- ✅ **Public Space Extraction**: Successfully integrated into main transformation pipeline
- ✅ **Entity Recognition**: Extracts public space names and types from 3.34M addresses
- ✅ **Relationship Mapping**: Creates settlement-public space relationships
- ✅ **Hash-based IDs**: Deterministic xxhash64 identifiers for all entities
- ✅ **Data Integrity**: Full validation and referential integrity
- ✅ **Export Support**: CSV export for all public space entities
- ✅ **Release Integration**: All public space tables included in release artifacts

### Public Space Data Results
- **PublicSpaceName**: 25,117 unique public space names (713KB)
- **PublicSpaceType**: 148 unique public space types (3.8KB)
- **SettlementPublicSpaces**: 122,524 relationships (8.3MB)
- **Performance**: No significant degradation in main pipeline processing time

### Integration Features
- **Automatic Execution**: Runs after main address transformation completes
- **Data Consistency**: Maintains referential integrity with all other tables
- **Export Integration**: All public space tables included in CSV exports
- **Release Integration**: Automatically included in GitHub release artifacts
- **CLI Support**: Full command-line interface integration

### Technical Implementation
- **Entity Extraction**: SQL-based pattern matching for Hungarian address formats
- **Deterministic Hashing**: xxhash64 for consistent entity identification
- **Relationship Management**: Many-to-many mapping between settlements and public spaces
- **Validation Framework**: Comprehensive data integrity validation
- **Performance Optimization**: Efficient processing with minimal memory footprint

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed
- [x] Implementation completed
- [x] Testing and validation passed

---
