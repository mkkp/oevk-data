#!/usr/bin/env python3
"""Test script for parallel export functionality."""

import duckdb
import os
import time
from src.etl.export_canonical_v2 import export_canonical_addresses_with_uuid
from src.utils.pipeline_logging import setup_logging, get_logger

# Setup logging
setup_logging("INFO")
logger = get_logger(__name__)


def test_parallel_export():
    """Test the parallel export functionality."""
    db_path = "data/oevk.db"

    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        logger.error("Please run the pipeline first: python src/cli.py run")
        return

    # Connect to database
    logger.info(f"Connecting to database: {db_path}")
    conn = duckdb.connect(db_path, read_only=True)

    # Get count of canonical addresses
    count = conn.execute("SELECT COUNT(*) FROM CanonicalAddress").fetchone()[0]
    logger.info(f"Found {count:,} canonical addresses in database")

    # Get count of settlements
    settlement_count = conn.execute("""
        SELECT COUNT(DISTINCT s.SettlementCode)
        FROM Settlement s
        JOIN CanonicalAddress ca ON s.SettlementName = ca.SettlementName
    """).fetchone()[0]
    logger.info(f"Found {settlement_count} settlements with canonical addresses")

    # Test export with different worker counts
    test_dir = "data/export_test"
    os.makedirs(test_dir, exist_ok=True)

    worker_counts = [1, 4, 8]

    for workers in worker_counts:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Testing with {workers} worker(s)")
        logger.info(f"{'=' * 60}")

        start_time = time.time()
        export_canonical_addresses_with_uuid(
            conn, test_dir, f"test_{workers}workers", max_workers=workers
        )
        elapsed = time.time() - start_time

        logger.info(f"✓ Completed with {workers} worker(s) in {elapsed:.1f}s")
        logger.info(f"  Average: {count / elapsed:.0f} addresses/sec")

    conn.close()
    logger.info("\n✓ All tests completed successfully")


if __name__ == "__main__":
    test_parallel_export()
