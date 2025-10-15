"""PostgreSQL dump export and import utilities."""

import gzip
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


def export_dump(
    host: str = "localhost",
    port: int = 5432,
    database: str = "oevk",
    user: str = "oevk",
    password: str = "oevk",
    output_dir: str = "exports",
    use_docker: bool = True,
    container_name: str = "oevk",
) -> str:
    """Export PostgreSQL database to gzipped dump file.

    Args:
        host: PostgreSQL host (default: localhost)
        port: PostgreSQL port (default: 5432)
        database: Database name (default: oevk)
        user: PostgreSQL user (default: oevk)
        password: PostgreSQL password (default: oevk)
        output_dir: Output directory for dump file (default: exports)
        use_docker: Use Docker container for pg_dump (default: True)
        container_name: Docker container name if use_docker=True (default: oevk)

    Returns:
        Path to the created dump file

    Raises:
        RuntimeError: If dump creation fails
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_filename = f"oevk_db_{timestamp}.sql.gz"
    dump_path = output_path / dump_filename

    logger.info("=" * 80)
    logger.info("PostgreSQL Dump Export")
    logger.info("=" * 80)
    logger.info(f"Database: {database}")
    logger.info(f"Output: {dump_path}")

    try:
        if use_docker:
            # Use pg_dump from Docker container
            logger.info(f"Exporting from Docker container: {container_name}")
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "pg_dump",
                    "-U",
                    user,
                    "-d",
                    database,
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-privileges",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,  # 5 minutes
            )
            dump_sql = result.stdout
        else:
            # Use local pg_dump with connection parameters
            logger.info(f"Exporting from {host}:{port}")
            env = {"PGPASSWORD": password}
            result = subprocess.run(
                [
                    "pg_dump",
                    "-h",
                    host,
                    "-p",
                    str(port),
                    "-U",
                    user,
                    "-d",
                    database,
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-privileges",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
                env=env,
            )
            dump_sql = result.stdout

        # Compress with gzip
        logger.info("Compressing dump with gzip...")
        with gzip.open(dump_path, "wt", encoding="utf-8") as f:
            f.write(dump_sql)

        file_size_mb = dump_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Dump created: {dump_path} ({file_size_mb:.1f} MB)")
        logger.info("=" * 80)

        return str(dump_path)

    except subprocess.CalledProcessError as e:
        logger.error(f"pg_dump failed: {e.stderr}")
        raise RuntimeError(f"Failed to create dump: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("pg_dump timed out after 5 minutes")
    except Exception as e:
        raise RuntimeError(f"Failed to create dump: {e}")


def import_dump(
    dump_path: str,
    host: str = "localhost",
    port: int = 5432,
    database: str = "oevk",
    user: str = "oevk",
    password: str = "oevk",
    use_docker: bool = True,
    container_name: str = "oevk",
) -> None:
    """Import gzipped PostgreSQL dump file.

    Args:
        dump_path: Path to .sql.gz dump file
        host: PostgreSQL host (default: localhost)
        port: PostgreSQL port (default: 5432)
        database: Database name (default: oevk)
        user: PostgreSQL user (default: oevk)
        password: PostgreSQL password (default: oevk)
        use_docker: Use Docker container for psql (default: True)
        container_name: Docker container name if use_docker=True (default: oevk)

    Raises:
        FileNotFoundError: If dump file not found
        RuntimeError: If import fails
    """
    dump_file = Path(dump_path)
    if not dump_file.exists():
        raise FileNotFoundError(f"Dump file not found: {dump_path}")

    if not dump_file.name.endswith(".sql.gz"):
        raise ValueError("Dump file must have .sql.gz extension")

    file_size_mb = dump_file.stat().st_size / (1024 * 1024)

    logger.info("=" * 80)
    logger.info("PostgreSQL Dump Import")
    logger.info("=" * 80)
    logger.info(f"Dump file: {dump_path} ({file_size_mb:.1f} MB)")
    logger.info(f"Database: {database}")

    try:
        # Decompress dump
        logger.info("Decompressing dump...")
        with gzip.open(dump_file, "rt", encoding="utf-8") as f:
            dump_sql = f.read()

        decompressed_size_mb = len(dump_sql.encode("utf-8")) / (1024 * 1024)
        logger.info(f"Decompressed size: {decompressed_size_mb:.1f} MB")

        if use_docker:
            # Import via Docker container
            logger.info(f"Importing to Docker container: {container_name}")

            # Copy SQL to container
            temp_sql = dump_file.parent / f"_temp_{dump_file.stem}.sql"
            temp_sql.write_text(dump_sql, encoding="utf-8")

            try:
                subprocess.run(
                    [
                        "docker",
                        "cp",
                        str(temp_sql),
                        f"{container_name}:/tmp/import.sql",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60,
                )

                # Execute SQL
                logger.info("Importing data (this may take 10-30 minutes for large files)...")
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "psql",
                        "-U",
                        user,
                        "-d",
                        database,
                        "-f",
                        "/tmp/import.sql",
                        "-v",
                        "ON_ERROR_STOP=1",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30 minutes for large files
                )

                if result.returncode != 0:
                    logger.error(f"psql stderr: {result.stderr}")
                    raise RuntimeError("Import failed")

            finally:
                # Cleanup temp file
                if temp_sql.exists():
                    temp_sql.unlink()

        else:
            # Import via local psql
            logger.info(f"Importing to {host}:{port}")
            logger.info("Importing data (this may take 10-30 minutes for large files)...")
            env = {"PGPASSWORD": password}
            result = subprocess.run(
                [
                    "psql",
                    "-h",
                    host,
                    "-p",
                    str(port),
                    "-U",
                    user,
                    "-d",
                    database,
                    "-v",
                    "ON_ERROR_STOP=1",
                ],
                input=dump_sql,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes for large files
                env=env,
            )

            if result.returncode != 0:
                logger.error(f"psql stderr: {result.stderr}")
                raise RuntimeError("Import failed")

        logger.info("✓ Import completed successfully")
        logger.info("=" * 80)

    except subprocess.TimeoutExpired:
        raise RuntimeError("Import timed out")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Import failed: {e.stderr}")
    except Exception as e:
        raise RuntimeError(f"Import failed: {e}")
