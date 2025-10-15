#!/usr/bin/env python3
"""
OEVK PostgreSQL Database Loader

This script loads the OEVK database into PostgreSQL. It can either:
1. Connect to an existing PostgreSQL database (provide connection details)
2. Automatically create a Docker PostgreSQL instance and load data

Usage:
    # Load to existing database
    python load_postgresql.py --host localhost --port 5432 --db oevk --user oevk --password oevk

    # Auto-create Docker database and load
    python load_postgresql.py --docker

    # Use environment variables
    export POSTGRES_HOST=localhost
    export POSTGRES_PORT=5432
    export POSTGRES_DB=oevk
    export POSTGRES_USER=oevk
    export POSTGRES_PASSWORD=oevk
    python load_postgresql.py

Requirements:
    - psycopg2-binary (install with: pip install -r requirements.txt)
    - Docker (only if using --docker mode)
"""

import argparse
import os
import sys
import time
import subprocess
from pathlib import Path


def print_banner():
    """Print welcome banner."""
    print("=" * 60)
    print("OEVK PostgreSQL Database Loader")
    print("=" * 60)
    print()


def check_docker_available():
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, check=True
        )
        print(f"✓ Docker found: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ Docker not found or not running")
        return False


def check_port_in_use(port):
    """Check if a port is already in use by a Docker container."""
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"publish={port}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        containers = result.stdout.strip().split("\n")
        return [c for c in containers if c]  # Filter empty strings
    except subprocess.CalledProcessError:
        return []


def create_docker_postgres(container_name="oevk-postgres", port=15432, password="oevk"):
    """Create and start a Docker PostgreSQL container."""
    print(f"\n📦 Creating Docker PostgreSQL container: {container_name}")

    # Check if port is already in use by another container
    containers_using_port = check_port_in_use(port)
    if containers_using_port:
        conflicting_containers = [
            c for c in containers_using_port if c != container_name
        ]
        if conflicting_containers:
            print(
                f"\n⚠️ Port {port} is already in use by: {', '.join(conflicting_containers)}"
            )
            print(f"\nOptions:")
            print(
                f"  1. Stop conflicting container(s): docker stop {' '.join(conflicting_containers)}"
            )
            print(f"  2. Use a different port: --docker-port <port>")
            print(f"  3. Connect to existing database instead of using --docker")
            raise Exception(f"Port {port} is already allocated")

    # Check if container already exists
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        if container_name in result.stdout:
            print(f"ℹ Container '{container_name}' already exists")

            # Check if it's running and get its port
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"name={container_name}",
                    "--format",
                    "{{.Names}}|{{.Ports}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            is_running = container_name in result.stdout

            # Extract port from running container
            if is_running:
                port_info = result.stdout.strip()
                if "->" in port_info:
                    # Format: "0.0.0.0:15433->5432/tcp"
                    import re

                    match = re.search(r"0\.0\.0\.0:(\d+)->5432", port_info)
                    if match:
                        detected_port = int(match.group(1))
                        if detected_port != port:
                            print(
                                f"ℹ️ Container is running on port {detected_port} (requested: {port})"
                            )
                            port = detected_port  # Use the existing port
                print(f"✓ Container is already running")

            if not is_running:
                print(f"▶ Starting existing container...")
                try:
                    subprocess.run(
                        ["docker", "start", container_name],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    if "port is already allocated" in e.stderr.lower():
                        print(f"⚠️ Container exists but port conflict detected")
                        print(f"🗑️ Removing old container and creating new one...")
                        subprocess.run(
                            ["docker", "rm", "-f", container_name], check=True
                        )
                        # Recreate with new port
                        subprocess.run(
                            [
                                "docker",
                                "run",
                                "--name",
                                container_name,
                                "-e",
                                f"POSTGRES_PASSWORD={password}",
                                "-e",
                                "POSTGRES_USER=oevk",
                                "-e",
                                "POSTGRES_DB=oevk",
                                "-d",
                                "-p",
                                f"{port}:5432",
                                "postgres",
                            ],
                            check=True,
                        )
                        print(f"✓ Container recreated on port {port}")
                    else:
                        raise
            else:
                print(f"✓ Container is already running")
        else:
            # Create new container
            print(f"🚀 Creating new PostgreSQL container...")
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--name",
                    container_name,
                    "-e",
                    f"POSTGRES_PASSWORD={password}",
                    "-e",
                    "POSTGRES_USER=oevk",
                    "-e",
                    "POSTGRES_DB=oevk",
                    "-d",
                    "-p",
                    f"{port}:5432",
                    "postgres",
                ],
                check=True,
            )
            print(f"✓ Container created and started on port {port}")

        # Wait for PostgreSQL to be ready
        print("⏳ Waiting for PostgreSQL to be ready...")
        time.sleep(5)

        # Try to connect to verify it's ready
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                import psycopg2

                conn = psycopg2.connect(
                    host="localhost",
                    port=port,
                    dbname="oevk",
                    user="oevk",
                    password=password,
                    connect_timeout=3,
                )
                conn.close()
                print("✓ PostgreSQL is ready!")
                return {
                    "host": "localhost",
                    "port": port,
                    "database": "oevk",
                    "user": "oevk",
                    "password": password,
                }
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(f"  Waiting... (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(3)
                else:
                    raise Exception(
                        f"PostgreSQL didn't become ready after {max_attempts} attempts"
                    )

    except subprocess.CalledProcessError as e:
        print(f"✗ Error creating Docker container: {e}")
        sys.exit(1)


def load_sql_file(conn, filepath, description, chunk_size=8192, strip_conflict=False):
    """Load a SQL file into the database using streaming.

    Args:
        conn: Database connection
        filepath: Path to SQL file
        description: Description for logging
        chunk_size: Size of chunks to read (in KB) for progress reporting
        strip_conflict: Remove ON CONFLICT clauses for faster loading (when no conflicts expected)
    """
    print(f"\n📄 Loading {description}...")
    print(f"   File: {filepath}")

    if not os.path.exists(filepath):
        print(f"✗ File not found: {filepath}")
        return False

    file_size = os.path.getsize(filepath)
    file_size_mb = file_size / (1024 * 1024)
    print(f"   Size: {file_size_mb:.2f} MB")

    if strip_conflict:
        print(
            f"   Optimization: ON CONFLICT clauses will be removed for faster loading"
        )

    try:
        cursor = conn.cursor()
        start_time = time.time()

        # For small files (<10MB), load directly
        if file_size < 10 * 1024 * 1024:
            with open(filepath, "r", encoding="utf-8") as f:
                sql_content = f.read()

            # Strip ON CONFLICT for performance if requested
            if strip_conflict:
                sql_content = sql_content.replace(" ON CONFLICT DO NOTHING", "")

            cursor.execute(sql_content)
        elif file_size < 100 * 1024 * 1024:  # 10-100MB
            # For medium files, use streaming with progress indicator
            print(f"   Loading in chunks (medium file)...")

            # Read file in chunks and build complete SQL
            sql_buffer = []
            bytes_read = 0
            chunk_size_bytes = chunk_size * 1024
            last_progress = 0

            with open(filepath, "r", encoding="utf-8") as f:
                while True:
                    chunk = f.read(chunk_size_bytes)
                    if not chunk:
                        break

                    sql_buffer.append(chunk)
                    bytes_read += len(chunk.encode("utf-8"))

                    # Show progress every 10%
                    progress = int((bytes_read / file_size) * 100)
                    if progress >= last_progress + 10:
                        print(f"   Reading... {progress}%", end="\r")
                        last_progress = progress

            print(f"   Reading... 100% - Done                ")

            # Execute the complete SQL
            sql_content = "".join(sql_buffer)
            sql_buffer = None  # Free memory

            # Strip ON CONFLICT for performance if requested
            if strip_conflict:
                print(f"   Removing ON CONFLICT clauses...")
                sql_content = sql_content.replace(" ON CONFLICT DO NOTHING", "")

            print(f"   Executing SQL statements...")
            cursor.execute(sql_content)
            sql_content = None  # Free memory
        else:
            # For very large files (>100MB), execute statement-by-statement
            print(f"   Processing very large file (>100MB) - using batch execution...")

            # Use autocommit mode to avoid transaction abort issues
            old_autocommit = conn.autocommit
            conn.autocommit = True

            statement_buffer = []
            bytes_read = 0
            last_progress = 0
            statements_executed = 0
            statements_skipped = 0

            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    bytes_read += len(line.encode("utf-8"))

                    # Skip empty lines and comments
                    stripped = line.strip()
                    if not stripped or stripped.startswith("--"):
                        continue

                    statement_buffer.append(line)

                    # Check if statement is complete (ends with semicolon)
                    if stripped.endswith(";"):
                        statement = "".join(statement_buffer)

                        # Strip ON CONFLICT for performance if requested
                        if strip_conflict:
                            statement = statement.replace(" ON CONFLICT DO NOTHING", "")

                        # Show progress every 5%
                        progress = int((bytes_read / file_size) * 100)
                        if progress >= last_progress + 5:
                            print(
                                f"   Progress: {progress}% ({statements_executed:,} executed, {statements_skipped:,} skipped)",
                                end="\r",
                            )
                            last_progress = progress

                        try:
                            cursor.execute(statement)
                            statements_executed += 1
                        except Exception as e:
                            # Expected for ON CONFLICT DO NOTHING or duplicate keys
                            error_msg = str(e).lower()
                            if (
                                "duplicate" in error_msg
                                or "conflict" in error_msg
                                or "unique constraint" in error_msg
                            ):
                                statements_skipped += 1
                            else:
                                # Unexpected error - log first few
                                if statements_executed + statements_skipped < 10:
                                    print(f"\n   Error: {e}")
                                statements_skipped += 1

                        statement_buffer = []

            print(
                f"   Progress: 100% ({statements_executed:,} executed, {statements_skipped:,} skipped)                "
            )

            # Restore original autocommit mode
            conn.autocommit = old_autocommit

        conn.commit()
        elapsed = time.time() - start_time
        throughput = file_size_mb / elapsed if elapsed > 0 else 0

        print(f"✓ Loaded successfully in {elapsed:.2f}s ({throughput:.2f} MB/s)")
        cursor.close()
        return True

    except Exception as e:
        print(f"✗ Error loading file: {e}")
        conn.rollback()
        return False


def clean_database(conn):
    """Truncate all tables in the database."""
    print("\n🧹 Cleaning database (truncating all tables)...")

    try:
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            print("  ℹ No tables found to clean")
            return True

        print(f"  Found {len(tables)} tables to truncate")

        # Truncate all tables with CASCADE
        for table in tables:
            try:
                cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE')
                print(f"  ✓ Truncated {table}")
            except Exception as e:
                print(f"  ⚠️ Could not truncate {table}: {e}")

        conn.commit()
        print("✓ Database cleaned successfully")
        cursor.close()
        return True

    except Exception as e:
        print(f"✗ Error cleaning database: {e}")
        return False


def drop_and_recreate_database(host, port, user, password, dbname):
    """Drop and recreate the database."""
    print(f"\n🗑️ Dropping and recreating database '{dbname}'...")

    try:
        import psycopg2

        # Connect to postgres database to drop/create
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname="postgres",
            user=user,
            password=password,
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Terminate existing connections
        cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{dbname}'
              AND pid <> pg_backend_pid()
        """)

        # Drop database
        print(f"  Dropping database '{dbname}'...")
        cursor.execute(f'DROP DATABASE IF EXISTS "{dbname}"')

        # Create database
        print(f"  Creating database '{dbname}'...")
        cursor.execute(f'CREATE DATABASE "{dbname}"')

        cursor.close()
        conn.close()

        print("✓ Database recreated successfully")
        return True

    except Exception as e:
        print(f"✗ Error recreating database: {e}")
        return False


def verify_database(conn, verbose=True):
    """Verify that the database was loaded correctly."""
    print("\n🔍 Verifying database...")

    try:
        cursor = conn.cursor()

        # Check some key tables (CanonicalAddress renamed to Address in PostgreSQL export)
        tables_to_check = ["County", "Settlement", "Address", "PollingStation"]

        results = []
        total_rows = 0
        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                results.append((table, count))
                total_rows += count
                if verbose:
                    print(f"  ✓ {table}: {count:,} rows")
            except Exception as e:
                if verbose:
                    print(f"  ✗ {table}: Error - {e}")
                results.append((table, None))

        cursor.close()

        # Check if we got data
        success = all(count is not None and count > 0 for _, count in results)

        if success:
            print(f"\n✅ Database verification successful! ({total_rows:,} total rows)")
        else:
            print("\n⚠️ Some tables are empty or missing")

        return success

    except Exception as e:
        print(f"✗ Verification error: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Load OEVK data into PostgreSQL database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load to existing database
  python load_postgresql.py --host localhost --port 5432 --db oevk --user oevk --password mypass

  # Create Docker database and load
  python load_postgresql.py --docker

  # Fresh load (drop and recreate database)
  python load_postgresql.py --docker --drop-database

  # Clean load (truncate tables, keep schema)
  python load_postgresql.py --docker --clean

  # Use environment variables
  export POSTGRES_HOST=localhost
  export POSTGRES_PORT=5432
  python load_postgresql.py

  # Fast loading with psql (recommended for large files)
  psql -h localhost -p 15432 -U oevk -d oevk -f data.sql
        """,
    )

    parser.add_argument(
        "--docker",
        action="store_true",
        help="Automatically create a Docker PostgreSQL container",
    )
    parser.add_argument(
        "--container-name",
        default="oevk-postgres",
        help="Docker container name (default: oevk-postgres)",
    )
    parser.add_argument(
        "--docker-port",
        type=int,
        default=15432,
        help="Docker PostgreSQL port (default: 15432)",
    )

    parser.add_argument(
        "--host",
        default=os.getenv("POSTGRES_HOST", "localhost"),
        help="PostgreSQL host (default: localhost or $POSTGRES_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("POSTGRES_PORT", "5432")),
        help="PostgreSQL port (default: 5432 or $POSTGRES_PORT)",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("POSTGRES_DB", "oevk"),
        help="Database name (default: oevk or $POSTGRES_DB)",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("POSTGRES_USER", "oevk"),
        help="Database user (default: oevk or $POSTGRES_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("POSTGRES_PASSWORD", "oevk"),
        help="Database password (default: oevk or $POSTGRES_PASSWORD)",
    )

    parser.add_argument(
        "--schema",
        default="schema.sql",
        help="Path to schema.sql file (default: schema.sql)",
    )
    parser.add_argument(
        "--data", default="data.sql", help="Path to data.sql file (default: data.sql)"
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip database verification after loading",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (only errors and final status)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=8192,
        help="Chunk size in KB for reading large files (default: 8192)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Truncate all tables before loading (keeps schema, removes data)",
    )
    parser.add_argument(
        "--drop-database",
        action="store_true",
        help="Drop and recreate database before loading (complete fresh start)",
    )

    args = parser.parse_args()

    print_banner()

    # Check for psycopg2
    try:
        import psycopg2

        print("✓ psycopg2 found")
    except ImportError:
        print("✗ psycopg2 not found")
        print("\nPlease install requirements:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    # Handle Docker mode
    if args.docker:
        if not check_docker_available():
            print("\n✗ Docker is required for --docker mode")
            print("Please install Docker or provide connection details instead")
            sys.exit(1)

        docker_config = create_docker_postgres(
            container_name=args.container_name,
            port=args.docker_port,
            password=args.password,
        )

        # Override connection settings with Docker config
        args.host = docker_config["host"]
        args.port = docker_config["port"]
        args.db = docker_config["database"]
        args.user = docker_config["user"]
        args.password = docker_config["password"]

    # Handle --drop-database first (before connecting to target database)
    if args.drop_database:
        if not drop_and_recreate_database(
            args.host, args.port, args.user, args.password, args.db
        ):
            print("\n✗ Failed to recreate database")
            sys.exit(1)

    # Connect to database
    print(f"\n🔌 Connecting to PostgreSQL...")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Database: {args.db}")
    print(f"   User: {args.user}")

    try:
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            dbname=args.db,
            user=args.user,
            password=args.password,
        )
        conn.autocommit = False
        print("✓ Connected successfully")

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nPlease check your connection settings or use --docker mode")
        sys.exit(1)

    # Handle --clean (truncate tables)
    if args.clean:
        if not clean_database(conn):
            print("\n✗ Failed to clean database")
            conn.close()
            sys.exit(1)

    # Determine if we can skip conflict checking (performance optimization)
    # When database is dropped or cleaned, no conflicts are possible
    skip_conflicts = args.drop_database or args.clean

    if skip_conflicts:
        print(
            "\n⚡ Performance mode: ON CONFLICT clauses will be removed (no existing data)"
        )

    # Load schema
    if not load_sql_file(
        conn,
        args.schema,
        "Schema (DDL)",
        chunk_size=args.chunk_size,
        strip_conflict=False,
    ):
        print("\n✗ Failed to load schema")
        conn.close()
        sys.exit(1)

    # Load data (with conflict stripping if applicable)
    if not load_sql_file(
        conn,
        args.data,
        "Data (DML)",
        chunk_size=args.chunk_size,
        strip_conflict=skip_conflicts,
    ):
        print("\n✗ Failed to load data")
        conn.close()
        sys.exit(1)

    # Verify database
    if not args.skip_verify:
        verify_success = verify_database(conn, verbose=not args.quiet)
        if not verify_success:
            print("\n⚠️ Database verification had issues")

    conn.close()

    print("\n" + "=" * 60)
    print("✅ Database loading completed successfully!")
    print("=" * 60)
    print("\nYou can now connect to your database:")
    print(f"  psql -h {args.host} -p {args.port} -U {args.user} -d {args.db}")
    print()


if __name__ == "__main__":
    main()
