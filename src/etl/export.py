"""Export logic for generating CSV files from target tables."""

import json
import os
import shutil
import sys
import uuid
from pathlib import Path

import duckdb

from src.utils.config import get_config
from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)

# OEVK namespace UUID for generating UUIDv3
OEVK_NAMESPACE = uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")


def to_uuid3(value):
    """Convert a value to UUID v3 using OEVK namespace."""
    if value is None or value == "":
        return None
    return str(uuid.uuid3(OEVK_NAMESPACE, str(value)))


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

    # Add PostgreSQL header comment and PostGIS extension if enabled
    pg_header = "-- PostgreSQL Schema for OEVK Data\n"
    pg_header += "-- Translated from SQLite schema\n"
    pg_header += "-- All ID columns use UUID type\n\n"

    if use_postgis:
        pg_header += "-- PostGIS extension for geospatial data support\n"
        pg_header += "CREATE EXTENSION IF NOT EXISTS postgis;\n\n"

    schema = pg_header + schema

    # Replace all ID columns (primary keys and foreign keys)
    schema = re.sub(r"\bID TEXT PRIMARY KEY\b", "ID UUID PRIMARY KEY", schema)

    # Match both underscore style (_ID) and camelCase style (AddressID, PollingStationID, etc.)
    schema = re.sub(r"\b(\w+_ID) TEXT NOT NULL\b", r"\1 UUID NOT NULL", schema)
    schema = re.sub(r"\b(\w+_ID) TEXT\b", r"\1 UUID", schema)
    schema = re.sub(r"\b(\w+ID) TEXT NOT NULL\b", r"\1 UUID NOT NULL", schema)
    schema = re.sub(r"\b(\w+ID) TEXT,", r"\1 UUID,", schema)

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
    # This combines data from CanonicalAddress with computed fields from canonical export
    custom_address_table = """
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

"""

    # Add PostgreSQL-specific statements
    postgresql_header = """-- PostgreSQL Schema for OEVK Data
-- Translated from SQLite schema
-- All ID columns use UUID type

"""

    # Add PostgreSQL-specific extensions and indexes at the end
    postgresql_indexes = """

-- PostgreSQL-specific extensions for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Trigram index for efficient LIKE/ILIKE queries on FullAddress
-- Enables fast substring searches like '%Bar%' and '%utca%'
CREATE INDEX IF NOT EXISTS idx_address_fulladdress_trgm ON Address USING gin (FullAddress gin_trgm_ops);


-- =============================================================================
-- VIEWS
-- =============================================================================

-- View that reconstructs the original address structure from normalized tables
-- This view joins Address with all foreign key tables to provide a denormalized view
-- Column names match the original CSV structure (new model names)

CREATE OR REPLACE VIEW AddressFullView AS
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

    return postgresql_header + schema + postgresql_indexes


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
    tables = [
        "County",
        "Settlement",
        "NationalIndividualElectoralDistrict",
        "SettlementIndividualElectoralDistrict",
        "PostalCode",
        "PostalCode_Settlement",
        "PollingStation",
        "PublicSpaceName",
        "PublicSpaceType",
        "SettlementPublicSpaces",
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

        logger.info("Generating PostgreSQL data INSERT statements...")
        data_path = os.path.join(output_dir, "data.sql")
        with open(data_path, "w", encoding="utf-8") as f:
            f.write("-- PostgreSQL Data INSERT Statements\n")
            f.write("-- All ID values are converted to UUID format\n\n")

            # Insert placeholder records for missing foreign key references
            # These are used by canonical addresses when data is missing
            f.write("-- Placeholder records for missing foreign key references\n")
            f.write("-- Used by Address table when foreign key data is unavailable\n\n")

            placeholder_uuid = "'00000000-0000-0000-0000-000000000000'"

            # Match exact schema column names from src/database/schema.sql
            f.write(f"INSERT INTO County (ID, CountyCode, CountyName) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown County') ON CONFLICT DO NOTHING;\n")
            f.write(f"INSERT INTO Settlement (ID, SettlementCode, SettlementName, County_ID) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown Settlement', {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")
            f.write(f"INSERT INTO NationalIndividualElectoralDistrict (ID, OEVK, Name, Center, Polygon, County_ID) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown District', NULL, NULL, {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")
            f.write(f"INSERT INTO SettlementIndividualElectoralDistrict (ID, TEVK, Name, County_ID, Settlement_ID) VALUES ({placeholder_uuid}, 'UNKNOWN', 'Unknown District', {placeholder_uuid}, {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")
            f.write(f"INSERT INTO PostalCode (ID, PostalCode) VALUES ({placeholder_uuid}, '0000') ON CONFLICT DO NOTHING;\n")
            f.write(f"INSERT INTO PollingStation (ID, PollingStationAddress, SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID) VALUES ({placeholder_uuid}, 'Unknown Polling Station Address', {placeholder_uuid}, {placeholder_uuid}, {placeholder_uuid}, {placeholder_uuid}) ON CONFLICT DO NOTHING;\n")
            f.write("\n")

            for table in tables:
                logger.info(f"  Exporting {table} to SQL...")
                export_table_to_postgresql(conn, table, f)

        logger.info(f"Data written to {data_path}")
        logger.info("PostgreSQL export completed")

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
                         ca.StreetName, ca.HouseNumber, ca.AccessibilityFlag
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
                     ca.StreetName, ca.HouseNumber, ca.AccessibilityFlag
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
