"""Export logic for generating CSV files from target tables."""

import os
import duckdb

from utils.pipeline_logging import get_logger

logger = get_logger(__name__)


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
    """Exports Address table partitioned by Settlement.

    Args:
        db_connection: An active DuckDB connection.
        export_dir: The directory to save partitioned CSV files.
        run_tag: The run tag to include in directory name.
    """
    logger.info(f"Exporting addresses partitioned by settlement to {export_dir}")

    # Create Address directory
    address_dir = os.path.join(export_dir, f"{run_tag}_Address")
    os.makedirs(address_dir, exist_ok=True)

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
        filename = f"Address_{settlement_code}_{safe_name}.csv"
        file_path = os.path.join(address_dir, filename)

        logger.info(f"Exporting addresses for {settlement_name} to {file_path}")

        # Export addresses for this settlement
        db_connection.execute(f"""
            COPY (
                SELECT a.* 
                FROM Address a 
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

    # Also export a consolidated Address.csv file
    consolidated_path = os.path.join(export_dir, f"{run_tag}_Address.csv")
    logger.info(f"Exporting consolidated addresses to {consolidated_path}")

    db_connection.execute(f"""
        COPY Address TO '{consolidated_path}' (HEADER, DELIMITER ',')
    """)

    if os.path.exists(consolidated_path):
        logger.info(
            f"Successfully exported consolidated addresses ({os.path.getsize(consolidated_path)} bytes)"
        )
    else:
        logger.error("Failed to export consolidated addresses")

    logger.info("Address export completed")


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
