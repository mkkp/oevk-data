# Data Model: Public Space Extraction

## New Entities

### PublicSpaceName
Represents unique public space names extracted from address data.

**Fields**:
- `ID` (TEXT, PRIMARY KEY): xxhash64(PublicSpaceName) - deterministic hash ID
- `PublicSpaceName` (TEXT, UNIQUE, NOT NULL): Normalized public space name

**Relationships**:
- One-to-Many with Address (via PublicSpaceName_ID foreign key)
- Many-to-Many with Settlement through SettlementPublicSpaces

**Validation Rules**:
- Must be unique across all settlements
- Preserve Hungarian diacritics and original casing
- Trim whitespace, convert empty strings to NULL

### PublicSpaceType
Represents unique public space types extracted from address data.

**Fields**:
- `ID` (TEXT, PRIMARY KEY): xxhash64(PublicSpaceType) - deterministic hash ID
- `PublicSpaceType` (TEXT, UNIQUE, NOT NULL): Normalized public space type

**Relationships**:
- One-to-Many with Address (via PublicSpaceType_ID foreign key)
- Many-to-Many with Settlement through SettlementPublicSpaces

**Validation Rules**:
- Must be unique across all settlements
- Preserve Hungarian diacritics and original casing
- Trim whitespace, convert empty strings to NULL

### SettlementPublicSpaces
Lookup table connecting settlements with their public spaces for efficient querying.

**Fields**:
- `Settlement_ID` (TEXT, NOT NULL): Foreign key to Settlement table
- `PublicSpaceName_ID` (TEXT, NOT NULL): Foreign key to PublicSpaceName table
- `PublicSpaceType_ID` (TEXT, NOT NULL): Foreign key to PublicSpaceType table

**Constraints**:
- Composite PRIMARY KEY (Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID)
- FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID)
- FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID)
- FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID)

**Validation Rules**:
- Each combination must be unique
- All foreign keys must reference existing entities

## Modified Entity

### Address
Modified to use normalized public space references instead of text fields.

**Modified Fields**:
- Remove: `PublicSpaceName` (TEXT)
- Remove: `PublicSpaceType` (TEXT)
- Add: `PublicSpaceName_ID` (TEXT, NOT NULL): Foreign key to PublicSpaceName
- Add: `PublicSpaceType_ID` (TEXT, NOT NULL): Foreign key to PublicSpaceType

**Updated Fields**:
- `FullAddress` (TEXT): Updated to use formatted house numbers (leading zeros removed)
- `HouseNumber` (TEXT): Updated to use formatted house numbers

**New Relationships**:
- Many-to-One with PublicSpaceName (via PublicSpaceName_ID)
- Many-to-One with PublicSpaceType (via PublicSpaceType_ID)

**Validation Rules**:
- PublicSpaceName_ID and PublicSpaceType_ID must reference existing entities
- Use NULL foreign keys for missing values
- House numbers formatted to remove leading zeros while preserving non-numeric characters

## Data Transformation Flow

### Phase 1: Extract Unique Values
1. Extract distinct PublicSpaceName values from address data
2. Extract distinct PublicSpaceType values from address data
3. Generate deterministic hash IDs for all unique values

### Phase 2: Populate Lookup Tables
1. Populate PublicSpaceName table with unique names and hash IDs
2. Populate PublicSpaceType table with unique types and hash IDs
3. Populate SettlementPublicSpaces with settlement-public space relationships

### Phase 3: Transform Addresses
1. Update addresses to use foreign key references
2. Format house numbers to remove leading zeros
3. Update FullAddress generation with formatted house numbers

## Referential Integrity

- All foreign key relationships must be validated
- Address transformation must ensure all PublicSpaceName_ID and PublicSpaceType_ID values exist
- SettlementPublicSpaces must only contain valid settlement-public space combinations
- Data migration must preserve existing relationships

## Performance Considerations

- Use vectorized operations for processing 3.3M+ records
- Process in chunks of 100k-500k rows
- Maintain ≤10% performance degradation target
- Leverage existing Polars/DuckDB infrastructure