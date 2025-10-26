-- PostgreSQL Schema for OEVK Data
-- Translated from SQLite schema
-- All ID columns use UUID type (converted from MD5 hex to UUID5)

-- PostGIS extension for geospatial data support
CREATE EXTENSION IF NOT EXISTS postgis;

-- County table
CREATE TABLE IF NOT EXISTS County (
    ID UUID PRIMARY KEY, -- md5(CountyCode)
    CountyCode TEXT UNIQUE NOT NULL,
    CountyName TEXT NOT NULL
);

-- Settlement table
CREATE TABLE IF NOT EXISTS Settlement (
    ID UUID PRIMARY KEY, -- md5(CountyCode|SettlementCode)
    SettlementCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    County_ID UUID NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, SettlementCode)
);

-- NationalIndividualElectoralDistrict (OEVK) table
CREATE TABLE IF NOT EXISTS NationalIndividualElectoralDistrict (
    ID UUID PRIMARY KEY, -- md5(CountyCode|OEVK)
    OEVK TEXT NOT NULL,
    Name TEXT NOT NULL,
    Center GEOMETRY(POINT, 4326), -- Center point coordinates using PostGIS (SRID 4326 = WGS 84)
    Polygon GEOMETRY(POLYGON, 4326), -- Boundary polygon coordinates using PostGIS (SRID 4326 = WGS 84)
    County_ID UUID NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, OEVK)
);

-- SettlementIndividualElectoralDistrict (TEVK) table
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID UUID PRIMARY KEY, -- md5(CountyCode|SettlementCode|TEVK)
    TEVK TEXT,
    Name TEXT NOT NULL,
    County_ID UUID NOT NULL,
    Settlement_ID UUID NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK)
);

-- PostalCode table
CREATE TABLE IF NOT EXISTS PostalCode (
    ID UUID PRIMARY KEY, -- md5(PostalCode)
    PostalCode TEXT UNIQUE NOT NULL
);

-- PostalCode_Settlement junction table
CREATE TABLE IF NOT EXISTS PostalCode_Settlement (
    ID UUID PRIMARY KEY, -- md5(PostalCode_ID|Settlement_ID)
    PostalCode_ID UUID NOT NULL,
    Settlement_ID UUID NOT NULL,
    FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    UNIQUE (PostalCode_ID, Settlement_ID)
);

-- PollingStation table
CREATE TABLE IF NOT EXISTS PollingStation (
    ID UUID PRIMARY KEY, -- md5(CountyCode|SettlementCode|OEVK|TEVK|PollingStationAddress)
    PollingStationAddress TEXT NOT NULL,
    SettlementIndividualElectoralDistrict_ID UUID NOT NULL,
    County_ID UUID NOT NULL,
    Settlement_ID UUID NOT NULL,
    NationalIndividualElectoralDistrict_ID UUID NOT NULL,
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

-- Add PostGIS GEOGRAPHY column for spatial queries
ALTER TABLE PollingStation ADD COLUMN IF NOT EXISTS Geometry GEOGRAPHY(POINT, 4326);
CREATE INDEX IF NOT EXISTS idx_PollingStation_Geometry ON PollingStation USING GIST(Geometry);



-- PublicSpaceType table
CREATE TABLE IF NOT EXISTS PublicSpaceType (
    ID UUID PRIMARY KEY, -- md5(PublicSpaceType)
    PublicSpaceType TEXT UNIQUE NOT NULL
);

-- PublicSpaceName table
CREATE TABLE IF NOT EXISTS PublicSpaceName (
    ID UUID PRIMARY KEY, -- md5(PublicSpaceName)
    PublicSpaceName TEXT UNIQUE NOT NULL
);

-- SettlementPublicSpaces junction table
CREATE TABLE IF NOT EXISTS SettlementPublicSpaces (
    ID UUID PRIMARY KEY, -- md5(Settlement_ID|PublicSpaceName_ID|PublicSpaceType_ID)
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
-- Spatial indexes for geospatial queries on OEVK geometries
CREATE INDEX IF NOT EXISTS idx_oevk_center_gist ON NationalIndividualElectoralDistrict USING GIST (Center);
CREATE INDEX IF NOT EXISTS idx_oevk_polygon_gist ON NationalIndividualElectoralDistrict USING GIST (Polygon);

CREATE INDEX IF NOT EXISTS idx_SettlementIndividualElectoralDistrict_County_ID ON SettlementIndividualElectoralDistrict(County_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementIndividualElectoralDistrict_Settlement_ID ON SettlementIndividualElectoralDistrict(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_PostalCode_Settlement_PostalCode_ID ON PostalCode_Settlement(PostalCode_ID);
CREATE INDEX IF NOT EXISTS idx_PostalCode_Settlement_Settlement_ID ON PostalCode_Settlement(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_PollingStation_County_ID ON PollingStation(County_ID);
CREATE INDEX IF NOT EXISTS idx_PollingStation_Settlement_ID ON PollingStation(Settlement_ID);






-- Address table (canonical/cleansed addresses)
-- This is the deduplicated, cleansed address data exported from CanonicalAddress
-- Includes PollingStation_ID and PIRCode directly (instead of junction tables)
CREATE TABLE IF NOT EXISTS Address (
    ID UUID PRIMARY KEY,
    CountyCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    StreetName TEXT NOT NULL,
    HouseNumber TEXT NOT NULL,
    FullAddress TEXT NOT NULL,
    AccessibilityFlag TEXT,
    Latitude REAL,
    Longitude REAL,
    GeocodingQuality TEXT,
    GeocodingSource TEXT,
    GeocodedAt TIMESTAMP,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    County_ID UUID,
    Settlement_ID UUID,
    PollingStation_ID UUID,
    PIRCode TEXT,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (PollingStation_ID) REFERENCES PollingStation(ID),
    UNIQUE (CountyCode, SettlementName, FullAddress)
);

-- Add PostGIS GEOGRAPHY column for spatial queries (populated after data import)
ALTER TABLE Address ADD COLUMN IF NOT EXISTS Geometry GEOGRAPHY(POINT, 4326);

-- Indexes for Address table
CREATE INDEX IF NOT EXISTS idx_Address_Coordinates ON Address(Latitude, Longitude);
CREATE INDEX IF NOT EXISTS idx_Address_Quality ON Address(GeocodingQuality);
CREATE INDEX IF NOT EXISTS idx_Address_County_ID ON Address(County_ID);
CREATE INDEX IF NOT EXISTS idx_Address_Settlement_ID ON Address(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_Address_PollingStation_ID ON Address(PollingStation_ID);
CREATE INDEX IF NOT EXISTS idx_Address_PIRCode ON Address(PIRCode);
CREATE INDEX IF NOT EXISTS idx_Address_Geometry ON Address USING GIST(Geometry);






-- AddressMapping table to track original to canonical address relationships






-- DeduplicationReport table for audit and verification











-- New indexes for public space tables
CREATE INDEX IF NOT EXISTS idx_PublicSpaceType_PublicSpaceType ON PublicSpaceType(PublicSpaceType);
CREATE INDEX IF NOT EXISTS idx_PublicSpaceName_PublicSpaceName ON PublicSpaceName(PublicSpaceName);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_Settlement_ID ON SettlementPublicSpaces(Settlement_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_PublicSpaceName_ID ON SettlementPublicSpaces(PublicSpaceName_ID);
CREATE INDEX IF NOT EXISTS idx_SettlementPublicSpaces_PublicSpaceType_ID ON SettlementPublicSpaces(PublicSpaceType_ID);







-- Staging table for OEVK JSON data
CREATE TABLE IF NOT EXISTS staging_oevk_json (
    maz TEXT NOT NULL, -- County code (maps to CountyCode)
    evk TEXT NOT NULL, -- OEVK code (maps to OEVK)
    centrum TEXT, -- Center point coordinates
    poligon TEXT, -- Polygon boundary coordinates
    run_tag TEXT NOT NULL,
    PRIMARY KEY (maz, evk, run_tag)
);


-- PostgreSQL-specific extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS postgis;

-- Trigram index for efficient LIKE/ILIKE queries on FullAddress
-- Enables fast substring searches like '%Bar%' and '%utca%'
CREATE INDEX IF NOT EXISTS idx_address_fulladdress_trgm ON Address USING gin (FullAddress gin_trgm_ops);

-- Spatial indexes for geocoded coordinates using PostGIS
CREATE INDEX IF NOT EXISTS idx_Address_Geometry ON Address USING GIST(Geometry);
CREATE INDEX IF NOT EXISTS idx_PollingStation_Geometry ON PollingStation USING GIST(Geometry);

