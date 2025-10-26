"""Optimized transformation logic for converting staging data to normalized target tables."""

import duckdb
import time
import concurrent.futures
from typing import List, Tuple, Optional
import polars as pl
from tqdm import tqdm

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
from src.etl.hashing_polars import (
    apply_hash_address_id,
    apply_hash_county_id,
    apply_hash_settlement_id,
    apply_hash_oevk_id,
    apply_hash_tevk_id,
    apply_hash_postal_code_id,
    apply_hash_polling_station_id,
)
from src.etl.string_ops_polars import apply_trim_leading_zeros

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
    # Check if Polars-based transformation is enabled (default: True)
    config = get_config()
    use_polars = config.get("processing.use_polars_transform", True)

    if use_polars:
        logger.info("Using Polars-based transformation (faster, optimized)")
        # Polars transformation is sequential only for now
        transform_addresses_polars(db_connection, run_tag, chunk_size)
    elif parallel:
        logger.info("Using SQL-based parallel transformation (legacy)")
        transform_addresses_parallel(db_connection, run_tag, chunk_size, db_path)
    else:
        logger.info("Using SQL-based sequential transformation (legacy)")
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

    # Run geocoding if enabled (after deduplication)
    from src.etl.geocoding import geocode_canonical_addresses, geocode_polling_stations

    try:
        # Geocode canonical addresses - use cache only by default (no Nominatim calls)
        # To enable actual geocoding, run: python src/cli.py geocode run
        geocode_canonical_addresses(db_connection, run_tag, update_from_cache=True)

        # Geocode polling stations - skipped by default (nominatim.enabled=False)
        # To enable: set NOMINATIM_ENABLED=true or run: python src/cli.py geocode run
        geocode_polling_stations(db_connection, run_tag)
    except Exception as e:
        logger.warning(f"Geocoding failed but continuing: {e}")

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
    db_connection: duckdb.DuckDBPyConnection, run_tag: str, chunk_size: int = 100000
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

        # Log progress every 10 chunks or on the last chunk to reduce overhead (Quick Win optimization)
        should_log = (chunk_num + 1) % 10 == 0 or (chunk_num + 1) == total_chunks

        if should_log:
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
    chunk_size: int = 100000,
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
            # Disable individual chunk progress bars to reduce overhead (Quick Win optimization)
            pbar_pos = None
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
                pbar_pos,
            )
            futures.append((chunk_num, future))

        # Wait for all chunks to complete with timeout and retry logic
        logger.info(f"Waiting for {len(futures)} chunks to complete...")

        # First attempt with timeout
        completed_futures = []
        failed_chunks = []

        # Create a mapping of futures to chunk numbers for as_completed
        future_to_chunk = {future: chunk_num for chunk_num, future in futures}

        # Create global progress bar and individual chunk progress bars
        with tqdm(total=total_count, desc="Overall progress", unit="rows", position=0,
                  bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as overall_pbar, \
             tqdm(total=len(futures), desc="Chunks completed", unit="chunk", position=1,
                  bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as chunk_pbar:

            # Process chunks as they complete (not in order)
            for future in concurrent.futures.as_completed([f for _, f in futures], timeout=300):
                chunk_num = future_to_chunk[future]
                try:
                    result = future.result()
                    completed_futures.append((chunk_num, result))
                    rows_processed = min(chunk_size, total_count - (chunk_num * chunk_size))
                    overall_pbar.update(rows_processed)
                    chunk_pbar.update(1)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Chunk {chunk_num + 1}/{total_chunks} timed out")
                    failed_chunks.append(chunk_num)
                    chunk_pbar.update(1)
                except Exception as e:
                    logger.error(f"Chunk {chunk_num + 1}/{total_chunks} failed: {e}")
                    failed_chunks.append(chunk_num)
                    chunk_pbar.update(1)

        # Retry failed chunks with smaller timeout
        if failed_chunks:
            logger.info(f"Retrying {len(failed_chunks)} failed chunks...")
            retry_futures = []

            for idx, chunk_num in enumerate(failed_chunks):
                offset = chunk_num * chunk_size
                # Show progress bars for retries (position 2-5 for up to 4 retries)
                pbar_pos = idx + 2 if idx < 4 else None
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
                    pbar_pos,
                )
                retry_futures.append((chunk_num, future))

            # Progress bar for retry attempts
            with tqdm(total=len(retry_futures), desc="Retrying failed chunks", unit="chunk",
                      bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
                for chunk_num, future in retry_futures:
                    try:
                        result = future.result(timeout=120)  # 2 minute timeout for retry
                        completed_futures.append((chunk_num, result))
                        logger.info(f"Chunk {chunk_num} completed successfully on retry")
                        pbar.update(1)
                    except concurrent.futures.TimeoutError:
                        logger.error(f"Chunk {chunk_num} failed again after retry")
                        pbar.update(1)
                    except Exception as e:
                        logger.error(f"Chunk {chunk_num} failed on retry with error: {e}")
                        pbar.update(1)

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
    pbar_position: int = None,
) -> None:
    """Process a single chunk in parallel."""
    chunk_start_time = time.time()

    # Create individual progress bar for this chunk if position provided
    chunk_pbar = None
    if pbar_position is not None:
        rows_in_chunk = min(chunk_size, total_count - offset)
        chunk_pbar = tqdm(
            total=rows_in_chunk,
            desc=f"Chunk {chunk_num + 1}/{total_chunks}",
            unit="rows",
            position=pbar_position,
            leave=False,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}'
        )

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

        # Update individual chunk progress bar to completion
        if chunk_pbar is not None:
            chunk_pbar.n = chunk_pbar.total
            chunk_pbar.refresh()
            chunk_pbar.close()

        chunk_end_time = time.time()
        chunk_elapsed = chunk_end_time - chunk_start_time
        total_elapsed = chunk_end_time - start_time

        processed_count = min((chunk_num + 1) * chunk_size, total_count)
        progress_percent = processed_count / total_count * 100

        # Calculate estimated time remaining based on average time per chunk
        avg_time_per_chunk = total_elapsed / (chunk_num + 1)
        remaining_chunks = total_chunks - (chunk_num + 1)
        estimated_remaining = avg_time_per_chunk * remaining_chunks

        logger.info(
            f"Parallel Chunk {chunk_num + 1}/{total_chunks} COMPLETED: {processed_count:,}/{total_count:,} ({progress_percent:.1f}%) - "
            f"Rows: {rows_affected:,} - Chunk: {format_time(chunk_elapsed)} - "
            f"Elapsed: {format_time(total_elapsed)} - ETA: {format_time(estimated_remaining)}"
        )

    except Exception as e:
        if chunk_pbar is not None:
            chunk_pbar.close()
        logger.error(f"ERROR in parallel chunk {chunk_num + 1}/{total_chunks}: {e}")
        raise
    finally:
        if chunk_pbar is not None and not chunk_pbar.disable:
            chunk_pbar.close()
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


# =============================================================================
# POLARS-BASED TRANSFORMATION FUNCTIONS
# =============================================================================


def fetch_staging_chunk_polars(
    db_connection: duckdb.DuckDBPyConnection,
    run_tag: str,
    offset: int,
    chunk_size: int,
) -> pl.DataFrame:
    """Fetch a chunk of staging data into Polars DataFrame via Arrow.

    Uses DuckDB's Arrow interface for zero-copy data transfer.

    Args:
        db_connection: Active DuckDB connection
        run_tag: Run tag to filter staging data
        offset: Starting row offset
        chunk_size: Number of rows to fetch

    Returns:
        Polars DataFrame with staging data
    """
    # Fetch data using Arrow for zero-copy transfer
    # Filter out addresses with NULL, 0, or '0' postal codes to match SQL behavior
    # Also normalize tevk_code and polling_station_address to match SQL behavior
    arrow_table = db_connection.execute(
        """
        SELECT
            county_code, settlement_code, oevk_code,
            COALESCE(tevk_code, '-') as tevk_code,
            postal_code,
            street_name, street_type, house_number, building, staircase,
            TRIM(polling_station_address) as polling_station_address
        FROM staging_korzet
        WHERE run_tag = ?
          AND postal_code IS NOT NULL
          AND postal_code != 0
          AND postal_code != '0'
          AND postal_code != ''
        ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code,
                 street_name, street_type, house_number, building, staircase
        LIMIT ? OFFSET ?
        """,
        [run_tag, chunk_size, offset]
    ).fetch_arrow_table()

    # Convert Arrow to Polars DataFrame
    chunk_df = pl.from_arrow(arrow_table)

    return chunk_df


def transform_chunk_polars(
    chunk_df: pl.DataFrame,
    global_offset: int,
) -> pl.DataFrame:
    """Transform a chunk using Polars vectorized operations.

    Args:
        chunk_df: Polars DataFrame with staging data
        global_offset: Global offset for OriginalOrder calculation

    Returns:
        Transformed Polars DataFrame ready for insertion
    """
    # Add row count for Sequence and OriginalOrder
    chunk_df = chunk_df.with_row_count(name="row_num", offset=1)

    # Trim leading zeros from address components using Polars map
    chunk_df = chunk_df.with_columns([
        pl.col("house_number").map_elements(apply_trim_leading_zeros, return_dtype=pl.Utf8).alias("HouseNumber"),
        pl.col("building").map_elements(apply_trim_leading_zeros, return_dtype=pl.Utf8).alias("Building"),
        pl.col("staircase").map_elements(apply_trim_leading_zeros, return_dtype=pl.Utf8).alias("Staircase"),
    ])

    # Create struct for hash ID generation
    chunk_df = chunk_df.with_columns([
        pl.struct([
            "county_code", "settlement_code", "street_name", "street_type",
            "house_number", "building", "staircase", "postal_code"
        ]).map_elements(apply_hash_address_id, return_dtype=pl.Utf8).alias("ID"),
    ])

    # Generate foreign key hash IDs
    chunk_df = chunk_df.with_columns([
        pl.col("county_code").map_elements(apply_hash_county_id, return_dtype=pl.Utf8).alias("County_ID"),
        pl.struct(["county_code", "settlement_code"]).map_elements(apply_hash_settlement_id, return_dtype=pl.Utf8).alias("Settlement_ID"),
        pl.struct(["county_code", "oevk_code"]).map_elements(apply_hash_oevk_id, return_dtype=pl.Utf8).alias("NationalIndividualElectoralDistrict_ID"),
        pl.struct(["county_code", "settlement_code", "tevk_code"]).map_elements(apply_hash_tevk_id, return_dtype=pl.Utf8).alias("SettlementIndividualElectoralDistrict_ID"),
        pl.col("postal_code").cast(pl.Utf8).map_elements(apply_hash_postal_code_id, return_dtype=pl.Utf8).alias("PostalCode_ID"),
        pl.struct(["county_code", "settlement_code", "oevk_code", "tevk_code", "polling_station_address"]).map_elements(apply_hash_polling_station_id, return_dtype=pl.Utf8).alias("PollingStation_ID"),
    ])

    # Create FullAddress by concatenating components
    chunk_df = chunk_df.with_columns([
        pl.concat_str([
            pl.col("street_name"),
            pl.lit(" "),
            pl.col("street_type").fill_null(""),
            pl.lit(" "),
            pl.col("HouseNumber"),
            pl.lit(" "),
            pl.col("Building").fill_null(""),
            pl.lit(" "),
            pl.col("Staircase").fill_null(""),
        ]).str.replace_all(r"\s+", " ").str.strip_chars().alias("FullAddress"),
    ])

    # Add Sequence and OriginalOrder
    chunk_df = chunk_df.with_columns([
        pl.col("row_num").alias("Sequence"),
        (pl.col("row_num") + global_offset - 1).alias("OriginalOrder"),
    ])

    # Select and rename columns to match Address table schema
    result_df = chunk_df.select([
        "ID",
        "Sequence",
        "OriginalOrder",
        "FullAddress",
        pl.col("street_name").alias("PublicSpaceName"),
        pl.col("street_type").fill_null("").alias("PublicSpaceType"),
        "HouseNumber",
        "Building",
        "Staircase",
        "PostalCode_ID",
        "PollingStation_ID",
        "SettlementIndividualElectoralDistrict_ID",
        "County_ID",
        "Settlement_ID",
        "NationalIndividualElectoralDistrict_ID",
    ])

    return result_df


def persist_chunk_to_duckdb(
    db_connection: duckdb.DuckDBPyConnection,
    transformed_df: pl.DataFrame,
) -> int:
    """Persist transformed Polars DataFrame to DuckDB Address table.

    Uses Arrow for zero-copy transfer.

    Args:
        db_connection: Active DuckDB connection
        transformed_df: Transformed Polars DataFrame

    Returns:
        Number of rows inserted/updated
    """
    # Convert Polars to Arrow
    arrow_table = transformed_df.to_arrow()

    # Register Arrow table with DuckDB (temporary)
    db_connection.register("temp_chunk_polars", arrow_table)

    # Insert into Address table with conflict handling
    try:
        result = db_connection.execute("""
            INSERT INTO Address (
                ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, PublicSpaceType,
                HouseNumber, Building, Staircase, PostalCode_ID, PollingStation_ID,
                SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID,
                NationalIndividualElectoralDistrict_ID
            )
            SELECT
                ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, PublicSpaceType,
                HouseNumber, Building, Staircase, PostalCode_ID, PollingStation_ID,
                SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID,
                NationalIndividualElectoralDistrict_ID
            FROM temp_chunk_polars
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
        """)
    except Exception as e:
        # On FK error, dump first row for debugging
        logger.error(f"Foreign key constraint violation. First row sample:")
        first_row = transformed_df.head(1)
        logger.error(f"  PostalCode_ID: {first_row['PostalCode_ID'][0]}")
        logger.error(f"  PollingStation_ID: {first_row['PollingStation_ID'][0]}")
        logger.error(f"  County_ID: {first_row['County_ID'][0]}")
        logger.error(f"  Settlement_ID: {first_row['Settlement_ID'][0]}")
        logger.error(f"  SettlementIndividualElectoralDistrict_ID: {first_row['SettlementIndividualElectoralDistrict_ID'][0]}")
        logger.error(f"  NationalIndividualElectoralDistrict_ID: {first_row['NationalIndividualElectoralDistrict_ID'][0]}")
        db_connection.unregister("temp_chunk_polars")
        raise

    # Unregister temporary table
    db_connection.unregister("temp_chunk_polars")

    # Return row count
    rows_affected = len(transformed_df)
    return rows_affected


def transform_addresses_polars(
    db_connection: duckdb.DuckDBPyConnection,
    run_tag: str,
    chunk_size: int = 100000,
) -> None:
    """Transform addresses using Polars-based processing (sequential mode).

    This function uses Polars DataFrames for in-memory transformation instead of
    complex SQL operations. Provides significant performance improvements through:
    - Vectorized operations (no row-by-row processing)
    - Faster xxhash64 in Python vs MD5 in DuckDB
    - Arrow zero-copy data transfer
    - Reduced SQL parsing overhead

    Args:
        db_connection: Active DuckDB connection
        run_tag: Run tag to process
        chunk_size: Number of rows per chunk (default: 100,000)
    """
    logger.info("Transforming Address data with Polars-based processing")

    # Get total count (excluding addresses with invalid postal codes)
    total_count = db_connection.execute(
        """SELECT COUNT(*) FROM staging_korzet
        WHERE run_tag = ?
          AND postal_code IS NOT NULL
          AND postal_code != 0
          AND postal_code != '0'
          AND postal_code != ''""",
        [run_tag]
    ).fetchone()[0]

    total_chunks = (total_count + chunk_size - 1) // chunk_size

    logger.info(
        f"Processing {total_count:,} addresses using Polars in {total_chunks} chunks of {chunk_size:,}"
    )

    start_time = time.time()

    for chunk_num in range(total_chunks):
        chunk_start_time = time.time()
        offset = chunk_num * chunk_size
        global_order_start = offset + 1

        # Fetch chunk (DuckDB → Arrow → Polars)
        chunk_df = fetch_staging_chunk_polars(db_connection, run_tag, offset, chunk_size)

        # Transform chunk (Polars vectorized operations)
        transformed_df = transform_chunk_polars(chunk_df, global_order_start)

        # Persist chunk (Polars → Arrow → DuckDB)
        rows_affected = persist_chunk_to_duckdb(db_connection, transformed_df)

        # Calculate timing
        chunk_elapsed = time.time() - chunk_start_time
        total_elapsed = time.time() - start_time
        processed_count = min((chunk_num + 1) * chunk_size, total_count)
        progress_percent = processed_count / total_count * 100

        # Log every 10 chunks or last chunk
        should_log = (chunk_num + 1) % 10 == 0 or (chunk_num + 1) == total_chunks

        if should_log:
            if progress_percent > 0:
                estimated_total = total_elapsed / (progress_percent / 100)
                time_remaining = estimated_total - total_elapsed

                logger.info(
                    f"Polars Chunk {chunk_num + 1}/{total_chunks}: {processed_count:,}/{total_count:,} "
                    f"({progress_percent:.1f}%) - Chunk: {format_time(chunk_elapsed)}, "
                    f"Elapsed: {format_time(total_elapsed)}, ETA: {format_time(time_remaining)}"
                )

    final_count = db_connection.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
    total_time = time.time() - start_time
    throughput = total_count / total_time if total_time > 0 else 0

    logger.info(
        f"Polars transformation complete: {final_count:,} addresses in {format_time(total_time)} "
        f"({throughput:.0f} addr/sec)"
    )
