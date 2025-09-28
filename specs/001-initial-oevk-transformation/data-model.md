# Data Model: OEVK Transformation App

This data model is based on the logical model and DDL provided in `docs/FUNCTIONAL_SPECIFICATION.md`. All primary and foreign keys are of type `TEXT` and will store the lowercase hexadecimal representation of an `xxhash64` digest.

## Entity Definitions

### 1. County
-   **Purpose**: Represents Hungarian counties.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(CountyCode)`
-   **Fields**:
    -   `CountyCode` (TEXT, UC): The unique county code (e.g., "01").
    -   `CountyName` (TEXT): The name of the county.

### 2. Settlement
-   **Purpose**: Represents settlements within counties.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(CountyCode|SettlementCode)`
-   **Fields**:
    -   `SettlementCode` (TEXT, UC): The unique settlement code.
    -   `SettlementName` (TEXT): The name of the settlement.
    -   `County_ID` (TEXT, FK): Foreign key to `County.ID`.

### 3. NationalIndividualElectoralDistrict (OEVK)
-   **Purpose**: Represents a national electoral district.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(CountyCode|OEVK)`
-   **Fields**:
    -   `OEVK` (TEXT, UC): The OEVK code.
    -   `Name` (TEXT): Derived name: `SettlementName + ' ' + OEVK`.
    -   `Center` (TEXT): Center coordinates as a string.
    -   `Polygon` (TEXT): Polygon coordinates as a string.
    -   `County_ID` (TEXT, FK): Foreign key to `County.ID`.

### 4. SettlementIndividualElectoralDistrict (TEVK)
-   **Purpose**: Represents a settlement-level electoral district.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(CountyCode|SettlementCode|TEVK|OEVK)`
-   **Fields**:
    -   `TEVK` (TEXT): The TEVK code (nullable).
    -   `Name` (TEXT): Derived name.
    -   `County_ID` (TEXT, FK): Foreign key to `County.ID`.
    -   `Settlement_ID` (TEXT, FK): Foreign key to `Settlement.ID`.
    -   `NationalIndividualElectoralDistrict_ID` (TEXT, FK): Foreign key to `NationalIndividualElectoralDistrict.ID`.

### 5. PostalCode
-   **Purpose**: Represents postal codes.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(PostalCode)`
-   **Fields**:
    -   `PostalCode` (TEXT, UC): The postal code string.

### 6. PostalCode_Settlement
-   **Purpose**: Many-to-many link between postal codes and settlements.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(PostalCode_ID|Settlement_ID)`
-   **Fields**:
    -   `PostalCode_ID` (TEXT, FK): Foreign key to `PostalCode.ID`.
    -   `Settlement_ID` (TEXT, FK): Foreign key to `Settlement.ID`.

### 7. PollingStation
-   **Purpose**: Represents a polling station.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(CountyCode|SettlementCode|OEVK|TEVK|PollingStationAddress)`
-   **Fields**:
    -   `PollingStationAddress` (TEXT): The address of the polling station.
    -   `SettlementIndividualElectoralDistrict_ID` (TEXT, FK): Foreign key to `SettlementIndividualElectoralDistrict.ID`.
    -   `County_ID` (TEXT, FK): Foreign key to `County.ID`.
    -   `Settlement_ID` (TEXT, FK): Foreign key to `Settlement.ID`.
    -   `NationalIndividualElectoralDistrict_ID` (TEXT, FK): Foreign key to `NationalIndividualElectoralDistrict.ID`.

### 8. Address
-   **Purpose**: Represents a specific address.
-   **Primary Key**: `ID` (TEXT) - `xxhash64(...)` based on full address components.
-   **Fields**:
    -   `Sequence` (INTEGER): A row number for ordering.
    -   `FullAddress` (TEXT): Derived full address string.
    -   `PublicSpaceName` (TEXT)
    -   `PublicSpaceType` (TEXT)
    -   `HouseNumber` (TEXT)
    -   `Building` (TEXT, nullable)
    -   `Staircase` (TEXT, nullable)
    -   `PostalCode_ID` (TEXT, FK): Foreign key to `PostalCode.ID`.
    -   `PollingStation_ID` (TEXT, FK): Foreign key to `PollingStation.ID`.
    -   `SettlementIndividualElectoralDistrict_ID` (TEXT, FK): Foreign key to `SettlementIndividualElectoralDistrict.ID`.
    -   `County_ID` (TEXT, FK): Foreign key to `County.ID`.
    -   `Settlement_ID` (TEXT, FK): Foreign key to `Settlement.ID`.
    -   `NationalIndividualElectoralDistrict_ID` (TEXT, FK): Foreign key to `NationalIndividualElectoralDistrict.ID`.
