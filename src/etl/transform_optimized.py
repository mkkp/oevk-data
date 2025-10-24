"""Optimized transformation logic for converting staging data to normalized target tables."""

import duckdb
import time
import concurrent.futures
from typing import List, Tuple, Optional
import polars as pl

# Hash functions are now implemented inline using DuckDB's built-in functions
# from src.etl.hashing import (
#     hash_county_id,
#     hash_settlement_id,
#     hash_oevk_id,
#     hash_tevk_id,
#     hash_postal_code_id,
#     hash_postal_code_settlement_id,
#     hash_polling_station_id,
#     hash_public_space_type_id,
#     hash_public_space_name_id,
#     hash_settlement_public_spaces_id,
#     hash_address_id,
# )
from src.utils.pipeline_logging import get_logger
from src.utils.config import get_config
from src.etl.deduplicate import AddressDeduplicator

logger = get_logger(__name__)


def register_hash_functions(db_connection: duckdb.DuckDBPyConnection) -> None:
    """Register hash functions with DuckDB."""
    # Check if macros already exist to avoid catalog write-write conflicts
    # This is especially important for parallel processing
    try:
        # Create SQL UDFs for hash functions using DuckDB's macro syntax
        # Using md5 instead of xxhash64 since DuckDB doesn't have xxhash64 built-in
        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_county_id(county_code) AS lower(substring(md5(county_code), 1, 16))
        """)

        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_settlement_id(county_code, settlement_code) AS lower(substring(md5(county_code || '|' || settlement_code), 1, 16))
        """)

        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_oevk_id(county_code, oevk) AS lower(substring(md5(county_code || '|' || oevk), 1, 16))
        """)

        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_tevk_id(county_code, settlement_code, tevk) AS lower(substring(md5(county_code || '|' || settlement_code || '|' || COALESCE(tevk, '-')), 1, 16))
        """)

        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_postal_code_id(postal_code) AS lower(substring(md5(postal_code), 1, 16))
        """)

        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_polling_station_id(county_code, settlement_code, oevk, tevk, polling_station_address) AS lower(substring(md5(county_code || '|' || settlement_code || '|' || oevk || '|' || COALESCE(tevk, '') || '|' || polling_station_address), 1, 16))
        """)

        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_address_id(county_code, settlement_code, public_space_name, public_space_type, house_number, building, staircase, postal_code) AS lower(substring(md5(county_code || '|' || settlement_code || '|' || public_space_name || '|' || public_space_type || '|' || house_number || '|' || COALESCE(building, '') || '|' || COALESCE(staircase, '') || '|' || postal_code), 1, 16))
        """)

        db_connection.execute("""
            CREATE OR REPLACE MACRO hash_postal_code_settlement_id(postal_code_id, settlement_id) AS lower(substring(md5(postal_code_id || '|' || settlement_id), 1, 16))
        """)

        # Utility function to trim leading zeros from address components
        # Uses Python UDF for complex regex operations
        def trim_leading_zeros_py(value):
            """Trim leading zeros from address component strings."""
            if not value:
                return value

            import re

            # Handle range notation (e.g., "000001-00005" -> "1-5")
            if '-' in value:
                parts = value.split('-', 1)
                if len(parts) == 2:
                    left = parts[0].lstrip('0') or '0'
                    right = parts[1].lstrip('0') or '0'
                    return f"{left}-{right}"

            # Handle slash notation (e.g., "000001/D" -> "1/D")
            if '/' in value:
                match = re.match(r'^(0*)(\d+)(/.*)?$', value)
                if match:
                    num = match.group(2) or '0'
                    suffix = match.group(3) or ''
                    return num + suffix

            # Handle numeric only (e.g., "000001" -> "1")
            if value.isdigit():
                return value.lstrip('0') or '0'

            # Non-numeric or mixed: return as-is
            return value

        # Check if function already exists before creating
        try:
            db_connection.create_function("trim_leading_zeros", trim_leading_zeros_py, return_type="VARCHAR")
        except Exception as func_err:
            if "already created" in str(func_err):
                logger.debug("trim_leading_zeros function already exists, skipping")
            else:
                raise

        logger.debug("Hash functions and utility macros registered as SQL macros using MD5")
    except Exception as e:
        if "Catalog write-write conflict" in str(e):
            logger.debug(
                "Hash functions already registered, skipping duplicate registration"
            )
        else:
            raise


def transform_all_optimized(
    db_connection: duckdb.DuckDBPyConnection,
    run_tag: str,
    chunk_size: int = 50000,
    parallel: bool = False,
    db_path: str = "",
    enable_deduplication: bool = True,
) -> Optional[dict]:
    """Transforms staging data into all 8 target tables with optimized performance.

    Args:
        db_connection: An active DuckDB connection.
        run_tag: The run tag to process from staging tables.
        chunk_size: Number of records to process per chunk (default: 50,000)
        parallel: Whether to process chunks in parallel (default: False)
        db_path: Path to database file (required for parallel processing)
        enable_deduplication: Whether to enable address deduplication (default: True)

    Returns:
        Deduplication result dictionary if enabled, None otherwise
    """
    logger.info(f"Starting optimized transformation for run_tag: {run_tag}")

    # Register hash functions
    register_hash_functions(db_connection)

    # Apply database schema if not already applied
    apply_target_schema(db_connection)

    # Transform in dependency order
    transform_counties(db_connection, run_tag)
    transform_settlements(db_connection, run_tag)
    transform_national_individual_electoral_districts(db_connection, run_tag)
    transform_postal_codes(db_connection, run_tag)
    transform_settlement_individual_electoral_districts(db_connection, run_tag)
    transform_polling_stations(db_connection, run_tag)

    # Optimized address transformation
    if parallel:
        transform_addresses_parallel(db_connection, run_tag, chunk_size, db_path)
    else:
        transform_addresses_optimized(db_connection, run_tag, chunk_size)

    transform_postal_code_settlement_relationships(db_connection, run_tag)

    logger.info("Core transformation completed successfully")

    # Run deduplication if enabled
    dedup_result = None
    if enable_deduplication:
        logger.info("Running address deduplication")
        dedup_result = deduplicate_addresses_in_pipeline(
            db_connection, run_tag, enable_deduplication=True
        )

    logger.info("Optimized transformation completed successfully")
    return dedup_result


def apply_target_schema(db_connection: duckdb.DuckDBPyConnection) -> None:
    """Applies the target database schema if not already applied."""
    logger.info("Applying target database schema")

    # Read and execute the schema file
    with open("src/database/schema.sql", "r") as f:
        schema_sql = f.read()

    # Execute the schema creation
    db_connection.execute(schema_sql)

    # Check for missing columns and add them (schema migration)
    migrate_schema(db_connection)

    logger.info("Target schema applied successfully")


def migrate_schema(db_connection: duckdb.DuckDBPyConnection) -> None:
    """Migrate existing schema by adding missing columns."""
    logger.info("Checking for schema migrations")

    # Check if Address table has OriginalOrder column
    try:
        result = db_connection.execute("PRAGMA table_info(Address)").fetchall()
        has_original_order = any(col[1] == "OriginalOrder" for col in result)

        if not has_original_order:
            logger.info("Adding OriginalOrder column to Address table")
            # First add the column without constraints
            db_connection.execute(
                "ALTER TABLE Address ADD COLUMN OriginalOrder INTEGER"
            )
            # Then set default value for existing rows
            db_connection.execute(
                "UPDATE Address SET OriginalOrder = 0 WHERE OriginalOrder IS NULL"
            )
            logger.info("OriginalOrder column added successfully")
    except Exception as e:
        logger.warning(f"Could not check/update Address table schema: {e}")

    logger.info("Schema migration check completed")


def transform_counties(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into County table."""
    logger.info("Transforming County data")

    # Extract unique counties from Korzet CSV data
    db_connection.execute(
        """
        INSERT INTO County (ID, CountyCode, CountyName)
        SELECT
            lower(substring(md5(county_code), 1, 16)) as ID,
            county_code,
            MAX(county_name) as CountyName
        FROM staging_korzet
        WHERE run_tag = ?
        GROUP BY county_code
        ON CONFLICT (CountyCode) DO NOTHING
    """,
        [run_tag],
    )

    row_count = db_connection.execute("SELECT COUNT(*) FROM County").fetchone()[0]
    logger.info(f"Transformed {row_count} counties")


def transform_settlements(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str
) -> None:
    """Transforms staging data into Settlement table."""
    logger.info("Transforming Settlement data")

    # Extract unique settlements from Korzet CSV data
    db_connection.execute(
        """
        INSERT INTO Settlement (ID, SettlementCode, SettlementName, County_ID)
        SELECT
            lower(substring(md5(sk.county_code || '|' || sk.settlement_code), 1, 16)) as ID,
            sk.settlement_code,
            MAX(sk.settlement_name) as SettlementName,
            c.ID as County_ID
        FROM staging_korzet sk
        JOIN County c ON sk.county_code = c.CountyCode
        WHERE sk.run_tag = ?
        GROUP BY sk.county_code, sk.settlement_code, c.ID
        ON CONFLICT (County_ID, SettlementCode) DO NOTHING
    """,
        [run_tag],
    )

    row_count = db_connection.execute("SELECT COUNT(*) FROM Settlement").fetchone()[0]
    logger.info(f"Transformed {row_count} settlements")


def transform_national_individual_electoral_districts(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str
) -> None:
    """Transforms staging data into NationalIndividualElectoralDistrict table."""
    logger.info("Transforming NationalIndividualElectoralDistrict data")

    # Extract OEVK data with polygon data from JSON source
    db_connection.execute(
        """
        INSERT INTO NationalIndividualElectoralDistrict (ID, OEVK, Name, Center, Polygon, County_ID)
        SELECT
            lower(substring(md5(sk.county_code || '|' || sk.oevk_code), 1, 16)) as ID,
            sk.oevk_code,
            c.CountyName || ' ' || sk.oevk_code as Name,
            oevk_json.centrum as Center,
            oevk_json.poligon as Polygon,
            c.ID as County_ID
        FROM staging_korzet sk
        JOIN County c ON sk.county_code = c.CountyCode
        LEFT JOIN staging_oevk_json oevk_json
            ON sk.county_code = oevk_json.maz
            AND sk.oevk_code = oevk_json.evk
            AND oevk_json.run_tag = ?
        WHERE sk.run_tag = ?
        GROUP BY sk.county_code, sk.oevk_code, c.ID, c.CountyName, oevk_json.centrum, oevk_json.poligon
        ON CONFLICT (County_ID, OEVK) DO NOTHING
    """,
        [run_tag, run_tag],
    )

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM NationalIndividualElectoralDistrict"
    ).fetchone()[0]

    # Log polygon data statistics
    polygon_count = db_connection.execute(
        "SELECT COUNT(*) FROM NationalIndividualElectoralDistrict WHERE Polygon IS NOT NULL"
    ).fetchone()[0]

    logger.info(f"Transformed {row_count} national individual electoral districts ({polygon_count} with polygon data)")


def transform_postal_codes(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str
) -> None:
    """Transforms staging data into PostalCode table."""
    logger.info("Transforming PostalCode data")

    # Extract unique postal codes from Korzet CSV data
    db_connection.execute(
        """
        INSERT INTO PostalCode (ID, PostalCode)
        SELECT
            hash_postal_code_id(CAST(postal_code AS VARCHAR)) as ID,
            CAST(postal_code AS VARCHAR) as PostalCode
        FROM staging_korzet
        WHERE run_tag = ? AND postal_code IS NOT NULL AND postal_code != 0
        GROUP BY postal_code
        ON CONFLICT (PostalCode) DO NOTHING
    """,
        [run_tag],
    )

    row_count = db_connection.execute("SELECT COUNT(*) FROM PostalCode").fetchone()[0]
    logger.info(f"Transformed {row_count} postal codes")


def transform_settlement_individual_electoral_districts(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str
) -> None:
    """Transforms staging data into SettlementIndividualElectoralDistrict table."""
    logger.info("Transforming SettlementIndividualElectoralDistrict data")

    # Extract TEVK data from Korzet CSV
    # TEVK is independent of OEVK - they are parallel electoral systems
    db_connection.execute(
        """
        INSERT INTO SettlementIndividualElectoralDistrict (
            ID, TEVK, Name, County_ID, Settlement_ID
        )
        SELECT
            hash_tevk_id(
                sk.county_code, sk.settlement_code,
                COALESCE(sk.tevk_code, '-')
            ) as ID,
            sk.tevk_code as TEVK,
            CASE
                WHEN sk.tevk_code IS NOT NULL AND sk.tevk_code != ''
                THEN MAX(sk.settlement_name) || ' ' || sk.tevk_code
                ELSE MAX(sk.settlement_name)
            END as Name,
            c.ID as County_ID,
            s.ID as Settlement_ID
        FROM staging_korzet sk
        JOIN County c ON sk.county_code = c.CountyCode
        JOIN Settlement s ON sk.county_code = c.CountyCode AND sk.settlement_code = s.SettlementCode
        WHERE sk.run_tag = ?
        GROUP BY sk.county_code, sk.settlement_code, sk.tevk_code, c.ID, s.ID
        ON CONFLICT (ID) DO NOTHING
    """,
        [run_tag],
    )

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM SettlementIndividualElectoralDistrict"
    ).fetchone()[0]
    logger.info(f"Transformed {row_count} settlement individual electoral districts")


def transform_polling_stations(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str
) -> None:
    """Transforms staging data into PollingStation table."""
    logger.info("Transforming PollingStation data")

    # Extract unique polling stations from Korzet CSV
    db_connection.execute(
        """
        INSERT INTO PollingStation (
            ID, PollingStationAddress, SettlementIndividualElectoralDistrict_ID,
            County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID
        )
        SELECT
            hash_polling_station_id(
                county_code, settlement_code, oevk_code,
                COALESCE(tevk_code, '-'), TRIM(polling_station_address)
            ) as ID,
            TRIM(polling_station_address) as PollingStationAddress,
            hash_tevk_id(county_code, settlement_code, COALESCE(tevk_code, '-')) as SettlementIndividualElectoralDistrict_ID,
            hash_county_id(county_code) as County_ID,
            hash_settlement_id(county_code, settlement_code) as Settlement_ID,
            hash_oevk_id(county_code, oevk_code) as NationalIndividualElectoralDistrict_ID
        FROM staging_korzet
        WHERE run_tag = ? AND polling_station_address IS NOT NULL AND TRIM(polling_station_address) != ''
        GROUP BY county_code, settlement_code, oevk_code, tevk_code, TRIM(polling_station_address)
        ON CONFLICT (ID) DO NOTHING
    """,
        [run_tag],
    )

    row_count = db_connection.execute("SELECT COUNT(*) FROM PollingStation").fetchone()[
        0
    ]
    logger.info(f"Transformed {row_count} polling stations")


def transform_addresses_optimized(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str, chunk_size: int = 50000
) -> None:
    """Transforms staging data into Address table in optimized chunks."""
    logger.info("Transforming Address data with optimized chunk size")

    # Get total count of addresses to process
    total_count = db_connection.execute(
        "SELECT COUNT(*) FROM staging_korzet WHERE run_tag = ?", [run_tag]
    ).fetchone()[0]

    total_chunks = (total_count + chunk_size - 1) // chunk_size  # ceiling division

    logger.info(
        f"Processing {total_count:,} addresses in chunks of {chunk_size:,} ({total_chunks} total chunks)"
    )

    # Track timing
    start_time = time.time()

    for chunk_num in range(total_chunks):
        chunk_start_time = time.time()
        offset = chunk_num * chunk_size

        # Calculate global OriginalOrder starting from offset + 1
        global_order_start = offset + 1

        # Optimized SQL with reduced window function calls
        db_connection.execute(
            """
        INSERT INTO Address (
            ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, PublicSpaceType,
            HouseNumber, Building, Staircase, PostalCode_ID, PollingStation_ID,
            SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID,
            NationalIndividualElectoralDistrict_ID
        )
        WITH chunk_data AS (
            SELECT
                county_code, settlement_code, oevk_code, tevk_code, postal_code,
                street_name, street_type, house_number, building, staircase,
                polling_station_address
            FROM staging_korzet
            WHERE run_tag = ?
            ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code,
                     street_name, street_type, house_number, building, staircase
            LIMIT ? OFFSET ?
        ),
            numbered_chunk AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code,
                                 street_name, street_type, house_number, building, staircase
                    ) as row_num
                FROM chunk_data
            )
            SELECT
                hash_address_id(
                    county_code,
                    settlement_code,
                    street_name,
                    COALESCE(street_type, ''),
                    house_number,
                    COALESCE(building, ''),
                    COALESCE(staircase, ''),
                    CAST(postal_code AS VARCHAR)
                ) as ID,
                row_num as Sequence,
                ? + row_num - 1 as OriginalOrder,
                TRIM(CONCAT_WS(' ', street_name, street_type, house_number,
                              COALESCE(building, ''), COALESCE(staircase, ''))) as FullAddress,
                street_name as PublicSpaceName,
                COALESCE(street_type, '') as PublicSpaceType,
                trim_leading_zeros(house_number) as HouseNumber,
                trim_leading_zeros(building) as Building,
                trim_leading_zeros(staircase) as Staircase,
                hash_postal_code_id(CAST(postal_code AS VARCHAR)) as PostalCode_ID,
                hash_polling_station_id(
                    county_code, settlement_code, oevk_code, COALESCE(tevk_code, '-'), TRIM(polling_station_address)
                ) as PollingStation_ID,
                hash_tevk_id(
                    county_code, settlement_code, COALESCE(tevk_code, '-')
                ) as SettlementIndividualElectoralDistrict_ID,
                hash_county_id(county_code) as County_ID,
                hash_settlement_id(county_code, settlement_code) as Settlement_ID,
                hash_oevk_id(county_code, oevk_code) as NationalIndividualElectoralDistrict_ID
            FROM numbered_chunk
            ON CONFLICT (ID) DO UPDATE SET
                Sequence = EXCLUDED.Sequence,
                OriginalOrder = EXCLUDED.OriginalOrder,
                FullAddress = EXCLUDED.FullAddress,
                PublicSpaceName = EXCLUDED.PublicSpaceName,
                PublicSpaceType = EXCLUDED.PublicSpaceType,
                HouseNumber = EXCLUDED.HouseNumber,
                Building = EXCLUDED.Building,
                Staircase = EXCLUDED.Staircase,
                PostalCode_ID = EXCLUDED.PostalCode_ID,
                PollingStation_ID = EXCLUDED.PollingStation_ID,
                SettlementIndividualElectoralDistrict_ID = EXCLUDED.SettlementIndividualElectoralDistrict_ID,
                County_ID = EXCLUDED.County_ID,
                Settlement_ID = EXCLUDED.Settlement_ID,
                NationalIndividualElectoralDistrict_ID = EXCLUDED.NationalIndividualElectoralDistrict_ID
        """,
            [run_tag, chunk_size, offset, global_order_start],
        )

        # Calculate timing metrics
        chunk_end_time = time.time()
        chunk_elapsed = chunk_end_time - chunk_start_time
        total_elapsed = chunk_end_time - start_time

        processed_count = min((chunk_num + 1) * chunk_size, total_count)
        progress_percent = processed_count / total_count * 100

        # Calculate estimated total time and time remaining
        if progress_percent > 0:
            estimated_total_time = total_elapsed / (progress_percent / 100)
            time_remaining = estimated_total_time - total_elapsed

            # Format time strings
            elapsed_str = format_time(total_elapsed)
            remaining_str = format_time(time_remaining)
            total_estimated_str = format_time(estimated_total_time)

            logger.info(
                f"Chunk {chunk_num + 1}/{total_chunks}: {processed_count:,}/{total_count:,} ({progress_percent:.1f}%) - Elapsed: {elapsed_str}, ETA: {remaining_str}, Total: ~{total_estimated_str}"
            )
        else:
            logger.info(
                f"Chunk {chunk_num + 1}/{total_chunks}: {processed_count:,}/{total_count:,} ({progress_percent:.1f}%) - Starting..."
            )

    final_count = db_connection.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
    total_time = time.time() - start_time
    logger.info(f"Transformed {final_count} addresses in {format_time(total_time)}")


def transform_addresses_parallel(
    db_connection: duckdb.DuckDBPyConnection,
    run_tag: str,
    chunk_size: int = 50000,
    db_path: str = "",
) -> None:
    """Transforms staging data into Address table using parallel processing."""
    logger.info("Transforming Address data with parallel processing")

    # Get total count of addresses to process
    total_count = db_connection.execute(
        "SELECT COUNT(*) FROM staging_korzet WHERE run_tag = ?", [run_tag]
    ).fetchone()[0]

    total_chunks = (total_count + chunk_size - 1) // chunk_size  # ceiling division

    logger.info(
        f"Processing {total_count:,} addresses in {total_chunks} parallel chunks of {chunk_size:,}"
    )

    # Track timing
    start_time = time.time()

    # Register hash functions in main connection first to ensure they exist
    # This prevents catalog write-write conflicts in parallel threads
    register_hash_functions(db_connection)

    # Process chunks in parallel with better error handling
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        chunk_results = []

        for chunk_num in range(total_chunks):
            offset = chunk_num * chunk_size
            future = executor.submit(
                process_chunk_parallel,
                db_path,
                run_tag,
                chunk_num,
                total_chunks,
                offset,
                chunk_size,
                total_count,
                start_time,
            )
            futures.append((chunk_num, future))

        # Wait for all chunks to complete with timeout and retry logic
        logger.info(f"Waiting for {len(futures)} chunks to complete...")

        # First attempt with timeout
        completed_futures = []
        failed_chunks = []

        for chunk_num, future in futures:
            try:
                result = future.result(timeout=180)  # 3 minute timeout per chunk
                completed_futures.append((chunk_num, result))
            except concurrent.futures.TimeoutError:
                logger.warning(f"Chunk {chunk_num} timed out after 3 minutes")
                failed_chunks.append(chunk_num)
                future.cancel()
            except Exception as e:
                logger.error(f"Chunk {chunk_num} failed with error: {e}")
                failed_chunks.append(chunk_num)

        # Retry failed chunks with smaller timeout
        if failed_chunks:
            logger.info(f"Retrying {len(failed_chunks)} failed chunks...")
            retry_futures = []

            for chunk_num in failed_chunks:
                offset = chunk_num * chunk_size
                future = executor.submit(
                    process_chunk_parallel,
                    db_path,
                    run_tag,
                    chunk_num,
                    total_chunks,
                    offset,
                    chunk_size,
                    total_count,
                    start_time,
                )
                retry_futures.append((chunk_num, future))

            for chunk_num, future in retry_futures:
                try:
                    result = future.result(timeout=120)  # 2 minute timeout for retry
                    completed_futures.append((chunk_num, result))
                    logger.info(f"Chunk {chunk_num} completed successfully on retry")
                except concurrent.futures.TimeoutError:
                    logger.error(f"Chunk {chunk_num} failed again after retry")
                except Exception as e:
                    logger.error(f"Chunk {chunk_num} failed on retry with error: {e}")

        # Log final results
        successful_chunks = len([c for c, _ in completed_futures])
        logger.info(
            f"Parallel processing completed: {successful_chunks}/{total_chunks} chunks successful"
        )

        if successful_chunks < total_chunks:
            logger.warning(
                f"{total_chunks - successful_chunks} chunks failed to complete"
            )

    final_count = db_connection.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
    total_time = time.time() - start_time
    logger.info(
        f"Transformed {final_count} addresses in {format_time(total_time)} using parallel processing"
    )


def process_chunk_parallel(
    db_path: str,
    run_tag: str,
    chunk_num: int,
    total_chunks: int,
    offset: int,
    chunk_size: int,
    total_count: int,
    start_time: float,
) -> None:
    """Process a single chunk in parallel."""
    chunk_start_time = time.time()

    logger.info(
        f"Starting parallel chunk {chunk_num + 1}/{total_chunks} (offset: {offset:,})"
    )

    # Create separate database connection for thread safety
    db_connection = duckdb.connect(db_path)

    # Hash functions are already registered in main thread, no need to register again
    # This prevents "Catalog write-write conflict" errors

    # Calculate global OriginalOrder starting from offset + 1
    global_order_start = offset + 1

    try:
        # Use the same optimized SQL as transform_addresses_optimized
        result = db_connection.execute(
            """
            INSERT INTO Address (
                ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, PublicSpaceType,
                HouseNumber, Building, Staircase, PostalCode_ID, PollingStation_ID,
                SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID,
                NationalIndividualElectoralDistrict_ID
            )
            WITH chunk_data AS (
                SELECT * FROM staging_korzet
                WHERE run_tag = ?
                ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code,
                         street_name, street_type, house_number, building, staircase
                LIMIT ? OFFSET ?
            ),
            numbered_chunk AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code,
                                 street_name, street_type, house_number, building, staircase
                    ) as row_num
                FROM chunk_data
            )
            SELECT
                hash_address_id(
                    county_code,
                    settlement_code,
                    street_name,
                    COALESCE(street_type, ''),
                    house_number,
                    COALESCE(building, ''),
                    COALESCE(staircase, ''),
                    CAST(postal_code AS VARCHAR)
                ) as ID,
                row_num as Sequence,
                ? + row_num - 1 as OriginalOrder,
                TRIM(CONCAT_WS(' ', street_name, street_type, house_number,
                              COALESCE(building, ''), COALESCE(staircase, ''))) as FullAddress,
                street_name as PublicSpaceName,
                COALESCE(street_type, '') as PublicSpaceType,
                trim_leading_zeros(house_number) as HouseNumber,
                trim_leading_zeros(building) as Building,
                trim_leading_zeros(staircase) as Staircase,
                hash_postal_code_id(CAST(postal_code AS VARCHAR)) as PostalCode_ID,
                hash_polling_station_id(
                    county_code, settlement_code, oevk_code, COALESCE(tevk_code, '-'), TRIM(polling_station_address)
                ) as PollingStation_ID,
                hash_tevk_id(
                    county_code, settlement_code, COALESCE(tevk_code, '-')
                ) as SettlementIndividualElectoralDistrict_ID,
                hash_county_id(county_code) as County_ID,
                hash_settlement_id(county_code, settlement_code) as Settlement_ID,
                hash_oevk_id(county_code, oevk_code) as NationalIndividualElectoralDistrict_ID
            FROM numbered_chunk
            ON CONFLICT (ID) DO UPDATE SET
                Sequence = EXCLUDED.Sequence,
                OriginalOrder = EXCLUDED.OriginalOrder,
                FullAddress = EXCLUDED.FullAddress,
                PublicSpaceName = EXCLUDED.PublicSpaceName,
                PublicSpaceType = EXCLUDED.PublicSpaceType,
                HouseNumber = EXCLUDED.HouseNumber,
                Building = EXCLUDED.Building,
                Staircase = EXCLUDED.Staircase,
                PostalCode_ID = EXCLUDED.PostalCode_ID,
                PollingStation_ID = EXCLUDED.PollingStation_ID,
                SettlementIndividualElectoralDistrict_ID = EXCLUDED.SettlementIndividualElectoralDistrict_ID,
                County_ID = EXCLUDED.County_ID,
                Settlement_ID = EXCLUDED.Settlement_ID,
                NationalIndividualElectoralDistrict_ID = EXCLUDED.NationalIndividualElectoralDistrict_ID
        """,
            [run_tag, chunk_size, offset, global_order_start],
        )

        # Get the number of rows inserted/updated
        rows_affected = result.fetchone()[0] if result else 0

        chunk_end_time = time.time()
        chunk_elapsed = chunk_end_time - chunk_start_time
        total_elapsed = chunk_end_time - start_time

        processed_count = min((chunk_num + 1) * chunk_size, total_count)
        progress_percent = processed_count / total_count * 100

        logger.info(
            f"Parallel Chunk {chunk_num + 1}/{total_chunks} COMPLETED: {processed_count:,}/{total_count:,} ({progress_percent:.1f}%) - Rows: {rows_affected:,} - Chunk Time: {format_time(chunk_elapsed)}, Total: {format_time(total_elapsed)}"
        )

    except Exception as e:
        logger.error(f"ERROR in parallel chunk {chunk_num + 1}/{total_chunks}: {e}")
        raise
    finally:
        # Commit the transaction and close the database connection
        db_connection.commit()
        db_connection.close()


def transform_postal_code_settlement_relationships(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str
) -> None:
    """Transforms postal code to settlement relationships."""
    logger.info("Transforming PostalCode_Settlement relationships")

    # Create relationships between postal codes and settlements
    db_connection.execute(
        """
        INSERT INTO PostalCode_Settlement (ID, PostalCode_ID, Settlement_ID)
        SELECT
            hash_postal_code_settlement_id(
                hash_postal_code_id(CAST(postal_code AS VARCHAR)),
                hash_settlement_id(county_code, settlement_code)
            ) as ID,
            hash_postal_code_id(CAST(postal_code AS VARCHAR)) as PostalCode_ID,
            hash_settlement_id(county_code, settlement_code) as Settlement_ID
        FROM staging_korzet
        WHERE run_tag = ? AND postal_code IS NOT NULL AND postal_code != 0
        GROUP BY postal_code, county_code, settlement_code
        ON CONFLICT (ID) DO UPDATE SET
            PostalCode_ID = EXCLUDED.PostalCode_ID,
            Settlement_ID = EXCLUDED.Settlement_ID
    """,
        [run_tag],
    )

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM PostalCode_Settlement"
    ).fetchone()[0]
    logger.info(f"Transformed {row_count} postal code-settlement relationships")


def format_time(seconds: float) -> str:
    """Format time in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def deduplicate_addresses_in_pipeline(
    db_connection: duckdb.DuckDBPyConnection,
    run_tag: str,
    enable_deduplication: bool = True,
) -> Optional[dict]:
    """
    Deduplicate addresses and store results in deduplication tables.

    This function runs after address transformation and:
    1. Extracts addresses from staging data
    2. Identifies and merges duplicates
    3. Stores canonical addresses and relationships in database
    4. Generates deduplication report

    Args:
        db_connection: Active DuckDB connection
        run_tag: Run tag to process
        enable_deduplication: Whether to enable deduplication (default: True)

    Returns:
        Deduplication report dictionary or None if disabled
    """
    if not enable_deduplication:
        logger.info("Deduplication disabled, skipping")
        return None

    logger.info("Starting address deduplication in pipeline")
    start_time = time.time()

    # Get configuration
    config = get_config()
    dedup_config = config.get_deduplication_settings()

    try:
        # Step 1: Extract addresses from staging data
        logger.info("Extracting addresses from staging data")
        addresses_query = """
            SELECT
                hash_address_id(
                    county_code,
                    COALESCE(settlement_code, ''),
                    street_name,
                    COALESCE(street_type, ''),
                    house_number,
                    COALESCE(building, ''),
                    COALESCE(staircase, ''),
                    CAST(postal_code AS VARCHAR)
                ) as address_id,
                county_code,
                settlement_name,
                street_name,
                COALESCE(street_type, '') as street_type,
                house_number,
                building,
                staircase,
                CASE
                    WHEN accessible = 'I' THEN TRUE
                    ELSE FALSE
                END as accessibility_flag,
                postal_code as pir_code,
                hash_polling_station_id(
                    county_code, COALESCE(settlement_code, ''), oevk_code,
                    COALESCE(tevk_code, '-'), TRIM(polling_station_address)
                ) as polling_station_id
            FROM staging_korzet
            WHERE run_tag = ?
        """

        # Execute query and convert to Polars DataFrame
        # Get column names first
        result = db_connection.execute(addresses_query, [run_tag])
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()

        # Convert to dictionary format for Polars
        data = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
        addresses_df = pl.DataFrame(data)

        logger.info(f"Extracted {len(addresses_df)} addresses for deduplication")

        # Step 2: Run deduplication
        deduplicator = AddressDeduplicator(
            seed=dedup_config.get("hash_seed", 20241012),
            enable_logging=dedup_config.get("enable_logging", True),
        )

        dedup_result = deduplicator.deduplicate_addresses(
            addresses_df, generate_report=dedup_config.get("generate_reports", True)
        )

        # Step 3: Store results in database
        logger.info("Storing deduplication results in database")

        # Store canonical addresses
        canonical_addresses = dedup_result["canonical_addresses"]

        db_connection.execute("DELETE FROM CanonicalAddress WHERE 1=1")

        # Register Polars DataFrame with DuckDB and insert
        db_connection.register("canonical_temp", canonical_addresses)
        db_connection.execute("""
            INSERT INTO CanonicalAddress (ID, CountyCode, SettlementName, StreetName, HouseNumber, FullAddress, AccessibilityFlag)
            SELECT
                CAST(canonical_address_id AS VARCHAR) as ID,
                county_code as CountyCode,
                settlement_name as SettlementName,
                street_name as StreetName,
                house_number as HouseNumber,
                full_address as FullAddress,
                CASE
                    WHEN accessibility_flag THEN 'I'
                    ELSE 'N'
                END as AccessibilityFlag
            FROM canonical_temp
            ON CONFLICT (CountyCode, SettlementName, FullAddress) DO UPDATE SET
                AccessibilityFlag = EXCLUDED.AccessibilityFlag
        """)
        db_connection.unregister("canonical_temp")

        canonical_count = len(canonical_addresses)
        logger.info(f"Stored {canonical_count} canonical addresses")

        # Store address mapping
        address_mapping = dedup_result["address_mapping"]

        db_connection.execute("DELETE FROM AddressMapping WHERE 1=1")

        db_connection.register("mapping_temp", address_mapping)
        db_connection.execute("""
            INSERT INTO AddressMapping (ID, OriginalAddressID, CanonicalAddressID, MappingType)
            SELECT
                lower(substring(md5(CAST(original_address_id AS VARCHAR) || '|' || CAST(canonical_address_id AS VARCHAR)), 1, 16)) as ID,
                CAST(original_address_id AS VARCHAR) as OriginalAddressID,
                CAST(canonical_address_id AS VARCHAR) as CanonicalAddressID,
                'deduplication' as MappingType
            FROM mapping_temp
            ON CONFLICT (OriginalAddressID, CanonicalAddressID) DO NOTHING
        """)
        db_connection.unregister("mapping_temp")

        logger.info(f"Stored {len(address_mapping)} address mappings")

        # Store polling station relationships
        polling_stations = dedup_result["address_polling_stations"]

        db_connection.execute("DELETE FROM AddressPollingStations WHERE 1=1")

        db_connection.register("polling_temp", polling_stations)
        db_connection.execute("""
            INSERT INTO AddressPollingStations (ID, CanonicalAddressID, PollingStationID)
            SELECT
                lower(substring(md5(CAST(canonical_address_id AS VARCHAR) || '|' || polling_station_id), 1, 16)) as ID,
                CAST(canonical_address_id AS VARCHAR) as CanonicalAddressID,
                polling_station_id as PollingStationID
            FROM polling_temp
            ON CONFLICT (CanonicalAddressID, PollingStationID) DO NOTHING
        """)
        db_connection.unregister("polling_temp")

        logger.info(f"Stored {len(polling_stations)} polling station relationships")

        # Store PIR codes
        pir_codes = dedup_result["address_pir_codes"]

        db_connection.execute("DELETE FROM AddressPIRCodes WHERE 1=1")

        db_connection.register("pir_temp", pir_codes)
        db_connection.execute("""
            INSERT INTO AddressPIRCodes (ID, CanonicalAddressID, PIRCode)
            SELECT
                lower(substring(md5(CAST(canonical_address_id AS VARCHAR) || '|' || pir_code), 1, 16)) as ID,
                CAST(canonical_address_id AS VARCHAR) as CanonicalAddressID,
                pir_code as PIRCode
            FROM pir_temp
        """)
        db_connection.unregister("pir_temp")

        logger.info(f"Stored {len(pir_codes)} PIR code relationships")

        # Step 4: Store deduplication report (if generated)
        if "deduplication_report" in dedup_result:
            report = dedup_result["deduplication_report"]

            db_connection.execute(
                "DELETE FROM DeduplicationReport WHERE RunID = ?", [report.run_id]
            )
            db_connection.execute(
                """
                INSERT INTO DeduplicationReport
                (ID, RunID, TotalAddresses, DuplicatesFound, CanonicalAddressesCreated,
                 ProcessingTimeMs, Status, ErrorMessage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    report.id,
                    report.run_id,
                    report.total_addresses,
                    report.duplicates_found,
                    report.canonical_addresses_created,
                    report.processing_time_ms,
                    report.status,
                    report.error_message,
                ],
            )

            logger.info(f"Stored deduplication report: {report.run_id}")

        # Log summary
        processing_time = time.time() - start_time
        original_count = len(addresses_df)
        deduplication_rate = (
            ((original_count - canonical_count) / original_count * 100)
            if original_count > 0
            else 0
        )

        logger.info(
            f"Deduplication complete in {format_time(processing_time)}: "
            f"{original_count:,} addresses → {canonical_count:,} canonical "
            f"({deduplication_rate:.1f}% reduction)"
        )

        return dedup_result

    except Exception as e:
        logger.error(f"Deduplication failed: {str(e)}", exc_info=True)
        raise
