-- Database Schema for OEVK Data Transformation
-- All primary keys are xxhash64 digests stored as lowercase hexadecimal strings

-- County table
CREATE TABLE IF NOT EXISTS County (
    ID TEXT PRIMARY KEY, -- xxhash64(CountyCode)
    CountyCode TEXT UNIQUE NOT NULL,
    CountyName TEXT NOT NULL
);

-- Settlement table
CREATE TABLE IF NOT EXISTS Settlement (
    ID TEXT PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode)
    SettlementCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, SettlementCode)
);

-- NationalIndividualElectoralDistrict (OEVK) table
CREATE TABLE IF NOT EXISTS NationalIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY, -- xxhash64(CountyCode|OEVK)
    OEVK TEXT NOT NULL,
    Name TEXT NOT NULL,
    Center TEXT,
    Polygon TEXT,
    County_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, OEVK)
);

-- SettlementIndividualElectoralDistrict (TEVK) table
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode|TEVK|OEVK)
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK, NationalIndividualElectoralDistrict_ID)
);

-- PostalCode table
CREATE TABLE IF NOT EXISTS PostalCode (
    ID TEXT PRIMARY KEY, -- xxhash64(PostalCode)
    PostalCode TEXT UNIQUE NOT NULL
);

-- PostalCode_Settlement junction table
CREATE TABLE IF NOT EXISTS PostalCode_Settlement (
    ID TEXT PRIMARY KEY, -- xxhash64(PostalCode_ID|Settlement_ID)
    PostalCode_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (PostalCode_ID, Settlement_ID)
);

-- PollingStation table
CREATE TABLE IF NOT EXISTS PollingStation (
    ID TEXT PRIMARY KEY, -- xxhash64(CountyCode|SettlementCode|OEVK|TEVK|PollingStationAddress)
    PollingStationAddress TEXT NOT NULL,
    SettlementIndividualElectoralDistrict_ID TEXT NOT NULL,
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) REFERENCES SettlementIndividualElectoralDistrict(ID),
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID),
    UNIQUE (County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID, SettlementIndividualElectoralDistrict_ID, PollingStationAddress)
);

-- Address table
CREATE TABLE IF NOT EXISTS Address (
    ID TEXT PRIMARY KEY, -- xxhash64(...) based on full address components
    Sequence INTEGER NOT NULL,
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