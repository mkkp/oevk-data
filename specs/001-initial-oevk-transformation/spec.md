# Feature Specification: Initial OEVK Transformation App

**Feature Branch**: `001-initial-oevk-transformation`  
**Created**: 2025-09-28  
**Status**: Draft  
**Input**: User description: "Initial OEVK transformation app"

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
As a data analyst, I need to transform Hungarian electoral address data from authoritative sources into a normalized relational model so that I can analyze voting patterns and district coverage efficiently.

### Acceptance Scenarios
1. **Given** the system has access to source data URLs, **When** the transformation process is initiated, **Then** all source data should be downloaded and loaded into staging tables
2. **Given** staging data is available, **When** the transformation process runs, **Then** all target tables should be populated with normalized data and referential integrity maintained
3. **Given** transformed data is available, **When** export is triggered, **Then** CSV files should be generated for each target table and Address data should be partitioned by Settlement

### Edge Cases
- What happens when source data is temporarily unavailable?
- How does system handle malformed or inconsistent data in source files? → Invalid records are moved to a "rejects" table.
- What happens when target database already contains data from previous runs? → All data is deleted from target tables before each run.

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: System MUST download Hungarian electoral address data from two authoritative sources (oevk.json and Korzet_allomany_orszagos.zip)
- **FR-002**: System MUST load source data into staging tables with minimal transformation
- **FR-003**: System MUST transform staged data into a normalized relational model with 8 target entities (County, Settlement, NationalIndividualElectoralDistrict, SettlementIndividualElectoralDistrict, PostalCode, PostalCode_Settlement, PollingStation, Address)
- **FR-004**: System MUST generate deterministic surrogate IDs for all entities to ensure idempotent processing
- **FR-005**: System MUST export all target tables as CSV files with proper formatting, and optionally generate a consolidated `Address.csv` if a specific command-line flag is provided.
- **FR-006**: System MUST export Address data partitioned by Settlement (one CSV file per settlement)
- **FR-007**: System MUST validate data quality and maintain referential integrity between entities
- **FR-008**: System MUST be restartable and produce identical results when run with identical inputs
- **FR-009**: System MUST handle large datasets (>3M rows) efficiently without manual intervention
- **FR-010**: System MUST preserve Hungarian diacritics and original casing in all text fields
- **FR-011**: System MUST automatically extract the CSV file from the downloaded ZIP archive.
- **FR-012**: System MUST move any records that fail validation during the transformation process to a dedicated "rejects" table for later analysis, and the process MUST continue with the next valid records.
- **FR-013**: System MUST delete all existing data from all target tables before initiating the transformation process to ensure idempotency.

### Non-Functional Requirements
- **NFR-001**: The system MUST log its operational status at the `INFO` level during a normal, successful run.

### Key Entities *(include if feature involves data)*
- **County**: Represents Hungarian counties with unique codes and names
- **Settlement**: Represents settlements within counties with unique codes and names
- **NationalIndividualElectoralDistrict (OEVK)**: Represents national electoral districts with geometry data
- **SettlementIndividualElectoralDistrict (TEVK)**: Represents settlement-level electoral districts
- **PostalCode**: Represents postal codes used in addresses
- **PostalCode_Settlement**: Junction table linking postal codes to settlements
- **PollingStation**: Represents voting locations with addresses
- **Address**: Represents individual voter addresses with full address components

---

## Clarifications

### Session 2025-09-28
- Q: How should the system behave if a validation error occurs during the transformation of a batch of records? → A: Log the errors and move the invalid records to a separate "rejects" table for later analysis, then continue.
- Q: How should the system handle data in the **target** tables from a previous run? → A: Delete all data from target tables before each run.
- Q: The `FUNCTIONAL_SPECIFICATION.md` mentions that a consolidated `Address.csv` file is "optional" in addition to the partitioned files. Should this consolidated file be generated by default? → A: Make it configurable with a command-line flag.
- Q: What is the expected logging level for normal, successful operation? → A: info

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

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed

---
