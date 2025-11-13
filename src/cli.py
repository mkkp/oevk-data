"Command-line interface for the OEVK data processing pipeline."

import argparse
import datetime
import glob
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add src directory to Python path
sys.path.insert(0, str(project_root / "src"))

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


from src.database.connection import get_database_connection
from src.etl.export import (
    create_release_symlinks,
    export_addresses_partitioned,
    export_tables_to_csv,
)
from src.etl.export_canonical_v3 import export_canonical_addresses_optimized
from src.etl.ingest import download_sources, load_staging_data
from src.etl.postgresql_dump import export_dump, import_dump
from src.etl.postgresql_verify import verify_and_dump_postgresql
from src.etl.transform_optimized import transform_all_optimized
from src.utils.config import Config
from src.utils.pipeline_logging import PipelineMetrics, get_logger, setup_logging

# Release workflow import (conditional to avoid import errors during development)
try:
    from src.release.workflow import ReleaseWorkflow

    RELEASE_AVAILABLE = True
except ImportError:
    RELEASE_AVAILABLE = False

logger = get_logger(__name__)


def get_git_repo_info():
    """
    Extract GitHub repository owner and name from git remote URL.

    Returns:
        tuple: (owner, repo_name) or (None, None) if not found
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        remote_url = result.stdout.strip()

        # Parse GitHub URL patterns:
        # - git@github.com:owner/repo.git
        # - https://github.com/owner/repo.git
        # - https://github.com/owner/repo

        # SSH format: git@github.com:owner/repo.git
        ssh_match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", remote_url)
        if ssh_match:
            return ssh_match.group(1), ssh_match.group(2)

        # HTTPS format: https://github.com/owner/repo.git or https://github.com/owner/repo
        https_match = re.match(
            r"https://github\.com/([^/]+)/(.+?)(?:\.git)?$", remote_url
        )
        if https_match:
            return https_match.group(1), https_match.group(2)

        logger.warning(f"Could not parse GitHub URL: {remote_url}")
        return None, None
    except subprocess.CalledProcessError:
        logger.warning("Could not get git remote URL")
        return None, None
    except Exception as e:
        logger.warning(f"Error getting git repo info: {e}")
        return None, None


def get_latest_export_timestamp(exports_dir="exports"):
    """
    Find the latest export timestamp from the exports directory.

    Args:
        exports_dir: Path to exports directory

    Returns:
        str: Latest timestamp (YYYYMMDD_HHMMSS) or None if not found
    """
    try:
        # Look for timestamped CSV files: YYYYMMDD_HHMMSS_*.csv
        csv_files = glob.glob(os.path.join(exports_dir, "*_*.csv"))

        # Also look for timestamped Address directories: YYYYMMDD_HHMMSS_Address
        address_dirs = glob.glob(os.path.join(exports_dir, "*_Address"))

        timestamps = set()

        # Extract timestamps from CSV files
        for csv_file in csv_files:
            basename = os.path.basename(csv_file)
            # Match YYYYMMDD_HHMMSS pattern
            match = re.match(r"(\d{8}_\d{6})_", basename)
            if match:
                timestamps.add(match.group(1))

        # Extract timestamps from Address directories
        for addr_dir in address_dirs:
            basename = os.path.basename(addr_dir)
            # Match YYYYMMDD_HHMMSS_Address pattern
            match = re.match(r"(\d{8}_\d{6})_Address$", basename)
            if match:
                timestamps.add(match.group(1))

        if not timestamps:
            logger.warning(f"No export timestamps found in {exports_dir}")
            return None

        # Return the latest timestamp (lexicographically sorted, which works for YYYYMMDD_HHMMSS)
        latest = max(timestamps)
        logger.info(f"Found latest export timestamp: {latest}")
        return latest

    except Exception as e:
        logger.warning(f"Error finding latest export timestamp: {e}")
        return None


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="OEVK Data Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline with default settings (cleans database before ingestion)
  python src/cli.py run

  # Run pipeline with custom database and output directory
  python src/cli.py run --db-path data/oevk.db --output-dir exports/

  # Run only specific stages
  python src/cli.py run --stages ingest,transform

  # Preserve existing database (skip cleanup before ingestion)
  python src/cli.py run --no-cleanup

  # Disable deduplication
  python src/cli.py run --no-deduplication
        """,
    )

    # Global verbose flag
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run the complete pipeline")
    run_parser.add_argument(
        "--db-path",
        default="data/oevk.db",
        help="Path to the database file (default: data/oevk.db)",
    )
    run_parser.add_argument(
        "--staging-dir",
        default="data/staging",
        help="Directory for staging files (default: data/staging)",
    )
    run_parser.add_argument(
        "--output-dir",
        default="exports",
        help="Directory for output files (default: exports)",
    )
    run_parser.add_argument(
        "--stages",
        default="ingest,transform,export",
        help="Comma-separated list of stages to run (default: all)",
    )
    run_parser.add_argument("--run-tag", help="Custom run tag (default: timestamp)")
    run_parser.add_argument(
        "--skip-postgresql-export",
        action="store_true",
        help="Skip PostgreSQL export (only generate CSV files)",
    )
    run_parser.add_argument(
        "--chunk-size",
        type=int,
        default=50000,
        help="Chunk size for address transformation (default: 50000)",
    )
    run_parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing (default: parallel enabled)",
    )
    run_parser.add_argument(
        "--no-optimized",
        action="store_true",
        help="Use original transformation instead of optimized (default: optimized enabled)",
    )
    run_parser.add_argument(
        "--no-deduplication",
        action="store_true",
        help="Disable address deduplication (default: deduplication enabled)",
    )
    run_parser.add_argument(
        "--export-original-addresses",
        action="store_true",
        help="Export OriginalAddress CSV files (default: only canonical addresses exported)",
    )
    run_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip database cleanup before ingestion (default: cleanup enabled)",
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export data to CSV files")
    export_parser.add_argument(
        "--db-path",
        default="data/oevk.db",
        help="Path to the database file (default: data/oevk.db)",
    )
    export_parser.add_argument(
        "--output-dir",
        default="exports",
        help="Output directory for CSV files (default: exports)",
    )
    export_parser.add_argument("--run-tag", help="Custom run tag (default: timestamp)")
    export_parser.add_argument(
        "--skip-postgresql-export",
        action="store_true",
        help="Skip PostgreSQL export (only generate CSV files)",
    )
    export_parser.add_argument(
        "--export-original-addresses",
        action="store_true",
        help="Export OriginalAddress CSV files (default: only canonical addresses exported)",
    )
    export_parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Maximum number of parallel workers for export (default: 8)",
    )
    export_parser.add_argument(
        "--tables-only",
        action="store_true",
        help="Export only entity tables, skip address exports (default: export all)",
    )
    export_parser.add_argument(
        "--addresses-only",
        action="store_true",
        help="Export only addresses, skip entity tables (default: export all)",
    )
    export_parser.add_argument(
        "--use-copies",
        action="store_true",
        help="Copy files instead of creating symlinks (Windows-compatible, auto-detected by default)",
    )
    export_parser.add_argument(
        "--use-symlinks",
        action="store_true",
        help="Create symlinks instead of copying files (Unix-only, auto-detected by default)",
    )

    # Database setup command
    db_parser = subparsers.add_parser(
        "db", help="Manage database operations (e.g., setup PostgreSQL)"
    )
    db_subparsers = db_parser.add_subparsers(dest="db_command", help="Database command")

    # db setup command
    setup_parser = db_subparsers.add_parser(
        "setup", help="Setup local PostgreSQL database via Docker"
    )
    setup_parser.add_argument(
        "--ddl-script",
        default="exports/schema.sql",
        help="Path to DDL script (default: exports/schema.sql)",
    )
    setup_parser.add_argument(
        "--dml-script",
        default="exports/data.sql",
        help="Path to DML script (default: exports/data.sql)",
    )
    setup_parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Force recreation of Docker container",
    )
    setup_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify imported data matches source database (samples 5%% of data)",
    )
    setup_parser.add_argument(
        "--verify-sample",
        type=float,
        default=5.0,
        help="Percentage of data to sample for verification (default: 5.0)",
    )
    setup_parser.add_argument(
        "--db-path",
        default="data/oevk.db",
        help="Path to source DuckDB database for verification (default: data/oevk.db)",
    )
    setup_parser.add_argument(
        "--ignore-verify-errors",
        action="store_true",
        help="Continue even if verification fails",
    )

    # db import-csv command
    import_csv_parser = db_subparsers.add_parser(
        "import-csv", help="Import CSV files into PostgreSQL using fast COPY method"
    )
    import_csv_parser.add_argument(
        "--exports-dir",
        default="exports",
        help="Path to exports directory containing schema.sql and postgresql/ (default: exports)",
    )
    import_csv_parser.add_argument(
        "--host",
        default="localhost",
        help="PostgreSQL host (default: localhost)",
    )
    import_csv_parser.add_argument(
        "--port",
        type=int,
        default=5432,
        help="PostgreSQL port (default: 5432)",
    )
    import_csv_parser.add_argument(
        "--database",
        default="oevk",
        help="PostgreSQL database name (default: oevk)",
    )
    import_csv_parser.add_argument(
        "--user",
        default="oevk",
        help="PostgreSQL user (default: oevk)",
    )
    import_csv_parser.add_argument(
        "--password",
        help="PostgreSQL password (optional, will prompt if not provided)",
    )
    import_csv_parser.add_argument(
        "--create-database",
        action="store_true",
        help="Create database if it doesn't exist",
    )
    import_csv_parser.add_argument(
        "--drop-database",
        action="store_true",
        help="Drop and recreate database (WARNING: destroys existing data)",
    )
    import_csv_parser.add_argument(
        "--docker",
        action="store_true",
        help="Use Docker PostgreSQL container (auto-creates if needed)",
    )
    import_csv_parser.add_argument(
        "--container-name",
        default="oevk-postgresql",
        help="Docker container name (default: oevk-postgresql)",
    )

    # db export-dump command
    export_dump_parser = db_subparsers.add_parser(
        "export-dump", help="Export PostgreSQL database to gzipped dump file"
    )
    export_dump_parser.add_argument(
        "--output-dir",
        default="exports",
        help="Output directory for dump file (default: exports)",
    )
    export_dump_parser.add_argument(
        "--container-name",
        default="oevk",
        help="Docker container name (default: oevk)",
    )
    export_dump_parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Use local pg_dump instead of Docker container",
    )
    export_dump_parser.add_argument(
        "--host",
        default="localhost",
        help="PostgreSQL host (default: localhost, only with --no-docker)",
    )
    export_dump_parser.add_argument(
        "--port",
        type=int,
        default=5432,
        help="PostgreSQL port (default: 5432, only with --no-docker)",
    )
    export_dump_parser.add_argument(
        "--database",
        default="oevk",
        help="Database name (default: oevk)",
    )
    export_dump_parser.add_argument(
        "--user",
        default="oevk",
        help="PostgreSQL user (default: oevk)",
    )
    export_dump_parser.add_argument(
        "--password",
        default="oevk",
        help="PostgreSQL password (default: oevk)",
    )

    # db import-dump command
    import_dump_parser = db_subparsers.add_parser(
        "import-dump", help="Import gzipped PostgreSQL dump file"
    )
    import_dump_parser.add_argument(
        "dump_file",
        help="Path to .sql.gz dump file to import",
    )
    import_dump_parser.add_argument(
        "--container-name",
        default="oevk",
        help="Docker container name (default: oevk)",
    )
    import_dump_parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Use local psql instead of Docker container",
    )
    import_dump_parser.add_argument(
        "--host",
        default="localhost",
        help="PostgreSQL host (default: localhost, only with --no-docker)",
    )
    import_dump_parser.add_argument(
        "--port",
        type=int,
        default=5432,
        help="PostgreSQL port (default: 5432, only with --no-docker)",
    )
    import_dump_parser.add_argument(
        "--database",
        default="oevk",
        help="Database name (default: oevk)",
    )
    import_dump_parser.add_argument(
        "--user",
        default="oevk",
        help="PostgreSQL user (default: oevk)",
    )
    import_dump_parser.add_argument(
        "--password",
        default="oevk",
        help="PostgreSQL password (default: oevk)",
    )

    # db verify command
    verify_parser = db_subparsers.add_parser(
        "verify", help="Verify PostgreSQL import and create gzipped dump"
    )
    verify_parser.add_argument(
        "--exports-dir",
        default="exports",
        help="Path to exports directory (default: exports)",
    )
    verify_parser.add_argument(
        "--container-name",
        default="oevk-verify",
        help="Docker container name (default: oevk-verify)",
    )
    verify_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep the verification container running after completion",
    )

    # Geocode commands
    geocode_parser = subparsers.add_parser(
        "geocode", help="Manage address geocoding with Nominatim"
    )
    geocode_subparsers = geocode_parser.add_subparsers(
        dest="geocode_command", help="Geocoding operation to perform"
    )

    # geocode setup command
    setup_geocode_parser = geocode_subparsers.add_parser(
        "setup", help="Set up and start Nominatim Docker service"
    )
    setup_geocode_parser.add_argument(
        "--force-reimport",
        action="store_true",
        help="Force reimport of OSM data (destroys existing Nominatim database)",
    )
    setup_geocode_parser.add_argument(
        "--container-name",
        default=None,
        help="Docker container name (default: from NOMINATIM_CONTAINER_NAME env var)",
    )
    setup_geocode_parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Disable progress monitoring during import",
    )
    setup_geocode_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify database by testing known Hungarian addresses after setup",
    )
    setup_geocode_parser.add_argument(
        "--create-dump",
        action="store_true",
        help="Create database dump (nominatim.tar.gz) after successful setup for faster future imports",
    )
    setup_geocode_parser.add_argument(
        "--use-dump",
        action="store_true",
        help="Restore from nominatim.tar.gz if available (5-10 min vs 1-2 hours fresh import)",
    )

    # geocode run command
    run_geocode_parser = geocode_subparsers.add_parser(
        "run", help="Run geocoding on addresses and polling stations"
    )
    run_geocode_parser.add_argument(
        "--db-path",
        default="data/oevk.db",
        help="Path to the database file (default: data/oevk.db)",
    )
    run_geocode_parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Number of addresses per batch (default: from NOMINATIM_BATCH_SIZE env var)",
    )
    run_geocode_parser.add_argument(
        "--run-tag",
        help="Run tag for tracking geocoding operations (default: 'geocoding')",
    )
    run_geocode_parser.add_argument(
        "--ignore-geocoded",
        action="store_true",
        help="Skip addresses that already have successful coordinates (retry only failures)",
    )
    run_geocode_parser.add_argument(
        "--update-from-cache",
        action="store_true",
        help="Update database from cache only (no actual geocoding) - useful to populate DB from pre-built cache",
    )

    # geocode status command
    status_geocode_parser = geocode_subparsers.add_parser(
        "status", help="Show geocoding statistics and coverage"
    )
    status_geocode_parser.add_argument(
        "--db-path",
        default="data/oevk.db",
        help="Path to the database file (default: data/oevk.db)",
    )

    # Release commands (if available)
    if RELEASE_AVAILABLE:
        release_parser = subparsers.add_parser(
            "release",
            help="Manage data releases (defaults to creating release with auto-detected repo and latest export)",
        )

        # Add optional flags that apply to default behavior
        release_parser.add_argument(
            "--staging-dir",
            default="data/staging",
            help="Staging directory (default: data/staging)",
        )
        release_parser.add_argument(
            "--exports-dir",
            default="exports",
            help="Exports directory (default: exports)",
        )
        release_parser.add_argument(
            "--github-token", help="GitHub token (default: GITHUB_TOKEN env var)"
        )
        release_parser.add_argument(
            "--draft", action="store_true", help="Create as draft release"
        )
        release_parser.add_argument(
            "--prerelease", action="store_true", help="Create as prerelease"
        )
        release_parser.add_argument(
            "--force", action="store_true", help="Force overwrite existing release"
        )
        release_parser.add_argument(
            "--force-rebuild",
            action="store_true",
            help="Force rebuild ZIP files even if they exist (default: skip if exists)",
        )
        release_parser.add_argument(
            "--skip-upload",
            action="store_true",
            help="Skip GitHub upload (create packages only)",
        )

        release_subparsers = release_parser.add_subparsers(
            dest="release_command", help="Release command"
        )

        # Release validate command
        validate_parser = release_subparsers.add_parser(
            "validate", help="Validate data for release"
        )
        validate_parser.add_argument(
            "--staging-dir",
            default="data/staging",
            help="Staging directory (default: data/staging)",
        )
        validate_parser.add_argument(
            "--exports-dir",
            default="exports",
            help="Exports directory (default: exports)",
        )

        # Release create command
        create_parser = release_subparsers.add_parser(
            "create", help="Create a new release"
        )
        create_parser.add_argument(
            "--tag", help="Release tag (default: auto-generated)"
        )
        create_parser.add_argument(
            "--repo-owner", required=True, help="GitHub repository owner"
        )
        create_parser.add_argument(
            "--repo-name", required=True, help="GitHub repository name"
        )
        create_parser.add_argument(
            "--github-token", help="GitHub token (default: GITHUB_TOKEN env var)"
        )
        create_parser.add_argument(
            "--staging-dir",
            default="data/staging",
            help="Staging directory (default: data/staging)",
        )
        create_parser.add_argument(
            "--exports-dir",
            default="exports",
            help="Exports directory (default: exports)",
        )
        create_parser.add_argument(
            "--draft", action="store_true", help="Create as draft release"
        )
        create_parser.add_argument(
            "--prerelease", action="store_true", help="Create as prerelease"
        )
        create_parser.add_argument(
            "--auto", action="store_true", help="Auto-generate tag and create release"
        )
        create_parser.add_argument(
            "--force", action="store_true", help="Force overwrite existing release"
        )
        create_parser.add_argument(
            "--force-rebuild",
            action="store_true",
            help="Force rebuild ZIP files even if they exist (default: skip if exists)",
        )
        create_parser.add_argument(
            "--skip-upload",
            action="store_true",
            help="Skip GitHub upload (create packages only)",
        )

        # Release status command
        status_parser = release_subparsers.add_parser(
            "status", help="Check release status"
        )
        status_parser.add_argument("--tag", required=True, help="Release tag")
        status_parser.add_argument(
            "--repo-owner", required=True, help="GitHub repository owner"
        )
        status_parser.add_argument(
            "--repo-name", required=True, help="GitHub repository name"
        )
        status_parser.add_argument(
            "--github-token", help="GitHub token (default: GITHUB_TOKEN env var)"
        )

        # Release export command
        release_export_parser = release_subparsers.add_parser(
            "export", help="Export data for release"
        )
        release_export_parser.add_argument(
            "--db-path",
            default="data/oevk.db",
            help="Path to the database file (default: data/oevk.db)",
        )
        release_export_parser.add_argument(
            "--output-dir",
            default="exports",
            help="Output directory for CSV files (default: exports)",
        )
        release_export_parser.add_argument(
            "--run-tag", help="Custom run tag (default: timestamp)"
        )
        release_export_parser.add_argument(
            "--max-workers",
            type=int,
            default=8,
            help="Maximum number of parallel workers for export (default: 8)",
        )

        # Release history command
        history_parser = release_subparsers.add_parser(
            "history", help="List recent releases"
        )
        history_parser.add_argument(
            "--repo-owner", required=True, help="GitHub repository owner"
        )
        history_parser.add_argument(
            "--repo-name", required=True, help="GitHub repository name"
        )
        history_parser.add_argument(
            "--github-token", help="GitHub token (default: GITHUB_TOKEN env var)"
        )
        history_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Number of releases to show (default: 10)",
        )

    args = parser.parse_args()

    # Setup logging with console output
    log_level = "DEBUG" if hasattr(args, "verbose") and args.verbose else "INFO"
    setup_logging(log_level=log_level, log_format="simple")

    if args.command == "run":
        run_pipeline(args)
    elif args.command == "export":
        export_data(args)
    elif args.command == "db":
        handle_db_command(args)
    elif args.command == "geocode":
        handle_geocode_command(args)
    elif args.command == "release" and RELEASE_AVAILABLE:
        handle_release_command(args)
    else:
        parser.print_help()
        sys.exit(1)


def export_data(args):
    """Export data to CSV files."""
    logger.info("Starting data export")

    # Initialize configuration
    config = Config()

    # Generate run tag
    run_tag = args.run_tag or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f"Run tag: {run_tag}")

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Clean up old export files before starting new export
    logger.info("Cleaning up old export files...")
    old_files_removed = 0

    # Remove old Address directories
    for old_dir in glob.glob(os.path.join(args.output_dir, "*_Address")):
        if os.path.isdir(old_dir):
            shutil.rmtree(old_dir)
            old_files_removed += 1
            logger.info(f"Removed old directory: {os.path.basename(old_dir)}")

    # Remove old timestamped CSV files (but not symlinks)
    for old_file in glob.glob(os.path.join(args.output_dir, "*_*.csv")):
        if os.path.isfile(old_file) and not os.path.islink(old_file):
            os.remove(old_file)
            old_files_removed += 1
            logger.debug(f"Removed old file: {os.path.basename(old_file)}")

    if old_files_removed > 0:
        logger.info(f"Cleaned up {old_files_removed} old export files/directories")
    else:
        logger.info("No old export files found to clean up")

    # Check if database exists
    if not os.path.exists(args.db_path):
        logger.error(f"Database not found at {args.db_path}")
        logger.error("Please run the pipeline first: python src/cli.py run")
        return

    try:
        # Get database connection
        logger.info(f"Connecting to database: {args.db_path}")
        conn = get_database_connection(args.db_path)

        # Determine what to export
        export_tables = not args.addresses_only
        export_addresses = not args.tables_only

        if args.tables_only and args.addresses_only:
            logger.warning(
                "Both --tables-only and --addresses-only specified, exporting all"
            )
            export_tables = True
            export_addresses = True

        # Determine export formats based on flag
        skip_postgresql = getattr(args, "skip_postgresql_export", False)
        formats = ["csv"] if skip_postgresql else ["csv", "postgresql"]

        if skip_postgresql:
            logger.info("PostgreSQL export disabled (--skip-postgresql-export)")

        # Export entity tables
        if export_tables:
            logger.info("=== EXPORTING ENTITY TABLES ===")
            export_tables_to_csv(conn, args.output_dir, run_tag, formats=formats)
            logger.info("Entity tables export completed")

        # Flag to track if PostgreSQL export was done
        postgresql_exported = export_tables and not skip_postgresql

        # Export addresses
        if export_addresses:
            logger.info("=== EXPORTING ADDRESSES ===")

            # Get max_workers from args or config
            max_workers = getattr(args, "max_workers", None) or config.get(
                "export.max_workers", 8
            )

            # Export canonical (deduplicated) addresses with UUID v3 (optimized)
            logger.info("Exporting canonical addresses (optimized single-query)")
            export_canonical_addresses_optimized(
                conn, args.output_dir, run_tag, formats=formats
            )
            postgresql_exported = postgresql_exported or (not skip_postgresql)

            # Optionally export all original addresses (for debugging/analysis)
            if args.export_original_addresses:
                logger.info(
                    "Exporting original addresses (--export-original-addresses enabled)"
                )
                export_addresses_partitioned(conn, args.output_dir, run_tag)
            else:
                logger.info(
                    "Skipping original address export (use --export-original-addresses to enable)"
                )

        # Create release symlinks/copies for validation compatibility
        # Determine method: explicit flag overrides auto-detection
        use_copies = None
        if hasattr(args, "use_copies") and args.use_copies:
            use_copies = True
        elif hasattr(args, "use_symlinks") and args.use_symlinks:
            use_copies = False
        create_release_symlinks(
            args.output_dir, run_tag, args.db_path, use_copies=use_copies
        )

        conn.close()

        # Verify PostgreSQL import and create gzipped dump
        if postgresql_exported:
            logger.info("")
            logger.info("=== POSTGRESQL VERIFICATION AND DUMP ===")
            try:
                dump_path = verify_and_dump_postgresql(
                    exports_dir=args.output_dir,
                    container_name="oevk-verify-export",
                    cleanup=True,
                    run_tag=run_tag,
                )
                if dump_path:
                    logger.info(f"✓ PostgreSQL dump created: {dump_path}")
            except Exception as e:
                logger.warning(f"PostgreSQL verification failed (non-fatal): {e}")
                logger.warning("Export completed but gzipped dump was not created")

        logger.info("✓ Export completed successfully")

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise


def run_pipeline(args):
    """Run the complete data processing pipeline."""
    logger.info("Starting OEVK data processing pipeline")

    # Initialize configuration
    config = Config()

    # Initialize performance metrics
    metrics = PipelineMetrics("oevk_pipeline")
    metrics.start_pipeline()

    # Generate run tag
    run_tag = args.run_tag or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f"Run tag: {run_tag}")

    # Create directories
    os.makedirs(args.staging_dir, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(
        os.path.dirname(args.db_path) if os.path.dirname(args.db_path) else ".",
        exist_ok=True,
    )

    # Define source URLs
    sources = {
        "oevk_json": "https://static.valasztas.hu/dyn/oevk_data/oevk.json",
        "korzet_zip": "https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip",
    }

    # Determine which stages to run
    stages = [stage.strip() for stage in args.stages.split(",")]

    # Clean up old database BEFORE creating connection (if ingestion stage is included)
    if "ingest" in stages:
        logger.info("=== DATABASE CLEANUP ===")
        if not (hasattr(args, "no_cleanup") and args.no_cleanup):
            if os.path.exists(args.db_path):
                logger.info(f"Removing existing database: {args.db_path}")
                os.remove(args.db_path)
                logger.info("Database removed successfully - starting with clean slate")
            else:
                logger.info("No existing database found - starting fresh")
        else:
            logger.info("Database cleanup skipped (--no-cleanup flag set)")
            logger.info("Existing data will be preserved")

    # Get database connection (after cleanup)
    conn = get_database_connection(args.db_path)

    try:
        # Run ingestion stage
        if "ingest" in stages:
            logger.info("=== INGESTION STAGE ===")

            metrics.log_step_start("ingest")
            file_paths = download_sources(sources, args.staging_dir)

            load_staging_data(conn, file_paths, run_tag)

            # Get row count after ingestion (try staging_korzet first, fall back to staging_oevk_json)
            try:
                staging_count_after = conn.execute(
                    "SELECT COUNT(*) FROM staging_korzet"
                ).fetchone()[0]
            except Exception:
                try:
                    staging_count_after = conn.execute(
                        "SELECT COUNT(*) FROM staging_oevk_json"
                    ).fetchone()[0]
                except Exception:
                    staging_count_after = 0
                    logger.warning("Could not get row count from staging tables")

            metrics.log_step_completion("ingest", row_count=staging_count_after)

        # Run transformation stage
        if "transform" in stages:
            logger.info("=== TRANSFORMATION STAGE ===")
            metrics.log_step_start("transform")

            # Log optimization settings
            logger.info(
                f"Optimization settings: chunk_size={args.chunk_size}, parallel={not args.no_parallel}"
            )

            # Get row counts before transformation
            target_counts_before = {}
            target_tables = [
                "County",
                "Settlement",
                "NationalIndividualElectoralDistrict",
                "SettlementIndividualElectoralDistrict",
                "PollingStation",
                "Address",
                "PostalCode",
                "PostalCode_Settlement",
                "PublicSpaceName",
                "PublicSpaceType",
                "SettlementPublicSpaces",
            ]
            for table in target_tables:
                target_counts_before[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]

            # Use optimized transformation with configurable chunk size and parallel processing
            if hasattr(args, "no_optimized") and args.no_optimized:
                from src.etl.transform import transform_all

                transform_all(conn, run_tag)
            else:
                enable_dedup = not (
                    hasattr(args, "no_deduplication") and args.no_deduplication
                )
                dedup_result = transform_all_optimized(
                    conn,
                    run_tag,
                    chunk_size=args.chunk_size,
                    parallel=not args.no_parallel,
                    db_path=args.db_path,
                    enable_deduplication=enable_dedup,
                )

                # Log deduplication results if available
                if dedup_result and "deduplication_report" in dedup_result:
                    report = dedup_result["deduplication_report"]
                    logger.info(
                        f"Deduplication: {report.total_addresses:,} addresses → "
                        f"{report.canonical_addresses_created:,} canonical "
                        f"({report.duplicates_found:,} duplicates merged)"
                    )

            # Run public space extraction after main transformation
            logger.info("=== PUBLIC SPACE EXTRACTION ===")
            from src.etl.transform_public_spaces import extract_public_space_entities

            extract_public_space_entities(conn)

            # Get row counts after transformation and calculate deltas
            total_rows_transformed = 0
            for table in target_tables:
                count_after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                    0
                ]
                delta = count_after - target_counts_before[table]
                total_rows_transformed += delta
                logger.info(f"{table}: {count_after} rows ({delta:+d} new)")

            metrics.log_step_completion("transform", row_count=total_rows_transformed)

        # Run export stage
        if "export" in stages:
            logger.info("=== EXPORT STAGE ===")
            metrics.log_step_start("export")

            # Get total row count for export (use Address table instead of staging)
            # staging_korzet may not exist if running export independently
            try:
                total_rows = conn.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
            except Exception:
                # Fallback if Address doesn't exist either
                total_rows = 0
                logger.warning("Could not get row count from Address table")

            # Determine export formats based on flag
            skip_postgresql = getattr(args, "skip_postgresql_export", False)
            formats = ["csv"] if skip_postgresql else ["csv", "postgresql"]

            if skip_postgresql:
                logger.info("PostgreSQL export disabled (--skip-postgresql-export)")

            export_tables_to_csv(conn, args.output_dir, run_tag, formats=formats)

            # Export canonical (deduplicated) addresses with UUID v3 (optimized)
            logger.info("Exporting canonical addresses (optimized single-query)")
            export_canonical_addresses_optimized(
                conn, args.output_dir, run_tag, formats=formats
            )

            # Optionally export all original addresses (for debugging/analysis)
            if args.export_original_addresses:
                logger.info(
                    "Exporting original addresses (--export-original-addresses enabled)"
                )
                export_addresses_partitioned(conn, args.output_dir, run_tag)
            else:
                logger.info(
                    "Skipping original address export (use --export-original-addresses to enable)"
                )

            # Create release symlinks/copies for validation compatibility
            # Determine method: explicit flag overrides auto-detection
            use_copies = None
            if hasattr(args, "use_copies") and args.use_copies:
                use_copies = True
            elif hasattr(args, "use_symlinks") and args.use_symlinks:
                use_copies = False
            create_release_symlinks(
                args.output_dir, run_tag, args.db_path, use_copies=use_copies
            )

            metrics.log_step_completion("export", row_count=total_rows)

        # Final pipeline summary
        total_duration = time.time() - (metrics.start_time or time.time())

        # Get total row count (prefer Address table if available, fall back to staging)
        try:
            total_rows = conn.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
        except Exception:
            try:
                total_rows = conn.execute(
                    "SELECT COUNT(*) FROM staging_korzet"
                ).fetchone()[0]
            except Exception:
                try:
                    total_rows = conn.execute(
                        "SELECT COUNT(*) FROM staging_oevk_json"
                    ).fetchone()[0]
                except Exception:
                    total_rows = 0
                    logger.warning("Could not get row count for performance summary")

        logger.info("=== PIPELINE PERFORMANCE SUMMARY ===")
        logger.info(f"Total duration: {total_duration:.2f} seconds")
        logger.info(f"Total rows processed: {total_rows:,}")
        logger.info(f"Processing rate: {total_rows / total_duration:.2f} rows/second")

        # NFR-002 Compliance Check
        nfr_002_target = 30 * 60  # 30 minutes in seconds
        if total_duration <= nfr_002_target:
            logger.info(
                f"✅ NFR-002 COMPLIANT: Pipeline completed in {total_duration:.2f}s (target: ≤{nfr_002_target}s)"
            )
        else:
            logger.warning(
                f"⚠️ NFR-002 NON-COMPLIANT: Pipeline took {total_duration:.2f}s (target: ≤{nfr_002_target}s)"
            )

        # Verify PostgreSQL import and create gzipped dump (after export stage)
        if "export" in stages and not skip_postgresql:
            logger.info("")
            logger.info("=== POSTGRESQL VERIFICATION AND DUMP ===")
            try:
                dump_path = verify_and_dump_postgresql(
                    exports_dir=args.output_dir,
                    container_name="oevk-verify-pipeline",
                    cleanup=True,
                    run_tag=run_tag,
                )
                if dump_path:
                    logger.info(f"✓ PostgreSQL dump created: {dump_path}")
            except Exception as e:
                logger.warning(f"PostgreSQL verification failed (non-fatal): {e}")
                logger.warning("Pipeline completed but gzipped dump was not created")

        logger.info("Pipeline completed successfully")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)

    finally:
        # Close database connection
        conn.close()


def handle_db_command(args):
    """Handle database subcommands."""
    if args.db_command == "setup":
        setup_database(args)
    elif args.db_command == "import-csv":
        import_csv_to_postgresql(args)
    elif args.db_command == "export-dump":
        export_database_dump(args)
    elif args.db_command == "import-dump":
        import_database_dump(args)
    elif args.db_command == "verify":
        verify_postgresql_import(args)
    else:
        print(
            "Unknown database command. Use 'db setup', 'db import-csv', 'db export-dump', 'db import-dump', or 'db verify'."
        )
        sys.exit(1)


def import_csv_to_postgresql(args):
    """Import CSV files into PostgreSQL using fast COPY method."""
    import getpass
    import subprocess
    from pathlib import Path

    from src.utils.docker_postgresql import DockerPostgreSQLManager

    logger.info("=== PostgreSQL CSV Import ===")

    exports_dir = Path(args.exports_dir)
    schema_file = exports_dir / "schema.sql"
    import_file = exports_dir / "import_postgresql.sql"
    postgresql_dir = exports_dir / "postgresql"

    # Validate files exist
    if not schema_file.exists():
        logger.error(f"Schema file not found: {schema_file}")
        logger.info("Run 'python -m src.cli export' first to generate PostgreSQL files")
        sys.exit(1)

    if not import_file.exists():
        logger.error(f"Import script not found: {import_file}")
        logger.info("Run 'python -m src.cli export' first to generate PostgreSQL files")
        sys.exit(1)

    if not postgresql_dir.exists() or not postgresql_dir.is_dir():
        logger.error(f"PostgreSQL CSV directory not found: {postgresql_dir}")
        logger.info(
            "Run 'python -m src.cli export' first to generate PostgreSQL CSV files"
        )
        sys.exit(1)

    # Count CSV files
    csv_files = list(postgresql_dir.glob("*.csv"))
    logger.info(f"Found {len(csv_files)} CSV files in {postgresql_dir}")

    # Docker mode
    if args.docker:
        logger.info("Using Docker PostgreSQL container")

        config = Config()
        use_postgis = config.get("postgresql.use_postgis", True)

        manager = DockerPostgreSQLManager(
            container_name=args.container_name, use_postgis=use_postgis
        )

        try:
            # Check if container exists
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={args.container_name}",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            if args.container_name in result.stdout:
                logger.info(f"Using existing container: {args.container_name}")

                # Check if running
                result = subprocess.run(
                    [
                        "docker",
                        "ps",
                        "--filter",
                        f"name={args.container_name}",
                        "--format",
                        "{{.Names}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                if args.container_name not in result.stdout:
                    logger.info("Starting container...")
                    subprocess.run(["docker", "start", args.container_name], check=True)

                    # Wait for ready
                    if not manager.wait_for_ready(timeout=30):
                        logger.error("Container failed to become ready")
                        sys.exit(1)
            else:
                logger.info(f"Creating new container: {args.container_name}")
                manager.create_container()

                if not manager.wait_for_ready(timeout=30):
                    logger.error("Container failed to become ready")
                    sys.exit(1)

            conn_info = manager.get_connection_info()
            host = "localhost"
            port = conn_info["port"]
            database = conn_info["database"]
            user = conn_info["user"]
            password = conn_info["password"]

        except Exception as e:
            logger.error(f"Failed to setup Docker container: {e}")
            sys.exit(1)
    else:
        # Direct connection
        host = args.host
        port = args.port
        database = args.database
        user = args.user
        password = args.password

        # Prompt for password if not provided
        if not password:
            password = getpass.getpass(f"Password for {user}@{host}:{port}: ")

    logger.info(f"Connection: {user}@{host}:{port}/{database}")

    # Handle database creation/recreation
    if args.drop_database:
        logger.warning(f"Dropping database: {database}")

        if args.docker:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    args.container_name,
                    "psql",
                    "-U",
                    user,
                    "-d",
                    "postgres",
                    "-c",
                    f"DROP DATABASE IF EXISTS {database};",
                ],
                capture_output=True,
                text=True,
            )
        else:
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
                    "postgres",
                    "-c",
                    f"DROP DATABASE IF EXISTS {database};",
                ],
                env={"PGPASSWORD": password},
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            logger.warning(f"Could not drop database: {result.stderr}")

        args.create_database = True  # Force creation after drop

    if args.create_database:
        logger.info(f"Creating database: {database}")

        if args.docker:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    args.container_name,
                    "psql",
                    "-U",
                    user,
                    "-d",
                    "postgres",
                    "-c",
                    f"CREATE DATABASE {database};",
                ],
                capture_output=True,
                text=True,
            )
        else:
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
                    "postgres",
                    "-c",
                    f"CREATE DATABASE {database};",
                ],
                env={"PGPASSWORD": password},
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            if "already exists" not in result.stderr:
                logger.error(f"Failed to create database: {result.stderr}")
                sys.exit(1)
            else:
                logger.info("Database already exists")

        # Enable PostGIS if available
        logger.info("Enabling PostGIS extension...")

        if args.docker:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    args.container_name,
                    "psql",
                    "-U",
                    user,
                    "-d",
                    database,
                    "-c",
                    "CREATE EXTENSION IF NOT EXISTS postgis;",
                ],
                capture_output=True,
                text=True,
            )
        else:
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
                    "-c",
                    "CREATE EXTENSION IF NOT EXISTS postgis;",
                ],
                env={"PGPASSWORD": password},
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            logger.warning(f"Could not enable PostGIS: {result.stderr}")

    # Import schema and CSV data
    if args.docker:
        # Use Docker exec for import (copy files to container)
        logger.info("Step 1/3: Copying files to Docker container...")

        # Copy exports directory to container
        exports_dir_abs = exports_dir.absolute()
        subprocess.run(
            [
                "docker",
                "cp",
                str(exports_dir_abs),
                f"{args.container_name}:/tmp/exports",
            ],
            check=True,
            capture_output=True,
        )
        logger.info(f"✓ Copied exports to /tmp/exports in container")

        # Import schema
        logger.info("Step 2/3: Importing schema...")
        result = subprocess.run(
            [
                "docker",
                "exec",
                args.container_name,
                "psql",
                "-U",
                user,
                "-d",
                database,
                "-f",
                "/tmp/exports/schema.sql",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Schema import failed: {result.stderr}")
            sys.exit(1)

        logger.info("✓ Schema imported successfully")

        # Create Docker-compatible import script (rewrite paths to /tmp/exports/postgresql/)
        logger.info("Creating Docker-compatible import script...")
        import re

        with open(import_file, "r", encoding="utf-8") as f:
            import_content = f.read()

        # Replace paths: FROM '/path/to/postgresql/File.csv' -> FROM '/tmp/exports/postgresql/File.csv'
        import_content = re.sub(
            r"FROM '.*?/postgresql/([^']+)'",
            r"FROM '/tmp/exports/postgresql/\1'",
            import_content,
        )

        # Write to temp file
        docker_import_file = exports_dir / "import_postgresql_docker.sql"
        with open(docker_import_file, "w", encoding="utf-8") as f:
            f.write(import_content)

        # Copy Docker import script to container
        subprocess.run(
            [
                "docker",
                "cp",
                str(docker_import_file),
                f"{args.container_name}:/tmp/import_postgresql.sql",
            ],
            check=True,
            capture_output=True,
        )

        # Import CSV data
        logger.info(f"Step 3/3: Importing CSV data ({len(csv_files)} files)...")
        logger.info("This may take 5-15 minutes for 3.3M addresses...")
        logger.info("Progress output will be shown below...")

        # Run without capturing output so we can see progress in real-time
        result = subprocess.run(
            [
                "docker",
                "exec",
                args.container_name,
                "psql",
                "-U",
                user,
                "-d",
                database,
                "-f",
                "/tmp/import_postgresql.sql",
            ]
        )

        if result.returncode != 0:
            logger.error(f"CSV import failed with exit code {result.returncode}")
            sys.exit(1)

        logger.info("✓ CSV data imported successfully")

        # Clean up temp file
        if docker_import_file.exists():
            docker_import_file.unlink()
    else:
        # Use host psql (requires psql installed locally)
        logger.info("Step 1/2: Importing schema...")
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
                "-f",
                str(schema_file),
            ],
            env={"PGPASSWORD": password},
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Schema import failed: {result.stderr}")
            sys.exit(1)

        logger.info("✓ Schema imported successfully")

        # Import CSV data
        logger.info(f"Step 2/2: Importing CSV data ({len(csv_files)} files)...")
        logger.info("This may take 5-15 minutes for 3.3M addresses...")
        logger.info("Progress output will be shown below...")

        # Run without capturing output so we can see progress in real-time
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
                "-f",
                str(import_file),
            ],
            env={"PGPASSWORD": password},
        )

        if result.returncode != 0:
            logger.error(f"CSV import failed with exit code {result.returncode}")
            sys.exit(1)

        logger.info("✓ CSV data imported successfully")

    # Verify import
    logger.info("Verifying import...")

    if args.docker:
        # Use Docker exec for verification (try lowercase first, then uppercase)
        result = subprocess.run(
            [
                "docker",
                "exec",
                args.container_name,
                "psql",
                "-U",
                user,
                "-d",
                database,
                "-t",
                "-c",
                "SELECT COUNT(*) FROM address;",
            ],
            capture_output=True,
            text=True,
        )

        # If lowercase fails, try uppercase (quoted)
        if result.returncode != 0:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    args.container_name,
                    "psql",
                    "-U",
                    user,
                    "-d",
                    database,
                    "-t",
                    "-c",
                    'SELECT COUNT(*) FROM "Address";',
                ],
                capture_output=True,
                text=True,
                check=True,
            )

        address_count = int(result.stdout.strip())
        logger.info(f"✓ Verification successful: {address_count:,} addresses imported")

        # Show table counts
        logger.info("\nTable row counts:")
        result = subprocess.run(
            [
                "docker",
                "exec",
                args.container_name,
                "psql",
                "-U",
                user,
                "-d",
                database,
                "-c",
                "SELECT schemaname, relname as tablename, n_live_tup as row_count FROM pg_stat_user_tables ORDER BY n_live_tup DESC;",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        logger.info(result.stdout)
    else:
        # Use host psql for verification (try lowercase first, then uppercase)
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
                "-t",
                "-c",
                "SELECT COUNT(*) FROM address;",
            ],
            env={"PGPASSWORD": password},
            capture_output=True,
            text=True,
        )

        # If lowercase fails, try uppercase (quoted)
        if result.returncode != 0:
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
                    "-t",
                    "-c",
                    'SELECT COUNT(*) FROM "Address";',
                ],
                env={"PGPASSWORD": password},
                capture_output=True,
                text=True,
                check=True,
            )

        address_count = int(result.stdout.strip())
        logger.info(f"✓ Verification successful: {address_count:,} addresses imported")

        # Show table counts
        logger.info("\nTable row counts:")
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
                "-c",
                "SELECT schemaname, relname as tablename, n_live_tup as row_count FROM pg_stat_user_tables ORDER BY n_live_tup DESC;",
            ],
            env={"PGPASSWORD": password},
            capture_output=True,
            text=True,
            check=True,
        )

        logger.info(result.stdout)

    logger.info("\n=== PostgreSQL CSV Import Completed Successfully ===")
    if args.docker:
        logger.info(
            f"Connection: docker exec -it {args.container_name} psql -U {user} -d {database}"
        )
    else:
        logger.info(f"Connection: psql -h {host} -p {port} -U {user} -d {database}")


# ============================================================================
# Nominatim Helper Functions
# ============================================================================


def monitor_nominatim_logs(container_name):
    """Monitor Nominatim logs in a background thread and show progress."""
    import subprocess
    import threading

    def _monitor():
        """Background monitoring function."""
        try:
            # Use the monitoring script
            subprocess.run(
                [
                    "python",
                    "scripts/monitor_nominatim_import.py",
                    "--container",
                    container_name,
                ],
                check=False,
            )
        except Exception as e:
            logger.debug(f"Monitoring thread error: {e}")

    # Start monitoring in background thread
    monitor_thread = threading.Thread(target=_monitor, daemon=True)
    monitor_thread.start()
    return monitor_thread


def wait_for_nominatim_ready(container_name, base_url, max_wait_minutes=120):
    """
    Wait for Nominatim with better progress indication.

    Args:
        container_name: Docker container name
        base_url: Nominatim base URL (e.g., http://localhost:8081)
        max_wait_minutes: Maximum wait time in minutes

    Returns:
        bool: True if ready, False if timeout
    """
    import time

    import requests

    start_time = time.time()
    max_seconds = max_wait_minutes * 60

    logger.info(f"Waiting for Nominatim (max {max_wait_minutes} minutes)...")
    logger.info(
        f"Monitoring logs in background. Check: docker logs -f {container_name}"
    )

    last_log_time = time.time()

    while (time.time() - start_time) < max_seconds:
        try:
            response = requests.get(f"{base_url}/status", timeout=5)
            if response.status_code == 200:
                elapsed = int(time.time() - start_time)
                logger.info(
                    f"✅ Nominatim ready after {elapsed // 60}m {elapsed % 60}s"
                )
                logger.info(f"Service URL: {base_url}")
                return True
        except Exception:
            pass

        elapsed = int(time.time() - start_time)
        current_time = time.time()

        # Log progress every minute
        if current_time - last_log_time >= 60:
            logger.info(f"Still importing... ({elapsed // 60} minutes elapsed)")
            last_log_time = current_time

        time.sleep(10)

    logger.error(f"Nominatim not ready after {max_wait_minutes} minutes")
    logger.info(f"Check logs: docker logs {container_name}")
    return False


def verify_nominatim_database(container_name, base_url):
    """
    Verify Nominatim database has Hungary data by testing known addresses.

    Args:
        container_name: Docker container name
        base_url: Nominatim base URL

    Returns:
        bool: True if verification passed
    """
    import requests

    logger.info("\nVerifying Nominatim database...")

    # Test geocoding of known Hungarian addresses
    test_queries = [
        ("Budapest, Barát utca 5", "Budapest"),
        ("Debrecen, Piac utca 1", "Debrecen"),
        ("Szeged, Dugonics tér 13", "Szeged"),
    ]

    failures = []

    for query, expected_city in test_queries:
        try:
            response = requests.get(
                f"{base_url}/search",
                params={"q": query, "format": "json", "limit": 1},
                timeout=10,
            )
            if response.status_code == 200:
                results = response.json()
                if len(results) > 0:
                    display_name = results[0].get("display_name", "")
                    if expected_city.lower() in display_name.lower():
                        logger.info(f"✓ {query}")
                    else:
                        failures.append(f"{query} - unexpected result: {display_name}")
                        logger.warning(f"✗ {query} - unexpected result")
                else:
                    failures.append(f"{query} - no results")
                    logger.warning(f"✗ {query} - no results")
            else:
                failures.append(f"{query} - HTTP {response.status_code}")
                logger.warning(f"✗ {query} - HTTP error")
        except Exception as e:
            failures.append(f"{query} - {str(e)}")
            logger.warning(f"✗ {query} - {e}")

    if not failures:
        logger.info("✅ Database verification passed")
        return True
    else:
        logger.warning(f"⚠️  {len(failures)}/{len(test_queries)} tests failed")
        logger.warning("Database may not be fully imported or accessible")
        return False


def create_nominatim_dump(container_name):
    """
    Create database dump for faster future setup.

    Args:
        container_name: Docker container name

    Returns:
        Path to created dump file or None if failed
    """
    import subprocess
    from pathlib import Path

    dump_file = Path("nominatim.tar.gz")

    logger.info("\nCreating database dump...")
    logger.info(f"Output: {dump_file}")
    logger.info("This may take 5-10 minutes...")

    try:
        # Stop container to ensure consistent state
        logger.info(f"Stopping container '{container_name}'...")
        subprocess.run(
            ["docker", "stop", container_name], check=True, capture_output=True
        )

        # Export volume as tar.gz using docker run
        logger.info("Exporting volume data...")
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                "nominatim_data:/data",
                "-v",
                f"{Path.cwd()}:/backup",
                "alpine",
                "tar",
                "czf",
                "/backup/nominatim.tar.gz",
                "-C",
                "/data",
                ".",
            ],
            check=True,
            capture_output=True,
        )

        # Restart container
        logger.info(f"Restarting container '{container_name}'...")
        subprocess.run(
            ["docker", "start", container_name], check=True, capture_output=True
        )

        # Wait for service to be ready again
        time.sleep(5)

        if dump_file.exists():
            dump_size_gb = dump_file.stat().st_size / (1024**3)
            logger.info(f"✅ Dump created: {dump_file} ({dump_size_gb:.2f} GB)")
            logger.info(
                "Future setups can use: python -m src.cli geocode setup --use-dump"
            )
            return dump_file
        else:
            logger.error("❌ Dump file not created")
            return None

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to create dump: {e}")
        # Try to restart container if it was stopped
        try:
            subprocess.run(
                ["docker", "start", container_name], check=False, capture_output=True
            )
        except Exception:
            pass
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error creating dump: {e}")
        return None


def restore_nominatim_dump(container_name, dump_file="nominatim.tar.gz"):
    """
    Restore Nominatim database from existing dump.

    Args:
        container_name: Docker container name
        dump_file: Path to dump file (default: nominatim.tar.gz)

    Returns:
        bool: True if successful
    """
    import subprocess
    from pathlib import Path

    dump_path = Path(dump_file)

    if not dump_path.exists():
        logger.error(f"❌ Dump file not found: {dump_file}")
        return False

    dump_size_gb = dump_path.stat().st_size / (1024**3)
    logger.info(f"\nRestoring from dump: {dump_file} ({dump_size_gb:.2f} GB)")
    logger.info("This may take 5-10 minutes...")

    try:
        # Remove existing volume if it exists
        logger.info("Removing existing volume (if any)...")
        subprocess.run(
            ["docker", "volume", "rm", "nominatim_data"],
            check=False,
            capture_output=True,
        )

        # Create new volume
        logger.info("Creating new volume...")
        subprocess.run(["docker", "volume", "create", "nominatim_data"], check=True)

        # Import volume from tar.gz
        logger.info("Importing volume data...")
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                "nominatim_data:/data",
                "-v",
                f"{Path.cwd()}:/backup",
                "alpine",
                "tar",
                "xzf",
                f"/backup/{dump_file}",
                "-C",
                "/data",
            ],
            check=True,
            capture_output=True,
        )

        # Start container
        logger.info("Starting Nominatim container...")
        subprocess.run(["docker", "compose", "up", "-d", "nominatim"], check=True)

        logger.info("✅ Restored from dump successfully")
        logger.info("Waiting for service to start...")

        # Give it a moment to start
        time.sleep(5)

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to restore from dump: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error restoring dump: {e}")
        return False


# ============================================================================
# Geocoding Commands
# ============================================================================


def geocode_setup(args):
    """Set up and start Nominatim Docker service with enhanced monitoring and options."""
    import subprocess
    from pathlib import Path

    from src.utils.config import get_config

    logger.info("=" * 80)
    logger.info("NOMINATIM GEOCODING SERVICE SETUP")
    logger.info("=" * 80)

    # Get configuration
    config = get_config()
    container_name = args.container_name or config.get("nominatim", {}).get(
        "container_name", "oevk-nominatim"
    )
    base_url = config.get("nominatim", {}).get("base_url", "http://localhost:8081")

    try:
        # Check if Docker is running
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            logger.error("❌ Docker is not running. Please start Docker and try again.")
            sys.exit(1)

        # Check for existing dump file to restore from
        dump_file = Path("nominatim.tar.gz")
        if args.use_dump and dump_file.exists():
            logger.info(f"Found existing database dump: {dump_file}")
            dump_size_gb = dump_file.stat().st_size / (1024**3)
            logger.info(f"Dump size: {dump_size_gb:.2f} GB")
            logger.info("Restoring from dump (much faster than fresh import)...")

            if restore_nominatim_dump(container_name, str(dump_file)):
                # Wait for service to be ready
                if wait_for_nominatim_ready(
                    container_name, base_url, max_wait_minutes=10
                ):
                    # Optionally verify
                    if args.verify:
                        verify_nominatim_database(container_name, base_url)

                    logger.info("\n" + "=" * 80)
                    logger.info("✅ NOMINATIM SETUP COMPLETE (RESTORED FROM DUMP)")
                    logger.info("=" * 80)
                    sys.exit(0)
            else:
                logger.warning("⚠️  Restore failed, falling back to fresh import...")

        # Check if container already exists
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

        container_exists = container_name in result.stdout

        if container_exists and args.force_reimport:
            logger.info(f"Removing existing container '{container_name}' for reimport")
            subprocess.run(["docker", "rm", "-f", container_name], check=True)
            # Also remove volume for clean reimport
            subprocess.run(
                ["docker", "volume", "rm", "nominatim_data"],
                check=False,
                capture_output=True,
            )
            container_exists = False

        if container_exists:
            # Check if container is running
            result = subprocess.run(
                [
                    "docker",
                    "ps",
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
                logger.info(f"✓ Container '{container_name}' is already running")
                logger.info(f"Service URL: {base_url}")

                # Optionally verify even if already running
                if args.verify:
                    verify_nominatim_database(container_name, base_url)

                logger.info("\n" + "=" * 80)
                logger.info("✅ NOMINATIM ALREADY RUNNING")
                logger.info("=" * 80)
                sys.exit(0)
            else:
                logger.info(f"Starting existing container '{container_name}'")
                subprocess.run(["docker", "start", container_name], check=True)

                # Wait briefly and verify
                if wait_for_nominatim_ready(
                    container_name, base_url, max_wait_minutes=5
                ):
                    if args.verify:
                        verify_nominatim_database(container_name, base_url)

                    logger.info("\n" + "=" * 80)
                    logger.info("✅ NOMINATIM SETUP COMPLETE (EXISTING CONTAINER)")
                    logger.info("=" * 80)
                    sys.exit(0)
        else:
            # Fresh import - start new container using docker compose
            logger.info("\n📦 Starting fresh Nominatim import")
            logger.info("   Download: Hungary OSM data (~286 MB)")
            logger.info("   Import time: 45-90 minutes (optimized PostgreSQL settings)")
            logger.info("   Total time: ~1-2 hours depending on hardware\n")

            subprocess.run(["docker", "compose", "up", "-d", "nominatim"], check=True)

            logger.info("✓ Container started")

            # Start background monitoring if not disabled
            if not args.no_monitor:
                logger.info("Starting progress monitor...\n")
                monitor_nominatim_logs(container_name)

        # Wait for service to be ready with enhanced monitoring
        if wait_for_nominatim_ready(container_name, base_url, max_wait_minutes=120):
            # Verify database
            if args.verify:
                verify_nominatim_database(container_name, base_url)

            # Optionally create dump for future use
            if args.create_dump:
                create_nominatim_dump(container_name)

            logger.info("\n" + "=" * 80)
            logger.info("✅ NOMINATIM SETUP COMPLETE")
            logger.info("=" * 80)
            logger.info(f"Service URL: {base_url}")
            logger.info(f"Container: {container_name}")
            logger.info("\nNext steps:")
            logger.info("  1. Test geocoding: python -m src.cli geocode status")
            logger.info("  2. Run geocoding: python -m src.cli geocode run")
            if args.create_dump:
                logger.info(
                    "  3. Share dump: Upload nominatim.tar.gz for faster team setup"
                )
            logger.info("=" * 80)
            sys.exit(0)
        else:
            logger.error("\n❌ Nominatim setup failed - service did not become ready")
            logger.info(f"Check logs: docker logs {container_name}")
            logger.info(f"Check status: docker ps -a | grep {container_name}")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to set up Nominatim service: {e}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Setup interrupted by user")
        logger.info(
            f"Note: Container may still be importing in background. Check: docker logs -f {container_name}"
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error during Nominatim setup: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        sys.exit(1)


def geocode_run(args):
    """Run geocoding on addresses and polling stations."""
    from src.etl.geocoding import geocode_canonical_addresses, geocode_polling_stations

    logger.info("Running geocoding on addresses and polling stations")

    # Get database connection
    db_connection = get_database_connection(args.db_path)

    try:
        run_tag = args.run_tag or "geocoding"

        # Override batch size if provided
        if args.batch_size:
            from src.utils.config import get_config

            config = get_config()
            config["nominatim"]["batch_size"] = args.batch_size

        # Geocode canonical addresses
        logger.info("Geocoding canonical addresses...")
        ignore_geocoded = (
            args.ignore_geocoded if hasattr(args, "ignore_geocoded") else False
        )
        update_from_cache = (
            args.update_from_cache if hasattr(args, "update_from_cache") else False
        )
        address_stats = geocode_canonical_addresses(
            db_connection,
            run_tag,
            ignore_geocoded=ignore_geocoded,
            update_from_cache=update_from_cache,
        )

        logger.info(f"Canonical address geocoding complete:")
        logger.info(f"  Total: {address_stats.get('total', 0)}")
        logger.info(f"  Cached: {address_stats.get('cached', 0)}")
        logger.info(f"  Exact matches: {address_stats.get('exact', 0)}")
        logger.info(f"  Street matches: {address_stats.get('street', 0)}")
        logger.info(f"  Settlement matches: {address_stats.get('settlement', 0)}")
        logger.info(f"  Failed: {address_stats.get('failed', 0)}")

        # Geocode polling stations
        logger.info("Geocoding polling stations...")
        station_stats = geocode_polling_stations(
            db_connection, run_tag, update_from_cache=update_from_cache
        )

        logger.info(f"Polling station geocoding complete:")
        logger.info(f"  Total: {station_stats.get('total', 0)}")
        logger.info(f"  Cached: {station_stats.get('cached', 0)}")
        logger.info(f"  Exact matches: {station_stats.get('exact', 0)}")
        logger.info(f"  Street matches: {station_stats.get('street', 0)}")
        logger.info(f"  Settlement matches: {station_stats.get('settlement', 0)}")
        logger.info(f"  Failed: {station_stats.get('failed', 0)}")

        logger.info("✅ Geocoding completed successfully")

    except Exception as e:
        logger.error(f"Geocoding failed: {e}")
        sys.exit(1)
    finally:
        db_connection.close()


def geocode_status(args):
    """Show geocoding statistics and coverage."""
    logger.info("Retrieving geocoding statistics")

    # Get database connection
    db_connection = get_database_connection(args.db_path)

    try:
        # Query canonical address statistics
        logger.info("\n=== Canonical Address Geocoding Status ===")

        total_addresses = db_connection.execute(
            "SELECT COUNT(*) FROM CanonicalAddress"
        ).fetchone()[0]

        geocoded_addresses = db_connection.execute(
            "SELECT COUNT(*) FROM CanonicalAddress WHERE Latitude IS NOT NULL"
        ).fetchone()[0]

        quality_stats = db_connection.execute("""
            SELECT
                GeocodingQuality,
                COUNT(*) as count
            FROM CanonicalAddress
            WHERE GeocodingQuality IS NOT NULL
            GROUP BY GeocodingQuality
            ORDER BY count DESC
        """).fetchall()

        logger.info(f"Total addresses: {total_addresses:,}")
        logger.info(
            f"Geocoded: {geocoded_addresses:,} ({geocoded_addresses / total_addresses * 100:.1f}%)"
        )
        logger.info(f"Not geocoded: {total_addresses - geocoded_addresses:,}")

        if quality_stats:
            logger.info("\nQuality distribution:")
            for quality, count in quality_stats:
                percentage = (
                    count / geocoded_addresses * 100 if geocoded_addresses > 0 else 0
                )
                logger.info(f"  {quality}: {count:,} ({percentage:.1f}%)")

        # Query polling station statistics
        logger.info("\n=== Polling Station Geocoding Status ===")

        total_stations = db_connection.execute(
            "SELECT COUNT(*) FROM PollingStation"
        ).fetchone()[0]

        geocoded_stations = db_connection.execute(
            "SELECT COUNT(*) FROM PollingStation WHERE Latitude IS NOT NULL"
        ).fetchone()[0]

        station_quality_stats = db_connection.execute("""
            SELECT
                GeocodingQuality,
                COUNT(*) as count
            FROM PollingStation
            WHERE GeocodingQuality IS NOT NULL
            GROUP BY GeocodingQuality
            ORDER BY count DESC
        """).fetchall()

        logger.info(f"Total polling stations: {total_stations:,}")
        logger.info(
            f"Geocoded: {geocoded_stations:,} ({geocoded_stations / total_stations * 100:.1f}%)"
        )
        logger.info(f"Not geocoded: {total_stations - geocoded_stations:,}")

        if station_quality_stats:
            logger.info("\nQuality distribution:")
            for quality, count in station_quality_stats:
                percentage = (
                    count / geocoded_stations * 100 if geocoded_stations > 0 else 0
                )
                logger.info(f"  {quality}: {count:,} ({percentage:.1f}%)")

        logger.info("\n✅ Status check complete")

    except Exception as e:
        logger.error(f"Failed to retrieve geocoding status: {e}")
        sys.exit(1)
    finally:
        db_connection.close()


def handle_geocode_command(args):
    """Handle geocoding subcommands."""
    if args.geocode_command == "setup":
        geocode_setup(args)
    elif args.geocode_command == "run":
        geocode_run(args)
    elif args.geocode_command == "status":
        geocode_status(args)
    else:
        print(
            "Unknown geocode command. Use 'geocode setup', 'geocode run', or 'geocode status'."
        )
        sys.exit(1)


def handle_release_command(args):
    """Handle release subcommands."""
    if not RELEASE_AVAILABLE:
        print("Release functionality is not available")
        sys.exit(1)

    try:
        # If no subcommand provided, default to create with smart defaults
        if args.release_command is None:
            logger.info(
                "No release subcommand specified, defaulting to 'create' with auto-detection"
            )

            # Auto-detect git repository
            repo_owner, repo_name = get_git_repo_info()
            if not repo_owner or not repo_name:
                print(
                    "❌ Error: Could not auto-detect GitHub repository from git remote"
                )
                print(
                    "Please ensure you're in a git repository with a GitHub remote configured"
                )
                print(
                    "Or use: python src/cli.py release create --repo-owner <owner> --repo-name <name>"
                )
                sys.exit(1)

            logger.info(f"Detected repository: {repo_owner}/{repo_name}")

            # Find latest export timestamp
            exports_dir = getattr(args, "exports_dir", "exports")
            timestamp = get_latest_export_timestamp(exports_dir)
            if not timestamp:
                print(f"❌ Error: No export files found in {exports_dir}")
                print(
                    "Please run 'python src/cli.py export' first to generate export files"
                )
                sys.exit(1)

            # Use timestamp as tag (format: v20251013_195208)
            tag = f"v{timestamp}"
            logger.info(f"Using tag from latest export: {tag}")

            # Create release with detected values
            workflow = ReleaseWorkflow(
                repo_owner=repo_owner,
                repo_name=repo_name,
                github_token=getattr(args, "github_token", None),
                staging_dir=getattr(args, "staging_dir", "data/staging"),
                exports_dir=exports_dir,
            )

            result = workflow.execute_full_release(
                tag=tag,
                draft=getattr(args, "draft", False),
                prerelease=getattr(args, "prerelease", False),
                force=getattr(args, "force", False),
                force_rebuild=getattr(args, "force_rebuild", False),
                skip_upload=getattr(args, "skip_upload", False),
            )

            print("=== RELEASE CREATED SUCCESSFULLY ===")
            print(f"Release URL: {result['release'].get('html_url')}")
            print(f"Release Tag: {result['package']['release_tag']}")
            print(f"Repository: {repo_owner}/{repo_name}")
            print(f"Artifacts: {len(result.get('artifacts', []))}")
            return

        if args.release_command == "export":
            # Handle release export - same as standalone export but with cleaner output
            logger.info("Exporting data for release")
            export_data(args)
            logger.info("✓ Release export completed successfully")

        elif args.release_command == "validate":
            workflow = ReleaseWorkflow(
                repo_owner="dummy",  # Not used for validation
                repo_name="dummy",
                staging_dir=args.staging_dir,
                exports_dir=args.exports_dir,
            )
            metadata = workflow.validate_release_data()

            print("=== RELEASE VALIDATION RESULTS ===")
            print(
                f"Overall Status: {'✅ PASS' if metadata.validation_status == 'passed' else '❌ FAIL'}"
            )
            print(f"Total Files: {metadata.total_files}")
            print(f"Total Size: {metadata.total_size} bytes")
            print(f"Pipeline Run ID: {metadata.pipeline_run_id}")

            # Verbose output
            if hasattr(args, "verbose") and args.verbose:
                print(f"\n=== VERBOSE DETAILS ===")
                print(f"Release ID: {metadata.release_id}")
                print(f"Validation Status: {metadata.validation_status}")
                print(f"Pipeline Run ID: {metadata.pipeline_run_id}")

                if metadata.validation_errors:
                    print(f"\nDetailed Validation Errors:")
                    for i, error in enumerate(metadata.validation_errors, 1):
                        print(f"  {i}. {error}")
                else:
                    print("\nDetailed Validation Errors: None")

            if metadata.validation_errors:
                print(f"\nValidation Errors: {len(metadata.validation_errors)}")
                for error in metadata.validation_errors:
                    print(f"  - {error}")
            else:
                print("\nValidation Errors: None")

            if metadata.validation_status != "passed":
                sys.exit(1)

        elif args.release_command == "create":
            workflow = ReleaseWorkflow(
                repo_owner=args.repo_owner,
                repo_name=args.repo_name,
                github_token=args.github_token,
                staging_dir=args.staging_dir,
                exports_dir=args.exports_dir,
            )

            # Determine tag
            tag = args.tag
            if args.auto and not tag:
                tag = None  # Let workflow auto-generate

            result = workflow.execute_full_release(
                tag=tag,
                draft=args.draft,
                prerelease=args.prerelease,
                force=args.force,
                force_rebuild=args.force_rebuild,
                skip_upload=args.skip_upload,
            )

            if args.skip_upload:
                print("=== PACKAGES CREATED SUCCESSFULLY (SKIPPED UPLOAD) ===")
                print(f"Release Tag: {result['package']['release_tag']}")
                print(f"Artifacts Created: {len(result.get('artifacts', []))}")
                for artifact in result.get("artifacts", []):
                    print(
                        f"  - {artifact.get('artifact_type')}: {artifact.get('file_path')}"
                    )
            else:
                print("=== RELEASE CREATED SUCCESSFULLY ===")
                print(f"Release URL: {result['release'].get('html_url')}")
                print(f"Release Tag: {result['package']['release_tag']}")
                print(f"Artifacts: {len(result.get('artifacts', []))}")

        elif args.release_command == "status":
            workflow = ReleaseWorkflow(
                repo_owner=args.repo_owner,
                repo_name=args.repo_name,
                github_token=args.github_token,
            )

            status = workflow.get_release_status(args.tag)

            print(f"=== RELEASE STATUS: {args.tag} ===")
            print(f"Exists: {'✅ YES' if status['exists'] else '❌ NO'}")

            if status["exists"]:
                release = status["release"]
                print(f"Title: {release.get('name')}")
                print(f"Published: {status.get('published_at')}")
                print(f"Draft: {'Yes' if status.get('draft') else 'No'}")
                print(f"Prerelease: {'Yes' if status.get('prerelease') else 'No'}")
                print(f"Artifacts: {status.get('artifacts', 0)}")
                print(f"URL: {release.get('html_url')}")

        elif args.release_command == "history":
            workflow = ReleaseWorkflow(
                repo_owner=args.repo_owner,
                repo_name=args.repo_name,
                github_token=args.github_token,
            )

            releases = workflow.list_releases(args.limit)

            print(f"=== RECENT RELEASES (Last {args.limit}) ===")
            for i, release in enumerate(releases, 1):
                print(f"\n{i}. {release.get('tag_name')}")
                print(f"   Title: {release.get('name')}")
                print(f"   Published: {release.get('published_at')}")
                print(f"   Draft: {'Yes' if release.get('draft') else 'No'}")
                print(f"   Prerelease: {'Yes' if release.get('prerelease') else 'No'}")
                print(f"   Artifacts: {len(release.get('assets', []))}")
                print(f"   URL: {release.get('html_url')}")

        else:
            # This should not be reached due to the None check at the start
            print(f"Unknown release command: {args.release_command}")
            print("Available commands: export, validate, create, status, history")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Release command failed: {e}")
        sys.exit(1)


def setup_database(args):
    """Setup PostgreSQL database in Docker."""
    logger.info("Setting up PostgreSQL database...")

    config = Config()
    pg_config = config.get("postgresql")
    use_postgis = pg_config.get("use_postgis", True)

    container_name = "oevk"

    # Detect platform for Docker image selection
    import platform

    machine = platform.machine().lower()
    docker_platform = (
        "linux/arm64" if machine in ["arm64", "aarch64"] else "linux/amd64"
    )

    # Check if container exists
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
        container_exists = container_name in result.stdout.strip().split("\n")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error(
            "Docker is not running or not installed. Please start Docker and try again."
        )
        sys.exit(1)

    if container_exists and args.force_recreate:
        logger.info(f"Removing existing container: {container_name}")
        subprocess.run(["docker", "rm", "-f", container_name], check=True)
        container_exists = False

    if not container_exists:
        # Choose Docker image based on PostGIS configuration
        postgres_image = "postgis/postgis:15-3.3" if use_postgis else "postgres:16"
        logger.info(
            f"Creating Docker container: {container_name} (image: {postgres_image}, platform: {docker_platform})"
        )
        docker_command = [
            "docker",
            "run",
            "--platform",
            docker_platform,
            "--name",
            container_name,
            "-e",
            f"POSTGRES_PASSWORD={pg_config['password']}",
            "-e",
            f"POSTGRES_USER={pg_config['user']}",
            "-e",
            f"POSTGRES_DB={pg_config['db']}",
            "-d",
            "-p",
            f"{pg_config['port']}:5432",
            postgres_image,
        ]
        subprocess.run(docker_command, check=True)
        logger.info("Waiting for PostgreSQL to be ready...")
        time.sleep(10)  # Wait for the database to initialize
    else:
        logger.info(f"Container {container_name} already exists. Starting it.")
        subprocess.run(["docker", "start", container_name], check=True)
        logger.info("Waiting for PostgreSQL to be ready...")
        time.sleep(5)

    # Connect to the database and execute scripts
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        logger.error(
            "psycopg2-binary is not installed. Please install it with: pip install psycopg2-binary"
        )
        sys.exit(1)

    conn = None
    for i in range(5):
        try:
            conn = psycopg2.connect(
                host=pg_config["host"],
                port=pg_config["port"],
                dbname=pg_config["db"],
                user=pg_config["user"],
                password=pg_config["password"],
            )
            break
        except psycopg2.OperationalError:
            logger.info(f"Waiting for database connection... ({i + 1}/5)")
            time.sleep(5)

    if not conn:
        logger.error("Could not connect to the PostgreSQL database.")
        sys.exit(1)

    conn.autocommit = True
    cur = conn.cursor()

    # Execute DDL script
    if os.path.exists(args.ddl_script):
        logger.info(f"Executing DDL script: {args.ddl_script}")
        with open(args.ddl_script, "r") as f:
            cur.execute(f.read())
        logger.info("DDL script executed successfully.")
    else:
        logger.warning(f"DDL script not found at: {args.ddl_script}")

    # Execute view creation script if it exists (after schema creation)
    view_script = os.path.join(os.path.dirname(args.ddl_script), "address_view.sql")
    if os.path.exists(view_script):
        logger.info(f"Executing view creation script: {view_script}")
        with open(view_script, "r") as f:
            cur.execute(f.read())
        logger.info("View creation script executed successfully.")
    else:
        logger.info(
            "View creation script not found (view may already be in schema.sql)"
        )

    cur.close()
    conn.close()

    # Execute DML script using psql via docker for better memory efficiency with large files
    if os.path.exists(args.dml_script):
        logger.info(f"Executing DML script: {args.dml_script}")
        logger.info("Using psql for efficient loading of large data file...")

        # Get absolute path for Docker volume mounting
        dml_abs_path = os.path.abspath(args.dml_script)

        # Use docker exec with psql to load the SQL file
        psql_command = [
            "docker",
            "exec",
            "-i",
            container_name,
            "psql",
            "-U",
            pg_config["user"],
            "-d",
            pg_config["db"],
            "-f",
            f"/tmp/{os.path.basename(args.dml_script)}",
        ]

        # First, copy the file into the container
        copy_command = [
            "docker",
            "cp",
            dml_abs_path,
            f"{container_name}:/tmp/{os.path.basename(args.dml_script)}",
        ]

        logger.info("Copying DML script to container...")
        subprocess.run(copy_command, check=True)

        logger.info(
            "Loading data into database (this may take a while for large files)..."
        )
        result = subprocess.run(psql_command, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Failed to execute DML script: {result.stderr}")
            sys.exit(1)

        logger.info("DML script executed successfully.")

        # Clean up the temporary file in the container
        cleanup_command = [
            "docker",
            "exec",
            container_name,
            "rm",
            f"/tmp/{os.path.basename(args.dml_script)}",
        ]
        subprocess.run(cleanup_command, check=False)
    else:
        logger.warning(f"DML script not found at: {args.dml_script}")

    # Verify import if requested
    if hasattr(args, "verify") and args.verify:
        logger.info("\n" + "=" * 80)
        logger.info("Starting import verification...")
        logger.info("=" * 80)

        from src.database.verify_import import (
            verify_postgresql_import,
            verify_view_exists,
        )

        # Get DuckDB path from args or use default
        duckdb_path = getattr(args, "db_path", "data/oevk.db")

        # Verify data integrity
        verification_passed = verify_postgresql_import(
            duckdb_path=duckdb_path,
            pg_config=pg_config,
            sample_percentage=getattr(args, "verify_sample", 5.0),
        )

        # Verify view exists
        view_passed = verify_view_exists(pg_config)

        if verification_passed and view_passed:
            logger.info("\n✅ VERIFICATION PASSED - Data integrity confirmed")
        else:
            logger.error("\n❌ VERIFICATION FAILED - Please check errors above")
            if not getattr(args, "ignore_verify_errors", False):
                sys.exit(1)

    logger.info("Database setup completed successfully.")


def export_database_dump(args):
    """Export PostgreSQL database to gzipped dump file."""
    try:
        dump_path = export_dump(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password,
            output_dir=args.output_dir,
            use_docker=not args.no_docker,
            container_name=args.container_name,
        )
        logger.info(f"✅ Dump exported successfully: {dump_path}")
    except Exception as e:
        logger.error(f"❌ Failed to export dump: {e}")
        sys.exit(1)


def import_database_dump(args):
    """Import gzipped PostgreSQL dump file."""
    try:
        import_dump(
            dump_path=args.dump_file,
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password,
            use_docker=not args.no_docker,
            container_name=args.container_name,
        )
        logger.info("✅ Dump imported successfully")
    except Exception as e:
        logger.error(f"❌ Failed to import dump: {e}")
        sys.exit(1)


def verify_postgresql_import(args):
    """Verify PostgreSQL import and create gzipped dump."""
    from pathlib import Path

    logger.info("=== PostgreSQL Import Verification and Dump Creation ===")

    exports_dir = Path(args.exports_dir)

    # Validate exports directory
    if not exports_dir.exists():
        logger.error(f"Exports directory not found: {exports_dir}")
        logger.info("Run 'python -m src.cli export' first to generate PostgreSQL files")
        sys.exit(1)

    schema_file = exports_dir / "schema.sql"
    import_file = exports_dir / "import_postgresql.sql"
    postgresql_dir = exports_dir / "postgresql"

    # Validate required files
    if not schema_file.exists():
        logger.error(f"Schema file not found: {schema_file}")
        logger.info("Run 'python -m src.cli export' first")
        sys.exit(1)

    if not import_file.exists():
        logger.error(f"Import script not found: {import_file}")
        logger.info("Run 'python -m src.cli export' first")
        sys.exit(1)

    if not postgresql_dir.exists():
        logger.error(f"PostgreSQL CSV directory not found: {postgresql_dir}")
        logger.info("Run 'python -m src.cli export' first")
        sys.exit(1)

    try:
        dump_path = verify_and_dump_postgresql(
            exports_dir=str(exports_dir),
            container_name=args.container_name,
            cleanup=not args.no_cleanup,
        )

        if dump_path:
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"✅ Verification completed successfully")
            logger.info(f"📦 Dump file: {dump_path}")
            logger.info("=" * 80)
        else:
            logger.warning("Verification completed but dump was not created")

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
