"""Export canonical addresses with UUID v3 - optimized single-query approach.

Includes PostGIS coordinate conversion functions for OEVK geospatial data.
"""

import csv
import os
import time
import uuid
from collections import defaultdict

import duckdb

from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)

# OEVK namespace UUID for generating UUIDv3
OEVK_NAMESPACE = uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")


def to_uuid3(value):
    """Convert a value to UUID v3 using OEVK namespace."""
    if value is None or value == "" or value == "NULL":
        return None
    return str(uuid.uuid3(OEVK_NAMESPACE, str(value)))


def clean_zero_only_field(value):
    """Clean fields that contain only zeros - treat as empty string."""
    if value is None or value == "" or value == "NULL":
        return ""
    if (
        isinstance(value, str)
        and value.strip()
        and all(c == "0" for c in value.strip())
    ):
        return ""
    return value


def trim_leading_zeros_udf(value):
    """Trim leading zeros from address components (UDF for DuckDB).

    Handles:
    - Simple numbers: "000123" -> "123"
    - Ranges: "000001-00005" -> "1-5"
    - Slash notation: "000001/D" -> "1/D"
    - Preserves non-numeric: "A", "L" -> unchanged
    - Empty/null: returns empty string

    Args:
        value: String value to trim

    Returns:
        String with leading zeros removed
    """
    if value is None or value == "" or value == "NULL":
        return ""

    value_str = str(value).strip()
    if not value_str:
        return ""

    # Handle range notation (e.g., "000001-00005" -> "1-5")
    if "-" in value_str and not value_str.startswith("-"):
        parts = value_str.split("-")
        trimmed_parts = [part.lstrip("0") or "0" for part in parts]
        return "-".join(trimmed_parts)

    # Handle slash notation (e.g., "000001/D" -> "1/D")
    if "/" in value_str:
        parts = value_str.split("/")
        trimmed_parts = [parts[0].lstrip("0") or "0"] + parts[1:]
        return "/".join(trimmed_parts)

    # Handle simple numeric strings
    if value_str.isdigit():
        return value_str.lstrip("0") or "0"

    # Handle strings that start with digits followed by letters (e.g., "000001A" -> "1A")
    if value_str[0].isdigit():
        i = 0
        while i < len(value_str) and value_str[i].isdigit():
            i += 1
        numeric_part = value_str[:i].lstrip("0") or "0"
        return numeric_part + value_str[i:]

    # Non-numeric values remain unchanged
    return value_str


def convert_center_to_point(center_text: str | None) -> str | None:
    """Convert center TEXT 'lat lon' to PostGIS POINT WKT format.

    Converts space-separated latitude/longitude coordinates to Well-Known Text (WKT)
    format suitable for PostGIS ST_GeomFromText() function. Swaps coordinate order
    from (lat, lon) to (lon, lat) as required by OGC/PostGIS standards.

    Args:
        center_text: Space-separated coordinates "lat lon" (e.g., "47.4979 19.0402")

    Returns:
        WKT POINT string "POINT(lon lat)" or None if input is invalid

    Examples:
        >>> convert_center_to_point("47.4979 19.0402")
        'POINT(19.0402 47.4979)'
        >>> convert_center_to_point(None)
        None
        >>> convert_center_to_point("91.0 19.0")  # Invalid latitude
        None
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

    Examples:
        >>> convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
        'POLYGON((19.0 47.5, 19.1 47.5, 19.1 47.4, 19.0 47.5))'
        >>> convert_polygon_to_wkt(None)
        None
        >>> convert_polygon_to_wkt("47.0 19.0,47.1 19.1")  # Less than 3 points
        None
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


def export_canonical_addresses_optimized(
    db_connection: duckdb.DuckDBPyConnection,
    export_dir: str,
    run_tag: str,
    formats: list = None,
) -> None:
    """Export canonical addresses with single-query optimization.

    Performance: Runs ONE complex query to fetch all addresses, then partitions
    by settlement in Python. Much faster than 3,177 separate queries.

    Args:
        db_connection: An active DuckDB connection.
        export_dir: The directory to save CSV files.
        run_tag: The run tag to include in filenames.
        formats: List of export formats. Defaults to ["csv"]. Can include "csv" and/or "postgresql".
    """
    if formats is None:
        formats = ["csv"]

    logger.info(
        f"Exporting canonical addresses (optimized single-query approach) to {', '.join(formats)}"
    )

    # Create Address directory
    address_dir = os.path.join(export_dir, f"{run_tag}_Address")
    os.makedirs(address_dir, exist_ok=True)

    # Get settlement codes for filename generation
    logger.info("Fetching settlement information...")
    settlement_codes = {}
    for code, name in db_connection.execute("""
        SELECT DISTINCT s.SettlementCode, s.SettlementName
        FROM Settlement s
        JOIN CanonicalAddress ca ON s.SettlementName = ca.SettlementName
        ORDER BY s.SettlementCode, s.SettlementName
    """).fetchall():
        settlement_codes[name] = code

    logger.info(f"Found {len(settlement_codes)} settlements")

    # Fetch ALL addresses in single query
    start_time = time.time()
    logger.info("Fetching all canonical addresses...")

    # Register Python UDF for trimming leading zeros with explicit return type
    try:
        db_connection.create_function("trim_leading_zeros", trim_leading_zeros_udf, return_type=str)
    except Exception as func_err:
        if "already created" in str(func_err):
            logger.debug("trim_leading_zeros function already exists, skipping")
        else:
            raise

    rows = db_connection.execute("""
        WITH address_details AS (
            SELECT
                am.CanonicalAddressID,
                a.PublicSpaceType,
                trim_leading_zeros(a.Building) as Building,
                trim_leading_zeros(a.Staircase) as Staircase,
                a.SettlementIndividualElectoralDistrict_ID,
                a.County_ID,
                a.Settlement_ID,
                a.NationalIndividualElectoralDistrict_ID,
                ROW_NUMBER() OVER (
                    PARTITION BY am.CanonicalAddressID
                    ORDER BY
                        -- Prioritize addresses with structured Building/Staircase (not in HouseNumber)
                        CASE
                            WHEN a.HouseNumber NOT LIKE '%/%' AND (a.Building IS NOT NULL AND a.Building != '' AND a.Building != '0') THEN 100
                            WHEN a.HouseNumber NOT LIKE '%/%' AND (a.Staircase IS NOT NULL AND a.Staircase != '' AND a.Staircase != '0') THEN 90
                            ELSE 50
                        END DESC,
                        a.ID
                ) as rn
            FROM AddressMapping am
            JOIN Address a ON am.OriginalAddressID = a.ID
        ),
        postal_codes AS (
            SELECT DISTINCT
                apc.CanonicalAddressID,
                FIRST_VALUE(pc.ID) OVER (PARTITION BY apc.CanonicalAddressID ORDER BY apc.PIRCode) as PostalCodeID
            FROM AddressPIRCodes apc
            LEFT JOIN PostalCode pc ON apc.PIRCode = pc.PostalCode
        ),
        polling_stations AS (
            SELECT DISTINCT
                CanonicalAddressID,
                FIRST_VALUE(PollingStationID) OVER (PARTITION BY CanonicalAddressID ORDER BY PollingStationID) as PollingStationID
            FROM AddressPollingStations
        )
        SELECT
            ca.ID as ID,
            ca.SettlementName,
            COALESCE(MIN(a.Sequence), 0) as Sequence,
            COALESCE(MIN(a.OriginalOrder), 0) as OriginalOrder,
            ca.FullAddress,
            ca.StreetName as PublicSpaceName,
            COALESCE(ad.PublicSpaceType, '') as PublicSpaceType,
            trim_leading_zeros(ca.HouseNumber) as HouseNumber,
            ad.Building,
            ad.Staircase,
            COALESCE(pc.PostalCodeID, '00000000-0000-0000-0000-000000000000') as PostalCode_ID,
            COALESCE(ps.PollingStationID, '00000000-0000-0000-0000-000000000000') as PollingStation_ID,
            COALESCE(ad.SettlementIndividualElectoralDistrict_ID, '00000000-0000-0000-0000-000000000000') as SettlementIndividualElectoralDistrict_ID,
            COALESCE(ad.County_ID, '00000000-0000-0000-0000-000000000000') as County_ID,
            COALESCE(ad.Settlement_ID, '00000000-0000-0000-0000-000000000000') as Settlement_ID,
            COALESCE(ad.NationalIndividualElectoralDistrict_ID, '00000000-0000-0000-0000-000000000000') as NationalIndividualElectoralDistrict_ID,
            COUNT(DISTINCT am.OriginalAddressID) as OriginalAddressCount
        FROM CanonicalAddress ca
        LEFT JOIN AddressMapping am ON ca.ID = am.CanonicalAddressID
        LEFT JOIN Address a ON am.OriginalAddressID = a.ID
        LEFT JOIN address_details ad ON ca.ID = ad.CanonicalAddressID AND ad.rn = 1
        LEFT JOIN postal_codes pc ON ca.ID = pc.CanonicalAddressID
        LEFT JOIN polling_stations ps ON ca.ID = ps.CanonicalAddressID
        GROUP BY ca.ID, ca.SettlementName, ca.FullAddress, ca.StreetName, ca.HouseNumber,
                 ad.PublicSpaceType, ad.Building, ad.Staircase,
                 ad.SettlementIndividualElectoralDistrict_ID, ad.County_ID, ad.Settlement_ID,
                 ad.NationalIndividualElectoralDistrict_ID, pc.PostalCodeID, ps.PollingStationID
        ORDER BY ca.SettlementName, ca.FullAddress
    """).fetchall()

    fetch_time = time.time() - start_time
    logger.info(f"Fetched {len(rows):,} addresses in {fetch_time:.1f}s")

    # Partition by settlement
    logger.info("Partitioning addresses by settlement...")
    settlement_data = defaultdict(list)
    for row in rows:
        settlement_name = row[1]
        settlement_data[settlement_name].append(row)

    logger.info(f"Partitioned into {len(settlement_data)} settlements")

    # Write files based on requested formats
    write_start = time.time()
    total_written = 0
    files_written = 0

    # Note: data.sql INSERT statements are no longer generated for canonical addresses
    # The import_postgresql.sql script uses CSV files with COPY commands (much faster)
    # Keeping this variable for backward compatibility but not opening the file
    postgresql_file = None

    # Legacy INSERT-based data.sql generation disabled - use CSV COPY instead
    # if "postgresql" in formats:
    #     data_path = os.path.join(export_dir, "data.sql")
    #     postgresql_file = open(data_path, "a", encoding="utf-8")
    #     postgresql_file.write("\n-- Canonical Addresses (deduplicated)\n")
    #     postgresql_file.write("-- Table: Address\n\n")
    #     logger.info("Appending canonical addresses to data.sql...")

    # Write CSV files if requested
    if "csv" in formats:
        logger.info("Writing CSV files...")

    # Track progress for ETA calculation
    total_settlements = len(settlement_data)
    processed_settlements = 0
    settlement_start_time = time.time()

    for settlement_name, addresses in settlement_data.items():
        processed_settlements += 1
        settlement_code = settlement_codes.get(settlement_name, "000")
        safe_name = settlement_name.replace("/", "_").replace("\\", "_")

        # Write CSV file if requested
        if "csv" in formats:
            filename = f"Address_{settlement_code}_{safe_name}.csv"
            file_path = os.path.join(address_dir, filename)

            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "ID",
                        "Sequence",
                        "OriginalOrder",
                        "FullAddress",
                        "PublicSpaceName",
                        "PublicSpaceType",
                        "HouseNumber",
                        "Building",
                        "Staircase",
                        "PostalCode_ID",
                        "PollingStation_ID",
                        "SettlementIndividualElectoralDistrict_ID",
                        "County_ID",
                        "Settlement_ID",
                        "NationalIndividualElectoralDistrict_ID",
                        "OriginalAddressCount",
                    ]
                )

                for row in addresses:
                    writer.writerow(
                        [
                            to_uuid3(row[0]),  # ID
                            row[2],  # Sequence
                            row[3],  # OriginalOrder
                            row[4],  # FullAddress
                            row[5] or "",  # PublicSpaceName
                            row[6] or "",  # PublicSpaceType
                            row[7],  # HouseNumber
                            clean_zero_only_field(row[8]),  # Building
                            clean_zero_only_field(row[9]),  # Staircase
                            to_uuid3(row[10]),  # PostalCode_ID
                            to_uuid3(row[11]),  # PollingStation_ID
                            to_uuid3(
                                row[12]
                            ),  # SettlementIndividualElectoralDistrict_ID
                            to_uuid3(row[13]),  # County_ID
                            to_uuid3(row[14]),  # Settlement_ID
                            to_uuid3(row[15]),  # NationalIndividualElectoralDistrict_ID
                            row[16],  # OriginalAddressCount
                        ]
                    )

        # Write PostgreSQL INSERT statements if requested (DISABLED - using CSV COPY instead)
        if False and postgresql_file:
            for row in addresses:
                # Helper function to format SQL values
                def format_sql_value(value, is_uuid=False, allow_empty_string=False):
                    if is_uuid:
                        uuid_val = to_uuid3(value)
                        return f"'{uuid_val}'" if uuid_val else "NULL"
                    elif value is None:
                        return "NULL"
                    elif value == "":
                        # For NOT NULL columns, return empty string instead of NULL
                        return "''" if allow_empty_string else "NULL"
                    elif isinstance(value, str):
                        escaped_value = value.replace("'", "''")
                        return f"'{escaped_value}'"
                    else:
                        return str(value)

                # Format values for INSERT statement
                values = [
                    format_sql_value(row[0], is_uuid=True),  # ID
                    format_sql_value(row[2]),  # Sequence
                    format_sql_value(row[3]),  # OriginalOrder
                    format_sql_value(row[4], allow_empty_string=True),  # FullAddress (NOT NULL)
                    format_sql_value(row[5] or "", allow_empty_string=True),  # PublicSpaceName (NOT NULL)
                    format_sql_value(row[6] or "", allow_empty_string=True),  # PublicSpaceType (NOT NULL)
                    format_sql_value(row[7], allow_empty_string=True),  # HouseNumber (NOT NULL)
                    format_sql_value(clean_zero_only_field(row[8]), allow_empty_string=True),  # Building
                    format_sql_value(clean_zero_only_field(row[9]), allow_empty_string=True),  # Staircase
                    format_sql_value(row[10], is_uuid=True),  # PostalCode_ID
                    format_sql_value(row[11], is_uuid=True),  # PollingStation_ID
                    format_sql_value(
                        row[12], is_uuid=True
                    ),  # SettlementIndividualElectoralDistrict_ID
                    format_sql_value(row[13], is_uuid=True),  # County_ID
                    format_sql_value(row[14], is_uuid=True),  # Settlement_ID
                    format_sql_value(
                        row[15], is_uuid=True
                    ),  # NationalIndividualElectoralDistrict_ID
                    format_sql_value(row[16]),  # OriginalAddressCount
                ]

                values_str = ", ".join(values)
                postgresql_file.write(
                    f"INSERT INTO Address (ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, "
                    f"PublicSpaceType, HouseNumber, Building, Staircase, PostalCode_ID, PollingStation_ID, "
                    f"SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID, "
                    f"NationalIndividualElectoralDistrict_ID, OriginalAddressCount) "
                    f"VALUES ({values_str}) ON CONFLICT DO NOTHING;\n"
                )

        total_written += len(addresses)
        files_written += 1

        # Log progress with ETA for every settlement
        elapsed_time = time.time() - settlement_start_time
        avg_time_per_settlement = elapsed_time / processed_settlements
        remaining_settlements = total_settlements - processed_settlements
        eta_seconds = avg_time_per_settlement * remaining_settlements

        # Format ETA as HH:MM:SS or MM:SS
        if eta_seconds >= 3600:
            eta_str = f"{int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m"
        elif eta_seconds >= 60:
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
        else:
            eta_str = f"{int(eta_seconds)}s"

        progress_pct = (processed_settlements / total_settlements) * 100
        logger.info(
            f"[{processed_settlements}/{total_settlements}] {progress_pct:.1f}% | "
            f"{settlement_name}: {len(addresses):,} addresses | "
            f"ETA: {eta_str}"
        )

    # Close PostgreSQL file if it was opened (no longer used - CSV COPY is much faster)
    # if postgresql_file:
    #     postgresql_file.close()
    #     logger.info("PostgreSQL data.sql file closed")

    write_time = time.time() - write_start
    total_time = time.time() - start_time

    logger.info(
        f"✓ Export completed: {files_written} files, {total_written:,} addresses "
        f"in {total_time:.1f}s ({total_written / total_time:.0f} addr/sec)"
    )
    logger.info(f"  - Query: {fetch_time:.1f}s, Write: {write_time:.1f}s")
