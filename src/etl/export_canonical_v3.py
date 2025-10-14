"""Export canonical addresses with UUID v3 - optimized single-query approach."""

import os
import uuid
import csv
import duckdb
import time
import shutil
import glob
from collections import defaultdict

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

    rows = db_connection.execute("""
        WITH address_details AS (
            SELECT
                am.CanonicalAddressID,
                a.PublicSpaceType,
                a.Building,
                a.Staircase,
                a.SettlementIndividualElectoralDistrict_ID,
                a.County_ID,
                a.Settlement_ID,
                a.NationalIndividualElectoralDistrict_ID,
                ROW_NUMBER() OVER (PARTITION BY am.CanonicalAddressID ORDER BY a.ID) as rn
            FROM AddressMapping am
            JOIN Address a ON am.OriginalAddressID = a.ID
        ),
        postal_codes AS (
            SELECT DISTINCT
                CanonicalAddressID,
                FIRST_VALUE(PIRCode) OVER (PARTITION BY CanonicalAddressID ORDER BY PIRCode) as PIRCode
            FROM AddressPIRCodes
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
            ca.HouseNumber,
            ad.Building,
            ad.Staircase,
            COALESCE(pc.PIRCode, '00000000-0000-0000-0000-000000000000') as PostalCode_ID,
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
                 ad.NationalIndividualElectoralDistrict_ID, pc.PIRCode, ps.PollingStationID
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

    # Open PostgreSQL data.sql file if needed (append mode)
    postgresql_file = None
    if "postgresql" in formats:
        data_path = os.path.join(export_dir, "data.sql")
        postgresql_file = open(data_path, "a", encoding="utf-8")
        postgresql_file.write("\n-- Canonical Addresses (deduplicated)\n")
        postgresql_file.write("-- Table: Address\n\n")
        logger.info("Appending canonical addresses to data.sql...")

    # Write CSV files if requested
    if "csv" in formats:
        logger.info("Writing CSV files...")

    for settlement_name, addresses in settlement_data.items():
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

        # Write PostgreSQL INSERT statements if requested
        if postgresql_file:
            for row in addresses:
                # Helper function to format SQL values
                def format_sql_value(value, is_uuid=False):
                    if is_uuid:
                        uuid_val = to_uuid3(value)
                        return f"'{uuid_val}'" if uuid_val else "NULL"
                    elif value is None or value == "":
                        return "NULL"
                    elif isinstance(value, str):
                        return f"'{value.replace("'", "''")}'"
                    else:
                        return str(value)

                # Format values for INSERT statement
                values = [
                    format_sql_value(row[0], is_uuid=True),  # ID
                    format_sql_value(row[2]),  # Sequence
                    format_sql_value(row[3]),  # OriginalOrder
                    format_sql_value(row[4]),  # FullAddress
                    format_sql_value(row[5] or ""),  # PublicSpaceName
                    format_sql_value(row[6] or ""),  # PublicSpaceType
                    format_sql_value(row[7]),  # HouseNumber
                    format_sql_value(clean_zero_only_field(row[8])),  # Building
                    format_sql_value(clean_zero_only_field(row[9])),  # Staircase
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

        # Log progress every 500 settlements
        if files_written % 500 == 0:
            logger.info(
                f"Progress: {files_written}/{len(settlement_data)} files, {total_written:,} addresses"
            )

    # Close PostgreSQL file if it was opened
    if postgresql_file:
        postgresql_file.close()
        logger.info("PostgreSQL data.sql file closed")

    write_time = time.time() - write_start
    total_time = time.time() - start_time

    logger.info(
        f"✓ Export completed: {files_written} files, {total_written:,} addresses "
        f"in {total_time:.1f}s ({total_written / total_time:.0f} addr/sec)"
    )
    logger.info(f"  - Query: {fetch_time:.1f}s, Write: {write_time:.1f}s")
