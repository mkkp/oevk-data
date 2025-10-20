"""PostgreSQL import verification and dump creation."""

import os
import subprocess
import gzip
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from src.utils.pipeline_logging import get_logger
from src.utils.docker_postgresql import DockerPostgreSQLManager

logger = get_logger(__name__)


def verify_and_dump_postgresql(
    exports_dir: str,
    container_name: str = "oevk-verify",
    cleanup: bool = True,
) -> Optional[str]:
    """Verify PostgreSQL import and create gzipped dump.

    This function:
    1. Creates a temporary Docker PostgreSQL container
    2. Imports schema.sql and data.sql
    3. Verifies the import by checking row counts
    4. Creates a pg_dump and compresses it with gzip
    5. Cleans up the temporary container

    Args:
        exports_dir: Directory containing schema.sql and data.sql
        container_name: Name for the temporary Docker container
        cleanup: Whether to remove the container after completion

    Returns:
        Path to the created gzipped dump file, or None if failed

    Raises:
        FileNotFoundError: If schema.sql or data.sql not found
        RuntimeError: If verification fails
    """
    exports_path = Path(exports_dir)
    schema_file = exports_path / "schema.sql"
    data_file = exports_path / "data.sql"

    # Validate input files
    if not schema_file.exists():
        raise FileNotFoundError(f"schema.sql not found in {exports_dir}")

    if not data_file.exists():
        raise FileNotFoundError(f"data.sql not found in {exports_dir}")

    logger.info("=" * 80)
    logger.info("PostgreSQL Import Verification and Dump Creation")
    logger.info("=" * 80)

    # Initialize Docker manager
    manager = DockerPostgreSQLManager(container_name=container_name)
    dump_file_path = None

    try:
        # Step 1: Create container
        logger.info("Step 1/5: Creating Docker PostgreSQL container...")
        manager.create_container()

        # Step 2: Wait for PostgreSQL to be ready
        logger.info("Step 2/5: Waiting for PostgreSQL to be ready...")
        if not manager.wait_for_ready(timeout=30):
            raise RuntimeError("PostgreSQL failed to become ready")

        # Step 3: Import schema and data
        logger.info("Step 3/5: Importing schema and data...")
        _import_sql_files(manager, schema_file, data_file)

        # Step 4: Verify import
        logger.info("Step 4/5: Verifying import...")
        row_count = _verify_import(manager)
        logger.info(f"Verification successful: {row_count:,} total rows imported")

        # Step 5: Create gzipped dump
        logger.info("Step 5/5: Creating gzipped database dump...")
        dump_file_path = _create_gzipped_dump(manager, exports_path)
        logger.info(f"Dump created: {dump_file_path}")

        logger.info("=" * 80)
        logger.info("✅ PostgreSQL verification and dump creation completed successfully")
        logger.info("=" * 80)

        return str(dump_file_path)

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise

    finally:
        if cleanup:
            logger.info("Cleaning up temporary container...")
            manager.stop_and_remove_container()


def _optimize_for_import(container_name: str, conn_info: dict) -> None:
    """Apply PostgreSQL performance optimizations for bulk import.

    These settings sacrifice durability for speed during import.
    They are safe for temporary containers used only for verification.

    Args:
        container_name: Docker container name
        conn_info: Connection information
    """
    optimizations = [
        # Disable fsync for faster writes (safe for temporary container)
        "ALTER SYSTEM SET fsync = 'off';",
        # Increase work memory for sorting/hashing
        "ALTER SYSTEM SET work_mem = '256MB';",
        # Increase maintenance work memory for index creation
        "ALTER SYSTEM SET maintenance_work_mem = '512MB';",
        # Disable autovacuum during bulk load
        "ALTER SYSTEM SET autovacuum = 'off';",
        # Increase checkpoint segments
        "ALTER SYSTEM SET max_wal_size = '2GB';",
        # Increase shared buffers
        "ALTER SYSTEM SET shared_buffers = '256MB';",
        # Reload configuration
        "SELECT pg_reload_conf();",
    ]

    optimization_sql = "\n".join(optimizations)

    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                conn_info["user"],
                "-d",
                conn_info["database"],
                "-c",
                optimization_sql,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info("  ✓ Performance optimizations applied")
        else:
            logger.warning(f"  ⚠ Could not apply optimizations: {result.stderr}")
    except Exception as e:
        logger.warning(f"  ⚠ Could not apply optimizations: {e}")


def _import_sql_files(
    manager: DockerPostgreSQLManager,
    schema_file: Path,
    data_file: Path,
) -> None:
    """Import SQL files into PostgreSQL container.

    Args:
        manager: Docker PostgreSQL manager
        schema_file: Path to schema.sql
        data_file: Path to data.sql

    Raises:
        RuntimeError: If import fails
    """
    conn_info = manager.get_connection_info()

    # Apply performance optimizations before import
    logger.info("Applying performance optimizations for import...")
    _optimize_for_import(manager.container_name, conn_info)

    # Import schema
    logger.info("Importing schema.sql...")
    _execute_sql_file(manager.container_name, schema_file, conn_info)

    # Import data
    logger.info("Importing data.sql (this may take 10-20 minutes for large datasets)...")
    _execute_sql_file(manager.container_name, data_file, conn_info, is_data=True)


def _execute_sql_file(
    container_name: str,
    sql_file: Path,
    conn_info: dict,
    is_data: bool = False,
) -> None:
    """Execute SQL file using psql in Docker container.

    Args:
        container_name: Docker container name
        sql_file: Path to SQL file
        conn_info: Connection information
        is_data: If True, use longer timeout for large data imports

    Raises:
        RuntimeError: If execution fails
    """
    file_size_mb = sql_file.stat().st_size / (1024 * 1024)
    logger.info(f"  File: {sql_file.name} ({file_size_mb:.1f} MB)")

    # Use longer timeout for large data files (30 minutes)
    exec_timeout = 1800 if is_data else 600
    copy_timeout = 120 if is_data else 60

    try:
        # Copy SQL file into container
        logger.info(f"  Copying {sql_file.name} to container...")
        subprocess.run(
            [
                "docker",
                "cp",
                str(sql_file),
                f"{container_name}:/tmp/{sql_file.name}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=copy_timeout,
        )

        # Execute SQL file
        logger.info(f"  Executing {sql_file.name}...")
        if is_data:
            logger.info(f"  (timeout: {exec_timeout // 60} minutes)")

        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                conn_info["user"],
                "-d",
                conn_info["database"],
                "-f",
                f"/tmp/{sql_file.name}",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            capture_output=True,
            text=True,
            timeout=exec_timeout,
        )

        if result.returncode != 0:
            logger.error(f"psql stderr: {result.stderr}")
            raise RuntimeError(f"Failed to execute {sql_file.name}")

        logger.info(f"  ✓ {sql_file.name} imported successfully")

    except subprocess.TimeoutExpired:
        timeout_min = exec_timeout // 60
        raise RuntimeError(f"Import of {sql_file.name} timed out after {timeout_min} minutes")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to copy {sql_file.name}: {e.stderr}")


def _verify_import(manager: DockerPostgreSQLManager) -> int:
    """Verify import by checking row counts.

    Args:
        manager: Docker PostgreSQL manager

    Returns:
        Total row count across all tables

    Raises:
        RuntimeError: If verification fails
    """
    conn_info = manager.get_connection_info()

    # Query to count rows in all tables
    count_query = """
        SELECT
            schemaname,
            relname as tablename,
            n_live_tup as row_count
        FROM pg_stat_user_tables
        ORDER BY n_live_tup DESC;
    """

    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                manager.container_name,
                "psql",
                "-U",
                conn_info["user"],
                "-d",
                conn_info["database"],
                "-t",  # Tuples only
                "-A",  # Unaligned output
                "-F",
                "|",  # Field separator
                "-c",
                count_query,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        # Parse output
        total_rows = 0
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 3:
                    table_name = parts[1]
                    row_count = int(parts[2])
                    total_rows += row_count
                    logger.info(f"  {table_name}: {row_count:,} rows")

        if total_rows == 0:
            raise RuntimeError("No rows found in database - import may have failed")

        return total_rows

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to verify import: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Verification query timed out")


def _create_gzipped_dump(
    manager: DockerPostgreSQLManager,
    output_dir: Path,
) -> Path:
    """Create gzipped pg_dump of the database.

    Args:
        manager: Docker PostgreSQL manager
        output_dir: Directory to save the dump file

    Returns:
        Path to the created dump file

    Raises:
        RuntimeError: If dump creation fails
    """
    conn_info = manager.get_connection_info()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_filename = f"oevk_db_{timestamp}.sql.gz"
    dump_path = output_dir / dump_filename

    logger.info(f"Creating dump: {dump_filename}")

    try:
        # Create pg_dump (plain SQL format)
        result = subprocess.run(
            [
                "docker",
                "exec",
                manager.container_name,
                "pg_dump",
                "-U",
                conn_info["user"],
                "-d",
                conn_info["database"],
                "--clean",  # Add DROP statements
                "--if-exists",  # Use IF EXISTS for drops
                "--no-owner",  # Don't output ownership commands
                "--no-privileges",  # Don't output privilege commands
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minutes
        )

        # Compress with gzip
        with gzip.open(dump_path, "wt", encoding="utf-8") as f:
            f.write(result.stdout)

        file_size_mb = dump_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Dump size: {file_size_mb:.1f} MB (compressed)")

        return dump_path

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"pg_dump failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("pg_dump timed out")
    except Exception as e:
        raise RuntimeError(f"Failed to create gzipped dump: {e}")
