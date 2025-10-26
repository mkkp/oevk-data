"""PostgreSQL import verification and dump creation."""

import os
import subprocess
import gzip
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from src.utils.pipeline_logging import get_logger
from src.utils.docker_postgresql import DockerPostgreSQLManager
from src.utils.config import Config

logger = get_logger(__name__)


def _detect_run_tag(exports_path: Path) -> str:
    """Auto-detect run tag from CSV filenames in exports directory.

    Args:
        exports_path: Path to exports directory

    Returns:
        Run tag (timestamp string like '20251026_130300')

    Raises:
        RuntimeError: If no CSV files found or run tag cannot be detected
    """
    # Look for CSV files with pattern YYYYMMDD_HHMMSS_TableName.csv
    csv_files = list(exports_path.glob("*_*.csv"))

    if not csv_files:
        # Fallback: use current timestamp
        logger.warning("No CSV files found for run tag detection, using current timestamp")
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    # Extract run tag from first CSV filename
    # Example: 20251026_130300_County.csv -> 20251026_130300
    filename = csv_files[0].stem  # Remove .csv extension
    parts = filename.split("_")

    if len(parts) >= 3:
        # YYYYMMDD_HHMMSS_TableName format
        run_tag = f"{parts[0]}_{parts[1]}"
        logger.info(f"Detected run tag from CSV files: {run_tag}")
        return run_tag

    # Fallback: use current timestamp
    logger.warning(f"Could not parse run tag from filename: {filename}, using current timestamp")
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def verify_and_dump_postgresql(
    exports_dir: str,
    container_name: str = "oevk-verify",
    cleanup: bool = True,
    run_tag: Optional[str] = None,
) -> Optional[str]:
    """Verify PostgreSQL import and create gzipped dump.

    This function:
    1. Creates a temporary Docker PostgreSQL container
    2. Imports schema.sql and CSV files using import_postgresql.sql
    3. Verifies the import by checking row counts
    4. Creates a pg_dump and compresses it with gzip
    5. Cleans up the temporary container

    Args:
        exports_dir: Directory containing schema.sql and PostgreSQL CSV files
        container_name: Name for the temporary Docker container
        cleanup: Whether to remove the container after completion
        run_tag: Pipeline run tag (timestamp) for dump filename. If None, auto-detected from CSV files

    Returns:
        Path to the created gzipped dump file, or None if failed

    Raises:
        FileNotFoundError: If schema.sql or import_postgresql.sql not found
        RuntimeError: If verification fails
    """
    exports_path = Path(exports_dir)
    schema_file = exports_path / "schema.sql"
    import_file = exports_path / "import_postgresql.sql"
    postgresql_dir = exports_path / "postgresql"

    # Auto-detect run_tag from CSV filenames if not provided
    if run_tag is None:
        run_tag = _detect_run_tag(exports_path)

    # Validate input files
    if not schema_file.exists():
        raise FileNotFoundError(f"schema.sql not found in {exports_dir}")

    if not import_file.exists():
        raise FileNotFoundError(f"import_postgresql.sql not found in {exports_dir}")

    if not postgresql_dir.exists() or not postgresql_dir.is_dir():
        raise FileNotFoundError(f"postgresql/ directory not found in {exports_dir}")

    logger.info("=" * 80)
    logger.info("PostgreSQL Import Verification and Dump Creation")
    logger.info("=" * 80)

    # Get PostGIS configuration
    config = Config()
    use_postgis = config.get("postgresql.use_postgis", True)

    # Initialize Docker manager
    manager = DockerPostgreSQLManager(container_name=container_name, use_postgis=use_postgis)
    dump_file_path = None

    try:
        # Step 1: Create container
        logger.info("Step 1/5: Creating Docker PostgreSQL container...")
        manager.create_container()

        # Step 2: Wait for PostgreSQL to be ready
        logger.info("Step 2/5: Waiting for PostgreSQL to be ready...")
        if not manager.wait_for_ready(timeout=30):
            raise RuntimeError("PostgreSQL failed to become ready")

        # Step 3: Import schema and CSV data
        logger.info("Step 3/5: Importing schema and CSV data...")
        _import_schema_and_csv(manager, schema_file, import_file, postgresql_dir)

        # Step 4: Verify import
        logger.info("Step 4/5: Verifying import...")
        row_count = _verify_import(manager)
        logger.info(f"Verification successful: {row_count:,} total rows imported")

        # Step 5: Create gzipped dump
        logger.info("Step 5/5: Creating gzipped database dump...")
        dump_file_path = _create_gzipped_dump(manager, exports_path, run_tag)
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
        ("fsync", "off"),
        ("work_mem", "256MB"),
        ("maintenance_work_mem", "1GB"),
        ("autovacuum", "off"),
        ("max_wal_size", "4GB"),
        ("shared_buffers", "512MB"),
        ("synchronous_commit", "off"),
        ("full_page_writes", "off"),
        ("checkpoint_timeout", "30min"),
    ]

    try:
        # Apply each optimization individually
        for param, value in optimizations:
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
                    f"ALTER SYSTEM SET {param} = '{value}';",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.debug(f"  Could not set {param}: {result.stderr.strip()}")

        # Restart PostgreSQL to apply settings
        logger.info("  Restarting PostgreSQL to apply optimizations...")
        subprocess.run(
            ["docker", "restart", container_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        # Wait for PostgreSQL to be ready again
        import time
        time.sleep(3)

        # Verify ready
        max_attempts = 10
        for _ in range(max_attempts):
            result = subprocess.run(
                ["docker", "exec", container_name, "pg_isready", "-U", conn_info["user"]],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                break
            time.sleep(1)

        logger.info("  ✓ Performance optimizations applied and PostgreSQL restarted")
    except Exception as e:
        logger.warning(f"  ⚠ Could not apply optimizations: {e}")


def _import_schema_and_csv(
    manager: DockerPostgreSQLManager,
    schema_file: Path,
    import_file: Path,
    postgresql_dir: Path,
) -> None:
    """Import schema and CSV files into PostgreSQL container.

    Args:
        manager: Docker PostgreSQL manager
        schema_file: Path to schema.sql
        import_file: Path to import_postgresql.sql
        postgresql_dir: Path to postgresql/ directory containing CSV files

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

    # Copy CSV files to container
    logger.info("Copying PostgreSQL CSV files to container...")
    _copy_csv_directory(manager.container_name, postgresql_dir)

    # Create Docker-compatible import script (with /tmp/postgresql paths)
    logger.info("Creating Docker-compatible import script...")
    docker_import_file = _create_docker_import_script(import_file)

    # Import data using CSV COPY commands
    logger.info("Importing CSV data (this may take 2-5 minutes for large datasets)...")
    _execute_sql_file(manager.container_name, docker_import_file, conn_info, is_data=True)

    # Clean up temporary Docker import script
    if docker_import_file.exists():
        docker_import_file.unlink()


def _create_docker_import_script(import_file: Path) -> Path:
    """Create Docker-compatible import script with /tmp/postgresql paths.

    The original import script uses absolute host paths like:
    /Users/robson/Project/oevk-data/exports/postgresql/County.csv

    This function creates a modified version with Docker container paths:
    /tmp/postgresql/County.csv

    Args:
        import_file: Path to original import_postgresql.sql

    Returns:
        Path to Docker-compatible import script

    Raises:
        RuntimeError: If script creation fails
    """
    import re

    docker_import_file = import_file.parent / "import_postgresql_docker.sql"

    try:
        # Read original import script
        with open(import_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace all absolute paths with Docker container paths
        # Pattern: FROM '/path/to/exports/postgresql/File.csv'
        # Replace: FROM '/tmp/postgresql/File.csv'
        content = re.sub(
            r"FROM '.*?/postgresql/([^']+)'",
            r"FROM '/tmp/postgresql/\1'",
            content
        )

        # Write Docker-compatible script
        with open(docker_import_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"  ✓ Created Docker import script: {docker_import_file.name}")
        return docker_import_file

    except Exception as e:
        raise RuntimeError(f"Failed to create Docker import script: {e}")


def _copy_csv_directory(
    container_name: str,
    postgresql_dir: Path,
) -> None:
    """Copy postgresql/ directory to container for CSV import.

    Args:
        container_name: Docker container name
        postgresql_dir: Path to postgresql/ directory containing CSV files

    Raises:
        RuntimeError: If copy fails
    """
    try:
        # Copy entire postgresql/ directory to container's /tmp
        logger.info(f"  Copying {postgresql_dir.name}/ directory...")
        subprocess.run(
            [
                "docker",
                "cp",
                str(postgresql_dir),
                f"{container_name}:/tmp/postgresql",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minutes for large CSV files
        )

        # Count CSV files
        csv_count = len(list(postgresql_dir.glob("*.csv")))
        logger.info(f"  ✓ Copied {csv_count} CSV files to container")

    except subprocess.TimeoutExpired:
        raise RuntimeError("Copying CSV directory timed out")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to copy CSV directory: {e.stderr}")


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

    # Use longer timeout for large data files (90 minutes for import with 3.3M rows + PostGIS geometry population)
    exec_timeout = 5400 if is_data else 600
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
            logger.info("  Progress will be shown below:")
            # Show progress in real-time for data import
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
                timeout=exec_timeout,
            )
        else:
            # Capture output for schema files
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
    run_tag: str,
) -> Path:
    """Create gzipped pg_dump of the database.

    Args:
        manager: Docker PostgreSQL manager
        output_dir: Directory to save the dump file
        run_tag: Pipeline run tag (timestamp) for dump filename

    Returns:
        Path to the created dump file

    Raises:
        RuntimeError: If dump creation fails
    """
    conn_info = manager.get_connection_info()
    dump_filename = f"oevk_db_{run_tag}.sql.gz"
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
