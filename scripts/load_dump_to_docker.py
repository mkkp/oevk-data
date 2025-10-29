#!/usr/bin/env python3
"""Load latest PostgreSQL dump into Docker PostGIS container.

This script:
1. Finds the latest .sql.gz dump file in exports directory
2. Creates or uses existing Docker PostGIS container
3. Creates database with PostGIS extension
4. Loads the dump into the database
5. Verifies the import was successful

Usage:
    # Use default settings (container: oevk-postgresql, port: 5432)
    python scripts/load_dump_to_docker.py

    # Custom container name and port
    python scripts/load_dump_to_docker.py --container oevk-db --port 5433

    # Load specific dump file
    python scripts/load_dump_to_docker.py --dump-file exports/oevk_db_20251029091200.sql.gz

    # Drop and recreate database
    python scripts/load_dump_to_docker.py --drop-database

    # Keep container running even if import fails
    python scripts/load_dump_to_docker.py --no-cleanup
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
import gzip
import os

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_info(msg: str):
    """Print info message."""
    print(f"{BLUE}INFO:{RESET} {msg}")


def print_success(msg: str):
    """Print success message."""
    print(f"{GREEN}✓{RESET} {msg}")


def print_warning(msg: str):
    """Print warning message."""
    print(f"{YELLOW}WARNING:{RESET} {msg}")


def print_error(msg: str):
    """Print error message."""
    print(f"{RED}ERROR:{RESET} {msg}")


def print_step(step: str, total: int, current: int):
    """Print step header."""
    print(f"\n{BOLD}=== Step {current}/{total}: {step} ==={RESET}")


def run_command(
    cmd: list, check: bool = True, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Run shell command with error handling."""
    try:
        result = subprocess.run(
            cmd, check=check, capture_output=capture_output, text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        if capture_output:
            print_error(f"Command failed: {' '.join(cmd)}")
            if e.stdout:
                print(f"STDOUT: {e.stdout}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
        raise


def find_latest_dump(exports_dir: Path) -> Optional[Path]:
    """Find the latest .sql.gz dump file in exports directory."""
    dump_files = list(exports_dir.glob("oevk_db_*.sql.gz"))

    if not dump_files:
        return None

    # Sort by modification time (newest first)
    dump_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return dump_files[0]


def check_docker() -> bool:
    """Check if Docker is installed and running."""
    try:
        result = run_command(["docker", "info"], capture_output=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def container_exists(container_name: str) -> bool:
    """Check if Docker container exists."""
    result = run_command(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^{container_name}$",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
    )
    return container_name in result.stdout


def container_running(container_name: str) -> bool:
    """Check if Docker container is running."""
    result = run_command(
        [
            "docker",
            "ps",
            "--filter",
            f"name=^{container_name}$",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
    )
    return container_name in result.stdout


def find_available_port(start_port: int = 5432) -> int:
    """Find an available port starting from start_port."""
    import socket

    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                port += 1

    raise RuntimeError(
        f"No available ports found in range {start_port}-{start_port + 100}"
    )


def create_container(
    container_name: str, port: int, image: str = "postgis/postgis:15-3.3"
) -> bool:
    """Create Docker PostGIS container."""
    print_info(
        f"Creating PostgreSQL container '{container_name}' (image: {image}, port: {port})..."
    )

    try:
        run_command(
            [
                "docker",
                "run",
                "--name",
                container_name,
                "-e",
                "POSTGRES_USER=oevk",
                "-e",
                "POSTGRES_PASSWORD=oevk",
                "-e",
                "POSTGRES_DB=postgres",
                "-p",
                f"{port}:5432",
                "-d",
                image,
            ],
            capture_output=True,
        )

        print_success(f"Container '{container_name}' created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create container: {e.stderr}")
        return False


def wait_for_postgres(container_name: str, timeout: int = 30) -> bool:
    """Wait for PostgreSQL to be ready."""
    print_info(f"Waiting for PostgreSQL to be ready (timeout: {timeout}s)...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        result = run_command(
            ["docker", "exec", container_name, "pg_isready", "-U", "oevk"],
            capture_output=True,
            check=False,
        )

        if result.returncode == 0:
            elapsed = time.time() - start_time
            print_success(f"PostgreSQL ready after {elapsed:.1f}s")
            return True

        time.sleep(0.5)

    print_error(f"PostgreSQL did not become ready within {timeout}s")
    return False


def optimize_postgresql(container_name: str) -> bool:
    """Apply PostgreSQL performance optimizations for large imports."""
    print_info("Applying performance optimizations...")

    optimizations = [
        "ALTER SYSTEM SET shared_buffers = '256MB';",
        "ALTER SYSTEM SET work_mem = '64MB';",
        "ALTER SYSTEM SET maintenance_work_mem = '256MB';",
        "ALTER SYSTEM SET effective_cache_size = '1GB';",
        "ALTER SYSTEM SET checkpoint_completion_target = 0.9;",
        "ALTER SYSTEM SET wal_buffers = '16MB';",
        "ALTER SYSTEM SET max_wal_size = '2GB';",
        "ALTER SYSTEM SET fsync = off;",  # Unsafe but faster for initial load
        "ALTER SYSTEM SET full_page_writes = off;",  # Unsafe but faster
    ]

    try:
        for opt in optimizations:
            run_command(
                [
                    "docker",
                    "exec",
                    container_name,
                    "psql",
                    "-U",
                    "oevk",
                    "-d",
                    "postgres",
                    "-c",
                    opt,
                ],
                capture_output=True,
                check=False,
            )

        # Restart PostgreSQL to apply settings
        print_info("Restarting PostgreSQL to apply settings...")
        run_command(["docker", "restart", container_name], capture_output=True)

        # Wait for it to come back up
        if not wait_for_postgres(container_name, timeout=30):
            print_warning("PostgreSQL restart timeout, but continuing...")
            return True

        print_success("Performance optimizations applied")
        return True

    except subprocess.CalledProcessError as e:
        print_warning(f"Failed to apply some optimizations: {e.stderr}")
        return True  # Non-fatal, continue anyway


def create_database(
    container_name: str, db_name: str, drop_if_exists: bool = False
) -> bool:
    """Create database with PostGIS extension."""
    print_info(f"Creating database '{db_name}'...")

    # Drop database if requested
    if drop_if_exists:
        print_info(f"Dropping existing database '{db_name}' if it exists...")
        run_command(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                "oevk",
                "-d",
                "postgres",
                "-c",
                f"DROP DATABASE IF EXISTS {db_name};",
            ],
            capture_output=True,
            check=False,
        )

    # Create database
    try:
        run_command(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                "oevk",
                "-d",
                "postgres",
                "-c",
                f"CREATE DATABASE {db_name};",
            ],
            capture_output=True,
        )
        print_success(f"Database '{db_name}' created")
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr:
            print_warning(f"Database '{db_name}' already exists")
        else:
            print_error(f"Failed to create database: {e.stderr}")
            return False

    # Create PostGIS extension
    print_info("Creating PostGIS extension...")
    try:
        run_command(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                "oevk",
                "-d",
                db_name,
                "-c",
                "CREATE EXTENSION IF NOT EXISTS postgis;",
            ],
            capture_output=True,
        )
        run_command(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                "oevk",
                "-d",
                db_name,
                "-c",
                "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            ],
            capture_output=True,
        )
        print_success("PostGIS and pg_trgm extensions enabled")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create extensions: {e.stderr}")
        return False


def load_dump(container_name: str, db_name: str, dump_file: Path) -> bool:
    """Load dump file into database using streaming to avoid memory issues."""
    print_info(f"Loading dump file: {dump_file.name}")

    # Get file size for progress indication
    file_size_mb = dump_file.stat().st_size / (1024 * 1024)
    print_info(f"Dump file size: {file_size_mb:.1f} MB (compressed)")

    try:
        # Decompress and pipe to psql using shell pipeline
        # This streams data without loading entire file into memory
        print_info("Importing data (this may take several minutes)...")

        # Use shell pipeline: gunzip -c file.sql.gz | docker exec -i container psql
        import shlex

        cmd = f"gunzip -c {shlex.quote(str(dump_file))} | docker exec -i {shlex.quote(container_name)} psql -U oevk -d {shlex.quote(db_name)} 2>&1"

        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        # Read output line by line to avoid memory issues
        last_line = ""
        for line in process.stdout:
            # Keep track of last line for error reporting
            last_line = line.strip()
            # Optionally show progress (commented out to avoid clutter)
            # if "COPY" in line or "ERROR" in line:
            #     print(line.strip())

        process.wait()

        if process.returncode != 0:
            print_error(f"Import failed with exit code {process.returncode}")
            if last_line:
                print(f"Last output: {last_line}")
            return False

        print_success("Dump loaded successfully")
        return True

    except Exception as e:
        print_error(f"Failed to load dump: {e}")
        return False


def verify_import(container_name: str, db_name: str) -> bool:
    """Verify import by checking row counts."""
    print_info("Verifying import...")

    tables = [
        "county",
        "settlement",
        "oevk",
        "tevk",
        "postal_code",
        "polling_station",
        "address",
        "public_space_name",
        "public_space_type",
    ]

    total_rows = 0
    success = True

    print("\nTable Row Counts:")
    print("-" * 50)

    for table in tables:
        try:
            result = run_command(
                [
                    "docker",
                    "exec",
                    container_name,
                    "psql",
                    "-U",
                    "oevk",
                    "-d",
                    db_name,
                    "-t",
                    "-c",
                    f"SELECT COUNT(*) FROM {table};",
                ],
                capture_output=True,
            )

            count = int(result.stdout.strip())
            total_rows += count

            status = "✓" if count > 0 else "⚠"
            print(f"{status} {table:30} {count:>12,} rows")

            if count == 0 and table == "address":
                print_warning(f"Table '{table}' is empty!")
                success = False

        except Exception as e:
            print_error(f"Failed to query {table}: {e}")
            success = False

    print("-" * 50)
    print(f"Total rows: {total_rows:>33,}")
    print()

    if success:
        print_success("Import verification passed")
    else:
        print_warning("Import verification found issues")

    return success


def show_connection_info(container_name: str, db_name: str, port: int):
    """Show connection information."""
    print(f"\n{BOLD}=== Connection Information ==={RESET}")
    print(f"Container:  {container_name}")
    print(f"Host:       localhost")
    print(f"Port:       {port}")
    print(f"Database:   {db_name}")
    print(f"User:       oevk")
    print(f"Password:   oevk")
    print()
    print(f"{BOLD}Connect with psql:{RESET}")
    print(f"  docker exec -it {container_name} psql -U oevk -d {db_name}")
    print()
    print(f"{BOLD}Connection string:{RESET}")
    print(f"  postgresql://oevk:oevk@localhost:{port}/{db_name}")
    print()


def cleanup_container(container_name: str):
    """Stop and remove container."""
    print_info(f"Cleaning up container '{container_name}'...")

    run_command(["docker", "stop", container_name], capture_output=True, check=False)
    run_command(["docker", "rm", container_name], capture_output=True, check=False)

    print_success("Container removed")


def main():
    parser = argparse.ArgumentParser(
        description="Load latest PostgreSQL dump into Docker PostGIS container",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dump-file",
        type=Path,
        help="Path to specific dump file (default: latest in exports/)",
    )
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=Path("exports"),
        help="Exports directory (default: exports)",
    )
    parser.add_argument(
        "--container",
        default="oevk-postgresql",
        help="Docker container name (default: oevk-postgresql)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="PostgreSQL port (default: auto-detect available port starting from 5432)",
    )
    parser.add_argument(
        "--db-name", default="oevk", help="Database name (default: oevk)"
    )
    parser.add_argument(
        "--drop-database",
        action="store_true",
        help="Drop and recreate database if it exists",
    )
    parser.add_argument(
        "--image",
        default="postgis/postgis:15-3.3",
        help="Docker image to use (default: postgis/postgis:15-3.3)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep container running even if import fails",
    )
    parser.add_argument(
        "--start-only",
        action="store_true",
        help="Only start the container without loading dump",
    )

    args = parser.parse_args()

    print(f"\n{BOLD}=== PostgreSQL Dump Loader ==={RESET}\n")

    # Step 0: Check Docker
    print_step("Checking Docker", 7, 0)
    if not check_docker():
        print_error("Docker is not installed or not running")
        print_info("Install Docker: https://docs.docker.com/get-docker/")
        sys.exit(1)
    print_success("Docker is available")

    # Step 1: Find dump file
    if not args.start_only:
        print_step("Finding dump file", 7, 1)

        if args.dump_file:
            dump_file = args.dump_file
            if not dump_file.exists():
                print_error(f"Dump file not found: {dump_file}")
                sys.exit(1)
        else:
            dump_file = find_latest_dump(args.exports_dir)
            if not dump_file:
                print_error(f"No dump files found in {args.exports_dir}")
                print_info("Run 'python -m src.cli db verify' to create a dump")
                sys.exit(1)

        print_success(f"Found dump: {dump_file}")

        # Show dump info
        file_size_mb = dump_file.stat().st_size / (1024 * 1024)
        mod_time = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(dump_file.stat().st_mtime)
        )
        print_info(f"  Size: {file_size_mb:.1f} MB")
        print_info(f"  Modified: {mod_time}")

    # Step 2: Setup container
    print_step("Setting up Docker container", 7, 2)

    container_created = False

    if container_exists(args.container):
        print_info(f"Container '{args.container}' already exists")

        if not container_running(args.container):
            print_info("Starting existing container...")
            run_command(["docker", "start", args.container], capture_output=True)
            print_success("Container started")
        else:
            print_success("Container is already running")

        # Get the port from existing container
        result = run_command(
            ["docker", "port", args.container, "5432"], capture_output=True
        )
        port_mapping = result.stdout.strip()
        if port_mapping:
            port = int(port_mapping.split(":")[-1])
        else:
            port = args.port or 5432
    else:
        # Find available port
        port = args.port or find_available_port(5432)

        if not create_container(args.container, port, args.image):
            sys.exit(1)

        container_created = True

    # Step 3: Wait for PostgreSQL
    print_step("Waiting for PostgreSQL", 7, 3)

    if not wait_for_postgres(args.container):
        if container_created and not args.no_cleanup:
            cleanup_container(args.container)
        sys.exit(1)

    # Step 4: Optimize PostgreSQL
    print_step("Optimizing PostgreSQL settings", 7, 4)

    optimize_postgresql(args.container)

    # Step 5: Create database
    print_step("Creating database", 7, 5)

    if not create_database(args.container, args.db_name, args.drop_database):
        if container_created and not args.no_cleanup:
            cleanup_container(args.container)
        sys.exit(1)

    # If start-only mode, stop here
    if args.start_only:
        print_success("\nContainer started successfully")
        show_connection_info(args.container, args.db_name, port)
        sys.exit(0)

    # Step 6: Load dump
    print_step("Loading dump", 7, 6)

    if not load_dump(args.container, args.db_name, dump_file):
        if container_created and not args.no_cleanup:
            cleanup_container(args.container)
        sys.exit(1)

    # Step 7: Verify import
    print_step("Verifying import", 7, 7)

    verification_success = verify_import(args.container, args.db_name)

    # Show connection info
    show_connection_info(args.container, args.db_name, port)

    if verification_success:
        print_success(f"{BOLD}Import completed successfully!{RESET}\n")
        sys.exit(0)
    else:
        print_warning(f"{BOLD}Import completed with warnings{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
