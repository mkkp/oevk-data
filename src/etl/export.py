"""Export logic for generating CSV files from target tables."""

import os
import uuid
import csv
import duckdb

from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)

# OEVK namespace UUID for generating UUIDv3
OEVK_NAMESPACE = uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")


def to_uuid3(value):
    """Convert a value to UUID v3 using OEVK namespace."""
    if value is None or value == "":
        return None
    return str(uuid.uuid3(OEVK_NAMESPACE, str(value)))


def export_tables_to_csv(
    db_connection: duckdb.DuckDBPyConnection, export_dir: str, run_tag: str
) -> None:
    """Exports all target tables (except Address) to CSV files.

    Args:
        db_connection: An active DuckDB connection.
        export_dir: The directory to save CSV files.
        run_tag: The run tag to include in filenames.
    """
    logger.info(f"Exporting tables to CSV in {export_dir}")

    # Create export directory if it doesn't exist
    os.makedirs(export_dir, exist_ok=True)

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

    for table in tables:
        export_table_to_csv(db_connection, table, export_dir, run_tag)

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


def create_release_symlinks(export_dir: str, run_tag: str, db_path: str) -> None:
    """Create symlinks for release system compatibility.

    The release validation system expects specific file names without timestamps.
    This function creates symlinks from the timestamped files to the expected names.

    Args:
        export_dir: The directory containing exported CSV files.
        run_tag: The run tag used in filenames.
        db_path: Path to the database file.
    """
    logger.info("Creating release symlinks for validation compatibility")

    # Required files for release validation
    required_files = {
        "addresses.csv": f"{run_tag}_Address.csv",
        "settlements.csv": f"{run_tag}_Settlement.csv",
        "counties.csv": f"{run_tag}_County.csv",
        "PublicSpaceName.csv": f"{run_tag}_PublicSpaceName.csv",
        "PublicSpaceType.csv": f"{run_tag}_PublicSpaceType.csv",
        "SettlementPublicSpaces.csv": f"{run_tag}_SettlementPublicSpaces.csv",
        "database.duckdb": db_path,
    }

    symlinks_created = 0

    for symlink_name, source_file in required_files.items():
        symlink_path = os.path.join(export_dir, symlink_name)

        # For database file, use the actual database path
        if symlink_name == "database.duckdb":
            source_path = source_file
            # Use relative path for database symlink
            source_relative = os.path.relpath(source_path, export_dir)
        else:
            source_path = os.path.join(export_dir, source_file)
            # Use relative path for CSV files (just the filename)
            source_relative = source_file

        # Remove existing symlink if it exists
        if os.path.exists(symlink_path) or os.path.islink(symlink_path):
            try:
                os.remove(symlink_path)
                logger.debug(f"Removed existing symlink: {symlink_path}")
            except OSError as e:
                logger.warning(f"Failed to remove existing symlink {symlink_path}: {e}")

        # Create symlink if source file exists
        if os.path.exists(source_path):
            try:
                # Use relative paths for symlinks to make them portable
                os.symlink(source_relative, symlink_path)
                logger.info(f"Created symlink: {symlink_name} -> {source_relative}")
                symlinks_created += 1
            except OSError as e:
                logger.error(f"Failed to create symlink {symlink_name}: {e}")
        else:
            logger.warning(
                f"Source file not found for symlink {symlink_name}: {source_path}"
            )

    logger.info(f"Created {symlinks_created} symlinks for release compatibility")
