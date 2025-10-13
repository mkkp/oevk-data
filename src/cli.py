"""Command-line interface for the OEVK data processing pipeline."""

import argparse
import datetime
import os
import sys
import time
from pathlib import Path

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
from src.etl.export_canonical_v2 import export_canonical_addresses_with_uuid
from src.etl.ingest import download_sources, load_staging_data
from src.etl.transform_optimized import transform_all_optimized
from src.utils.pipeline_logging import PipelineMetrics, get_logger, setup_logging

# Release workflow import (conditional to avoid import errors during development)
try:
    from src.release.workflow import ReleaseWorkflow

    RELEASE_AVAILABLE = True
except ImportError:
    RELEASE_AVAILABLE = False

logger = get_logger(__name__)


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

    # Release commands (if available)
    if RELEASE_AVAILABLE:
        release_parser = subparsers.add_parser("release", help="Manage data releases")
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
    elif args.command == "release" and RELEASE_AVAILABLE:
        handle_release_command(args)
    else:
        parser.print_help()
        sys.exit(1)


def run_pipeline(args):
    """Run the complete data processing pipeline."""
    logger.info("Starting OEVK data processing pipeline")

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

            # Get row count after ingestion
            staging_count_after = conn.execute(
                "SELECT COUNT(*) FROM staging_korzet"
            ).fetchone()[0]

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

            # Get total row count for export
            total_rows = conn.execute("SELECT COUNT(*) FROM staging_korzet").fetchone()[
                0
            ]

            export_tables_to_csv(conn, args.output_dir, run_tag)

            # Export canonical (deduplicated) addresses with UUID v3
            export_canonical_addresses_with_uuid(conn, args.output_dir, run_tag)

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

            # Create release symlinks for validation compatibility
            create_release_symlinks(args.output_dir, run_tag, args.db_path)

            metrics.log_step_completion("export", row_count=total_rows)

        # Final pipeline summary
        total_duration = time.time() - (metrics.start_time or time.time())
        total_rows = conn.execute("SELECT COUNT(*) FROM staging_korzet").fetchone()[0]

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

        logger.info("Pipeline completed successfully")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)

    finally:
        # Close database connection
        conn.close()


def handle_release_command(args):
    """Handle release subcommands."""
    if not RELEASE_AVAILABLE:
        print("Release functionality is not available")
        sys.exit(1)

    try:
        if args.release_command == "validate":
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
            print(f"Unknown release command: {args.release_command}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Release command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
