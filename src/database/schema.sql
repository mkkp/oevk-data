-- Database Schema for OEVK Data Transformation
-- All primary keys are MD5 digests (first 16 characters) stored as lowercase hexadecimal strings

-- County table
CREATE TABLE IF NOT EXISTS County (
    ID TEXT PRIMARY KEY, -- md5(CountyCode)
    CountyCode TEXT UNIQUE NOT NULL,
    CountyName TEXT NOT NULL
);

-- Settlement table
CREATE TABLE IF NOT EXISTS Settlement (
    ID TEXT PRIMARY KEY, -- md5(CountyCode|SettlementCode)
    SettlementCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, SettlementCode)
);

-- NationalIndividualElectoralDistrict (OEVK) table
CREATE TABLE IF NOT EXISTS NationalIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY, -- md5(CountyCode|OEVK)
    OEVK TEXT NOT NULL,
    Name TEXT NOT NULL,
    Center TEXT, -- Center point coordinates (space-separated: "lat lon")
    Polygon TEXT, -- Boundary polygon coordinates (comma-separated pairs: "lat1 lon1,lat2 lon2,...")
    County_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, OEVK)
);

-- SettlementIndividualElectoralDistrict (TEVK) table
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY, -- md5(CountyCode|SettlementCode|TEVK)
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK)
);

-- PostalCode table
CREATE TABLE IF NOT EXISTS PostalCode (
    ID TEXT PRIMARY KEY, -- md5(PostalCode)
    PostalCode TEXT UNIQUE NOT NULL
);

-- PostalCode_Settlement junction table
CREATE TABLE IF NOT EXISTS PostalCode_Settlement (
    ID TEXT PRIMARY KEY, -- md5(PostalCode_ID|Settlement_ID)
    PostalCode_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (PostalCode_ID, Settlement_ID)
);

-- PollingStation table
CREATE TABLE IF NOT EXISTS PollingStation (
    ID TEXT PRIMARY KEY, -- md5(CountyCode|SettlementCode|OEVK|TEVK|PollingStationAddress)
    PollingStationAddress TEXT NOT NULL,
    SettlementIndividualElectoralDistrict_ID TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    Latitude REAL,
    Longitude REAL,
    GeocodingQuality TEXT,
    GeocodingSource TEXT,
    GeocodedAt TIMESTAMP,
    MatchedAddress TEXT,
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID),
    UNIQUE (County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID, SettlementIndividualElectoralDistrict_ID, PollingStationAddress)
);

CREATE INDEX IF NOT EXISTS idx_PollingStation_Coordinates ON PollingStation(Latitude, Longitude);
CREATE INDEX IF NOT EXISTS idx_PollingStation_Quality ON PollingStation(GeocodingQuality);

-- Address table
CREATE TABLE IF NOT EXISTS Address (
    ID TEXT PRIMARY KEY, -- md5(...) based on full address components
    Sequence INTEGER NOT NULL,
    OriginalOrder INTEGER NOT NULL,
    FullAddress TEXT NOT NULL,
    PublicSpaceName TEXT NOT NULL,
    PublicSpaceType TEXT NOT NULL,
    HouseNumber TEXT NOT NULL,
    Building TEXT,
    Staircase TEXT,
    PostalCode_ID TEXT NOT NULL,
    PollingStation_ID TEXT NOT NULL,
    SettlementIndividualElectoralDistrict_ID TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID),
    FOREIGN KEY (PollingStation_ID) REFERENCES PollingStation(ID),
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID)
);

-- PublicSpaceType table
CREATE TABLE IF NOT EXISTS PublicSpaceType (
    ID TEXT PRIMARY KEY, -- md5(PublicSpaceType)
    PublicSpaceType TEXT UNIQUE NOT NULL
);

-- PublicSpaceName table
CREATE TABLE IF NOT EXISTS PublicSpaceName (
    ID TEXT PRIMARY KEY, -- md5(PublicSpaceName)
    PublicSpaceName TEXT UNIQUE NOT NULL
);

-- SettlementPublicSpaces junction table
CREATE TABLE IF NOT EXISTS SettlementPublicSpaces (
    ID TEXT PRIMARY KEY, -- md5(Settlement_ID|PublicSpaceName_ID|PublicSpaceType_ID)
    Settlement_ID TEXT NOT NULL,
    PublicSpaceName_ID TEXT NOT NULL,
    PublicSpaceType_ID TEXT NOT NULL,
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID),
    FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID),
    UNIQUE (Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID)
);

-- Update Address table to use foreign keys instead of text fields
CREATE TABLE IF NOT EXISTS Address_new (
    ID TEXT PRIMARY KEY, -- md5(...) based on full address components
    Sequence INTEGER NOT NULL,
    OriginalOrder INTEGER NOT NULL,
    FullAddress TEXT NOT NULL,
    PublicSpaceName_ID TEXT NOT NULL,
    PublicSpaceType_ID TEXT NOT NULL,
    HouseNumber TEXT NOT NULL,
    Building TEXT,
    Staircase TEXT,
    PostalCode_ID TEXT NOT NULL,
    PollingStation_ID TEXT NOT NULL,
    SettlementIndividualElectoralDistrict_ID TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID),
    FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID),
    FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID),
    FOREIGN KEY (PollingStation_ID) REFERENCES PollingStation(ID),
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_County_CountyCode ON County(CountyCode);
CREATE INDEX IF NOT EXISTS idx_Settlement_County_ID ON Settlement(County_ID);
CREATE INDEX IF NOT EXISTS idx_Settlement_County_SettlementCode ON Settlement(County_ID, SettlementCode);
CREATE INDEX IF NOT EXISTS idx_NationalIndividualElectoralDistrict_County_ID ON NationalIndividualElectoralDistrict(County_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementIndividualElectoralDistrict_County_ID ON SettlementIndividualElectoralDistrict(County_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementIndividualElectoralDistrict_Settlement_ID ON SettlementIndividualElectoralDistrict(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_PostalCode_Settlement_PostalCode_ID ON PostalCode_Settlement(PostalCode_ID);
CREATE INDEX IF NOT EXISTS idx_PostalCode_Settlement_Settlement_ID ON PostalCode_Settlement(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_PollingStation_County_ID ON PollingStation(County_ID);
CREATE INDEX IF NOT EXISTS idx_PollingStation_Settlement_ID ON PollingStation(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_Address_PostalCode_ID ON Address(PostalCode_ID);
CREATE INDEX IF NOT EXISTS idx_Address_PollingStation_ID ON Address(PollingStation_ID);
CREATE INDEX IF NOT EXISTS idx_Address_County_ID ON Address(County_ID);
CREATE INDEX IF NOT EXISTS idx_Address_Settlement_ID ON Address(Settlement_ID);

-- Deduplication tables
-- CanonicalAddress table for deduplicated addresses
CREATE TABLE IF NOT EXISTS CanonicalAddress (
    ID TEXT PRIMARY KEY, -- md5(CountyCode|SettlementName|FullAddress)
    CountyCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    StreetName TEXT NOT NULL,
    HouseNumber TEXT NOT NULL,
    FullAddress TEXT NOT NULL, -- Formatted Hungarian address (e.g., "Körtöltés utca 1/D.")
    AccessibilityFlag TEXT,
    Latitude REAL,
    Longitude REAL,
    GeocodingQuality TEXT,
    GeocodingSource TEXT,
    GeocodedAt TIMESTAMP,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (CountyCode, SettlementName, FullAddress)
);

CREATE INDEX IF NOT EXISTS idx_CanonicalAddress_Coordinates ON CanonicalAddress(Latitude, Longitude);
CREATE INDEX IF NOT EXISTS idx_CanonicalAddress_Quality ON CanonicalAddress(GeocodingQuality);

-- AddressMapping table to track original to canonical address relationships
CREATE TABLE IF NOT EXISTS AddressMapping (
    ID TEXT PRIMARY KEY, -- md5(OriginalAddressID|CanonicalAddressID)
    OriginalAddressID TEXT NOT NULL,
    CanonicalAddressID TEXT NOT NULL,
    MappingType TEXT DEFAULT 'deduplication', -- deduplication, manual_override, etc.
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (CanonicalAddressID) REFERENCES CanonicalAddress(ID),
    UNIQUE (OriginalAddressID, CanonicalAddressID)
);

-- AddressPollingStations table to preserve polling station assignments
CREATE TABLE IF NOT EXISTS AddressPollingStations (
    ID TEXT PRIMARY KEY, -- md5(CanonicalAddressID|PollingStationID)
    CanonicalAddressID TEXT NOT NULL,
    PollingStationID TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (CanonicalAddressID) REFERENCES CanonicalAddress(ID),
    FOREIGN KEY (PollingStationID) REFERENCES PollingStation(ID),
    UNIQUE (CanonicalAddressID, PollingStationID)
);

-- AddressPIRCodes table to preserve PIR code relationships
CREATE TABLE IF NOT EXISTS AddressPIRCodes (
    ID TEXT PRIMARY KEY, -- md5(CanonicalAddressID|PIRCode)
    CanonicalAddressID TEXT NOT NULL,
    PIRCode TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (CanonicalAddressID) REFERENCES CanonicalAddress(ID),
    UNIQUE (CanonicalAddressID, PIRCode)
);

-- DeduplicationReport table for audit and verification
CREATE TABLE IF NOT EXISTS DeduplicationReport (
    ID TEXT PRIMARY KEY, -- md5(RunID)
    RunID TEXT NOT NULL,
    TotalAddresses INTEGER NOT NULL,
    DuplicatesFound INTEGER NOT NULL,
    CanonicalAddressesCreated INTEGER NOT NULL,
    ProcessingTimeMs INTEGER NOT NULL,
    Status TEXT NOT NULL, -- completed, failed, partial
    ErrorMessage TEXT,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (RunID)
);

-- New indexes for deduplication tables
CREATE INDEX IF NOT EXISTS idx_CanonicalAddress_County_Settlement_Street ON CanonicalAddress(CountyCode, SettlementName, StreetName);
CREATE INDEX IF NOT EXISTS idx_AddressMapping_OriginalAddressID ON AddressMapping(OriginalAddressID);
CREATE INDEX IF NOT EXISTS idx_AddressMapping_CanonicalAddressID ON AddressMapping(CanonicalAddressID);
CREATE INDEX IF NOT EXISTS idx_AddressPollingStations_CanonicalAddressID ON AddressPollingStations(CanonicalAddressID);
CREATE INDEX IF NOT EXISTS idx_AddressPollingStations_PollingStationID ON AddressPollingStations(PollingStationID);
CREATE INDEX IF NOT EXISTS idx_AddressPIRCodes_CanonicalAddressID ON AddressPIRCodes(CanonicalAddressID);
CREATE INDEX IF NOT EXISTS idx_DeduplicationReport_RunID ON DeduplicationReport(RunID);
CREATE INDEX IF NOT EXISTS idx_DeduplicationReport_CreatedAt ON DeduplicationReport(CreatedAt);

-- New indexes for public space tables
CREATE INDEX IF NOT EXISTS idx_PublicSpaceType_PublicSpaceType ON PublicSpaceType(PublicSpaceType);
CREATE INDEX IF NOT EXISTS idx_PublicSpaceName_PublicSpaceName ON PublicSpaceName(PublicSpaceName);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_Settlement_ID ON SettlementPublicSpaces(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_PublicSpaceName_ID ON SettlementPublicSpaces(PublicSpaceName_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_PublicSpaceType_ID ON SettlementPublicSpaces(PublicSpaceType_ID);
CREATE INDEX IF NOT EXISTS idx_Address_new_PublicSpaceName_ID ON Address_new(PublicSpaceName_ID);
CREATE INDEX IF NOT EXISTS idx_Address_new_PublicSpaceType_ID ON Address_new(PublicSpaceType_ID);
CREATE INDEX IF NOT EXISTS idx_Address_new_PostalCode_ID ON Address_new(PostalCode_ID);
CREATE INDEX IF NOT EXISTS idx_Address_new_PollingStation_ID ON Address_new(PollingStation_ID);
CREATE INDEX IF NOT EXISTS idx_Address_new_County_ID ON Address_new(County_ID);
CREATE INDEX IF NOT EXISTS idx_Address_new_Settlement_ID ON Address_new(Settlement_ID);

-- Staging table for OEVK JSON data
CREATE TABLE IF NOT EXISTS staging_oevk_json (
    maz TEXT NOT NULL, -- County code (maps to CountyCode)
    evk TEXT NOT NULL, -- OEVK code (maps to OEVK)
    centrum TEXT, -- Center point coordinates
    poligon TEXT, -- Polygon boundary coordinates
    run_tag TEXT NOT NULL,
    PRIMARY KEY (maz, evk, run_tag)
);
