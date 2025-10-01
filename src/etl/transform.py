"""Transformation logic for converting staging data to normalized target tables."""

import duckdb

from src.etl.hashing import (
    hash_county_id,
    hash_settlement_id,
    hash_oevk_id,
    hash_tevk_id,
    hash_postal_code_id,
    hash_postal_code_settlement_id,
    hash_polling_station_id,
    hash_address_id,
)
from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


def register_hash_functions(db_connection: duckdb.DuckDBPyConnection) -> None:
    """Register hash functions with DuckDB."""
    # Create SQL macros for hash functions using DuckDB's macro syntax
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
        CREATE OR REPLACE MACRO hash_tevk_id(county_code, settlement_code, tevk, oevk) AS lower(substring(md5(county_code || '|' || settlement_code || '|' || COALESCE(tevk, '') || '|' || oevk), 1, 16))
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


def transform_all(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into all 8 target tables.

    Args:
        db_connection: An active DuckDB connection.
        run_tag: The run tag to process from staging tables.
    """
    logger.info(f"Starting transformation for run_tag: {run_tag}")

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
    transform_addresses(db_connection, run_tag)
    transform_postal_code_settlement_relationships(db_connection, run_tag)

    logger.info("Transformation completed successfully")


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
            hash_county_id(county_code) as ID,
            county_code,
            MAX(county_name) as CountyName
        FROM staging_korzet
        WHERE run_tag = ?
        GROUP BY county_code
        ON CONFLICT (ID) DO NOTHING
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
            hash_settlement_id(county_code, settlement_code) as ID,
            settlement_code,
            MAX(settlement_name) as SettlementName,
            hash_county_id(county_code) as County_ID
        FROM staging_korzet
        WHERE run_tag = ?
        GROUP BY county_code, settlement_code
        ON CONFLICT (ID) DO NOTHING
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

    # Extract OEVK data from both sources
    db_connection.execute(
        """
        INSERT INTO NationalIndividualElectoralDistrict (ID, OEVK, Name, Center, Polygon, County_ID)
        SELECT 
            hash_oevk_id(county_code, oevk_code) as ID,
            oevk_code,
            MAX(settlement_name) || ' ' || oevk_code as Name,
            NULL as Center,  -- Will be populated from JSON if available
            NULL as Polygon, -- Will be populated from JSON if available
            hash_county_id(county_code) as County_ID
        FROM staging_korzet
        WHERE run_tag = ?
        GROUP BY county_code, oevk_code
        ON CONFLICT (ID) DO NOTHING
    """,
        [run_tag],
    )

    # TODO: Enhance with OEVK JSON data for Center and Polygon

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM NationalIndividualElectoralDistrict"
    ).fetchone()[0]
    logger.info(f"Transformed {row_count} national individual electoral districts")


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
        ON CONFLICT (ID) DO NOTHING
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
    db_connection.execute(
        """
        INSERT INTO SettlementIndividualElectoralDistrict (
            ID, TEVK, Name, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID
        )
        SELECT 
            hash_tevk_id(
                county_code, settlement_code, 
                COALESCE(tevk_code, '-'), oevk_code
            ) as ID,
            tevk_code as TEVK,
            CASE 
                WHEN tevk_code IS NOT NULL AND tevk_code != '' 
                THEN MAX(settlement_name) || ' ' || tevk_code
                ELSE MAX(settlement_name)
            END as Name,
            hash_county_id(county_code) as County_ID,
            hash_settlement_id(county_code, settlement_code) as Settlement_ID,
            hash_oevk_id(county_code, oevk_code) as NationalIndividualElectoralDistrict_ID
        FROM staging_korzet
        WHERE run_tag = ?
        GROUP BY county_code, settlement_code, tevk_code, oevk_code
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
                COALESCE(tevk_code, '-'), polling_station_address
            ) as ID,
            polling_station_address as PollingStationAddress,
            hash_tevk_id(
                county_code, settlement_code, COALESCE(tevk_code, '-'), oevk_code
            ) as SettlementIndividualElectoralDistrict_ID,
            hash_county_id(county_code) as County_ID,
            hash_settlement_id(county_code, settlement_code) as Settlement_ID,
            hash_oevk_id(county_code, oevk_code) as NationalIndividualElectoralDistrict_ID
        FROM staging_korzet
        WHERE run_tag = ? AND polling_station_address IS NOT NULL AND polling_station_address != ''
        GROUP BY county_code, settlement_code, oevk_code, tevk_code, polling_station_address
        ON CONFLICT (ID) DO NOTHING
    """,
        [run_tag],
    )

    row_count = db_connection.execute("SELECT COUNT(*) FROM PollingStation").fetchone()[
        0
    ]
    logger.info(f"Transformed {row_count} polling stations")


def transform_addresses(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into Address table in chunks."""
    import time

    logger.info("Transforming Address data")

    # Get total count of addresses to process
    total_count = db_connection.execute(
        "SELECT COUNT(*) FROM staging_korzet WHERE run_tag = ?", [run_tag]
    ).fetchone()[0]

    # Process in chunks of 10000
    chunk_size = 10000
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

        # Extract addresses from Korzet CSV in chunks using simpler approach
        db_connection.execute(
            """
            INSERT INTO Address (
                ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, PublicSpaceType,
                HouseNumber, Building, Staircase, PostalCode_ID, PollingStation_ID,
                SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID,
                NationalIndividualElectoralDistrict_ID
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
                ROW_NUMBER() OVER (ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code, 
                                   street_name, street_type, house_number, building, staircase) as Sequence,
                ? + ROW_NUMBER() OVER (ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code, 
                                      street_name, street_type, house_number, building, staircase) - 1 as OriginalOrder,
                TRIM(CONCAT_WS(' ', street_name, street_type, house_number, 
                              COALESCE(building, ''), COALESCE(staircase, ''))) as FullAddress,
                street_name as PublicSpaceName,
                COALESCE(street_type, '') as PublicSpaceType,
                house_number as HouseNumber,
                building as Building,
                staircase as Staircase,
                hash_postal_code_id(CAST(postal_code AS VARCHAR)) as PostalCode_ID,
                hash_polling_station_id(
                    county_code, settlement_code, oevk_code, COALESCE(tevk_code, '-'), polling_station_address
                ) as PollingStation_ID,
                hash_tevk_id(
                    county_code, settlement_code, COALESCE(tevk_code, '-'), oevk_code
                ) as SettlementIndividualElectoralDistrict_ID,
                hash_county_id(county_code) as County_ID,
                hash_settlement_id(county_code, settlement_code) as Settlement_ID,
                hash_oevk_id(county_code, oevk_code) as NationalIndividualElectoralDistrict_ID
            FROM (
                SELECT * FROM staging_korzet 
                WHERE run_tag = ?
                ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code, 
                         street_name, street_type, house_number, building, staircase
                LIMIT ? OFFSET ?
            ) as chunk
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
            [global_order_start, run_tag, chunk_size, offset],
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
