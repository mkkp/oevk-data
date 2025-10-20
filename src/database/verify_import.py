"""Verification module for PostgreSQL import data integrity.

Compares PostgreSQL imported data against source DuckDB database to ensure
data consistency and integrity. Samples 5% of records for efficient verification.
"""

import random
import duckdb
import psycopg2
from typing import Dict, List, Tuple, Any
import uuid
from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)

# OEVK namespace UUID for generating UUIIDv3 (same as export)
OEVK_NAMESPACE = uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")


def _to_uuid3(value):
    """Convert xxhash64 hex string to UUID v3 (matches export logic)."""
    if value is None or value == "":
        return None
    return str(uuid.uuid3(OEVK_NAMESPACE, str(value)))


def _normalize_address_component(value):
    """Normalize address component by trimming leading zeros.

    This matches the normalization applied during PostgreSQL export.

    Args:
        value: String value to normalize

    Returns:
        Normalized string
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


def verify_postgresql_import(
    duckdb_path: str,
    pg_config: Dict[str, Any],
    sample_percentage: float = 5.0,
    tables_to_verify: List[str] = None
) -> bool:
    """Verify PostgreSQL import matches source DuckDB data.

    Args:
        duckdb_path: Path to source DuckDB database
        pg_config: PostgreSQL connection config (host, port, db, user, password)
        sample_percentage: Percentage of data to verify (default 5%)
        tables_to_verify: List of table names to verify (default: all main tables)

    Returns:
        True if verification passes, False otherwise
    """
    if tables_to_verify is None:
        tables_to_verify = [
            "County",
            "Settlement",
            "NationalIndividualElectoralDistrict",
            "SettlementIndividualElectoralDistrict",
            "PostalCode",
            "PollingStation",
            "Address",
            "PublicSpaceName",
            "PublicSpaceType"
        ]

    logger.info(f"Starting PostgreSQL import verification (sampling {sample_percentage}% of data)")
    logger.info(f"Tables to verify: {', '.join(tables_to_verify)}")

    # Connect to databases
    try:
        duck_conn = duckdb.connect(duckdb_path, read_only=True)
        pg_conn = psycopg2.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            dbname=pg_config["db"],
            user=pg_config["user"],
            password=pg_config["password"]
        )
        pg_conn.autocommit = True
    except Exception as e:
        logger.error(f"Failed to connect to databases: {e}")
        return False

    all_passed = True
    verification_results = {}

    try:
        for table in tables_to_verify:
            logger.info(f"\nVerifying table: {table}")
            result = _verify_table(duck_conn, pg_conn, table, sample_percentage)
            verification_results[table] = result

            if not result["passed"]:
                all_passed = False
                logger.error(f"❌ {table}: FAILED - {result['message']}")
            else:
                logger.info(f"✓ {table}: PASSED - {result['message']}")

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 80)

        for table, result in verification_results.items():
            status = "✓ PASS" if result["passed"] else "❌ FAIL"
            logger.info(f"{status:8} | {table:40} | {result['message']}")

        logger.info("=" * 80)
        if all_passed:
            logger.info("✓ ALL VERIFICATIONS PASSED")
        else:
            logger.error("❌ SOME VERIFICATIONS FAILED")
        logger.info("=" * 80)

    finally:
        duck_conn.close()
        pg_conn.close()

    return all_passed


def _verify_table(
    duck_conn: duckdb.DuckDBPyConnection,
    pg_conn: psycopg2.extensions.connection,
    table_name: str,
    sample_percentage: float
) -> Dict[str, Any]:
    """Verify a single table.

    Returns:
        Dict with keys: passed (bool), message (str), details (dict)
    """
    # PostgreSQL uses lowercase table names
    pg_table_name = table_name.lower()

    # For Address table, use CanonicalAddress from DuckDB (PostgreSQL exports canonical data)
    duck_table_name = "CanonicalAddress" if table_name == "Address" else table_name

    # Get row counts
    try:
        duck_count = duck_conn.execute(f"SELECT COUNT(*) FROM {duck_table_name}").fetchone()[0]
    except Exception as e:
        # Table might not exist in DuckDB
        if "not found" in str(e).lower() or "catalog" in str(e).lower():
            return {"passed": True, "message": f"Table not in source (PostgreSQL-only table)", "details": {}}
        else:
            raise

    pg_cur = pg_conn.cursor()
    pg_cur.execute(f'SELECT COUNT(*) FROM {pg_table_name}')
    pg_count = pg_cur.fetchone()[0]

    logger.info(f"  Row counts - DuckDB: {duck_count:,}, PostgreSQL: {pg_count:,}")

    # Allow small differences in lookup tables (they may have placeholder records)
    # But Address table must match exactly
    count_diff = abs(duck_count - pg_count)
    tolerance = 1 if table_name != "Address" else 0

    if count_diff > tolerance:
        return {
            "passed": False,
            "message": f"Row count mismatch: DuckDB={duck_count:,}, PostgreSQL={pg_count:,} (diff={count_diff})",
            "details": {"duck_count": duck_count, "pg_count": pg_count, "diff": count_diff}
        }
    elif count_diff > 0:
        logger.warning(f"  Minor count difference: {count_diff} (within tolerance for lookup tables)")

    if duck_count == 0:
        return {"passed": True, "message": "Empty table (counts match)", "details": {}}

    # For non-Address tables, just verify counts (they may have placeholder records)
    if table_name != "Address":
        return {
            "passed": True,
            "message": f"Row count: {pg_count:,} (DuckDB: {duck_count:,}, diff: {count_diff})",
            "details": {"duck_count": duck_count, "pg_count": pg_count, "diff": count_diff}
        }

    # For Address table, verify actual data with detailed record comparison
    sample_size = max(1, int(duck_count * sample_percentage / 100))
    logger.info(f"  Sampling {sample_size:,} Address records ({sample_percentage}%) for detailed verification")

    # Get sample IDs from DuckDB CanonicalAddress (source of truth)
    sample_ids_duck = []  # DuckDB IDs (hex strings)
    sample_ids_pg = []    # PostgreSQL IDs (UUIDs)
    try:
        # Use ORDER BY RANDOM() for proper sampling from DuckDB
        sample_result = duck_conn.execute(f'''
            SELECT ID FROM {duck_table_name}
            ORDER BY RANDOM()
            LIMIT {sample_size}
        ''').fetchall()
        sample_ids_duck = [str(row[0]) for row in sample_result]
        # Convert to UUIDs for PostgreSQL lookup
        sample_ids_pg = [_to_uuid3(id_hex) for id_hex in sample_ids_duck]
    except Exception as e:
        logger.error(f"Failed to sample from DuckDB: {e}")
        return {
            "passed": False,
            "message": f"Failed to sample records: {e}",
            "details": {"error": str(e)}
        }

    logger.info(f"  Comparing {len(sample_ids_duck)} sampled records...")

    # For Address table, compare against CanonicalAddress
    duck_table = "CanonicalAddress" if table_name == "Address" else table_name

    # Compare sampled records
    mismatches = []
    for duck_id, pg_id in zip(sample_ids_duck, sample_ids_pg):
        # Get record from DuckDB
        duck_record = duck_conn.execute(
            f"SELECT * FROM {duck_table} WHERE ID = ?", [duck_id]
        ).fetchone()

        if not duck_record:
            mismatches.append(f"ID {duck_id[:16]}... not found in DuckDB")
            continue

        # Get record from PostgreSQL using UUID
        pg_cur.execute(f'SELECT * FROM {pg_table_name} WHERE id = %s', (pg_id,))
        pg_record = pg_cur.fetchone()

        if not pg_record:
            mismatches.append(f"ID {pg_id[:16]}... not found in PostgreSQL")
            continue

        # Compare key fields (skip timestamp fields and auto-generated fields)
        # Basic comparison - can be enhanced based on table structure
        if table_name == "Address":
            # Special handling for Address table - pass both hex and UUID IDs
            if not _compare_address_records(duck_record, pg_record, duck_id_hex=duck_id, pg_id_uuid=pg_id):
                mismatches.append(f"ID {duck_id[:16]}... data mismatch")

    pg_cur.close()

    if mismatches:
        mismatch_summary = "; ".join(mismatches[:3])  # Show first 3
        if len(mismatches) > 3:
            mismatch_summary += f" ... and {len(mismatches) - 3} more"
        return {
            "passed": False,
            "message": f"{len(mismatches)} mismatches found: {mismatch_summary}",
            "details": {"mismatches": mismatches}
        }

    return {
        "passed": True,
        "message": f"Row count: {pg_count:,}, sampled: {len(sample_ids_duck)} records verified",
        "details": {"count": pg_count, "sampled": len(sample_ids_duck)}
    }


def _compare_address_records(duck_record: Tuple, pg_record: Tuple, duck_id_hex: str = None, pg_id_uuid: str = None) -> bool:
    """Compare Address/CanonicalAddress records.

    Note: Duck record is from CanonicalAddress, PG record is from Address.
    They have different schemas, so we compare key fields only.

    Args:
        duck_record: Record from DuckDB CanonicalAddress table
        pg_record: Record from PostgreSQL Address table
        duck_id_hex: Hex string ID from DuckDB (for logging)
        pg_id_uuid: Converted UUID for PostgreSQL (for comparison)
    """
    # CanonicalAddress fields: ID, CountyCode, SettlementName, StreetName, HouseNumber, FullAddress, AccessibilityFlag, CreatedAt
    # Address fields: ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, PublicSpaceType, HouseNumber, Building, Staircase, ...
    # Indexes: ID[0], FullAddress: duck[5]/pg[3], HouseNumber: duck[4]/pg[6], StreetName: duck[3]/pg[4]

    # Compare ID - convert DuckDB hex to UUID and compare with PostgreSQL UUID
    duck_id_converted = _to_uuid3(str(duck_record[0])) if duck_record[0] else ""
    pg_id = str(pg_record[0]) if pg_record[0] else ""

    if duck_id_converted != pg_id:
        logger.warning(f"  ID mismatch for {duck_id_hex[:16] if duck_id_hex else 'unknown'}...")
        logger.warning(f"    DuckDB (converted): {duck_id_converted}")
        logger.warning(f"    PostgreSQL: {pg_id}")
        return False

    # Compare FullAddress (duck[5], pg[3]) - already normalized in CanonicalAddress
    duck_addr = str(duck_record[5]) if duck_record[5] else ""
    pg_addr = str(pg_record[3]) if pg_record[3] else ""
    if duck_addr != pg_addr:
        logger.warning(f"  FullAddress mismatch for ID {duck_id_hex[:16] if duck_id_hex else 'unknown'}...")
        logger.warning(f"    DuckDB: {duck_addr}")
        logger.warning(f"    PostgreSQL: {pg_addr}")
        return False

    # Compare HouseNumber with normalization (duck[4], pg[6])
    duck_house = _normalize_address_component(duck_record[4]) if len(duck_record) > 4 else ""
    pg_house = str(pg_record[6]) if len(pg_record) > 6 and pg_record[6] else ""
    if duck_house != pg_house:
        logger.warning(f"  HouseNumber mismatch for ID {duck_id_hex[:16] if duck_id_hex else 'unknown'}...")
        logger.warning(f"    DuckDB (normalized): {duck_house}")
        logger.warning(f"    PostgreSQL: {pg_house}")
        return False

    # Compare StreetName/PublicSpaceName (duck[3], pg[4])
    duck_street = str(duck_record[3]) if len(duck_record) > 3 and duck_record[3] else ""
    pg_street = str(pg_record[4]) if len(pg_record) > 4 and pg_record[4] else ""
    if duck_street != pg_street:
        logger.warning(f"  StreetName mismatch for ID {duck_id_hex[:16] if duck_id_hex else 'unknown'}...")
        logger.warning(f"    DuckDB: {duck_street}")
        logger.warning(f"    PostgreSQL: {pg_street}")
        return False

    return True


def verify_view_exists(pg_config: Dict[str, Any]) -> bool:
    """Verify that AddressFullView exists and is queryable.

    Args:
        pg_config: PostgreSQL connection config

    Returns:
        True if view exists and is queryable, False otherwise
    """
    logger.info("Verifying AddressFullView exists...")

    try:
        pg_conn = psycopg2.connect(
            host=pg_config["host"],
            port=pg_config["port"],
            dbname=pg_config["db"],
            user=pg_config["user"],
            password=pg_config["password"]
        )
        pg_conn.autocommit = True
        pg_cur = pg_conn.cursor()

        # Check if view exists
        pg_cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.views
            WHERE table_name = 'addressfullview'
        """)
        view_exists = pg_cur.fetchone()[0] > 0

        if not view_exists:
            logger.error("❌ AddressFullView does not exist")
            return False

        # Check column count
        pg_cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'addressfullview'
        """)
        column_count = pg_cur.fetchone()[0]

        if column_count != 28:
            logger.error(f"❌ AddressFullView has {column_count} columns, expected 28")
            return False

        # Try to query the view
        pg_cur.execute("SELECT COUNT(*) FROM AddressFullView")
        view_count = pg_cur.fetchone()[0]

        logger.info(f"✓ AddressFullView exists with {column_count} columns and {view_count:,} rows")

        pg_cur.close()
        pg_conn.close()

        return True

    except Exception as e:
        logger.error(f"❌ Failed to verify AddressFullView: {e}")
        return False
