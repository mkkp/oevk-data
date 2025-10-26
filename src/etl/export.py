"""Export logic for generating CSV files from target tables."""

import json
import os
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
        pairs = polygon_text.strip().split(',')
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
        coord_str = ', '.join(f"{lon} {lat}" for lon, lat in coords)
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

    # Convert ID columns from TEXT to UUID
    # Pattern: ID TEXT PRIMARY KEY -> ID UUID PRIMARY KEY
    import re

    # Replace the DuckDB schema header with PostgreSQL-specific header
    schema = re.sub(
        r"^-- Database Schema for OEVK Data Transformation\n-- All primary keys are MD5 digests[^\n]*\n\n",
        "",
        schema,
        flags=re.MULTILINE
    )

    # Add PostgreSQL header comment and PostGIS extension if enabled
    pg_header = "-- PostgreSQL Schema for OEVK Data\n"
    pg_header += "-- Translated from SQLite schema\n"
    pg_header += "-- All ID columns use UUID type (converted from MD5 hex to UUID5)\n\n"

    if use_postgis:
        pg_header += "-- PostGIS extension for geospatial data support\n"
        pg_header += "CREATE EXTENSION IF NOT EXISTS postgis;\n\n"

    schema = pg_header + schema

    # Convert all ID columns from TEXT to UUID
    # Pattern: ID TEXT PRIMARY KEY -> ID UUID PRIMARY KEY
    schema = re.sub(r'\bID TEXT\b', 'ID UUID', schema)
    # Pattern: _ID TEXT -> _ID UUID (for foreign keys)
    schema = re.sub(r'_ID TEXT\b', '_ID UUID', schema)
    # Pattern: _ID TEXT, -> _ID UUID, (with comma)
    schema = re.sub(r'_ID TEXT,', '_ID UUID,', schema)

    # Convert OEVK Center and Polygon to PostGIS GEOMETRY types if enabled
    if use_postgis:
        # Replace Center TEXT with GEOMETRY(POINT, 4326)
        schema = re.sub(
            r"Center TEXT, -- Center point coordinates \(space-separated: \"lat lon\"\)",
            "Center GEOMETRY(POINT, 4326), -- Center point coordinates using PostGIS (SRID 4326 = WGS 84)",
            schema
        )
        # Replace Polygon TEXT with GEOMETRY(POLYGON, 4326)
        schema = re.sub(
            r"Polygon TEXT, -- Boundary polygon coordinates \(comma-separated pairs: \"lat1 lon1,lat2 lon2,...\"\)",
            "Polygon GEOMETRY(POLYGON, 4326), -- Boundary polygon coordinates using PostGIS (SRID 4326 = WGS 84)",
            schema
        )

        # Add spatial indexes after NationalIndividualElectoralDistrict indexes
        spatial_indexes = """
-- Spatial indexes for geospatial queries on OEVK geometries
CREATE INDEX IF NOT EXISTS idx_oevk_center_gist ON NationalIndividualElectoralDistrict USING GIST (Center);
CREATE INDEX IF NOT EXISTS idx_oevk_polygon_gist ON NationalIndividualElectoralDistrict USING GIST (Polygon);
"""
        # Insert spatial indexes after the NationalIndividualElectoralDistrict_County_ID index
        schema = re.sub(
            r"(CREATE INDEX IF NOT EXISTS idx_NationalIndividualElectoralDistrict_County_ID ON NationalIndividualElectoralDistrict\(County_ID\);)",
            r"\1" + spatial_indexes,
            schema
        )

        # Add GEOGRAPHY columns for geocoding if enabled
        geocoding_use_postgis = config.get("geocoding", {}).get("use_postgis", True)
        if geocoding_use_postgis:
            # Add Geometry GEOGRAPHY column to Address after coordinate columns
            schema = re.sub(
                r"(CREATE INDEX IF NOT EXISTS idx_Address_Quality ON Address\(GeocodingQuality\);)",
                r"\1\n\n-- Add PostGIS GEOGRAPHY column for spatial queries\nALTER TABLE Address ADD COLUMN IF NOT EXISTS Geometry GEOGRAPHY(POINT, 4326);",
                schema
            )
            # Add GIST spatial index for Address
            schema = re.sub(
                r"(ALTER TABLE Address ADD COLUMN IF NOT EXISTS Geometry GEOGRAPHY\(POINT, 4326\);)",
                r"\1\nCREATE INDEX IF NOT EXISTS idx_Address_Geometry ON Address USING GIST(Geometry);",
                schema
            )

            # Add Geometry GEOGRAPHY column to PollingStation after coordinate columns
            schema = re.sub(
                r"(CREATE INDEX IF NOT EXISTS idx_PollingStation_Quality ON PollingStation\(GeocodingQuality\);)",
                r"\1\n\n-- Add PostGIS GEOGRAPHY column for spatial queries\nALTER TABLE PollingStation ADD COLUMN IF NOT EXISTS Geometry GEOGRAPHY(POINT, 4326);",
                schema
            )
            # Add GIST spatial index for PollingStation
            schema = re.sub(
                r"(ALTER TABLE PollingStation ADD COLUMN IF NOT EXISTS Geometry GEOGRAPHY\(POINT, 4326\);)",
                r"\1\nCREATE INDEX IF NOT EXISTS idx_PollingStation_Geometry ON PollingStation USING GIST(Geometry);",
                schema
            )

    # For PostgreSQL export, we only want the canonical (cleansed) data:
    # - Remove original Address table (dirty data)
    # - Remove Address_new (SQLite artifact)
    # - Remove AddressMapping (internal transformation data)
    # - Remove DeduplicationReport (internal analytics)
    # - Rename CanonicalAddress to Address (this is the clean data)
    # - Update AddressPollingStations and AddressPIRCodes to reference Address

    # Remove unwanted tables
    schema = re.sub(
        r"-- Address table.*?CREATE TABLE IF NOT EXISTS Address \(.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )
    schema = re.sub(
        r"CREATE TABLE IF NOT EXISTS Address_new.*?;", "", schema, flags=re.DOTALL
    )
    schema = re.sub(
        r"CREATE TABLE IF NOT EXISTS AddressMapping.*?;", "", schema, flags=re.DOTALL
    )
    schema = re.sub(
        r"CREATE TABLE IF NOT EXISTS DeduplicationReport.*?;",
        "",
        schema,
        flags=re.DOTALL,
    )
    # Remove AddressPollingStations and AddressPIRCodes tables (replaced by direct columns in Address)
    schema = re.sub(
        r"-- AddressPollingStations table.*?CREATE TABLE IF NOT EXISTS AddressPollingStations.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )
    schema = re.sub(
        r"-- AddressPIRCodes table.*?CREATE TABLE IF NOT EXISTS AddressPIRCodes.*?\);",
        "",
        schema,
        flags=re.DOTALL,
    )

    # Remove comment sections for removed tables
    schema = re.sub(r"-- Deduplication tables.*?\n", "", schema)
    schema = re.sub(r"-- New indexes for deduplication tables.*?\n", "", schema)

    # Remove indexes for removed tables
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_Address_new.*?;", "", schema)
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_Address_.*?;", "", schema)
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_AddressMapping.*?;", "", schema)
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_CanonicalAddress.*?;", "", schema)
    schema = re.sub(
        r"CREATE INDEX IF NOT EXISTS idx_DeduplicationReport.*?;", "", schema
    )
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_AddressPollingStations.*?;", "", schema)
    schema = re.sub(r"CREATE INDEX IF NOT EXISTS idx_AddressPIRCodes.*?;", "", schema)

    # Remove CanonicalAddress table and insert custom Address table at the right position
    # The Address table must come BEFORE AddressPollingStations and AddressPIRCodes
    # which reference it

    # Replace CanonicalAddress table with a placeholder
    schema = re.sub(
        r"-- CanonicalAddress table.*?CREATE TABLE IF NOT EXISTS CanonicalAddress \(.*?\);",
        "%%ADDRESS_TABLE_PLACEHOLDER%%",
        schema,
        flags=re.DOTALL,
    )

    # Update references: CanonicalAddressID -> AddressID in remaining tables
    schema = re.sub(r"\bCanonicalAddressID\b", "AddressID", schema)
    schema = re.sub(r"REFERENCES CanonicalAddress", "REFERENCES Address", schema)

    # Update index names: idx_*_CanonicalAddressID -> idx_*_AddressID
    schema = re.sub(r"idx_(\w+)_CanonicalAddressID", r"idx_\1_AddressID", schema)

    # Create custom Address table for PostgreSQL with the exact structure we export
    # This combines data from CanonicalAddress with PollingStation_ID and PIRCode
    custom_address_table = """
-- Address table (canonical/cleansed addresses)
-- This is the deduplicated, cleansed address data exported from CanonicalAddress
-- Includes PollingStation_ID and PIRCode directly (instead of junction tables)
CREATE TABLE IF NOT EXISTS Address (
    ID UUID PRIMARY KEY,
    CountyCode TEXT NOT NULL,
    SettlementName TEXT NOT NULL,
    StreetName TEXT NOT NULL,
    HouseNumber TEXT NOT NULL,
    Building TEXT,
    Staircase TEXT,
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
CREATE EXTENSION IF NOT EXISTS postgis;

-- Trigram index for efficient LIKE/ILIKE queries on FullAddress
-- Enables fast substring searches like '%Bar%' and '%utca%'
CREATE INDEX IF NOT EXISTS idx_address_fulladdress_trgm ON Address USING gin (FullAddress gin_trgm_ops);

-- Spatial indexes for geocoded coordinates using PostGIS
CREATE INDEX IF NOT EXISTS idx_Address_Geometry ON Address USING GIST(Geometry);
CREATE INDEX IF NOT EXISTS idx_PollingStation_Geometry ON PollingStation USING GIST(Geometry);

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
        "County",                                    # Base reference (no dependencies)
        "Settlement",                                # Depends on County
        "NationalIndividualElectoralDistrict",      # Depends on County (OEVK)
        "SettlementIndividualElectoralDistrict",    # Depends on County, Settlement (TEVK)
        "PostalCode",                                # Base reference (no dependencies)
        "PostalCode_Settlement",                     # Junction table
        "PollingStation",                            # Depends on multiple tables
        "PublicSpaceName",                           # Base reference
        "PublicSpaceType",                           # Base reference
        "SettlementPublicSpaces",                    # Junction table
        "AddressPollingStations",                    # Junction table
        "AddressPIRCodes",                           # Junction table
        "CanonicalAddress",                          # Deduplicated addresses (no FK constraints)
        "AddressMapping",                            # Deduplication mapping
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
        postgresql_tables = [t for t in tables if t not in [
            "CanonicalAddress",
            "AddressMapping",
            "AddressPollingStations",
            "AddressPIRCodes"
        ]]

        # Export tables to CSV
        csv_files = export_tables_to_postgresql_csv(conn, postgresql_dir, postgresql_tables)

        # Export CanonicalAddress as Address (the canonical address table for PostgreSQL)
        canonical_csv = export_canonical_address_to_csv(conn, postgresql_dir)
        csv_files["Address"] = canonical_csv

        # Generate optimized import script
        logger.info("Generating optimized PostgreSQL import script...")
        import_script_path = os.path.join(output_dir, "import_postgresql.sql")
        # Convert to absolute path for PostgreSQL COPY command
        postgresql_dir_abs = os.path.abspath(postgresql_dir)
        config = get_config()  # Get configuration for PostgreSQL settings
        generate_postgresql_import_script(import_script_path, postgresql_dir_abs, csv_files, config)

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
    db_connection: duckdb.DuckDBPyConnection,
    output_dir: str,
    tables: list
) -> dict:
    """Export tables to CSV files for PostgreSQL COPY command.

    Converts MD5 hex IDs to UUID5 format for PostgreSQL compatibility.

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

    for table in tables:
        csv_path = os.path.join(output_dir, f"{table}.csv")
        logger.info(f"  Exporting {table} to CSV...")

        # Get PostGIS configuration for OEVK table
        config = get_config()
        use_postgis = config.get_postgresql_settings().get("use_postgis", True)

        # Get table columns to build SELECT with UUID conversion
        columns_result = db_connection.execute(f"DESCRIBE {table}").fetchall()
        columns = [col[0] for col in columns_result]

        # Build SELECT list with UUID5 conversion for ID columns
        select_items = []
        for col in columns:
            if col == 'ID' or col.endswith('_ID'):
                # Convert ID columns to UUID5
                select_items.append(f"to_uuid5({col}) as {col}")
            else:
                select_items.append(col)

        select_clause = ", ".join(select_items)

        # Special handling for NationalIndividualElectoralDistrict with PostGIS
        if table == "NationalIndividualElectoralDistrict" and use_postgis:
            # Convert Center and Polygon to WKT format, and IDs to UUID5
            query = f"""
                SELECT
                    to_uuid5(ID) as ID,
                    OEVK,
                    Name,
                    CASE
                        WHEN Center IS NOT NULL THEN
                            'POINT(' || split_part(Center, ' ', 2) || ' ' || split_part(Center, ' ', 1) || ')'
                        ELSE NULL
                    END as Center,
                    CASE
                        WHEN Polygon IS NOT NULL THEN
                            'POLYGON((' || regexp_replace(Polygon, '([0-9.]+) ([0-9.]+)', '\\2 \\1', 'g') || '))'
                        ELSE NULL
                    END as Polygon,
                    to_uuid5(County_ID) as County_ID
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
    db_connection: duckdb.DuckDBPyConnection,
    output_dir: str
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
    logger.info("  Exporting CanonicalAddress to CSV as Address (with foreign keys and UUID5 conversion)...")

    # Get total row count for progress tracking
    total_rows = db_connection.execute("SELECT COUNT(*) FROM CanonicalAddress").fetchone()[0]
    logger.info(f"    Total addresses to export: {total_rows:,}")

    if total_rows == 0:
        # Create empty CSV with headers
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'CountyCode', 'SettlementName', 'StreetName', 'HouseNumber',
                'Building', 'Staircase', 'FullAddress', 'AccessibilityFlag', 'Latitude', 'Longitude',
                'GeocodingQuality', 'GeocodingSource', 'GeocodedAt', 'CreatedAt',
                'County_ID', 'Settlement_ID', 'PollingStation_ID', 'PIRCode'
            ])
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
            ca.CountyCode,
            ca.SettlementName,
            ca.StreetName,
            ca.HouseNumber,
            ca.Building,
            ca.Staircase,
            ca.FullAddress,
            ca.AccessibilityFlag,
            ca.Latitude,
            ca.Longitude,
            ca.GeocodingQuality,
            ca.GeocodingSource,
            ca.GeocodedAt,
            ca.CreatedAt,
            c.ID as County_ID,
            s.ID as Settlement_ID,
            ps.PollingStationID as PollingStation_ID,
            pir.PIRCode
        FROM CanonicalAddress ca
        LEFT JOIN County c ON ca.CountyCode = c.CountyCode
        LEFT JOIN Settlement s ON c.ID = s.County_ID AND ca.SettlementName = s.SettlementName
        LEFT JOIN (
            SELECT CanonicalAddressID, MIN(PollingStationID) as PollingStationID
            FROM AddressPollingStations
            GROUP BY CanonicalAddressID
        ) ps ON ca.ID = ps.CanonicalAddressID
        LEFT JOIN (
            SELECT CanonicalAddressID, MIN(PIRCode) as PIRCode
            FROM AddressPIRCodes
            GROUP BY CanonicalAddressID
        ) pir ON ca.ID = pir.CanonicalAddressID
    """).fetchall()

    fetch_time = time.time() - fetch_start
    logger.info(f"    Fetched {len(result):,} rows in {fetch_time:.1f}s ({len(result)/fetch_time:.0f} rows/s)")

    # Write CSV with UUID conversion in Python (batched for progress tracking)
    logger.info(f"    Converting MD5 IDs to UUID5 and writing CSV...")
    write_start = time.time()
    batch_size = 100000
    processed = 0

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow([
            'ID', 'CountyCode', 'SettlementName', 'StreetName', 'HouseNumber',
            'Building', 'Staircase',
            'FullAddress', 'AccessibilityFlag', 'Latitude', 'Longitude',
            'GeocodingQuality', 'GeocodingSource', 'GeocodedAt', 'CreatedAt',
            'County_ID', 'Settlement_ID', 'PollingStation_ID', 'PIRCode'
        ])

        # Process and write in batches
        for i in range(0, len(result), batch_size):
            batch_start = time.time()
            batch = result[i:i+batch_size]

            # Convert MD5 hex IDs to UUID5 in Python
            converted_batch = []
            for row in batch:
                converted_row = list(row)
                converted_row[0] = to_uuid5(row[0])   # ID
                converted_row[15] = to_uuid5(row[15])  # County_ID (was 13, now 15 due to Building/Staircase)
                converted_row[16] = to_uuid5(row[16])  # Settlement_ID (was 14, now 16)
                converted_row[17] = to_uuid5(row[17])  # PollingStation_ID (was 15, now 17)
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
    with open(csv_path, 'r', encoding='utf-8') as f:
        return sum(1 for _ in csv.reader(f)) - 1  # Exclude header


def generate_chunked_copy_commands(
    f,
    table: str,
    csv_path: str,
    csv_dir: str,
    csv_file: str,
    chunk_size: int,
    columns: str = None
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
            f.write(f"\\copy {table} {columns} FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n")
        else:
            f.write(f"\\copy {table} FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n")
        return

    # For large files, split into chunks during export
    num_chunks = (row_count + chunk_size - 1) // chunk_size
    f.write(f"-- Large table with {row_count:,} rows, importing in {num_chunks} chunks of {chunk_size:,} rows\n")

    logger.info(f"  Splitting {table} ({row_count:,} rows) into {num_chunks} chunks...")

    # Split CSV into chunks
    import csv as csv_module
    base_name = csv_file.replace('.csv', '')
    chunk_files = []
    output_dir = os.path.dirname(csv_path)

    with open(csv_path, 'r', encoding='utf-8') as infile:
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
                chunk_file_handle = open(chunk_path, 'w', encoding='utf-8', newline='')
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
        f.write(f"\\echo '[{i}/{len(chunk_files)}] {progress_pct:.1f}% - Importing {table}: {rows_imported:,}/{row_count:,} rows'\n")
        if columns:
            f.write(f"\\copy {table} {columns} FROM '{csv_dir}/{chunk_filename}' WITH (FORMAT CSV, HEADER, NULL '');\n")
        else:
            f.write(f"\\copy {table} FROM '{csv_dir}/{chunk_filename}' WITH (FORMAT CSV, HEADER, NULL '');\n")


def generate_postgresql_import_script(
    script_path: str,
    csv_dir: str,
    csv_files: dict,
    config: Config,
    defer_foreign_keys: bool = True,
    chunk_size: int = 100000
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
        f.write("-- Uses \\copy command for fast data loading (10-50x faster than INSERT)\n")
        f.write("-- \n")
        f.write("-- Prerequisites:\n")
        f.write("--   1. PostgreSQL database created\n")
        f.write("--   2. PostGIS extension enabled: CREATE EXTENSION IF NOT EXISTS postgis;\n")
        f.write("--   3. Schema created: Run schema.sql first\n")
        f.write("--\n")
        f.write("-- Usage: psql -U username -d database -f import_postgresql.sql\n")
        f.write("--\n")
        f.write("-- Expected import time: 2-5 minutes (vs 30-120 minutes with INSERT)\n")
        f.write("--\n")
        f.write("-- Note: PostGIS geometries are imported as WKT text then converted to GEOMETRY types\n")
        f.write("--\n\n")

        # Performance optimizations (session-level settings only)
        f.write("-- Step 1: Performance optimizations for bulk import\n")
        f.write("SET maintenance_work_mem = '1GB';\n")
        f.write("SET synchronous_commit = off;  -- Faster, but risk of data loss on crash\n")
        f.write("-- Note: checkpoint_completion_target requires server-level configuration\n")
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

            # Drop FKs from Address table
            f.write("ALTER TABLE Address DROP CONSTRAINT IF EXISTS address_county_id_fkey;\n")
            f.write("ALTER TABLE Address DROP CONSTRAINT IF EXISTS address_settlement_id_fkey;\n")

            # Drop FK from Address table for PollingStation_ID
            f.write("ALTER TABLE Address DROP CONSTRAINT IF EXISTS address_pollingstation_id_fkey;\n")

            # Drop FKs from other tables
            f.write("ALTER TABLE Settlement DROP CONSTRAINT IF EXISTS settlement_county_id_fkey;\n")
            f.write("ALTER TABLE NationalIndividualElectoralDistrict DROP CONSTRAINT IF EXISTS nationalindividualelectoraldistrict_county_id_fkey;\n")
            f.write("ALTER TABLE SettlementIndividualElectoralDistrict DROP CONSTRAINT IF EXISTS settlementindividualelectoraldistrict_county_id_fkey;\n")
            f.write("ALTER TABLE SettlementIndividualElectoralDistrict DROP CONSTRAINT IF EXISTS settlementindividualelectoraldistrict_settlement_id_fkey;\n")
            f.write("ALTER TABLE PollingStation DROP CONSTRAINT IF EXISTS pollingstation_county_id_fkey;\n")
            f.write("ALTER TABLE PollingStation DROP CONSTRAINT IF EXISTS pollingstation_settlement_id_fkey;\n")
            f.write("ALTER TABLE PollingStation DROP CONSTRAINT IF EXISTS pollingstation_settlementindividualelectoraldistrict_id_fkey;\n")
            f.write("ALTER TABLE PollingStation DROP CONSTRAINT IF EXISTS pollingstation_nationalindividualelectoraldistrict_id_fkey;\n")
            f.write("ALTER TABLE PostalCode_Settlement DROP CONSTRAINT IF EXISTS postalcode_settlement_postalcode_id_fkey;\n")
            f.write("ALTER TABLE PostalCode_Settlement DROP CONSTRAINT IF EXISTS postalcode_settlement_settlement_id_fkey;\n")
            f.write("ALTER TABLE SettlementPublicSpaces DROP CONSTRAINT IF EXISTS settlementpublicspaces_settlement_id_fkey;\n")
            f.write("ALTER TABLE SettlementPublicSpaces DROP CONSTRAINT IF EXISTS settlementpublicspaces_publicspacename_id_fkey;\n")
            f.write("ALTER TABLE SettlementPublicSpaces DROP CONSTRAINT IF EXISTS settlementpublicspaces_publicspacetype_id_fkey;\n")
            f.write("\n")

        # Insert placeholder records
        f.write("-- Step 3: Insert placeholder records for missing foreign keys\n")
        placeholder_uuid = "'00000000-0000-0000-0000-000000000000'"
        f.write(f"INSERT INTO County (ID, CountyCode, CountyName) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown County') ON CONFLICT DO NOTHING;\n")
        f.write(f"INSERT INTO Settlement (ID, SettlementCode, SettlementName, County_ID) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown Settlement', {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")

        if use_postgis:
            f.write(f"INSERT INTO NationalIndividualElectoralDistrict (ID, OEVK, Name, Center, Polygon, County_ID) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown District', NULL, NULL, {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")
        else:
            f.write(f"INSERT INTO NationalIndividualElectoralDistrict (ID, OEVK, Name, Center, Polygon, County_ID) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown District', NULL, NULL, {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")

        f.write(f"INSERT INTO SettlementIndividualElectoralDistrict (ID, TEVK, Name, County_ID, Settlement_ID) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown District', {placeholder_uuid}, {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")
        f.write(f"INSERT INTO PostalCode (ID, PostalCode) VALUES ({placeholder_uuid}, '0000') ON CONFLICT DO NOTHING;\n")
        f.write(f"INSERT INTO PollingStation (ID, PollingStationAddress, SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID, Latitude, Longitude, GeocodingQuality, GeocodingSource, GeocodedAt, MatchedAddress) VALUES ({placeholder_uuid}, 'Unknown Polling Station Address', {placeholder_uuid}, {placeholder_uuid}, {placeholder_uuid}, {placeholder_uuid}, NULL, NULL, NULL, NULL, NULL, NULL) ON CONFLICT DO NOTHING;\n")
        f.write("\n")

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

        for table in import_order:
            if table in csv_files:
                csv_file = os.path.basename(csv_files[table])

                # Special handling for PostGIS geometry columns
                if table == "NationalIndividualElectoralDistrict" and use_postgis:
                    f.write(f"\\echo 'Importing {table} with PostGIS geometries...'\n")
                    # Add temporary TEXT columns for WKT import
                    f.write(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS Center_WKT TEXT;\n")
                    f.write(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS Polygon_WKT TEXT;\n")
                    # Import with temp columns
                    f.write(f"\\copy {table} (ID, OEVK, Name, Center_WKT, Polygon_WKT, County_ID) FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n")
                    # Convert WKT to GEOMETRY - Center points are usually valid
                    f.write(f"UPDATE {table} SET Center = ST_GeomFromText(Center_WKT, 4326) WHERE Center_WKT IS NOT NULL AND Center_WKT != '';\n")
                    # For polygons, try to fix with ST_MakeValid, skip if completely invalid
                    # This updates row-by-row to avoid transaction abort on invalid geometries
                    f.write(f"DO $$\n")
                    f.write(f"DECLARE\n")
                    f.write(f"  r RECORD;\n")
                    f.write(f"BEGIN\n")
                    f.write(f"  FOR r IN SELECT ID, Polygon_WKT FROM {table} WHERE Polygon_WKT IS NOT NULL AND Polygon_WKT != '' LOOP\n")
                    f.write(f"    BEGIN\n")
                    f.write(f"      UPDATE {table} SET Polygon = ST_MakeValid(ST_GeomFromText(r.Polygon_WKT, 4326)) WHERE ID = r.ID;\n")
                    f.write(f"    EXCEPTION WHEN OTHERS THEN\n")
                    f.write(f"      -- Skip invalid geometries that can't be fixed\n")
                    f.write(f"      RAISE NOTICE 'Skipping invalid polygon for ID %', r.ID;\n")
                    f.write(f"    END;\n")
                    f.write(f"  END LOOP;\n")
                    f.write(f"END $$;\n")
                    # Drop temporary columns
                    f.write(f"ALTER TABLE {table} DROP COLUMN Center_WKT;\n")
                    f.write(f"ALTER TABLE {table} DROP COLUMN Polygon_WKT;\n")
                # Special handling for Address table - has Geometry column added via ALTER TABLE
                elif table == "Address":
                    f.write(f"\\echo 'Importing {table}...'\n")
                    # Use chunked import for large table
                    csv_path = csv_files[table]
                    columns = "(ID, CountyCode, SettlementName, StreetName, HouseNumber, Building, Staircase, FullAddress, AccessibilityFlag, Latitude, Longitude, GeocodingQuality, GeocodingSource, GeocodedAt, CreatedAt, County_ID, Settlement_ID, PollingStation_ID, PIRCode)"
                    generate_chunked_copy_commands(f, table, csv_path, csv_dir, csv_file, chunk_size, columns)
                # Special handling for PollingStation - also has Geometry column
                elif table == "PollingStation":
                    f.write(f"\\echo 'Importing {table}...'\n")
                    # Get column list from CSV header, excluding Geometry
                    # For now, we'll list all expected columns explicitly
                    f.write(f"\\copy {table} (ID, PollingStationAddress, SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID, Latitude, Longitude, GeocodingQuality, GeocodingSource, GeocodedAt, MatchedAddress) FROM '{csv_dir}/{csv_file}' WITH (FORMAT CSV, HEADER, NULL '');\n")
                else:
                    f.write(f"\\echo 'Importing {table}...'\n")
                    # Use chunked import for all tables
                    csv_path = csv_files[table]
                    generate_chunked_copy_commands(f, table, csv_path, csv_dir, csv_file, chunk_size, columns=None)

                f.write("\n")

        # Populate PostGIS GEOGRAPHY columns for geocoding (chunked for better performance)
        if geocoding_use_postgis:
            f.write("-- Step 5: Populate PostGIS GEOGRAPHY columns from geocoding coordinates\n")
            f.write("-- Using chunked updates with ST_SetSRID + ST_MakePoint for better performance\n")
            f.write("-- Committing transaction before geometry updates to avoid long locks\n")
            f.write("COMMIT;\n\n")

            # Chunked update for Address table (100k rows per chunk)
            postgis_chunk_size = 100000
            f.write(f"-- Update Address.Geometry in chunks of {postgis_chunk_size:,} rows\n")
            f.write("\\echo 'Populating PostGIS GEOGRAPHY for Address table in chunks...'\n")
            f.write("DO $$\n")
            f.write("DECLARE\n")
            f.write("    batch_size INT := 100000;\n")
            f.write("    total_updated BIGINT := 0;\n")
            f.write("    rows_updated INT;\n")
            f.write("BEGIN\n")
            f.write("    LOOP\n")
            f.write("        UPDATE Address\n")
            f.write("        SET Geometry = ST_SetSRID(ST_MakePoint(Longitude, Latitude), 4326)::geography\n")
            f.write("        WHERE Geometry IS NULL\n")
            f.write("          AND Latitude IS NOT NULL\n")
            f.write("          AND Longitude IS NOT NULL\n")
            f.write("          AND ID IN (\n")
            f.write("              SELECT ID FROM Address\n")
            f.write("              WHERE Geometry IS NULL\n")
            f.write("                AND Latitude IS NOT NULL\n")
            f.write("                AND Longitude IS NOT NULL\n")
            f.write("              LIMIT batch_size\n")
            f.write("          );\n")
            f.write("        GET DIAGNOSTICS rows_updated = ROW_COUNT;\n")
            f.write("        total_updated := total_updated + rows_updated;\n")
            f.write("        RAISE NOTICE 'Updated % addresses (total: %)', rows_updated, total_updated;\n")
            f.write("        EXIT WHEN rows_updated = 0;\n")
            f.write("        COMMIT;\n")
            f.write("    END LOOP;\n")
            f.write("    RAISE NOTICE 'Completed: % addresses updated with PostGIS geometry', total_updated;\n")
            f.write("END $$;\n\n")

            f.write("\\echo 'Populating PostGIS GEOGRAPHY columns for PollingStation...'\n")
            f.write("UPDATE PollingStation\n")
            f.write("SET Geometry = ST_SetSRID(ST_MakePoint(Longitude, Latitude), 4326)::geography\n")
            f.write("WHERE Latitude IS NOT NULL AND Longitude IS NOT NULL;\n\n")

            f.write("-- Begin new transaction for remaining operations\n")
            f.write("BEGIN;\n\n")

        # Recreate foreign keys after data import
        if defer_foreign_keys:
            f.write("-- Step 5.5: Recreate foreign key constraints (deferred for performance)\n")
            f.write("\\echo 'Recreating foreign key constraints...'\n")

            # Address table FKs
            f.write("ALTER TABLE Address ADD CONSTRAINT address_county_id_fkey FOREIGN KEY (County_ID) REFERENCES County(ID);\n")
            f.write("ALTER TABLE Address ADD CONSTRAINT address_settlement_id_fkey FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID);\n")

            # Address table PollingStation_ID FK
            f.write("ALTER TABLE Address ADD CONSTRAINT address_pollingstation_id_fkey FOREIGN KEY (PollingStation_ID) REFERENCES PollingStation(ID);\n")

            # Reference tables FKs
            f.write("ALTER TABLE Settlement ADD CONSTRAINT settlement_county_id_fkey FOREIGN KEY (County_ID) REFERENCES County(ID);\n")
            f.write("ALTER TABLE NationalIndividualElectoralDistrict ADD CONSTRAINT nationalindividualelectoraldistrict_county_id_fkey FOREIGN KEY (County_ID) REFERENCES County(ID);\n")
            f.write("ALTER TABLE SettlementIndividualElectoralDistrict ADD CONSTRAINT settlementindividualelectoraldistrict_county_id_fkey FOREIGN KEY (County_ID) REFERENCES County(ID);\n")
            f.write("ALTER TABLE SettlementIndividualElectoralDistrict ADD CONSTRAINT settlementindividualelectoraldistrict_settlement_id_fkey FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID);\n")
            f.write("ALTER TABLE PollingStation ADD CONSTRAINT pollingstation_county_id_fkey FOREIGN KEY (County_ID) REFERENCES County(ID);\n")
            f.write("ALTER TABLE PollingStation ADD CONSTRAINT pollingstation_settlement_id_fkey FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID);\n")
            f.write("ALTER TABLE PollingStation ADD CONSTRAINT pollingstation_settlementindividualelectoraldistrict_id_fkey FOREIGN KEY (SettlementIndividualElectoralDistrict_ID) REFERENCES SettlementIndividualElectoralDistrict(ID);\n")
            f.write("ALTER TABLE PollingStation ADD CONSTRAINT pollingstation_nationalindividualelectoraldistrict_id_fkey FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID);\n")
            f.write("ALTER TABLE PostalCode_Settlement ADD CONSTRAINT postalcode_settlement_postalcode_id_fkey FOREIGN KEY (PostalCode_ID) REFERENCES PostalCode(ID);\n")
            f.write("ALTER TABLE PostalCode_Settlement ADD CONSTRAINT postalcode_settlement_settlement_id_fkey FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID);\n")
            f.write("ALTER TABLE SettlementPublicSpaces ADD CONSTRAINT settlementpublicspaces_settlement_id_fkey FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID);\n")
            f.write("ALTER TABLE SettlementPublicSpaces ADD CONSTRAINT settlementpublicspaces_publicspacename_id_fkey FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID);\n")
            f.write("ALTER TABLE SettlementPublicSpaces ADD CONSTRAINT settlementpublicspaces_publicspacetype_id_fkey FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID);\n")
            f.write("\n")

        # Commit transaction
        f.write("-- Step 6: Commit transaction\n")
        f.write("COMMIT;\n\n")

        # Analyze tables
        f.write("-- Step 7: Analyze tables for query optimization\n")
        f.write("\\echo 'Analyzing tables...'\n")
        for table in import_order:
            if table in csv_files:
                f.write(f"ANALYZE {table};\n")
        f.write("\n")

        # Summary
        f.write("-- Import complete!\n")
        f.write("\\echo 'Import complete! Run SELECT COUNT(*) FROM Address; to verify.'\n")


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
    output_file.write("-- Includes geocoding data (Latitude, Longitude, GeocodingQuality, etc.)\n\n")

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
