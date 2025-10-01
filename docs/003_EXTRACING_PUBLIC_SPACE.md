## 🎯 Public Space Extraction

1. I would like to extract PublicSpaceName and PublicSpaceTyeps to own normalized and referencable tables.
2. In the FullAddress the HouseNumber have leading zeros which should be removed. Be carefull, there are cases whan ranges are used, like 001-003, in this case only the leading zeros should be removed from the first number and second number, so it should be 1-3.
3. Create a lookup table called SettlementPublicSpaces which connects Settlement, PublicSpaceName and PublicSpaceType. This is to be able to query all public spaces in a settlement.
4. Modify the Address table to reference PublicSpaceName and PublicSpaceType by their IDs instead of storing them as text fields.

Update related documentation and code accordingly.
Update diagrams and scripts to reflect these changes.

### Added and modified Entities & Attributes
- **PublicSpaceName** (`ID` PK, `PublicSpaceName`),
- **PublicSpaceType** (`ID` PK, `PublicSpaceType`),
- **SettlementPublicSpaces** (`Settlement_ID` FK, `PublicSpaceName_ID` FK, `PublicSpaceType_ID` FK) - Lookup table for querying public spaces by settlement
- **Address** (`ID` PK, `Sequence`, `FullAddress`, `HouseNumber`, `Building`, `Staircase`, `PostalCode_ID` FK, `PollingStation_ID` FK, `SettlementIndividualElectoralDistrict_ID` FK, `County_ID` FK, `Settlement_ID` FK, `NationalIndividualElectoralDistrict_ID` FK, `PublicSpaceName_ID` FK, `PublicSpaceType_ID` FK)

## 🎯 Implementation Plan for Public Space Extraction

Based on my analysis of the current codebase and the requirements from docs/003_EXTRACING_PUBLIC_SPACE.md, here's the comprehensive implementation plan:

### Phase 1: Database Schema Updates

1. Add New Tables to Schema
 • Create PublicSpaceName table with ID (PK) and PublicSpaceName fields
 • Create PublicSpaceType table with ID (PK) and PublicSpaceType fields
 • Create SettlementPublicSpaces lookup table with composite primary key
 • Modify Address table to replace text fields with foreign keys
2. Update Schema Migration Logic
 • Add migration logic to handle schema changes
 • Preserve existing data during migration


### Phase 2: Hashing Functions

1. Add New Hash Functions
 • hash_public_space_name_id(public_space_name: str)
 • hash_public_space_type_id(public_space_type: str)
2. Update Existing Hash Functions
 • Modify hash_address_id() to use hash IDs instead of text values
 • Register new hash functions with DuckDB


### Phase 3: Transformation Logic

1. Add New Transformation Functions
 • transform_public_space_names() - Extract unique public space names
 • transform_public_space_types() - Extract unique public space types
 • transform_settlement_public_spaces() - Populate SettlementPublicSpaces lookup table
2. Update Address Transformation
 • Modify address transformation to use foreign keys instead of text fields
 • Update the optimized SQL queries in transform_optimized.py
 • Update the parallel processing logic
3. House Number Formatting
 • Implement logic to remove leading zeros from house numbers
 • Handle ranges like "001-003" → "1-3"
 • Update FullAddress generation to use formatted house numbers


### Phase 4: Export Logic

1. Update Export Functions
 • Add new tables to export list: PublicSpaceName, PublicSpaceType, SettlementPublicSpaces
 • Update address export to include foreign key relationships
2. Update Partitioned Address Export
 • Ensure partitioned address files include proper foreign key references


### Phase 5: Documentation & Testing

1. Update Data Model Documentation
 • Update ER diagrams to include new entities
 • Update data flow diagrams
2. Update Specifications
 • Update functional specifications with new requirements
 • Update release workflow documentation if needed
3. Add Tests
 • Unit tests for new hash functions
 • Integration tests for new transformation logic
 • Tests for house number formatting edge cases


### Technical Implementation Details

#### Schema Changes

-- New tables
CREATE TABLE IF NOT EXISTS PublicSpaceName (
    ID TEXT PRIMARY KEY, -- xxhash64(PublicSpaceName)
    PublicSpaceName TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS PublicSpaceType (
    ID TEXT PRIMARY KEY, -- xxhash64(PublicSpaceType)
    PublicSpaceType TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS SettlementPublicSpaces (
    Settlement_ID TEXT NOT NULL,
    PublicSpaceName_ID TEXT NOT NULL,
    PublicSpaceType_ID TEXT NOT NULL,
    PRIMARY KEY (Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID),
    FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID)
);

-- Modified Address table
ALTER TABLE Address
DROP COLUMN PublicSpaceName,
DROP COLUMN PublicSpaceType,
ADD COLUMN PublicSpaceName_ID TEXT NOT NULL,
ADD COLUMN PublicSpaceType_ID TEXT NOT NULL,
ADD FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID),
ADD FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID);

#### House Number Formatting Logic

def format_house_number(house_number: str) -> str:
    """Remove leading zeros from house numbers, handling ranges like '001-003'."""
    if '-' in house_number:
        parts = house_number.split('-')
        formatted_parts = [str(int(part)) for part in parts]
        return '-'.join(formatted_parts)
    else:
        return str(int(house_number)) if house_number.isdigit() else house_number

#### Updated Address Transformation

The transformation will need to:

1. First extract unique public space names and types
2. Populate SettlementPublicSpaces lookup table with settlement-public space relationships
3. Then transform addresses using the normalized IDs
4. Update the FullAddress generation to use formatted house numbers

### Impact Analysis

• Performance: Minimal impact as we're adding two small lookup tables
• Data Integrity: Improved through proper normalization
• Backward Compatibility: Will require data migration for existing databases
• Release Workflow: May need updates to handle new tables in exports

### Next Steps

1. Create detailed specification for this feature
2. Implement schema changes with proper migration
3. Update transformation logic to handle normalized tables
4. Test thoroughly with existing data
5. Update documentation and diagrams

This plan provides a comprehensive roadmap for implementing the public space extraction feature while maintaining data integrity and performance.
