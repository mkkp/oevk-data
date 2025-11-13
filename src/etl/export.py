"""Export logic for generating CSV files from target tables."""

import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path

import duckdb

from src.utils.config import Config, get_config
from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)

# OEVK namespace UUID for generating UUIDs
# Using UUID5 (SHA-1 based) for better collision resistance than UUID3 (MD5)
OEVK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "oevk.hu")


def _to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case.

    Args:
        name: String in PascalCase or camelCase

    Returns:
        String in snake_case

    Examples:
        >>> _to_snake_case("CountyID")
        'county_id'
        >>> _to_snake_case("NationalIndividualElectoralDistrict")
        'national_individual_electoral_district'
    """
    # Insert underscore before uppercase letters (except at start)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Insert underscore before uppercase letters followed by lowercase
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


# Mapping from DuckDB table names (PascalCase) to PostgreSQL table names (snake_case)
# These are the actual table names used in PostgreSQL schema and CSV exports
DUCKDB_TO_POSTGRESQL_TABLE_NAMES = {
    "NationalIndividualElectoralDistrict": "oevk",
    "SettlementIndividualElectoralDistrict": "tevk",
    "PostalCode_Settlement": "postal_code_settlement",
    "SettlementPublicSpaces": "settlement_public_spaces",
    "PublicSpaceType": "public_space_type",
    "PublicSpaceName": "public_space_name",
    "PostalCode": "postal_code",
    "PollingStation": "polling_station",
    "Settlement": "settlement",
    "County": "county",
    "Address": "address",  # CanonicalAddress exported as Address
}


def to_uuid3(value):
    """Convert a value to UUID v3 using OEVK namespace.

    DEPRECATED: Use to_uuid5() instead for PostgreSQL exports.
    """
    if value is None or value == "":
        return None
    return str(uuid.uuid3(OEVK_NAMESPACE, str(value)))


def to_uuid5(value):
    """Convert a MD5 hex value or any string to UUID v5 using OEVK namespace.

    This function converts MD5 hex IDs (used internally in DuckDB) to proper
    UUID5 format for PostgreSQL compatibility. UUID5 uses SHA-1 hashing and provides
    consistent, reproducible UUIDs based on a namespace and name.

    Args:
        value: The value to convert (typically MD5 hex string, first 16 chars)

    Returns:
        UUID5 string in standard format (xxxxxxxx-xxxx-5xxx-xxxx-xxxxxxxxxxxx) or None
    """
    if value is None or value == "":
        return None
    return str(uuid.uuid5(OEVK_NAMESPACE, str(value)))


def convert_center_to_point(center_text: str | None) -> str | None:
    """Convert center TEXT 'lat lon' to PostGIS POINT WKT format.

    Converts space-separated latitude/longitude coordinates to Well-Known Text (WKT)
    format suitable for PostGIS ST_GeomFromText() function. Swaps coordinate order
    from (lat, lon) to (lon, lat) as required by OGC/PostGIS standards.

    Args:
        center_text: Space-separated coordinates "lat lon" (e.g., "47.4979 19.0402")

    Returns:
        WKT POINT string "POINT(lon lat)" or None if input is invalid
    """
    if not center_text or center_text.strip() == "":
        return None

    try:
        parts = center_text.strip().split()
        if len(parts) != 2:
            logger.warning(f"Invalid center format (expected 'lat lon'): {center_text}")
            return None

        lat = float(parts[0])
        lon = float(parts[1])

        # Validate coordinate ranges (WGS 84 bounds)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            logger.warning(f"Coordinates out of range: lat={lat}, lon={lon}")
            return None

        # Return WKT with lon, lat order (PostGIS/OGC standard)
        return f"POINT({lon} {lat})"

    except (ValueError, IndexError) as e:
        logger.error(f"Error converting center '{center_text}': {e}")
        return None


def convert_polygon_to_wkt(polygon_text: str | None) -> str | None:
    """Convert polygon TEXT to PostGIS POLYGON WKT format.

    Converts comma-separated coordinate pairs to Well-Known Text (WKT) format
    suitable for PostGIS ST_GeomFromText() function. Swaps coordinate order
    from (lat, lon) to (lon, lat) and auto-closes polygons if needed.

    Args:
        polygon_text: Comma-separated coordinate pairs "lat1 lon1,lat2 lon2,..."
                     (e.g., "47.5 19.0,47.5 19.1,47.4 19.1")

    Returns:
        WKT POLYGON string "POLYGON((lon1 lat1, lon2 lat2, ...))" or None if invalid
    """
    if not polygon_text or polygon_text.strip() == "":
        return None

    try:
        pairs = polygon_text.strip().split(",")
        coords = []

        for pair in pairs:
            parts = pair.strip().split()
            if len(parts) != 2:
                logger.warning(f"Invalid coordinate pair: {pair}")
                continue

            lat = float(parts[0])
            lon = float(parts[1])

            # Validate coordinate ranges (WGS 84 bounds)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                logger.warning(f"Coordinates out of range: lat={lat}, lon={lon}")
                continue

            # Swap to (lon, lat) order for PostGIS
            coords.append((lon, lat))

        # PostGIS requires at least 3 points for a polygon
        if len(coords) < 3:
            logger.warning(f"Polygon must have at least 3 points, got {len(coords)}")
            return None

        # Auto-close polygon: first point must equal last point
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        # Format as WKT: POLYGON((lon1 lat1, lon2 lat2, ...))
        coord_str = ", ".join(f"{lon} {lat}" for lon, lat in coords)
        return f"POLYGON(({coord_str}))"

    except (ValueError, IndexError) as e:
        logger.error(f"Error converting polygon '{polygon_text}': {e}")
        return None


def generate_postgresql_schema():
    """Translates SQLite schema to PostgreSQL-compatible schema.

    Converts ID columns from TEXT to UUID type and makes other necessary
    PostgreSQL-specific adjustments. Adds PostGIS extension and GEOMETRY types
    for OEVK geospatial data if POSTGRESQL_USE_POSTGIS is enabled.

    Returns:
        str: PostgreSQL-compatible schema DDL
    """
    # Get PostGIS configuration
    config = get_config()
    use_postgis = config.get_postgresql_settings().get("use_postgis", True)

    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()

    # Replace the DuckDB schema header with PostgreSQL-specific header
    schema = re.sub(
        r"^-- Database Schema for OEVK Data Transformation\n-- All primary keys are MD5 digests[^\n]*\n\n",
        "",
        schema,
        flags=re.MULTILINE,
    )

    # Add PostgreSQL header comment and PostGIS extension if enabled
    pg_header = "-- PostgreSQL Schema for OEVK Data\n"
    pg_header += "-- Translated from SQLite schema\n"
    pg_header += "-- All ID columns use UUID type (converted from MD5 hex to UUID5)\n\n"

    if use_postgis:
        pg_header += "-- PostGIS extension for geospatial data support\n"
        pg_header += "CREATE EXTENSION IF NOT EXISTS postgis;\n\n"

    schema = pg_header + schema

    # ========================================
    # PostgreSQL Naming Convention Transformations
    # ========================================
    # Apply snake_case naming for tables and columns as per project.md conventions

    # 1. Convert table names to snake_case with special abbreviations
    # NOTE: Order matters! More specific names (CanonicalAddress) before generic (Address)
    table_mappings = {
        "NationalIndividualElectoralDistrict": "oevk",
        "SettlementIndividualElectoralDistrict": "tevk",
        "PostalCode_Settlement": "postal_code_settlement",
        "SettlementPublicSpaces": "settlement_public_spaces",
        "PublicSpaceType": "public_space_type",
        "PublicSpaceName": "public_space_name",
        "PostalCode": "postal_code",
        "PollingStation": "polling_station",
        "Settlement": "settlement",
        "County": "county",
        "CanonicalAddress": "address",  # Must come before "Address"
        "Address": "address",  # Catch any remaining Address references
        "AddressPollingStations": "address_polling_stations",
        "AddressPIRCodes": "address_pir_codes",
        "AddressMapping": "address_mapping",
        "staging_oevk_json": "staging_oevk_json",  # already snake_case
    }

    # Apply table name transformations
    for old_name, new_name in table_mappings.items():
        # Table definitions: CREATE TABLE IF NOT EXISTS OldName
        schema = re.sub(
            rf"\bCREATE TABLE IF NOT EXISTS {old_name}\b",
            f"CREATE TABLE IF NOT EXISTS {new_name}",
            schema,
        )
        # References: REFERENCES OldName(ID)
        schema = re.sub(
            rf"\bREFERENCES {old_name}\(", f"REFERENCES {new_name}(", schema
        )
        # Index/table names in various contexts
        schema = re.sub(rf"\bON {old_name}\(", f"ON {new_name}(", schema)
        schema = re.sub(rf"\bFROM {old_name}\b", f"FROM {new_name}", schema)
        schema = re.sub(
            rf"\bALTER TABLE {old_name}\b", f"ALTER TABLE {new_name}", schema
        )
        # Comments: -- OldName table -> -- new_name table
        schema = re.sub(rf"-- {old_name} table\b", f"-- {new_name} table", schema)

    # Additional comment fixes for specific patterns
    schema = re.sub(
        r"-- Update Address table to use foreign keys",
        "-- Update address table to use foreign keys",
        schema,
    )

    # 2. Convert column names to snake_case
    column_mappings = {
        # Generic ID columns
        r"\bID\b": "id",
        # Foreign key columns with special abbreviations
        r"\bNationalIndividualElectoralDistrict_ID\b": "oevk_id",
        r"\bSettlementIndividualElectoralDistrict_ID\b": "tevk_id",
        # Standard foreign key columns
        r"\bCounty_ID\b": "county_id",
        r"\bSettlement_ID\b": "settlement_id",
        r"\bPublicSpaceName_ID\b": "public_space_name_id",
        r"\bPublicSpaceType_ID\b": "public_space_type_id",
        r"\bPostalCode_ID\b": "postal_code_id",
        r"\bPollingStation_ID\b": "polling_station_id",
        r"\bCanonicalAddressID\b": "address_id",
        r"\bPollingStationID\b": "polling_station_id",
        r"\bOriginalAddressID\b": "original_address_id",
        # Regular columns
        r"\bCountyCode\b": "county_code",
        r"\bCountyName\b": "county_name",
        r"\bSettlementCode\b": "settlement_code",
        r"\bSettlementName\b": "settlement_name",
        r"\bOEVK\b": "oevk",
        r"\bTEVK\b": "tevk",
        r"\bName\b": "name",
        r"\bCenter\b": "center",
        r"\bPolygon\b": "polygon",
        r"\bPostalCode\b": "postal_code",
        r"\bPollingStationCode\b": "polling_station_code",
        r"\bPollingStationAddress\b": "polling_station_address",
        r"\bLatitude\b": "latitude",
        r"\bLongitude\b": "longitude",
        r"\bGeocodingQuality\b": "geocoding_quality",
        r"\bGeocodingSource\b": "geocoding_source",
        r"\bGeocodedAt\b": "geocoded_at",
        r"\bMatchedAddress\b": "matched_address",
        r"\bPublicSpaceType\b": "public_space_type",
        r"\bPublicSpaceName\b": "public_space_name",
        r"\bHouseNumber\b": "house_number",
        r"\bBuilding\b": "building",
        r"\bStaircase\b": "staircase",
        r"\bFullAddress\b": "full_address",
        r"\bAccessibilityFlag\b": "accessibility_flag",
        r"\bCreatedAt\b": "created_at",
        r"\bGeometry\b": "geometry",
        r"\bMappingType\b": "mapping_type",
        r"\bPIRCode\b": "pir_code",
        r"\bSequence\b": "sequence",
        r"\bOriginalOrder\b": "original_order",
        r"\bOriginalAddressCount\b": "original_address_count",
    }

    # Apply column name transformations
    for old_pattern, new_name in column_mappings.items():
        schema = re.sub(old_pattern, new_name, schema)

    # 2.5. Remove table name prefixes from column names (per project.md conventions)
    # This must happen AFTER general column transformations to avoid conflicts
    # Use simple global replacements - these are safe because column names are unique enough

    # County columns
    schema = re.sub(r"\bcounty_code\b", "code", schema)
    schema = re.sub(r"\bcounty_name\b", "name", schema)

    # Settlement columns
    schema = re.sub(r"\bsettlement_code\b", "code", schema)
    schema = re.sub(r"\bsettlement_name\b", "name", schema)

    # oevk column (careful with table references)
    schema = re.sub(r"\boevk TEXT", "code TEXT", schema)
    schema = re.sub(r", oevk\)", ", code)", schema)  # UNIQUE constraints

    # tevk column (careful with table references)
    schema = re.sub(r"\btevk TEXT", "code TEXT", schema)
    schema = re.sub(r", tevk\)", ", code)", schema)  # UNIQUE constraints

    # postal_code column (in postal_code table)
    schema = re.sub(r"    postal_code TEXT UNIQUE", "    code TEXT UNIQUE", schema)

    # polling_station columns
    schema = re.sub(r"\bpolling_station_code\b", "code", schema)
    schema = re.sub(r"\bpolling_station_address\b", "address", schema)

    # public_space_name column (in public_space_name table)
    schema = re.sub(
        r"    public_space_name TEXT UNIQUE", "    name TEXT UNIQUE", schema
    )

    # public_space_type column (in public_space_type table)
    schema = re.sub(
        r"    public_space_type TEXT UNIQUE", "    name TEXT UNIQUE", schema
    )

    # 2.6. Remove timestamp columns (created_at, geocoded_at) - not user-facing
    # Remove geocoded_at from polling_station
    schema = re.sub(r"    geocoded_at TIMESTAMP,\n", "", schema)

    # Remove created_at from various tables
    schema = re.sub(
        r"    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n", "", schema
    )

    # Remove indexes on removed columns
    # Note: These patterns match PascalCase names before snake_case conversion happens at step 3
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_[A-Za-z]+_CreatedAt ON [A-Za-z]+\(CreatedAt\);\n",
        "",
        schema,
    )
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_[A-Za-z]+_GeocodedAt ON [A-Za-z]+\(GeocodedAt\);\n",
        "",
        schema,
    )

    # 3. Convert index names to snake_case with proper patterns
    # Pattern: idx_TableName_ColumnName -> idx_table_name_column_name
    schema = re.sub(
        r"idx_([A-Z][a-zA-Z]+)_([A-Z][a-zA-Z_]+)",
        lambda m: f"idx_{_to_snake_case(m.group(1))}_{_to_snake_case(m.group(2))}",
        schema,
    )

    # 3.5. Remove timestamp indexes again (after snake_case conversion)
    # This catches any indexes that weren't removed in step 2.6
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_[a-z_]+_created_at ON [A-Za-z]+\(created_at\);\n",
        "",
        schema,
    )
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_[a-z_]+_geocoded_at ON [A-Za-z]+\(geocoded_at\);\n",
        "",
        schema,
    )

    # Convert all ID columns from TEXT to UUID
    # Pattern: id TEXT PRIMARY KEY -> id UUID PRIMARY KEY
    schema = re.sub(r"\bid TEXT\b", "id UUID", schema)
    # Pattern: _id TEXT -> _id UUID (for foreign keys)
    schema = re.sub(r"_id TEXT\b", "_id UUID", schema)
    # Pattern: _id TEXT, -> _id UUID, (with comma)
    schema = re.sub(r"_id TEXT,", "_id UUID,", schema)

    # Convert polling_station code column from VARCHAR to TEXT NOT NULL
    # Pattern: code VARCHAR, -> code TEXT NOT NULL,
    schema = re.sub(r"\bcode VARCHAR,", "code TEXT NOT NULL,", schema)

    # Convert OEVK center and polygon to PostGIS GEOMETRY types if enabled
    if use_postgis:
        # Replace center TEXT with GEOMETRY(POINT, 4326)
        # Note: Pattern matches after column name transformation (center not Center)
        schema = re.sub(
            r"center TEXT, -- center point coordinates \(space-separated: \"lat lon\"\)",
            "center GEOMETRY(POINT, 4326), -- Center point coordinates using PostGIS (SRID 4326 = WGS 84)",
            schema,
        )
        # Replace polygon TEXT with GEOMETRY(POLYGON, 4326)
        schema = re.sub(
            r"polygon TEXT, -- Boundary polygon coordinates \(comma-separated pairs: \"lat1 lon1,lat2 lon2,...\"\)",
            "polygon GEOMETRY(POLYGON, 4326), -- Boundary polygon coordinates using PostGIS (SRID 4326 = WGS 84)",
            schema,
        )

        # Add spatial indexes after oevk indexes
        spatial_indexes = """
-- Spatial indexes for geospatial queries on OEVK geometries
CREATE INDEX IF NOT EXISTS idx_oevk_center_gist ON oevk USING GIST (center);
CREATE INDEX IF NOT EXISTS idx_oevk_polygon_gist ON oevk USING GIST (polygon);
"""
        # Insert spatial indexes after the oevk county_id index
        schema = re.sub(
            r"(CREATE INDEX IF NOT EXISTS idx_oevk_county_id ON oevk\(county_id\);)",
            r"\1" + spatial_indexes,
            schema,
        )

        # Add GEOGRAPHY columns for geocoding if enabled
        geocoding_use_postgis = config.get("geocoding", {}).get("use_postgis", True)
        if geocoding_use_postgis:
            # Add geometry GEOGRAPHY column to address after coordinate columns
            schema = re.sub(
                r"(CREATE INDEX IF NOT EXISTS idx_address_quality ON address\(geocoding_quality\);)",
                r"\1\n\n-- Add PostGIS GEOGRAPHY column for spatial queries\nALTER TABLE address ADD COLUMN IF NOT EXISTS geometry GEOGRAPHY(POINT, 4326);",
                schema,
            )
            # Add GIST spatial index for address
            schema = re.sub(
                r"(ALTER TABLE address ADD COLUMN IF NOT EXISTS geometry GEOGRAPHY\(POINT, 4326\);)",
                r"\1\nCREATE INDEX IF NOT EXISTS idx_address_geometry ON address USING GIST(geometry);",
                schema,
            )

            # Add geometry GEOGRAPHY column to polling_station after coordinate columns
            schema = re.sub(
                r"(CREATE INDEX IF NOT EXISTS idx_polling_station_quality ON polling_station\(geocoding_quality\);)",
                r"\1\n\n-- Add PostGIS GEOGRAPHY column for spatial queries\nALTER TABLE polling_station ADD COLUMN IF NOT EXISTS geometry GEOGRAPHY(POINT, 4326);",
                schema,
            )
            # Add GIST spatial index for polling_station
            schema = re.sub(
                r"(ALTER TABLE polling_station ADD COLUMN IF NOT EXISTS geometry GEOGRAPHY\(POINT, 4326\);)",
                r"\1\nCREATE INDEX IF NOT EXISTS idx_polling_station_geometry ON polling_station USING GIST(geometry);",
                schema,
            )

    # For PostgreSQL export, we only want the canonical (cleansed) data:
    # - Remove original Address table (dirty data)
    # - Remove Address_new (SQLite artifact)
    # - Remove AddressMapping (internal transformation data)
    # - Remove DeduplicationReport (internal analytics)
    # - Rename CanonicalAddress to Address (this is the clean data)
    # - Update AddressPollingStations and AddressPIRCodes to reference Address

    # Remove unwanted tables
    # Note: Table names have already been transformed to snake_case by this point
    schema = re.sub(
        r"-- address table\s+CREATE TABLE IF NOT EXISTS address \(.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )
    schema = re.sub(
        r"CREATE TABLE IF NOT EXISTS Address_new.*?;", "", schema, flags=re.DOTALL
    )
    # Remove address_mapping table (snake_case version after transformation)
    schema = re.sub(
        r"-- address_mapping table.*?CREATE TABLE IF NOT EXISTS address_mapping.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )
    schema = re.sub(
        r"CREATE TABLE IF NOT EXISTS deduplication_report.*?;",
        "",
        schema,
        flags=re.DOTALL,
    )
    # Remove address_polling_stations and address_pir_codes tables (replaced by direct columns in Address)
    # Note: Use snake_case names as table names were already transformed
    schema = re.sub(
        r"-- address_polling_stations table.*?CREATE TABLE IF NOT EXISTS address_polling_stations.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )
    schema = re.sub(
        r"-- address_pir_codes table.*?CREATE TABLE IF NOT EXISTS address_pir_codes.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )

    # Remove comment sections for removed tables
    schema = re.sub(r"-- Deduplication tables.*?\n", "", schema)
    schema = re.sub(r"-- DeduplicationReport table.*?\n", "", schema)
    schema = re.sub(r"-- New indexes for deduplication tables.*?\n", "", schema)

    # Remove indexes for removed tables
    # Note: These patterns use snake_case because index names were already converted at step 3
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_address_new.*?;\n?", "", schema)
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_address_mapping.*?;\n?", "", schema
    )
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_canonical_address.*?;\n?", "", schema
    )
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_deduplication_report.*?;\n?", "", schema
    )
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_address_polling_stations.*?;\n?", "", schema
    )
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_address_pir_codes.*?;\n?", "", schema
    )

    # Remove orphaned indexes that reference Address_new table (case-insensitive)
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_Address_new.*?;\n?", "", schema)

    # Remove incorrect public_space indexes that use wrong column names
    # These use 'public_space_type' and 'public_space_name' columns which don't exist (should be 'name')
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_public_space_type_public_space_type ON public_space_type\(public_space_type\);\n?",
        "",
        schema,
    )
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_public_space_name_public_space_name ON public_space_name\(public_space_name\);\n?",
        "",
        schema,
    )

    # Remove the entire "Update address table to use foreign keys" section with premature indexes
    # This section contains address table indexes that appear before the address table definition
    # We'll add proper indexes in the custom_address_table below
    schema = re.sub(
        r"-- Update address table to use foreign keys.*?(?=-- address table|CREATE TABLE IF NOT EXISTS address)",
        "",
        schema,
        flags=re.DOTALL,
    )

    # Remove address table (CanonicalAddress after transformation) and insert custom address table
    # The address table must come BEFORE address_polling_stations and address_pir_codes
    # Note: Table names have already been transformed to snake_case by this point

    # Replace address table (transformed from CanonicalAddress) with a placeholder
    # Note: The comment has already been transformed from "CanonicalAddress" to "address" by this point
    schema = re.sub(
        r"-- address table for deduplicated addresses.*?CREATE TABLE IF NOT EXISTS address \(.*?\);",
        "%%ADDRESS_TABLE_PLACEHOLDER%%",
        schema,
        flags=re.DOTALL,
    )

    # Create custom Address table for PostgreSQL with the exact structure we export
    # This combines data from CanonicalAddress with all necessary foreign keys
    custom_address_table = """
-- address table (canonical/cleansed addresses)
-- This is the deduplicated, cleansed address data exported from CanonicalAddress
-- Includes all foreign keys for relationships
CREATE TABLE IF NOT EXISTS address (
    id UUID PRIMARY KEY,
    house_number TEXT,  -- Can be NULL for infrastructure/area addresses or when building/staircase suffices
    building TEXT,
    staircase TEXT,
    full_address TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    geocoding_quality TEXT,
    geocoding_source TEXT,
    county_id UUID NOT NULL,
    settlement_id UUID NOT NULL,
    public_space_name_id UUID NOT NULL,
    public_space_type_id UUID NOT NULL,
    oevk_id UUID NOT NULL,
    tevk_id UUID NOT NULL,
    postal_code_id UUID NOT NULL,
    polling_station_id UUID NOT NULL,
    FOREIGN KEY (county_id) REFERENCES county(id),
    FOREIGN KEY (settlement_id) REFERENCES settlement(id),
    FOREIGN KEY (public_space_name_id) REFERENCES public_space_name(id),
    FOREIGN KEY (public_space_type_id) REFERENCES public_space_type(id),
    FOREIGN KEY (oevk_id) REFERENCES oevk(id),
    FOREIGN KEY (tevk_id) REFERENCES tevk(id),
    FOREIGN KEY (postal_code_id) REFERENCES postal_code(id),
    FOREIGN KEY (polling_station_id) REFERENCES polling_station(id),
    UNIQUE (full_address, settlement_id)
);

-- Add PostGIS GEOGRAPHY column for spatial queries (populated after data import)
ALTER TABLE address ADD COLUMN IF NOT EXISTS geometry GEOGRAPHY(POINT, 4326);

-- Indexes for address table
CREATE INDEX IF NOT EXISTS idx_address_coordinates ON address(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_address_quality ON address(geocoding_quality);
CREATE INDEX IF NOT EXISTS idx_address_county_id ON address(county_id);
CREATE INDEX IF NOT EXISTS idx_address_settlement_id ON address(settlement_id);
CREATE INDEX IF NOT EXISTS idx_address_public_space_name_id ON address(public_space_name_id);
CREATE INDEX IF NOT EXISTS idx_address_public_space_type_id ON address(public_space_type_id);
CREATE INDEX IF NOT EXISTS idx_address_oevk_id ON address(oevk_id);
CREATE INDEX IF NOT EXISTS idx_address_tevk_id ON address(tevk_id);
CREATE INDEX IF NOT EXISTS idx_address_postal_code_id ON address(postal_code_id);
CREATE INDEX IF NOT EXISTS idx_address_polling_station_id ON address(polling_station_id);
CREATE INDEX IF NOT EXISTS idx_address_geometry ON address USING GIST(geometry);

"""

    # Add PostgreSQL-specific statements
    postgresql_header = """-- PostgreSQL Schema for OEVK Data
-- Translated from SQLite schema
-- All ID columns use TEXT type (xxhash64 hex values)

"""

    # Add PostgreSQL-specific extensions and indexes at the end
    postgresql_indexes = """

-- PostgreSQL-specific extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Trigram index for efficient LIKE/ILIKE queries on full_address
-- Enables fast substring searches like '%Bar%' and '%utca%'
CREATE INDEX IF NOT EXISTS idx_address_full_address_trgm ON address USING gin (full_address gin_trgm_ops);

-- Spatial indexes for geocoded coordinates using PostGIS
CREATE INDEX IF NOT EXISTS idx_address_geometry ON address USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_polling_station_geometry ON polling_station USING GIST(geometry);

"""

    # Note: Removed AddressFullView as it was designed for the old raw Address table
    # The new Address table is canonical/deduplicated data without many of those columns
    _unused_view_code = """
-- This view is incompatible with canonical Address table structure
CREATE OR REPLACE VIEW AddressFullView_REMOVED AS
SELECT
    -- Address primary key
    a.ID AS address_id,

    -- Sequence and ordering
    a.Sequence AS sequence,
    a.OriginalOrder AS original_order,

    -- County information (Vármegye)
    c.ID AS county_id,
    c.CountyCode AS county_code,
    c.CountyName AS county_name,

    -- National Electoral District (OEVK)
    oevk.ID AS national_individual_electoral_district_id,
    oevk.OEVK AS oevk_code,
    oevk.Name AS oevk_name,

    -- Settlement information (Település)
    s.ID AS settlement_id,
    s.SettlementCode AS settlement_code,
    s.SettlementName AS settlement_name,

    -- Settlement Electoral District (TEVK)
    tevk.ID AS settlement_individual_electoral_district_id,
    tevk.TEVK AS tevk_code,
    tevk.Name AS tevk_name,

    -- Polling Station (Szavazókör)
    ps.ID AS polling_station_id,
    ps.PollingStationAddress AS polling_station_address,

    -- Postal Code (Irányítószám/PIR)
    pc.ID AS postal_code_id,
    pc.PostalCode AS postal_code,

    -- Address components (Cím komponensek)
    a.PublicSpaceName AS public_space_name,  -- Közterület név
    a.PublicSpaceType AS public_space_type,  -- Közterület jelleg
    a.HouseNumber AS house_number,           -- Házszám
    a.Building AS building,                  -- Épület
    a.Staircase AS staircase,                -- Lépcsőház

    -- Full address (Teljes cím)
    a.FullAddress AS full_address,

    -- Deduplication metadata
    a.OriginalAddressCount AS original_address_count,

    -- Polling station mapping
    (
        SELECT COUNT(*)
        FROM AddressPollingStations aps
        WHERE aps.AddressID = a.ID
    ) AS polling_station_count,

    -- PIR code mapping
    (
        SELECT STRING_AGG(PIRCode, ', ' ORDER BY PIRCode)
        FROM AddressPIRCodes apir
        WHERE apir.AddressID = a.ID
    ) AS pir_codes

FROM Address a
-- Join County
INNER JOIN County c ON a.County_ID = c.ID
-- Join Settlement
INNER JOIN Settlement s ON a.Settlement_ID = s.ID
-- Join National Electoral District (OEVK)
INNER JOIN NationalIndividualElectoralDistrict oevk ON a.NationalIndividualElectoralDistrict_ID = oevk.ID
-- Join Settlement Electoral District (TEVK)
INNER JOIN SettlementIndividualElectoralDistrict tevk ON a.SettlementIndividualElectoralDistrict_ID = tevk.ID
-- Join Polling Station
INNER JOIN PollingStation ps ON a.PollingStation_ID = ps.ID
-- Join Postal Code
INNER JOIN PostalCode pc ON a.PostalCode_ID = pc.ID;

-- Note: Views automatically use indexes from the underlying tables
-- The following tables already have appropriate indexes:
-- - County(CountyCode)
-- - Settlement(County_ID, SettlementCode)
-- - PostalCode(PostalCode)

-- Add comment to the view
COMMENT ON VIEW AddressFullView IS 'Denormalized view of addresses with all related entities joined. Column names use the new model naming convention as specified in FUNCTIONAL_REQUIREMENTS.md';
"""

    # Replace the placeholder with the custom Address table definition
    # This ensures Address table appears in the correct position (before AddressPollingStations)
    schema = schema.replace("%%ADDRESS_TABLE_PLACEHOLDER%%", custom_address_table)

    # Final cleanup: Remove staging tables and duplicate statements
    # Remove staging_oevk_json table (internal ETL artifact)
    schema = re.sub(
        r"-- Staging table for oevk JSON data.*?CREATE TABLE IF NOT EXISTS staging_oevk_json.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )

    # Remove duplicate extension creation statements (will be added by postgresql_indexes)
    # Keep only the first PostGIS extension at the top
    schema = re.sub(
        r"-- PostgreSQL-specific extensions\nCREATE EXTENSION IF NOT EXISTS pg_trgm;\nCREATE EXTENSION IF NOT EXISTS postgis;\n",
        "",
        schema,
    )

    # Remove any remaining orphaned index sections
    schema = re.sub(
        r"-- New indexes for public space tables.*?\n(?=CREATE INDEX|-- |$)",
        "",
        schema,
    )

    return schema + postgresql_indexes


def export_tables_to_csv(
    conn,
    output_dir: str,
    run_tag: str,
    formats: list = None,
    max_workers: int = 8,
):
    """Exports all target tables (except Address) to CSV files and optionally PostgreSQL SQL.

    Args:
        conn: An active DuckDB connection.
        output_dir: The directory to save CSV files.
        run_tag: The run tag to include in filenames.
        formats: List of export formats. Defaults to ["csv"]. Can include "csv" and/or "postgresql".
        max_workers: Maximum number of parallel workers (not currently used).
    """
    if formats is None:
        formats = ["csv"]

    logger.info(f"Exporting tables to {', '.join(formats)} in {output_dir}")

    # Create export directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # List of tables to export (excluding Address which gets special treatment)
    # Order matters for foreign key dependencies in PostgreSQL import
    tables = [
        "County",  # Base reference (no dependencies)
        "Settlement",  # Depends on County
        "NationalIndividualElectoralDistrict",  # Depends on County (OEVK)
        "SettlementIndividualElectoralDistrict",  # Depends on County, Settlement (TEVK)
        "PostalCode",  # Base reference (no dependencies)
        "PostalCode_Settlement",  # Junction table
        "PollingStation",  # Depends on multiple tables
        "PublicSpaceName",  # Base reference
        "PublicSpaceType",  # Base reference
        "SettlementPublicSpaces",  # Junction table
        "AddressPollingStations",  # Junction table
        "AddressPIRCodes",  # Junction table
        "CanonicalAddress",  # Deduplicated addresses (no FK constraints)
        "AddressMapping",  # Deduplication mapping
    ]

    # Handle CSV export
    if "csv" in formats:
        for table in tables:
            export_table_to_csv(conn, table, output_dir, run_tag)
        logger.info("CSV export completed")

    # Handle PostgreSQL export
    if "postgresql" in formats:
        logger.info("Generating PostgreSQL schema...")
        schema_sql = generate_postgresql_schema()
        schema_path = os.path.join(output_dir, "schema.sql")
        with open(schema_path, "w", encoding="utf-8") as f:
            f.write(schema_sql)
        logger.info(f"Schema written to {schema_path}")

        # Create postgresql directory for CSV files
        postgresql_dir = os.path.join(output_dir, "postgresql")
        os.makedirs(postgresql_dir, exist_ok=True)

        logger.info("Exporting PostgreSQL data to CSV files (fast COPY method)...")

        # For PostgreSQL export, exclude tables that are not needed:
        # - CanonicalAddress: exported separately as Address table
        # - AddressMapping: only needed for DuckDB deduplication
        # - AddressPollingStations: replaced by PollingStation_ID column in Address
        # - AddressPIRCodes: replaced by PIRCode column in Address
        postgresql_tables = [
            t
            for t in tables
            if t
            not in [
                "CanonicalAddress",
                "AddressMapping",
                "AddressPollingStations",
                "AddressPIRCodes",
            ]
        ]

        # Export tables to CSV
        csv_files = export_tables_to_postgresql_csv(
            conn, postgresql_dir, postgresql_tables
        )

        # Export CanonicalAddress as Address (the canonical address table for PostgreSQL)
        canonical_csv = export_canonical_address_to_csv(conn, postgresql_dir)
        csv_files["Address"] = canonical_csv

        # Generate optimized import script
        logger.info("Generating optimized PostgreSQL import script...")
        import_script_path = os.path.join(output_dir, "import_postgresql.sql")
        # Convert to absolute path for PostgreSQL COPY command
        postgresql_dir_abs = os.path.abspath(postgresql_dir)
        config = get_config()  # Get configuration for PostgreSQL settings
        generate_postgresql_import_script(
            import_script_path, postgresql_dir_abs, csv_files, config
        )

        logger.info(f"PostgreSQL CSV files written to {postgresql_dir}/")
        logger.info(f"Import script written to {import_script_path}")
        logger.info("To import: psql -U user -d dbname -f import_postgresql.sql")
        logger.info("PostgreSQL export completed")

        # NOTE: Legacy INSERT-based data.sql generation has been removed
        # The CSV-based import is 10-50x faster (2-5 min vs 30-120 min)
        # If you need INSERT statements, use: pg_dump after importing CSV data

    logger.info("Table export completed")


def export_table_to_csv(
    db_connection: duckdb.DuckDBPyConnection,
    table_name: str,
    export_dir: str,
    run_tag: str,
) -> None:
    """Exports a single table to CSV.

    Args:
        db_connection: An active DuckDB connection.
        table_name: Name of the table to export.
        export_dir: The directory to save the CSV file.
        run_tag: The run tag to include in filename.
    """
    filename = f"{run_tag}_{table_name}.csv"
    file_path = os.path.join(export_dir, filename)

    logger.info(f"Exporting {table_name} to {file_path}")

    # Export table to CSV
    db_connection.execute(f"""
        COPY {table_name} TO '{file_path}' (HEADER, DELIMITER ',')
    """)

    # Verify file was created
    if os.path.exists(file_path):
        logger.info(
            f"Successfully exported {table_name} ({os.path.getsize(file_path)} bytes)"
        )
    else:
        logger.error(f"Failed to export {table_name}")


def export_tables_to_postgresql_csv(
    db_connection: duckdb.DuckDBPyConnection, output_dir: str, tables: list
) -> dict:
    """Export tables to CSV files for PostgreSQL COPY command.

    Converts MD5 hex IDs to UUID5 format for PostgreSQL compatibility.
    Transforms column names from PascalCase to snake_case to match PostgreSQL schema.

    Args:
        db_connection: DuckDB connection
        output_dir: Directory to write CSV files
        tables: List of table names to export

    Returns:
        Dictionary mapping table names to CSV file paths
    """
    csv_files = {}

    # Create DuckDB UDF for UUID5 conversion
    db_connection.create_function("to_uuid5", to_uuid5, return_type="VARCHAR")

    # Helper function to convert column names to snake_case for PostgreSQL
    def to_postgres_column_name(col_name: str) -> str:
        """Convert DuckDB PascalCase column names to PostgreSQL snake_case."""
        # Special mappings for known columns
        mappings = {
            "ID": "id",
            "OEVK": "code",  # NationalIndividualElectoralDistrict
            "TEVK": "code",  # SettlementIndividualElectoralDistrict
            "PostalCode": "code",  # PostalCode table
            "PollingStationCode": "code",  # PollingStation table
            "PollingStationAddress": "address",
            "CountyCode": "code",
            "CountyName": "name",
            "SettlementCode": "code",
            "SettlementName": "name",
            "PublicSpaceName": "name",
            "PublicSpaceType": "name",
            "Center": "center_wkt",  # For PostGIS WKT format
            "Polygon": "polygon_wkt",  # For PostGIS WKT format
            "GeocodedAt": None,  # Remove this column
            "CreatedAt": None,  # Remove this column
        }

        if col_name in mappings:
            return mappings[col_name]

        # Apply general snake_case transformation
        return _to_snake_case(col_name)

    for table in tables:
        csv_path = os.path.join(output_dir, f"{table}.csv")
        logger.info(f"  Exporting {table} to CSV...")

        # Get PostGIS configuration for OEVK table
        config = get_config()
        use_postgis = config.get_postgresql_settings().get("use_postgis", True)

        # Get table columns to build SELECT with UUID conversion
        columns_result = db_connection.execute(f"DESCRIBE {table}").fetchall()
        columns = [col[0] for col in columns_result]

        # Build SELECT list with UUID5 conversion for ID columns and snake_case column names
        select_items = []
        for col in columns:
            # Get PostgreSQL column name
            pg_col = to_postgres_column_name(col)

            # Skip columns that should be removed (like GeocodedAt, CreatedAt)
            if pg_col is None:
                continue

            if col == "ID" or col.endswith("_ID"):
                # Convert ID columns to UUID5 with snake_case alias
                select_items.append(f"to_uuid5({col}) as {pg_col}")
            else:
                # Use snake_case alias for non-ID columns
                select_items.append(f"{col} as {pg_col}")

        select_clause = ", ".join(select_items)

        # Special handling for NationalIndividualElectoralDistrict with PostGIS
        if table == "NationalIndividualElectoralDistrict" and use_postgis:
            # Convert Center and Polygon to WKT format, IDs to UUID5, and use snake_case column names
            query = f"""
                SELECT
                    to_uuid5(ID) as id,
                    OEVK as code,
                    Name as name,
                    CASE
                        WHEN Center IS NOT NULL THEN
                            'POINT(' || split_part(Center, ' ', 2) || ' ' || split_part(Center, ' ', 1) || ')'
                        ELSE NULL
                    END as center_wkt,
                    CASE
                        WHEN Polygon IS NOT NULL THEN
                            -- Swap lat/lon to lon/lat and auto-close polygon if needed
                            CASE
                                -- Check if polygon is already closed (first coord == last coord)
                                WHEN split_part(Polygon, ',', 1) = split_part(Polygon, ',', -1) THEN
                                    'POLYGON((' || regexp_replace(Polygon, '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g') || '))'
                                ELSE
                                    -- Auto-close: append first coordinate to the end
                                    'POLYGON((' || regexp_replace(Polygon, '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g') || ',' ||
                                    split_part(regexp_replace(split_part(Polygon, ',', 1), '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g'), ' ', 1) || ' ' ||
                                    split_part(regexp_replace(split_part(Polygon, ',', 1), '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g'), ' ', 2) || '))'
                            END
                        ELSE NULL
                    END as polygon_wkt,
                    to_uuid5(County_ID) as county_id
                FROM NationalIndividualElectoralDistrict
            """
        # Special handling for junction tables - rename CanonicalAddressID to AddressID
        elif table == "AddressPollingStations":
            query = f"""
                SELECT
                    to_uuid5(ID) as ID,
                    to_uuid5(CanonicalAddressID) as AddressID,
                    to_uuid5(PollingStationID) as PollingStationID,
                    CreatedAt
                FROM AddressPollingStations
            """
        elif table == "AddressPIRCodes":
            query = f"""
                SELECT
                    to_uuid5(ID) as ID,
                    to_uuid5(CanonicalAddressID) as AddressID,
                    PIRCode,
                    CreatedAt
                FROM AddressPIRCodes
            """
        else:
            query = f"SELECT {select_clause} FROM {table}"

        # Export to CSV
        db_connection.execute(f"""
            COPY ({query}) TO '{csv_path}' (HEADER, DELIMITER ',', QUOTE '"')
        """)

        csv_files[table] = csv_path

        # Log row count
        row_count = db_connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        logger.info(f"    {table}: {row_count:,} rows")

    return csv_files


def export_canonical_address_to_csv(
    db_connection: duckdb.DuckDBPyConnection, output_dir: str
) -> str:
    """Export CanonicalAddress table to CSV as 'Address' for PostgreSQL.

    Converts MD5 hex IDs to UUID5 format for PostgreSQL compatibility.
    Uses batched processing with progress tracking for large datasets.

    Args:
        db_connection: DuckDB connection
        output_dir: Directory to write CSV file

    Returns:
        Path to CSV file
    """
    import csv
    import time

    csv_path = os.path.join(output_dir, "Address.csv")
    logger.info(
        "  Exporting CanonicalAddress to CSV as Address (with foreign keys and UUID5 conversion)..."
    )

    # Get total row count for progress tracking
    total_rows = db_connection.execute(
        "SELECT COUNT(*) FROM CanonicalAddress"
    ).fetchone()[0]
    logger.info(f"    Total addresses to export: {total_rows:,}")

    if total_rows == 0:
        # Create empty CSV with headers (PostgreSQL snake_case naming)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "house_number",
                    "building",
                    "staircase",
                    "full_address",
                    "latitude",
                    "longitude",
                    "geocoding_quality",
                    "geocoding_source",
                    "county_id",
                    "settlement_id",
                    "public_space_name_id",
                    "public_space_type_id",
                    "oevk_id",
                    "tevk_id",
                    "postal_code_id",
                    "polling_station_id",
                ]
            )
        logger.info(f"    Address (from CanonicalAddress): 0 rows")
        return csv_path

    start_time = time.time()

    # Fetch all data in single query WITHOUT UUID conversion (much faster)
    # We'll convert to UUID5 in Python which is faster than repeated SQL queries
    logger.info(f"    Fetching all {total_rows:,} addresses in single query...")
    fetch_start = time.time()

    result = db_connection.execute("""
        SELECT
            ca.ID,
            ca.HouseNumber,
            ca.Building,
            ca.Staircase,
            ca.FullAddress,
            ca.Latitude,
            ca.Longitude,
            ca.GeocodingQuality,
            ca.GeocodingSource,
            c.ID as County_ID,
            s.ID as Settlement_ID,
            psn.ID as PublicSpaceName_ID,
            pst.ID as PublicSpaceType_ID,
            oevk_fk.NationalIndividualElectoralDistrict_ID,
            tevk_fk.SettlementIndividualElectoralDistrict_ID,
            pc_fk.PostalCode_ID,
            ps_fk.PollingStationID as PollingStation_ID
        FROM CanonicalAddress ca
        LEFT JOIN County c ON ca.CountyCode = c.CountyCode
        LEFT JOIN Settlement s ON c.ID = s.County_ID AND ca.SettlementName = s.SettlementName
        -- Join to get public space foreign keys from original Address records
        LEFT JOIN (
            SELECT
                am.CanonicalAddressID,
                MIN(psn_inner.ID) as PublicSpaceName_ID
            FROM AddressMapping am
            INNER JOIN Address a ON am.OriginalAddressID = a.ID
            INNER JOIN PublicSpaceName psn_inner ON a.PublicSpaceName = psn_inner.PublicSpaceName
            GROUP BY am.CanonicalAddressID
        ) psn_map ON ca.ID = psn_map.CanonicalAddressID
        LEFT JOIN PublicSpaceName psn ON psn_map.PublicSpaceName_ID = psn.ID
        LEFT JOIN (
            SELECT
                am.CanonicalAddressID,
                MIN(pst_inner.ID) as PublicSpaceType_ID
            FROM AddressMapping am
            INNER JOIN Address a ON am.OriginalAddressID = a.ID
            INNER JOIN PublicSpaceType pst_inner ON a.PublicSpaceType = pst_inner.PublicSpaceType
            GROUP BY am.CanonicalAddressID
        ) pst_map ON ca.ID = pst_map.CanonicalAddressID
        LEFT JOIN PublicSpaceType pst ON pst_map.PublicSpaceType_ID = pst.ID
        -- Get OEVK, TEVK, and PostalCode from original Address records
        LEFT JOIN (
            SELECT
                am.CanonicalAddressID,
                MIN(a.NationalIndividualElectoralDistrict_ID) as NationalIndividualElectoralDistrict_ID
            FROM AddressMapping am
            INNER JOIN Address a ON am.OriginalAddressID = a.ID
            GROUP BY am.CanonicalAddressID
        ) oevk_fk ON ca.ID = oevk_fk.CanonicalAddressID
        LEFT JOIN (
            SELECT
                am.CanonicalAddressID,
                MIN(a.SettlementIndividualElectoralDistrict_ID) as SettlementIndividualElectoralDistrict_ID
            FROM AddressMapping am
            INNER JOIN Address a ON am.OriginalAddressID = a.ID
            GROUP BY am.CanonicalAddressID
        ) tevk_fk ON ca.ID = tevk_fk.CanonicalAddressID
        LEFT JOIN (
            SELECT
                am.CanonicalAddressID,
                MIN(a.PostalCode_ID) as PostalCode_ID
            FROM AddressMapping am
            INNER JOIN Address a ON am.OriginalAddressID = a.ID
            GROUP BY am.CanonicalAddressID
        ) pc_fk ON ca.ID = pc_fk.CanonicalAddressID
        -- Get PollingStation from junction table
        LEFT JOIN (
            SELECT CanonicalAddressID, MIN(PollingStationID) as PollingStationID
            FROM AddressPollingStations
            GROUP BY CanonicalAddressID
        ) ps_fk ON ca.ID = ps_fk.CanonicalAddressID
        WHERE c.ID IS NOT NULL
            AND s.ID IS NOT NULL
            AND psn_map.PublicSpaceName_ID IS NOT NULL
            AND pst_map.PublicSpaceType_ID IS NOT NULL
            AND oevk_fk.NationalIndividualElectoralDistrict_ID IS NOT NULL
            AND tevk_fk.SettlementIndividualElectoralDistrict_ID IS NOT NULL
            AND pc_fk.PostalCode_ID IS NOT NULL
            AND ps_fk.PollingStationID IS NOT NULL
    """).fetchall()

    fetch_time = time.time() - fetch_start
    logger.info(
        f"    Fetched {len(result):,} rows in {fetch_time:.1f}s ({len(result) / fetch_time:.0f} rows/s)"
    )

    # Write CSV with UUID conversion in Python (batched for progress tracking)
    logger.info(f"    Converting MD5 IDs to UUID5 and writing CSV...")
    write_start = time.time()
    batch_size = 100000
    processed = 0

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        # Write header (PostgreSQL snake_case naming)
        writer.writerow(
            [
                "id",
                "house_number",
                "building",
                "staircase",
                "full_address",
                "latitude",
                "longitude",
                "geocoding_quality",
                "geocoding_source",
                "county_id",
                "settlement_id",
                "public_space_name_id",
                "public_space_type_id",
                "oevk_id",
                "tevk_id",
                "postal_code_id",
                "polling_station_id",
            ]
        )

        # Process and write in batches
        for i in range(0, len(result), batch_size):
            batch_start = time.time()
            batch = result[i : i + batch_size]

            # Convert MD5 hex IDs to UUID5 in Python
            converted_batch = []
            for row in batch:
                converted_row = list(row)
                converted_row[0] = to_uuid5(row[0])  # ID
                converted_row[9] = to_uuid5(row[9])  # County_ID
                converted_row[10] = to_uuid5(row[10])  # Settlement_ID
                converted_row[11] = to_uuid5(row[11])  # PublicSpaceName_ID
                converted_row[12] = to_uuid5(row[12])  # PublicSpaceType_ID
                converted_row[13] = to_uuid5(
                    row[13]
                )  # NationalIndividualElectoralDistrict_ID
                converted_row[14] = to_uuid5(
                    row[14]
                )  # SettlementIndividualElectoralDistrict_ID
                converted_row[15] = to_uuid5(row[15])  # PostalCode_ID
                converted_row[16] = to_uuid5(row[16])  # PollingStation_ID
                converted_batch.append(converted_row)

            writer.writerows(converted_batch)

            processed += len(batch)
            batch_time = time.time() - batch_start
            elapsed = time.time() - write_start

            # Calculate ETA
            if processed > 0 and processed < len(result):
                rate = processed / elapsed
                remaining = len(result) - processed
                eta_seconds = remaining / rate if rate > 0 else 0

                if eta_seconds >= 60:
                    eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                else:
                    eta_str = f"{int(eta_seconds)}s"

                progress_pct = (processed / len(result)) * 100
                logger.info(
                    f"    [{processed:,}/{len(result):,}] {progress_pct:.1f}% | "
                    f"Converted {len(batch):,} rows in {batch_time:.1f}s | "
                    f"Rate: {rate:.0f} rows/s | ETA: {eta_str}"
                )

    write_time = time.time() - write_start
    total_time = time.time() - start_time
    logger.info(
        f"    Address (from CanonicalAddress): {len(result):,} rows exported in {total_time:.1f}s "
        f"(fetch: {fetch_time:.1f}s, write: {write_time:.1f}s)"
    )

    return csv_path


def count_csv_rows(csv_path: str) -> int:
    """Count number of rows in CSV file (excluding header)."""
    import csv

    with open(csv_path, "r", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # Exclude header


def generate_chunked_copy_commands(
    f,
    table: str,
    csv_path: str,
    csv_dir: str,
    csv_file: str,
    chunk_size: int,
    columns: str = None,
) -> None:
    """Generate COPY commands with chunking for large CSV files.

    Args:
        f: File handle to write to
        table: Table name
        csv_path: Full path to CSV file
        csv_dir: Directory containing CSV files
        csv_file: CSV filename
        chunk_size: Number of rows per chunk
        columns: Optional column list for COPY command
    """
    # Count rows in CSV
    row_count = count_csv_rows(csv_path)

    # If small enough, do single COPY
    if row_count <= chunk_size:
        if columns:
            f.write(
                f"\\copy {table} {columns} FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n"
            )
        else:
            f.write(
                f"\\copy {table} FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n"
            )
        return

    # For large files, split into chunks during export
    num_chunks = (row_count + chunk_size - 1) // chunk_size
    f.write(
        f"-- Large table with {row_count:,} rows, importing in {num_chunks} chunks of {chunk_size:,} rows\n"
    )

    logger.info(f"  Splitting {table} ({row_count:,} rows) into {num_chunks} chunks...")

    # Split CSV into chunks
    import csv as csv_module

    base_name = csv_file.replace(".csv", "")
    chunk_files = []
    output_dir = os.path.dirname(csv_path)

    with open(csv_path, "r", encoding="utf-8") as infile:
        reader = csv_module.reader(infile)
        header = next(reader)

        chunk_num = 1
        rows_in_chunk = 0
        chunk_file_handle = None
        writer = None

        for row in reader:
            if rows_in_chunk == 0:
                # Start new chunk
                chunk_filename = f"{base_name}_chunk{chunk_num:04d}.csv"
                chunk_path = os.path.join(output_dir, chunk_filename)
                chunk_file_handle = open(chunk_path, "w", encoding="utf-8", newline="")
                writer = csv_module.writer(chunk_file_handle)
                writer.writerow(header)
                chunk_files.append(chunk_filename)

            writer.writerow(row)
            rows_in_chunk += 1

            if rows_in_chunk >= chunk_size:
                chunk_file_handle.close()
                chunk_num += 1
                rows_in_chunk = 0

        # Close final chunk
        if chunk_file_handle and not chunk_file_handle.closed:
            chunk_file_handle.close()

    # Generate COPY command for each chunk
    for i, chunk_filename in enumerate(chunk_files, 1):
        progress_pct = (i / len(chunk_files)) * 100
        rows_imported = min(i * chunk_size, row_count)
        f.write(
            f"\\echo '[{i}/{len(chunk_files)}] {progress_pct:.1f}% - Importing {table}: {rows_imported:,}/{row_count:,} rows'\n"
        )
        if columns:
            f.write(
                f"\\copy {table} {columns} FROM '{csv_dir}/{chunk_filename}' WITH (FORMAT CSV, HEADER, NULL '');\n"
            )
        else:
            f.write(
                f"\\copy {table} FROM '{csv_dir}/{chunk_filename}' WITH (FORMAT CSV, HEADER, NULL '');\n"
            )


def generate_postgresql_import_script(
    script_path: str,
    csv_dir: str,
    csv_files: dict,
    config: Config,
    defer_foreign_keys: bool = True,
    chunk_size: int = 100000,
) -> None:
    """Generate optimized PostgreSQL import script using COPY command with chunking.

    Args:
        script_path: Path to write import script
        csv_dir: Directory containing CSV files
        csv_files: Dictionary mapping table names to CSV paths
        config: Configuration object
        defer_foreign_keys: If True, create foreign keys after data import for better performance
        chunk_size: Number of rows per chunk for large tables (default: 100000)
    """
    # Get geocoding PostGIS setting
    geocoding_use_postgis = config.get("geocoding", {}).get("use_postgis", True)
    use_postgis = config.get_postgresql_settings().get("use_postgis", True)

    with open(script_path, "w", encoding="utf-8") as f:
        f.write("-- PostgreSQL Optimized Import Script\n")
        f.write(
            "-- Uses \\copy command for fast data loading (10-50x faster than INSERT)\n"
        )
        f.write("-- \n")
        f.write("-- Prerequisites:\n")
        f.write("--   1. PostgreSQL database created\n")
        f.write(
            "--   2. PostGIS extension enabled: CREATE EXTENSION IF NOT EXISTS postgis;\n"
        )
        f.write("--   3. Schema created: Run schema.sql first\n")
        f.write("--\n")
        f.write("-- Usage: psql -U username -d database -f import_postgresql.sql\n")
        f.write("--\n")
        f.write(
            "-- Expected import time: 2-5 minutes (vs 30-120 minutes with INSERT)\n"
        )
        f.write("--\n")
        f.write(
            "-- Note: PostGIS geometries are imported as WKT text then converted to GEOMETRY types\n"
        )
        f.write("--\n\n")

        # Performance optimizations (session-level settings only)
        f.write("-- Step 1: Performance optimizations for bulk import\n")
        f.write("SET maintenance_work_mem = '1GB';\n")
        f.write(
            "SET synchronous_commit = off;  -- Faster, but risk of data loss on crash\n"
        )
        f.write(
            "-- Note: checkpoint_completion_target requires server-level configuration\n"
        )
        f.write("\\timing on\n")
        f.write("\n")

        # Start transaction
        f.write("-- Step 2: Begin transaction\n")
        f.write("BEGIN;\n\n")

        # Drop foreign keys for faster import
        if defer_foreign_keys:
            f.write("-- Step 2.5: Drop foreign key constraints for faster import\n")
            f.write("-- Foreign keys will be recreated after data import\n")
            f.write("\\echo 'Dropping foreign key constraints...'\n")

            # Drop FKs from address table (PostgreSQL snake_case naming)
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_county_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_settlement_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_public_space_name_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_public_space_type_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_oevk_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_tevk_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_postal_code_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE address DROP CONSTRAINT IF EXISTS address_polling_station_id_fkey;\n"
            )

            # Drop FKs from other tables (PostgreSQL snake_case naming)
            f.write(
                "ALTER TABLE settlement DROP CONSTRAINT IF EXISTS settlement_county_id_fkey;\n"
            )
            f.write("ALTER TABLE oevk DROP CONSTRAINT IF EXISTS oevk_county_id_fkey;\n")
            f.write("ALTER TABLE tevk DROP CONSTRAINT IF EXISTS tevk_county_id_fkey;\n")
            f.write(
                "ALTER TABLE tevk DROP CONSTRAINT IF EXISTS tevk_settlement_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE polling_station DROP CONSTRAINT IF EXISTS polling_station_county_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE polling_station DROP CONSTRAINT IF EXISTS polling_station_settlement_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE polling_station DROP CONSTRAINT IF EXISTS polling_station_tevk_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE polling_station DROP CONSTRAINT IF EXISTS polling_station_oevk_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE postal_code_settlement DROP CONSTRAINT IF EXISTS postal_code_settlement_postal_code_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE postal_code_settlement DROP CONSTRAINT IF EXISTS postal_code_settlement_settlement_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE settlement_public_spaces DROP CONSTRAINT IF EXISTS settlement_public_spaces_settlement_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE settlement_public_spaces DROP CONSTRAINT IF EXISTS settlement_public_spaces_public_space_name_id_fkey;\n"
            )
            f.write(
                "ALTER TABLE settlement_public_spaces DROP CONSTRAINT IF EXISTS settlement_public_spaces_public_space_type_id_fkey;\n"
            )
            f.write("\n")

        # Placeholder records removed - database verification shows no NULL or invalid foreign keys

        # Define import order (respecting foreign key dependencies)
        import_order = [
            "County",
            "Settlement",
            "NationalIndividualElectoralDistrict",
            "SettlementIndividualElectoralDistrict",
            "PostalCode",
            "PostalCode_Settlement",
            "PublicSpaceName",
            "PublicSpaceType",
            "SettlementPublicSpaces",
            "PollingStation",
            "Address",  # CanonicalAddress with PollingStation_ID and PIRCode columns
        ]

        # COPY commands for each table
        f.write("-- Step 4: Import data using COPY (fast!)\n")
        f.write("\\echo 'Importing data...'\n\n")

        for duckdb_table in import_order:
            if duckdb_table in csv_files:
                csv_file = os.path.basename(csv_files[duckdb_table])
                # Get PostgreSQL table name
                pg_table = DUCKDB_TO_POSTGRESQL_TABLE_NAMES.get(
                    duckdb_table, duckdb_table.lower()
                )

                # Special handling for PostGIS geometry columns
                if (
                    duckdb_table == "NationalIndividualElectoralDistrict"
                    and use_postgis
                ):
                    f.write(
                        f"\\echo 'Importing {pg_table} with PostGIS geometries...'\n"
                    )
                    # Add temporary TEXT columns for WKT import (PostgreSQL snake_case)
                    f.write(
                        f"ALTER TABLE {pg_table} ADD COLUMN IF NOT EXISTS center_wkt TEXT;\n"
                    )
                    f.write(
                        f"ALTER TABLE {pg_table} ADD COLUMN IF NOT EXISTS polygon_wkt TEXT;\n"
                    )
                    # Import with temp columns (PostgreSQL snake_case)
                    f.write(
                        f"\\copy {pg_table} (id, code, name, center_wkt, polygon_wkt, county_id) FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n"
                    )
                    # Convert WKT to GEOMETRY - center points are usually valid
                    f.write(
                        f"UPDATE {pg_table} SET center = ST_GeomFromText(center_wkt, 4326) WHERE center_wkt IS NOT NULL AND center_wkt != '';\n"
                    )
                    # For polygons, try to fix with ST_MakeValid, skip if completely invalid
                    # This updates row-by-row to avoid transaction abort on invalid geometries
                    f.write(f"DO $$\n")
                    f.write(f"DECLARE\n")
                    f.write(f"  r RECORD;\n")
                    f.write(f"BEGIN\n")
                    f.write(
                        f"  FOR r IN SELECT id, polygon_wkt FROM {pg_table} WHERE polygon_wkt IS NOT NULL AND polygon_wkt != '' LOOP\n"
                    )
                    f.write(f"    BEGIN\n")
                    f.write(
                        f"      UPDATE {pg_table} SET polygon = ST_MakeValid(ST_GeomFromText(r.polygon_wkt, 4326)) WHERE id = r.id;\n"
                    )
                    f.write(f"    EXCEPTION WHEN OTHERS THEN\n")
                    f.write(f"      -- Skip invalid geometries that can't be fixed\n")
                    f.write(
                        f"      RAISE NOTICE 'Skipping invalid polygon for id %', r.id;\n"
                    )
                    f.write(f"    END;\n")
                    f.write(f"  END LOOP;\n")
                    f.write(f"END $$;\n")
                    # Drop temporary columns
                    f.write(f"ALTER TABLE {pg_table} DROP COLUMN center_wkt;\n")
                    f.write(f"ALTER TABLE {pg_table} DROP COLUMN polygon_wkt;\n")
                # Special handling for address table - has geometry column added via ALTER TABLE
                elif duckdb_table == "Address":
                    f.write(f"\\echo 'Importing {pg_table}...'\n")
                    # Use chunked import for large table (PostgreSQL snake_case naming)
                    csv_path = csv_files[duckdb_table]
                    columns = "(id, house_number, building, staircase, full_address, latitude, longitude, geocoding_quality, geocoding_source, county_id, settlement_id, public_space_name_id, public_space_type_id, oevk_id, tevk_id, postal_code_id, polling_station_id)"
                    generate_chunked_copy_commands(
                        f, pg_table, csv_path, csv_dir, csv_file, chunk_size, columns
                    )
                # Special handling for polling_station - also has geometry column
                elif duckdb_table == "PollingStation":
                    f.write(f"\\echo 'Importing {pg_table}...'\n")
                    # PostgreSQL snake_case naming
                    f.write(
                        f"\\copy {pg_table} (id, code, address, tevk_id, county_id, settlement_id, oevk_id, latitude, longitude, geocoding_quality, geocoding_source, matched_address) FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n"
                    )
                else:
                    f.write(f"\\echo 'Importing {pg_table}...'\n")
                    # Use chunked import for all tables
                    csv_path = csv_files[duckdb_table]
                    generate_chunked_copy_commands(
                        f,
                        pg_table,
                        csv_path,
                        csv_dir,
                        csv_file,
                        chunk_size,
                        columns=None,
                    )

                f.write("\n")

        # Populate PostGIS GEOGRAPHY columns for geocoding (chunked for better performance)
        if geocoding_use_postgis:
            f.write(
                "-- Step 5: Populate PostGIS GEOGRAPHY columns from geocoding coordinates\n"
            )
            f.write(
                "-- Using chunked updates with ST_SetSRID + ST_MakePoint for better performance\n"
            )
            f.write(
                "-- Committing transaction before geometry updates to avoid long locks\n"
            )
            f.write("COMMIT;\n\n")

            # Chunked update for address table (100k rows per chunk)
            postgis_chunk_size = 100000
            f.write(
                f"-- Update address.geometry in chunks of {postgis_chunk_size:,} rows\n"
            )
            f.write(
                "\\echo 'Populating PostGIS GEOGRAPHY for address table in chunks...'\n"
            )
            f.write("DO $$\n")
            f.write("DECLARE\n")
            f.write("    batch_size INT := 100000;\n")
            f.write("    total_updated BIGINT := 0;\n")
            f.write("    rows_updated INT;\n")
            f.write("BEGIN\n")
            f.write("    LOOP\n")
            f.write("        UPDATE address\n")
            f.write(
                "        SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography\n"
            )
            f.write("        WHERE geometry IS NULL\n")
            f.write("          AND latitude IS NOT NULL\n")
            f.write("          AND longitude IS NOT NULL\n")
            f.write("          AND id IN (\n")
            f.write("              SELECT id FROM address\n")
            f.write("              WHERE geometry IS NULL\n")
            f.write("                AND latitude IS NOT NULL\n")
            f.write("                AND longitude IS NOT NULL\n")
            f.write("              LIMIT batch_size\n")
            f.write("          );\n")
            f.write("        GET DIAGNOSTICS rows_updated = ROW_COUNT;\n")
            f.write("        total_updated := total_updated + rows_updated;\n")
            f.write(
                "        RAISE NOTICE 'Updated % addresses (total: %)', rows_updated, total_updated;\n"
            )
            f.write("        EXIT WHEN rows_updated = 0;\n")
            f.write("        COMMIT;\n")
            f.write("    END LOOP;\n")
            f.write(
                "    RAISE NOTICE 'Completed: % addresses updated with PostGIS geometry', total_updated;\n"
            )
            f.write("END $$;\n\n")

            f.write(
                "\\echo 'Populating PostGIS GEOGRAPHY columns for polling_station...'\n"
            )
            f.write("UPDATE polling_station\n")
            f.write(
                "SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography\n"
            )
            f.write("WHERE latitude IS NOT NULL AND longitude IS NOT NULL;\n\n")

            f.write("-- Begin new transaction for remaining operations\n")
            f.write("BEGIN;\n\n")

        # Recreate foreign keys after data import
        if defer_foreign_keys:
            f.write(
                "-- Step 5.5: Recreate foreign key constraints (deferred for performance)\n"
            )
            f.write("\\echo 'Recreating foreign key constraints...'\n")

            # address table FKs (PostgreSQL snake_case naming)
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_county_id_fkey FOREIGN KEY (county_id) REFERENCES county(id);\n"
            )
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_settlement_id_fkey FOREIGN KEY (settlement_id) REFERENCES settlement(id);\n"
            )
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_public_space_name_id_fkey FOREIGN KEY (public_space_name_id) REFERENCES public_space_name(id);\n"
            )
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_public_space_type_id_fkey FOREIGN KEY (public_space_type_id) REFERENCES public_space_type(id);\n"
            )
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_oevk_id_fkey FOREIGN KEY (oevk_id) REFERENCES oevk(id);\n"
            )
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_tevk_id_fkey FOREIGN KEY (tevk_id) REFERENCES tevk(id);\n"
            )
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_postal_code_id_fkey FOREIGN KEY (postal_code_id) REFERENCES postal_code(id);\n"
            )
            f.write(
                "ALTER TABLE address ADD CONSTRAINT address_polling_station_id_fkey FOREIGN KEY (polling_station_id) REFERENCES polling_station(id);\n"
            )

            # Reference tables FKs (PostgreSQL snake_case naming)
            f.write(
                "ALTER TABLE settlement ADD CONSTRAINT settlement_county_id_fkey FOREIGN KEY (county_id) REFERENCES county(id);\n"
            )
            f.write(
                "ALTER TABLE oevk ADD CONSTRAINT oevk_county_id_fkey FOREIGN KEY (county_id) REFERENCES county(id);\n"
            )
            f.write(
                "ALTER TABLE tevk ADD CONSTRAINT tevk_county_id_fkey FOREIGN KEY (county_id) REFERENCES county(id);\n"
            )
            f.write(
                "ALTER TABLE tevk ADD CONSTRAINT tevk_settlement_id_fkey FOREIGN KEY (settlement_id) REFERENCES settlement(id);\n"
            )
            f.write(
                "ALTER TABLE polling_station ADD CONSTRAINT polling_station_county_id_fkey FOREIGN KEY (county_id) REFERENCES county(id);\n"
            )
            f.write(
                "ALTER TABLE polling_station ADD CONSTRAINT polling_station_settlement_id_fkey FOREIGN KEY (settlement_id) REFERENCES settlement(id);\n"
            )
            f.write(
                "ALTER TABLE polling_station ADD CONSTRAINT polling_station_tevk_id_fkey FOREIGN KEY (tevk_id) REFERENCES tevk(id);\n"
            )
            f.write(
                "ALTER TABLE polling_station ADD CONSTRAINT polling_station_oevk_id_fkey FOREIGN KEY (oevk_id) REFERENCES oevk(id);\n"
            )
            f.write(
                "ALTER TABLE postal_code_settlement ADD CONSTRAINT postal_code_settlement_postal_code_id_fkey FOREIGN KEY (postal_code_id) REFERENCES postal_code(id);\n"
            )
            f.write(
                "ALTER TABLE postal_code_settlement ADD CONSTRAINT postal_code_settlement_settlement_id_fkey FOREIGN KEY (settlement_id) REFERENCES settlement(id);\n"
            )
            f.write(
                "ALTER TABLE settlement_public_spaces ADD CONSTRAINT settlement_public_spaces_settlement_id_fkey FOREIGN KEY (settlement_id) REFERENCES settlement(id);\n"
            )
            f.write(
                "ALTER TABLE settlement_public_spaces ADD CONSTRAINT settlement_public_spaces_public_space_name_id_fkey FOREIGN KEY (public_space_name_id) REFERENCES public_space_name(id);\n"
            )
            f.write(
                "ALTER TABLE settlement_public_spaces ADD CONSTRAINT settlement_public_spaces_public_space_type_id_fkey FOREIGN KEY (public_space_type_id) REFERENCES public_space_type(id);\n"
            )
            f.write("\n")

        # Commit transaction
        f.write("-- Step 6: Commit transaction\n")
        f.write("COMMIT;\n\n")

        # Analyze tables (using PostgreSQL snake_case names)
        f.write("-- Step 7: Analyze tables for query optimization\n")
        f.write("\\echo 'Analyzing tables...'\n")
        for duckdb_table in import_order:
            if duckdb_table in csv_files:
                pg_table = DUCKDB_TO_POSTGRESQL_TABLE_NAMES.get(
                    duckdb_table, duckdb_table.lower()
                )
                f.write(f"ANALYZE {pg_table};\n")
        f.write("\n")

        # Summary
        f.write("-- Import complete!\n")
        f.write(
            "\\echo 'Import complete! Run SELECT COUNT(*) FROM address; to verify.'\n"
        )


def export_canonical_address_to_postgresql(
    db_connection: duckdb.DuckDBPyConnection,
    output_file,
) -> None:
    """Exports CanonicalAddress table with geocoding data to PostgreSQL INSERT statements.

    Converts xxhash64 ID values to UUID v3 format and includes geocoding metadata.
    CanonicalAddress is exported as "Address" table in PostgreSQL (renamed for clarity).

    Args:
        db_connection: An active DuckDB connection.
        output_file: File handle to write INSERT statements to.
    """
    table_name = "CanonicalAddress"

    # Get column names from CanonicalAddress
    schema_info = db_connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = [col[1] for col in schema_info]

    # Identify ID column (primary key)
    id_columns = {"ID"}

    # Fetch all rows
    rows = db_connection.execute(f"SELECT * FROM {table_name}").fetchall()

    if not rows:
        output_file.write(f"-- Table {table_name} is empty\n\n")
        return

    output_file.write(f"-- Table: Address (exported from CanonicalAddress)\n")
    output_file.write(f"-- Rows: {len(rows)}\n")
    output_file.write(
        "-- Includes geocoding data (Latitude, Longitude, GeocodingQuality, etc.)\n\n"
    )

    # Generate INSERT statements
    for row in rows:
        values = []
        for i, value in enumerate(row):
            col_name = columns[i]

            # Convert ID column to UUID
            if col_name in id_columns:
                uuid_value = to_uuid3(value)
                if uuid_value is None:
                    values.append("NULL")
                else:
                    values.append(f"'{uuid_value}'")
            elif value is None:
                values.append("NULL")
            elif isinstance(value, str):
                # Escape single quotes for SQL
                escaped_value = value.replace("'", "''")
                values.append(f"'{escaped_value}'")
            elif isinstance(value, (int, float)):
                values.append(str(value))
            else:
                # For other types, convert to string and escape
                escaped_value = str(value).replace("'", "''")
                values.append(f"'{escaped_value}'")

        columns_str = ", ".join(columns)
        values_str = ", ".join(values)
        # Use "Address" as the table name in PostgreSQL (CanonicalAddress is renamed)
        output_file.write(
            f"INSERT INTO Address ({columns_str}) VALUES ({values_str}) ON CONFLICT DO NOTHING;\n"
        )

    output_file.write("\n")


def export_table_to_postgresql(
    db_connection: duckdb.DuckDBPyConnection,
    table_name: str,
    output_file,
) -> None:
    """Exports a single table to PostgreSQL INSERT statements.

    Converts xxhash64 ID values to UUID v3 format.
    For NationalIndividualElectoralDistrict table, converts Center and Polygon
    to PostGIS GEOMETRY format if POSTGRESQL_USE_POSTGIS is enabled.

    Args:
        db_connection: An active DuckDB connection.
        table_name: Name of the table to export.
        output_file: File handle to write INSERT statements to.
    """
    # Get PostGIS configuration
    config = get_config()
    use_postgis = config.get_postgresql_settings().get("use_postgis", True)

    # Get column names and types
    schema_info = db_connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = [col[1] for col in schema_info]  # col[1] is the column name

    # Identify ID columns that need UUID conversion
    id_columns = set()
    for col_name in columns:
        if col_name == "ID" or col_name.endswith("_ID"):
            id_columns.add(col_name)

    # Check if this is the OEVK table with geospatial data
    is_oevk_table = table_name == "NationalIndividualElectoralDistrict"
    center_idx = columns.index("Center") if "Center" in columns else -1
    polygon_idx = columns.index("Polygon") if "Polygon" in columns else -1

    # Fetch all rows
    rows = db_connection.execute(f"SELECT * FROM {table_name}").fetchall()

    if not rows:
        output_file.write(f"-- Table {table_name} is empty\n\n")
        return

    output_file.write(f"-- Table: {table_name}\n")
    output_file.write(f"-- Rows: {len(rows)}\n")
    if is_oevk_table and use_postgis:
        output_file.write("-- PostGIS: Enabled (Center and Polygon as GEOMETRY)\n")
    elif is_oevk_table:
        output_file.write("-- PostGIS: Disabled (Center and Polygon as TEXT)\n")

    # Generate INSERT statements
    for row in rows:
        values = []
        for i, value in enumerate(row):
            col_name = columns[i]

            # Handle PostGIS conversion for OEVK Center and Polygon
            if is_oevk_table and use_postgis and i == center_idx:
                # Convert Center to PostGIS POINT
                wkt = convert_center_to_point(value)
                if wkt:
                    values.append(f"ST_GeomFromText('{wkt}', 4326)")
                else:
                    values.append("NULL")
            elif is_oevk_table and use_postgis and i == polygon_idx:
                # Convert Polygon to PostGIS POLYGON
                wkt = convert_polygon_to_wkt(value)
                if wkt:
                    values.append(f"ST_GeomFromText('{wkt}', 4326)")
                else:
                    values.append("NULL")
            # Convert ID columns to UUID
            elif col_name in id_columns:
                uuid_value = to_uuid3(value)
                if uuid_value is None:
                    values.append("NULL")
                else:
                    values.append(f"'{uuid_value}'")
            elif value is None:
                values.append("NULL")
            elif isinstance(value, str):
                # Escape single quotes for SQL
                escaped_value = value.replace("'", "''")
                values.append(f"'{escaped_value}'")
            elif isinstance(value, (int, float)):
                values.append(str(value))
            else:
                # For other types, convert to string and escape
                escaped_value = str(value).replace("'", "''")
                values.append(f"'{escaped_value}'")

        columns_str = ", ".join(columns)
        values_str = ", ".join(values)
        output_file.write(
            f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str}) ON CONFLICT DO NOTHING;\n"
        )

    output_file.write("\n")


def export_addresses_partitioned(
    db_connection: duckdb.DuckDBPyConnection, export_dir: str, run_tag: str
) -> None:
    """Exports Address table partitioned by Settlement with canonical formatted addresses.

    Uses UUID v3 with 'oevk' namespace for all IDs.

    Args:
        db_connection: An active DuckDB connection.
        export_dir: The directory to save partitioned CSV files.
        run_tag: The run tag to include in directory name.
    """
    logger.info(f"Exporting addresses partitioned by settlement to {export_dir}")

    # Create Address directory
    address_dir = os.path.join(export_dir, f"{run_tag}_Address")
    os.makedirs(address_dir, exist_ok=True)

    # Create UDF for UUID v3 generation using MD5 hash
    # UUID v3 = MD5(namespace + name) formatted as UUID
    oevk_namespace_str = str(OEVK_NAMESPACE)
    db_connection.execute(f"""
        CREATE OR REPLACE MACRO uuid3_oevk(name) AS (
            CASE
                WHEN name IS NULL THEN NULL
                ELSE CAST(
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 1, 8) || '-' ||
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 9, 4) || '-' ||
                    '3' || substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 14, 3) || '-' ||
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 17, 4) || '-' ||
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 21, 12)
                AS VARCHAR)
            END
        );
    """)

    # Get unique settlements
    settlements = db_connection.execute("""
        SELECT DISTINCT s.ID, s.SettlementName, s.SettlementCode
        FROM Settlement s
        JOIN Address a ON s.ID = a.Settlement_ID
    """).fetchall()

    logger.info(f"Found {len(settlements)} settlements with addresses")

    for settlement_id, settlement_name, settlement_code in settlements:
        # Create filename-safe settlement identifier
        safe_name = settlement_name.replace("/", "_").replace("\\", "_")
        filename = f"OriginalAddress_{settlement_code}_{safe_name}.csv"
        file_path = os.path.join(address_dir, filename)

        logger.info(
            f"Exporting original addresses for {settlement_name} to {file_path}"
        )

        # Export addresses for this settlement with canonical formatted addresses
        db_connection.execute(f"""
            COPY (
                SELECT
                    uuid3_oevk(a.ID) as ID,
                    a.Sequence,
                    a.OriginalOrder,
                    COALESCE(ca.FullAddress, a.FullAddress) as FullAddress,
                    a.PublicSpaceName,
                    a.PublicSpaceType,
                    a.HouseNumber,
                    a.Building,
                    a.Staircase,
                    uuid3_oevk(a.PostalCode_ID) as PostalCode_ID,
                    uuid3_oevk(a.PollingStation_ID) as PollingStation_ID,
                    uuid3_oevk(a.SettlementIndividualElectoralDistrict_ID) as SettlementIndividualElectoralDistrict_ID,
                    uuid3_oevk(a.County_ID) as County_ID,
                    uuid3_oevk(a.Settlement_ID) as Settlement_ID,
                    uuid3_oevk(a.NationalIndividualElectoralDistrict_ID) as NationalIndividualElectoralDistrict_ID,
                    uuid3_oevk(am.CanonicalAddressID) as CanonicalAddress_ID
                FROM Address a
                LEFT JOIN AddressMapping am ON a.ID = am.OriginalAddressID
                LEFT JOIN CanonicalAddress ca ON am.CanonicalAddressID = ca.ID
                WHERE a.Settlement_ID = '{settlement_id}'
                ORDER BY a.Sequence
            ) TO '{file_path}' (HEADER, DELIMITER ',')
        """)

        # Verify file was created
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logger.info(
                f"Successfully exported {settlement_name} addresses ({file_size} bytes)"
            )
        else:
            logger.error(f"Failed to export addresses for {settlement_name}")

    # Also export a consolidated Address.csv file with canonical addresses
    consolidated_path = os.path.join(export_dir, f"{run_tag}_Address.csv")
    logger.info(f"Exporting consolidated addresses to {consolidated_path}")

    db_connection.execute(f"""
        COPY (
            SELECT
                uuid3_oevk(a.ID) as ID,
                a.Sequence,
                a.OriginalOrder,
                COALESCE(ca.FullAddress, a.FullAddress) as FullAddress,
                a.PublicSpaceName,
                a.PublicSpaceType,
                a.HouseNumber,
                a.Building,
                a.Staircase,
                uuid3_oevk(a.PostalCode_ID) as PostalCode_ID,
                uuid3_oevk(a.PollingStation_ID) as PollingStation_ID,
                uuid3_oevk(a.SettlementIndividualElectoralDistrict_ID) as SettlementIndividualElectoralDistrict_ID,
                uuid3_oevk(a.County_ID) as County_ID,
                uuid3_oevk(a.Settlement_ID) as Settlement_ID,
                uuid3_oevk(a.NationalIndividualElectoralDistrict_ID) as NationalIndividualElectoralDistrict_ID,
                uuid3_oevk(am.CanonicalAddressID) as CanonicalAddress_ID
            FROM Address a
            LEFT JOIN AddressMapping am ON a.ID = am.OriginalAddressID
            LEFT JOIN CanonicalAddress ca ON am.CanonicalAddressID = ca.ID
            ORDER BY a.Sequence
        ) TO '{consolidated_path}' (HEADER, DELIMITER ',')
    """)

    if os.path.exists(consolidated_path):
        logger.info(
            f"Successfully exported consolidated addresses ({os.path.getsize(consolidated_path)} bytes)"
        )
    else:
        logger.error("Failed to export consolidated addresses")

    logger.info("Address export completed")


def export_canonical_addresses(
    db_connection: duckdb.DuckDBPyConnection, export_dir: str, run_tag: str
) -> None:
    """Exports ONLY canonical (deduplicated) addresses partitioned by settlement.

    Exports unique canonical addresses instead of all original duplicates.
    Aggregates relationships (polling stations, PIR codes) from all original
    addresses that map to each canonical address.

    Uses UUID v3 with 'oevk' namespace for all IDs, and formats reference lists
    without brackets for clean CSV output.

    Creates partitioned exports:
    - Address_{settlement_code}_{settlement_name}.csv (deduplicated per settlement)
    - {run_tag}_CanonicalAddress.csv (consolidated)

    Args:
        db_connection: An active DuckDB connection.
        export_dir: The directory to save CSV files (same as OriginalAddress).
        run_tag: The run tag to include in filenames.
    """
    logger.info(f"Exporting canonical (deduplicated) addresses to {export_dir}")

    # Create Address directory (same as OriginalAddress)
    address_dir = os.path.join(export_dir, f"{run_tag}_Address")
    os.makedirs(address_dir, exist_ok=True)

    # Create UDF for UUID v3 generation using MD5 hash
    # UUID v3 = MD5(namespace + name) formatted as UUID
    oevk_namespace_str = str(OEVK_NAMESPACE)
    db_connection.execute(f"""
        CREATE OR REPLACE MACRO uuid3_oevk(name) AS (
            CASE
                WHEN name IS NULL THEN NULL
                ELSE CAST(
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 1, 8) || '-' ||
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 9, 4) || '-' ||
                    '3' || substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 14, 3) || '-' ||
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 17, 4) || '-' ||
                    substr(md5('{oevk_namespace_str}' || CAST(name AS VARCHAR)), 21, 12)
                AS VARCHAR)
            END
        );
    """)

    # Get settlements with canonical addresses
    settlements = db_connection.execute("""
        SELECT DISTINCT s.SettlementCode, s.SettlementName
        FROM Settlement s
        JOIN CanonicalAddress ca ON s.SettlementName = ca.SettlementName
        ORDER BY s.SettlementCode, s.SettlementName
    """).fetchall()

    logger.info(f"Found {len(settlements)} settlements with canonical addresses")

    # Export canonical addresses partitioned by settlement
    for settlement_code, settlement_name in settlements:
        # Create filename-safe settlement identifier
        safe_name = settlement_name.replace("/", "_").replace("\\", "_")
        filename = f"Address_{settlement_code}_{safe_name}.csv"
        file_path = os.path.join(address_dir, filename)

        logger.info(
            f"Exporting canonical addresses for {settlement_name} to {file_path}"
        )

        db_connection.execute(f"""
            COPY (
                SELECT
                    uuid3_oevk(ca.ID) as CanonicalAddressID,
                    ca.CountyCode,
                    ca.SettlementName,
                    ca.FullAddress,
                    ca.StreetName,
                    ca.HouseNumber,
                    ca.AccessibilityFlag,
                    ca.Latitude,
                    ca.Longitude,
                    ca.GeocodingQuality,
                    ca.GeocodingSource,
                    ca.GeocodedAt,
                    ca.CreatedAt,
                    CASE
                        WHEN COUNT(DISTINCT aps.PollingStationID) > 0
                        THEN ARRAY_TO_STRING(LIST(DISTINCT uuid3_oevk(aps.PollingStationID)), ',')
                        ELSE NULL
                    END as PollingStationIDs,
                    CASE
                        WHEN COUNT(DISTINCT apc.PIRCode) > 0
                        THEN ARRAY_TO_STRING(LIST(DISTINCT uuid3_oevk(apc.PIRCode)), ',')
                        ELSE NULL
                    END as PIRCodes,
                    COUNT(DISTINCT am.OriginalAddressID) as OriginalAddressCount
                FROM CanonicalAddress ca
                LEFT JOIN AddressMapping am ON ca.ID = am.CanonicalAddressID
                LEFT JOIN AddressPollingStations aps ON ca.ID = aps.CanonicalAddressID
                LEFT JOIN AddressPIRCodes apc ON ca.ID = apc.CanonicalAddressID
                WHERE ca.SettlementName = '{settlement_name}'
                GROUP BY ca.ID, ca.CountyCode, ca.SettlementName, ca.FullAddress,
                         ca.StreetName, ca.HouseNumber, ca.AccessibilityFlag,
                         ca.Latitude, ca.Longitude, ca.GeocodingQuality, ca.GeocodingSource, ca.GeocodedAt, ca.CreatedAt
                ORDER BY ca.FullAddress
            ) TO '{file_path}' (HEADER, DELIMITER ',')
        """)

        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logger.info(f"Successfully exported {settlement_name} ({file_size} bytes)")
        else:
            logger.error(f"Failed to export {settlement_name}")

    # Also export consolidated canonical addresses
    consolidated_path = os.path.join(export_dir, f"{run_tag}_CanonicalAddress.csv")
    logger.info(f"Exporting consolidated canonical addresses to {consolidated_path}")

    db_connection.execute(f"""
        COPY (
            SELECT
                uuid3_oevk(ca.ID) as CanonicalAddressID,
                ca.CountyCode,
                ca.SettlementName,
                ca.FullAddress,
                ca.StreetName,
                ca.HouseNumber,
                ca.AccessibilityFlag,
                ca.Latitude,
                ca.Longitude,
                ca.GeocodingQuality,
                ca.GeocodingSource,
                ca.GeocodedAt,
                ca.CreatedAt,
                CASE
                    WHEN COUNT(DISTINCT aps.PollingStationID) > 0
                    THEN ARRAY_TO_STRING(LIST(DISTINCT uuid3_oevk(aps.PollingStationID)), ',')
                    ELSE NULL
                END as PollingStationIDs,
                CASE
                    WHEN COUNT(DISTINCT apc.PIRCode) > 0
                    THEN ARRAY_TO_STRING(LIST(DISTINCT uuid3_oevk(apc.PIRCode)), ',')
                    ELSE NULL
                END as PIRCodes,
                COUNT(DISTINCT am.OriginalAddressID) as OriginalAddressCount
            FROM CanonicalAddress ca
            LEFT JOIN AddressMapping am ON ca.ID = am.CanonicalAddressID
            LEFT JOIN AddressPollingStations aps ON ca.ID = aps.CanonicalAddressID
            LEFT JOIN AddressPIRCodes apc ON ca.ID = apc.CanonicalAddressID
            GROUP BY ca.ID, ca.CountyCode, ca.SettlementName, ca.FullAddress,
                     ca.StreetName, ca.HouseNumber, ca.AccessibilityFlag,
                     ca.Latitude, ca.Longitude, ca.GeocodingQuality, ca.GeocodingSource, ca.GeocodedAt, ca.CreatedAt
            ORDER BY ca.CountyCode, ca.SettlementName, ca.FullAddress
        ) TO '{consolidated_path}' (HEADER, DELIMITER ',')
    """)

    if os.path.exists(consolidated_path):
        # Count canonical addresses
        count = db_connection.execute(
            "SELECT COUNT(*) FROM CanonicalAddress"
        ).fetchone()[0]
        logger.info(
            f"Successfully exported {count} canonical addresses ({os.path.getsize(consolidated_path)} bytes)"
        )
    else:
        logger.error("Failed to export canonical addresses")

    logger.info("Canonical address export completed")


def export_public_space_tables(
    db_connection: duckdb.DuckDBPyConnection, export_dir: str, run_tag: str
) -> None:
    """Exports public space tables to CSV files.

    Args:
        db_connection: An active DuckDB connection.
        export_dir: The directory to save CSV files.
        run_tag: The run tag to include in filenames.
    """
    logger.info(f"Exporting public space tables to CSV in {export_dir}")

    # Create export directory if it doesn't exist
    os.makedirs(export_dir, exist_ok=True)

    # List of public space tables to export
    tables = [
        "PublicSpaceName",
        "PublicSpaceType",
        "SettlementPublicSpaces",
    ]

    for table in tables:
        export_table_to_csv(db_connection, table, export_dir, run_tag)

    logger.info("Public space table export completed")


def create_release_symlinks(
    export_dir: str, run_tag: str, db_path: str, use_copies: bool = None
) -> None:
    """Create symlinks or copies for release system compatibility.

    The release validation system expects specific file names without timestamps.
    This function creates symlinks (Unix) or copies (Windows) from timestamped files.

    Args:
        export_dir: The directory containing exported CSV files.
        run_tag: The run tag used in filenames.
        db_path: Path to the database file.
        use_copies: If True, copy files instead of symlinks. If None, auto-detect (Windows=copy, Unix=symlink).
    """
    # Auto-detect platform if not specified
    if use_copies is None:
        use_copies = sys.platform.startswith("win")

    method = "copies" if use_copies else "symlinks"
    logger.info(
        f"Creating release {method} for validation compatibility (platform: {sys.platform})"
    )

    # Required files for release validation
    # Note: addresses.csv points to the Address directory (not a file)
    required_files = {
        "Addresses": f"{run_tag}_Address",  # Directory symlink
        "Settlements.csv": f"{run_tag}_Settlement.csv",
        "Counties.csv": f"{run_tag}_County.csv",
        "PublicSpaceName.csv": f"{run_tag}_PublicSpaceName.csv",
        "PublicSpaceType.csv": f"{run_tag}_PublicSpaceType.csv",
        "SettlementPublicSpaces.csv": f"{run_tag}_SettlementPublicSpaces.csv",
        "database.duckdb": db_path,
    }

    created_count = 0
    manifest = {}  # Track source -> target mapping

    for target_name, source_file in required_files.items():
        target_path = os.path.join(export_dir, target_name)

        # For database file, use the actual database path
        if target_name == "database.duckdb":
            source_path = source_file
            # Use relative path for database symlink
            source_relative = os.path.relpath(source_path, export_dir)
        else:
            source_path = os.path.join(export_dir, source_file)
            # Use relative path for CSV files (just the filename)
            source_relative = source_file

        # Remove existing file/symlink/directory if it exists
        if os.path.exists(target_path) or os.path.islink(target_path):
            try:
                if os.path.isdir(target_path) and not os.path.islink(target_path):
                    shutil.rmtree(target_path)
                else:
                    os.remove(target_path)
                logger.debug(f"Removed existing target: {target_path}")
            except OSError as e:
                logger.warning(f"Failed to remove existing target {target_path}: {e}")

        # Create symlink or copy if source exists
        if os.path.exists(source_path):
            try:
                if use_copies:
                    # Copy files (Windows-compatible)
                    if os.path.isdir(source_path):
                        # Copy directory
                        shutil.copytree(source_path, target_path)
                        logger.info(
                            f"Copied directory: {target_name} <- {source_relative}"
                        )
                    else:
                        # Copy file
                        shutil.copy2(source_path, target_path)
                        logger.info(f"Copied file: {target_name} <- {source_relative}")
                else:
                    # Create symlink (Unix)
                    os.symlink(source_relative, target_path)
                    logger.info(f"Created symlink: {target_name} -> {source_relative}")

                created_count += 1
                manifest[target_name] = source_relative
            except (OSError, IOError) as e:
                logger.error(f"Failed to create {method[:-1]} for {target_name}: {e}")
        else:
            logger.warning(f"Source file not found for {target_name}: {source_path}")

    # Create manifest file for tracking
    manifest_path = os.path.join(export_dir, "export_manifest.json")
    try:
        manifest_data = {
            "run_tag": run_tag,
            "method": method,
            "platform": sys.platform,
            "files": manifest,
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)
        logger.info(f"Created manifest file: {manifest_path}")
    except Exception as e:
        logger.warning(f"Failed to create manifest file: {e}")

    logger.info(f"Created {created_count} {method} for release compatibility")
