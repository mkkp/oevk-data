"""Export canonical addresses with UUID v3 conversion and clean formatting."""

import os
import uuid
import csv
import duckdb
from typing import List

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
    """Clean fields that contain only zeros - treat as empty string.

    Examples:
        '0' -> ''
        '00' -> ''
        '000' -> ''
        '01' -> '01' (kept as-is)
        '0A' -> '0A' (kept as-is)
        '' -> ''
        None -> ''
    """
    if value is None or value == "" or value == "NULL":
        return ""

    # Check if string contains only zeros
    if (
        isinstance(value, str)
        and value.strip()
        and all(c == "0" for c in value.strip())
    ):
        return ""

    return value


def format_id_list(id_list_str):
    """Convert list of IDs to comma-separated UUIDs without brackets."""
    if not id_list_str or id_list_str == "NULL" or id_list_str == "[]":
        return None

    # Remove brackets if present
    clean_str = id_list_str.strip("[]")
    if not clean_str:
        return None

    # Split and convert each ID to UUID
    ids = [id.strip() for id in clean_str.split(",") if id.strip()]
    uuids = [to_uuid3(id) for id in ids if id and id != "NULL"]

    return ",".join(uuids) if uuids else None


def export_canonical_addresses_with_uuid(
    db_connection: duckdb.DuckDBPyConnection, export_dir: str, run_tag: str
) -> None:
    """Export canonical addresses with UUID v3 conversion.

    Exports partitioned by settlement in same directory as OriginalAddress.
    Uses UUID v3 with 'oevk' namespace for all IDs.
    Formats reference lists as comma-separated values without brackets.

    Args:
        db_connection: An active DuckDB connection.
        export_dir: The directory to save CSV files.
        run_tag: The run tag to include in filenames.
    """
    logger.info(f"Exporting canonical addresses with UUID v3 to {export_dir}")

    # Create Address directory (same as OriginalAddress)
    address_dir = os.path.join(export_dir, f"{run_tag}_Address")
    os.makedirs(address_dir, exist_ok=True)

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

        # Query canonical addresses with same structure as original addresses
        rows = db_connection.execute(f"""
            SELECT
                ca.ID as ID,
                MIN(a.Sequence) as Sequence,
                MIN(a.OriginalOrder) as OriginalOrder,
                ca.FullAddress,
                ca.StreetName as PublicSpaceName,
                (SELECT DISTINCT a2.PublicSpaceType FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as PublicSpaceType,
                ca.HouseNumber,
                (SELECT DISTINCT a2.Building FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as Building,
                (SELECT DISTINCT a2.Staircase FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as Staircase,
                (SELECT DISTINCT PIRCode FROM AddressPIRCodes WHERE CanonicalAddressID = ca.ID LIMIT 1) as PostalCode_ID,
                (SELECT DISTINCT PollingStationID FROM AddressPollingStations WHERE CanonicalAddressID = ca.ID LIMIT 1) as PollingStation_ID,
                (SELECT DISTINCT a2.SettlementIndividualElectoralDistrict_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as SettlementIndividualElectoralDistrict_ID,
                (SELECT DISTINCT a2.County_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as County_ID,
                (SELECT DISTINCT a2.Settlement_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as Settlement_ID,
                (SELECT DISTINCT a2.NationalIndividualElectoralDistrict_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as NationalIndividualElectoralDistrict_ID,
                COUNT(DISTINCT am.OriginalAddressID) as OriginalAddressCount
            FROM CanonicalAddress ca
            LEFT JOIN AddressMapping am ON ca.ID = am.CanonicalAddressID
            LEFT JOIN Address a ON am.OriginalAddressID = a.ID
            WHERE ca.SettlementName = '{settlement_name}'
            GROUP BY ca.ID, ca.FullAddress, ca.StreetName, ca.HouseNumber
            ORDER BY ca.FullAddress
        """).fetchall()

        # Write CSV with UUID conversion - same structure as OriginalAddress
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Write header - same as OriginalAddress plus OriginalAddressCount
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

            # Write data rows with UUID conversion
            for row in rows:
                (
                    ca_id,
                    seq,
                    orig_order,
                    full_addr,
                    public_space_name,
                    public_space_type,
                    house_num,
                    building,
                    staircase,
                    postal_code_id,
                    polling_station_id,
                    tevk_id,
                    county_id,
                    settlement_id,
                    oevk_id,
                    orig_count,
                ) = row

                writer.writerow(
                    [
                        to_uuid3(ca_id),
                        seq,
                        orig_order,
                        full_addr,
                        public_space_name or "",
                        public_space_type or "",
                        house_num,
                        clean_zero_only_field(building),
                        clean_zero_only_field(staircase),
                        to_uuid3(postal_code_id),
                        to_uuid3(polling_station_id),
                        to_uuid3(tevk_id),
                        to_uuid3(county_id),
                        to_uuid3(settlement_id),
                        to_uuid3(oevk_id),
                        orig_count,
                    ]
                )

        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logger.info(f"Successfully exported {settlement_name} ({file_size} bytes)")
        else:
            logger.error(f"Failed to export {settlement_name}")

    # Also export consolidated canonical addresses
    consolidated_path = os.path.join(export_dir, f"{run_tag}_CanonicalAddress.csv")
    logger.info(f"Exporting consolidated canonical addresses to {consolidated_path}")

    rows = db_connection.execute("""
        SELECT
            ca.ID as ID,
            MIN(a.Sequence) as Sequence,
            MIN(a.OriginalOrder) as OriginalOrder,
            ca.FullAddress,
            ca.StreetName as PublicSpaceName,
            (SELECT DISTINCT a2.PublicSpaceType FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as PublicSpaceType,
            ca.HouseNumber,
            (SELECT DISTINCT a2.Building FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as Building,
            (SELECT DISTINCT a2.Staircase FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as Staircase,
            (SELECT DISTINCT PIRCode FROM AddressPIRCodes WHERE CanonicalAddressID = ca.ID LIMIT 1) as PostalCode_ID,
            (SELECT DISTINCT PollingStationID FROM AddressPollingStations WHERE CanonicalAddressID = ca.ID LIMIT 1) as PollingStation_ID,
            (SELECT DISTINCT a2.SettlementIndividualElectoralDistrict_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as SettlementIndividualElectoralDistrict_ID,
            (SELECT DISTINCT a2.County_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as County_ID,
            (SELECT DISTINCT a2.Settlement_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as Settlement_ID,
            (SELECT DISTINCT a2.NationalIndividualElectoralDistrict_ID FROM Address a2 JOIN AddressMapping am2 ON a2.ID = am2.OriginalAddressID WHERE am2.CanonicalAddressID = ca.ID LIMIT 1) as NationalIndividualElectoralDistrict_ID,
            COUNT(DISTINCT am.OriginalAddressID) as OriginalAddressCount
        FROM CanonicalAddress ca
        LEFT JOIN AddressMapping am ON ca.ID = am.CanonicalAddressID
        LEFT JOIN Address a ON am.OriginalAddressID = a.ID
        GROUP BY ca.ID, ca.FullAddress, ca.StreetName, ca.HouseNumber
        ORDER BY ca.FullAddress
    """).fetchall()

    with open(consolidated_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write header - same as OriginalAddress plus OriginalAddressCount
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

        # Write data rows with UUID conversion
        for row in rows:
            (
                ca_id,
                seq,
                orig_order,
                full_addr,
                public_space_name,
                public_space_type,
                house_num,
                building,
                staircase,
                postal_code_id,
                polling_station_id,
                tevk_id,
                county_id,
                settlement_id,
                oevk_id,
                orig_count,
            ) = row

            writer.writerow(
                [
                    to_uuid3(ca_id),
                    seq,
                    orig_order,
                    full_addr,
                    public_space_name or "",
                    public_space_type or "",
                    house_num,
                    clean_zero_only_field(building),
                    clean_zero_only_field(staircase),
                    to_uuid3(postal_code_id),
                    to_uuid3(polling_station_id),
                    to_uuid3(tevk_id),
                    to_uuid3(county_id),
                    to_uuid3(settlement_id),
                    to_uuid3(oevk_id),
                    orig_count,
                ]
            )

    if os.path.exists(consolidated_path):
        count = len(rows)
        logger.info(
            f"Successfully exported {count} canonical addresses ({os.path.getsize(consolidated_path)} bytes)"
        )
    else:
        logger.error("Failed to export canonical addresses")

    logger.info("Canonical address export completed")
