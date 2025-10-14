-- PostgreSQL Schema for OEVK Data
-- Translated from SQLite schema
-- All ID columns use UUID type

-- Database Schema for OEVK Data Transformation
-- All primary keys are xxhash64 digests stored as lowercase hexadecimal strings

-- County table
CREATE TABLE IF NOT EXISTS County (
    ID UUID PRIMARY KEY, -- xxhash64(CountyCode)
    CountyCode TEXT UNIQUE NOT NULL,
    CountyName TEXT NOT NULL
);

-- Settlement table
CREATE TABLE IF NOT EXISTS Settlement (
    ID UUID PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode)
    SettlementCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    County_ID UUID NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, SettlementCode)
);

-- NationalIndividualElectoralDistrict (OEVK) table
CREATE TABLE IF NOT EXISTS NationalIndividualElectoralDistrict (
    ID UUID PRIMARY KEY, -- xxhash64(CountyCode|OEVK)
    OEVK TEXT NOT NULL,
    Name TEXT NOT NULL,
    Center TEXT,
    Polygon TEXT,
    County_ID UUID NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, OEVK)
);

-- SettlementIndividualElectoralDistrict (TEVK) table
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID UUID PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode|TEVK|OEVK)
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID UUID NOT NULL,
    Settlement_ID UUID NOT NULL,
    NationalIndividualElectoralDistrict_ID UUID NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK, NationalIndividualElectoralDistrict_ID)
);

-- PostalCode table
CREATE TABLE IF NOT EXISTS PostalCode (
    ID UUID PRIMARY KEY, -- xxhash64(PostalCode)
    PostalCode TEXT UNIQUE NOT NULL
);

-- PostalCode_Settlement junction table
CREATE TABLE IF NOT EXISTS PostalCode_Settlement (
    ID UUID PRIMARY KEY, -- xxhash64(PostalCode_ID|Settlement_ID)
    PostalCode_ID UUID NOT NULL,
    Settlement_ID UUID NOT NULL,
    FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (PostalCode_ID, Settlement_ID)
);

-- PollingStation table
CREATE TABLE IF NOT EXISTS PollingStation (
    ID UUID PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode|OEVK|TEVK|PollingStationAddress)
    PollingStationAddress TEXT NOT NULL,
    SettlementIndividualElectoralDistrict_ID UUID NOT NULL,
    County_ID UUID NOT NULL,
    Settlement_ID UUID NOT NULL,
    NationalIndividualElectoralDistrict_ID UUID NOT NULL,
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID),
    UNIQUE (County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID, SettlementIndividualElectoralDistrict_ID, PollingStationAddress)
);



-- PublicSpaceType table
CREATE TABLE IF NOT EXISTS PublicSpaceType (
    ID UUID PRIMARY KEY, -- xxhash64(PublicSpaceType)
    PublicSpaceType TEXT UNIQUE NOT NULL
);

-- PublicSpaceName table
CREATE TABLE IF NOT EXISTS PublicSpaceName (
    ID UUID PRIMARY KEY, -- xxhash64(PublicSpaceName)
    PublicSpaceName TEXT UNIQUE NOT NULL
);

-- SettlementPublicSpaces junction table
CREATE TABLE IF NOT EXISTS SettlementPublicSpaces (
    ID UUID PRIMARY KEY, -- xxhash64(Settlement_ID|PublicSpaceName_ID|PublicSpaceType_ID)
    Settlement_ID UUID NOT NULL,
    PublicSpaceName_ID UUID NOT NULL,
    PublicSpaceType_ID UUID NOT NULL,
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID),
    FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID),
    UNIQUE (Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID)
);

-- Update Address table to use foreign keys instead of text fields


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






-- Address table (canonical/cleansed addresses)
-- This is the deduplicated, cleansed address data exported from CanonicalAddress
CREATE TABLE IF NOT EXISTS Address (
    ID UUID PRIMARY KEY,
    Sequence INTEGER NOT NULL,
    OriginalOrder INTEGER NOT NULL,
    FullAddress TEXT NOT NULL,
    PublicSpaceName TEXT NOT NULL,
    PublicSpaceType TEXT NOT NULL,
    HouseNumber TEXT NOT NULL,
    Building TEXT,
    Staircase TEXT,
    PostalCode_ID UUID NOT NULL,
    PollingStation_ID UUID NOT NULL,
    SettlementIndividualElectoralDistrict_ID UUID NOT NULL,
    County_ID UUID NOT NULL,
    Settlement_ID UUID NOT NULL,
    NationalIndividualElectoralDistrict_ID UUID NOT NULL,
    OriginalAddressCount INTEGER,
    FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID),
    FOREIGN KEY (PollingStation_ID) REFERENCES PollingStation(ID),
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID)
);



-- AddressMapping table to track original to canonical address relationships


-- AddressPollingStations table to preserve polling station assignments
CREATE TABLE IF NOT EXISTS AddressPollingStations (
    ID UUID PRIMARY KEY, -- xxhash64(AddressID|PollingStationID)
    AddressID UUID NOT NULL,
    PollingStationID UUID NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AddressID) REFERENCES Address(ID),
    FOREIGN KEY (PollingStationID) REFERENCES PollingStation(ID),
    UNIQUE (AddressID, PollingStationID)
);

-- AddressPIRCodes table to preserve PIR code relationships
CREATE TABLE IF NOT EXISTS AddressPIRCodes (
    ID UUID PRIMARY KEY, -- xxhash64(AddressID|PIRCode)
    AddressID UUID NOT NULL,
    PIRCode TEXT NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AddressID) REFERENCES Address(ID),
    UNIQUE (AddressID, PIRCode)
);

-- DeduplicationReport table for audit and verification





CREATE INDEX IF NOT EXISTS idx_AddressPollingStations_AddressID ON AddressPollingStations(AddressID);
CREATE INDEX IF NOT EXISTS idx_AddressPollingStations_PollingStationID ON AddressPollingStations(PollingStationID);
CREATE INDEX IF NOT EXISTS idx_AddressPIRCodes_AddressID ON AddressPIRCodes(AddressID);



-- New indexes for public space tables
CREATE INDEX IF NOT EXISTS idx_PublicSpaceType_PublicSpaceType ON PublicSpaceType(PublicSpaceType);
CREATE INDEX IF NOT EXISTS idx_PublicSpaceName_PublicSpaceName ON PublicSpaceName(PublicSpaceName);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_Settlement_ID ON SettlementPublicSpaces(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_PublicSpaceName_ID ON SettlementPublicSpaces(PublicSpaceName_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_PublicSpaceType_ID ON SettlementPublicSpaces(PublicSpaceType_ID);








-- PostgreSQL-specific extensions for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Trigram index for efficient LIKE/ILIKE queries on FullAddress
-- Enables fast substring searches like '%Bar%' and '%utca%'
CREATE INDEX IF NOT EXISTS idx_address_fulladdress_trgm ON Address USING gin (FullAddress gin_trgm_ops);
