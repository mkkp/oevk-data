"""Command-line interface for the OEVK data processing pipeline."""

import argparse
import datetime
import os
import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import duckdb

from src.database.connection import get_database_connection
from src.etl.ingest import download_sources, load_staging_data
from src.etl.transform import transform_all
from src.etl.export import export_tables_to_csv, export_addresses_partitioned
from src.utils.logging import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="OEVK Data Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline with default settings
  python src/cli.py run
  
  # Run pipeline with custom database and output directory
  python src/cli.py run --db-path data/oevk.db --output-dir exports/
  
  # Run only specific stages
  python src/cli.py run --stages ingest,transform
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the complete pipeline')
    run_parser.add_argument('--db-path', default='data/oevk.db', 
                          help='Path to the database file (default: data/oevk.db)')
    run_parser.add_argument('--staging-dir', default='data/staging',
                          help='Directory for staging files (default: data/staging)')
    run_parser.add_argument('--output-dir', default='exports',
                          help='Directory for output files (default: exports)')
    run_parser.add_argument('--stages', default='ingest,transform,export',
                          help='Comma-separated list of stages to run (default: all)')
    run_parser.add_argument('--run-tag', 
                          help='Custom run tag (default: timestamp)')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        run_pipeline(args)
    else:
        parser.print_help()
        sys.exit(1)


def run_pipeline(args):
    """Run the complete data processing pipeline."""
    logger.info("Starting OEVK data processing pipeline")
    
    # Generate run tag
    run_tag = args.run_tag or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    logger.info(f"Run tag: {run_tag}")
    
    # Create directories
    os.makedirs(args.staging_dir, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.db_path) if os.path.dirname(args.db_path) else '.', exist_ok=True)
    
    # Get database connection
    conn = get_database_connection(args.db_path)
    
    # Define source URLs
    sources = {
        'oevk_json': 'https://static.valasztas.hu/dyn/oevk_data/oevk.json',
        'korzet_zip': 'https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip'
    }
    
    # Determine which stages to run
    stages = [stage.strip() for stage in args.stages.split(',')]
    
    try:
        # Run ingestion stage
        if 'ingest' in stages:
            logger.info("=== INGESTION STAGE ===")
            file_paths = download_sources(sources, args.staging_dir)
            load_staging_data(conn, file_paths, run_tag)
        
        # Run transformation stage
        if 'transform' in stages:
            logger.info("=== TRANSFORMATION STAGE ===")
            transform_all(conn, run_tag)
        
        # Run export stage
        if 'export' in stages:
            logger.info("=== EXPORT STAGE ===")
            export_tables_to_csv(conn, args.output_dir, run_tag)
            export_addresses_partitioned(conn, args.output_dir, run_tag)
        
        logger.info("Pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)
    
    finally:
        # Close database connection
        conn.close()


if __name__ == "__main__":
    main()