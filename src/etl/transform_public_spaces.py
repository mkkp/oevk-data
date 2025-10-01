"""
Public space extraction and transformation logic.

This module extracts unique public space names and types from address data,
creates normalized tables for public space entities, and establishes
relationships between settlements and their public spaces.
"""

import duckdb
from src.etl.hashing import (
    hash_public_space_name_id,
    hash_public_space_type_id,
    hash_settlement_public_spaces_id,
)
from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


def register_public_space_hash_functions(
    db_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Register public space hash functions with DuckDB as SQL macros."""
    # Create SQL macros for public space hash functions using DuckDB's macro syntax
    # Using md5 instead of xxhash64 since DuckDB doesn't have xxhash64 built-in
    db_connection.execute("""
        CREATE OR REPLACE MACRO hash_public_space_name_id(public_space_name) AS lower(substring(md5(public_space_name), 1, 16))
    """)

    db_connection.execute("""
        CREATE OR REPLACE MACRO hash_public_space_type_id(public_space_type) AS lower(substring(md5(public_space_type), 1, 16))
    """)

    db_connection.execute("""
        CREATE OR REPLACE MACRO hash_settlement_public_spaces_id(settlement_id, public_space_name_id, public_space_type_id) AS lower(substring(md5(settlement_id || '|' || public_space_name_id || '|' || public_space_type_id), 1, 16))
    """)

    logger.debug("Public space hash functions registered as SQL macros using MD5")


def extract_public_space_entities(db_connection: duckdb.DuckDBPyConnection) -> None:
    """
    Extract unique public space names and types from address data.

    This function:
    1. Creates PublicSpaceName, PublicSpaceType, and SettlementPublicSpaces tables
    2. Extracts unique public space names and types from Address table
    3. Generates deterministic hash IDs for all entities
    4. Populates the lookup tables with relationships
    5. Updates Address table with foreign key references

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Starting public space entity extraction")

    # Register hashing functions with DuckDB as SQL macros
    register_public_space_hash_functions(db_connection)

    # Create the new tables
    create_public_space_tables(db_connection)

    # Create temporary view with precomputed hash IDs for optimization
    create_temp_hash_view(db_connection)

    # Extract and populate public space names
    extract_public_space_names(db_connection)

    # Extract and populate public space types
    extract_public_space_types(db_connection)

    # Create settlement-public space relationships
    create_settlement_public_space_relationships(db_connection)

    # Update Address table with foreign key references
    update_address_table_with_foreign_keys(db_connection)

    # Format house numbers and update FullAddress
    format_house_numbers_and_addresses(db_connection)

    # Clean up temporary view
    db_connection.execute("DROP VIEW IF EXISTS temp_address_hashes")

    logger.info("Public space entity extraction completed successfully")


def create_public_space_tables(db_connection: duckdb.DuckDBPyConnection) -> None:
    """
    Create the three new public space tables.

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Creating public space tables")

    # Create PublicSpaceName table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS PublicSpaceName (
            ID VARCHAR PRIMARY KEY,
            PublicSpaceName VARCHAR NOT NULL UNIQUE
        )
    """)

    # Create PublicSpaceType table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS PublicSpaceType (
            ID VARCHAR PRIMARY KEY,
            PublicSpaceType VARCHAR NOT NULL UNIQUE
        )
    """)

    # Create SettlementPublicSpaces lookup table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS SettlementPublicSpaces (
            ID VARCHAR PRIMARY KEY,
            Settlement_ID VARCHAR NOT NULL,
            PublicSpaceName_ID VARCHAR NOT NULL,
            PublicSpaceType_ID VARCHAR NOT NULL,
            FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
            FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID),
            FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID),
            UNIQUE (Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID)
        )
    """)

    logger.info("Public space tables created successfully")


def create_temp_hash_view(db_connection: duckdb.DuckDBPyConnection) -> None:
    """
    Create a temporary view with precomputed hash IDs for optimization.

    This view helps avoid repeated hash computations in multiple queries.

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Creating temporary hash view for optimization")

    db_connection.execute("""
        CREATE OR REPLACE VIEW temp_address_hashes AS
        SELECT 
            ID,
            Settlement_ID,
            PublicSpaceName,
            PublicSpaceType,
            HouseNumber,
            hash_public_space_name_id(TRIM(PublicSpaceName)) as PublicSpaceName_ID,
            hash_public_space_type_id(TRIM(PublicSpaceType)) as PublicSpaceType_ID,
            hash_settlement_public_spaces_id(
                Settlement_ID,
                hash_public_space_name_id(TRIM(PublicSpaceName)),
                hash_public_space_type_id(TRIM(PublicSpaceType))
            ) as SettlementPublicSpaces_ID
        FROM Address
        WHERE PublicSpaceName IS NOT NULL 
          AND TRIM(PublicSpaceName) != ''
          AND PublicSpaceType IS NOT NULL 
          AND TRIM(PublicSpaceType) != ''
    """)


def extract_public_space_names(db_connection: duckdb.DuckDBPyConnection) -> None:
    """
    Extract unique public space names from address data.

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Extracting unique public space names")

    db_connection.execute("""
        INSERT INTO PublicSpaceName (ID, PublicSpaceName)
        SELECT 
            PublicSpaceName_ID as ID,
            TRIM(PublicSpaceName) as PublicSpaceName
        FROM temp_address_hashes
        GROUP BY PublicSpaceName_ID, TRIM(PublicSpaceName)
        ON CONFLICT (ID) DO NOTHING
    """)

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM PublicSpaceName"
    ).fetchone()[0]
    logger.info(f"Extracted {row_count} unique public space names")


def extract_public_space_types(db_connection: duckdb.DuckDBPyConnection) -> None:
    """
    Extract unique public space types from address data.

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Extracting unique public space types")

    db_connection.execute("""
        INSERT INTO PublicSpaceType (ID, PublicSpaceType)
        SELECT 
            PublicSpaceType_ID as ID,
            TRIM(PublicSpaceType) as PublicSpaceType
        FROM temp_address_hashes
        GROUP BY PublicSpaceType_ID, TRIM(PublicSpaceType)
        ON CONFLICT (ID) DO NOTHING
    """)

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM PublicSpaceType"
    ).fetchone()[0]
    logger.info(f"Extracted {row_count} unique public space types")


def create_settlement_public_space_relationships(
    db_connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Create relationships between settlements and their public spaces.

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Creating settlement-public space relationships")

    db_connection.execute("""
        INSERT INTO SettlementPublicSpaces (
            ID, Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID
        )
        SELECT DISTINCT
            SettlementPublicSpaces_ID as ID,
            Settlement_ID,
            PublicSpaceName_ID,
            PublicSpaceType_ID
        FROM temp_address_hashes
        ON CONFLICT (ID) DO NOTHING
    """)

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM SettlementPublicSpaces"
    ).fetchone()[0]
    logger.info(f"Created {row_count} settlement-public space relationships")


def update_address_table_with_foreign_keys(
    db_connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Update Address table with foreign key references to public space entities.

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Updating Address table with foreign key references")

    # Add new columns if they don't exist
    try:
        db_connection.execute("""
            ALTER TABLE Address 
            ADD COLUMN IF NOT EXISTS PublicSpaceName_ID VARCHAR
        """)

        db_connection.execute("""
            ALTER TABLE Address 
            ADD COLUMN IF NOT EXISTS PublicSpaceType_ID VARCHAR
        """)
    except Exception as e:
        logger.warning(f"Could not add columns to Address table: {e}")

    # Update the foreign key references
    db_connection.execute("""
        UPDATE Address
        SET 
            PublicSpaceName_ID = (
                SELECT PublicSpaceName_ID 
                FROM temp_address_hashes t 
                WHERE t.ID = Address.ID
            ),
            PublicSpaceType_ID = (
                SELECT PublicSpaceType_ID 
                FROM temp_address_hashes t 
                WHERE t.ID = Address.ID
            )
        WHERE ID IN (SELECT ID FROM temp_address_hashes)
    """)

    # Get count of updated addresses
    updated_count = db_connection.execute(
        "SELECT COUNT(*) FROM Address WHERE PublicSpaceName_ID IS NOT NULL"
    ).fetchone()[0]
    logger.info(f"Updated {updated_count} addresses with foreign key references")


def format_house_numbers_and_addresses(
    db_connection: duckdb.DuckDBPyConnection,
) -> None:
    """
    Format house numbers to remove leading zeros and update FullAddress.

    Args:
        db_connection: An active DuckDB connection
    """
    logger.info("Formatting house numbers and updating addresses")

    # Add formatted house number column if it doesn't exist
    try:
        db_connection.execute("""
            ALTER TABLE Address 
            ADD COLUMN IF NOT EXISTS HouseNumberFormatted VARCHAR
        """)
    except Exception as e:
        logger.warning(f"Could not add HouseNumberFormatted column: {e}")

    # Format house numbers (remove leading zeros)
    db_connection.execute("""
        UPDATE Address
        SET HouseNumberFormatted = 
            CASE 
                WHEN regexp_matches(HouseNumber, '^0+[1-9]') THEN 
                    regexp_replace(HouseNumber, '^0+', '')
                ELSE HouseNumber
            END
        WHERE HouseNumber IS NOT NULL
    """)

    # Update FullAddress with formatted house numbers
    db_connection.execute("""
        UPDATE Address
        SET FullAddress = 
            CASE 
                WHEN PublicSpaceName IS NOT NULL AND TRIM(PublicSpaceName) != '' 
                     AND PublicSpaceType IS NOT NULL AND TRIM(PublicSpaceType) != ''
                     AND HouseNumberFormatted IS NOT NULL
                THEN 
                    TRIM(PublicSpaceName) || ' ' || TRIM(PublicSpaceType) || ' ' || HouseNumberFormatted
                ELSE FullAddress
            END
    """)

    # Get count of formatted addresses
    formatted_count = db_connection.execute(
        "SELECT COUNT(*) FROM Address WHERE HouseNumberFormatted IS NOT NULL"
    ).fetchone()[0]
    logger.info(
        f"Formatted house numbers and updated addresses for {formatted_count} records"
    )


def get_public_space_extraction_metrics(
    db_connection: duckdb.DuckDBPyConnection,
) -> dict:
    """
    Get metrics about the public space extraction process.

    Args:
        db_connection: An active DuckDB connection

    Returns:
        Dictionary containing extraction metrics
    """
    metrics = {}

    try:
        # Count of unique public space names
        metrics["unique_public_space_names"] = db_connection.execute(
            "SELECT COUNT(*) FROM PublicSpaceName"
        ).fetchone()[0]

        # Count of unique public space types
        metrics["unique_public_space_types"] = db_connection.execute(
            "SELECT COUNT(*) FROM PublicSpaceType"
        ).fetchone()[0]

        # Count of settlement-public space relationships
        metrics["settlement_public_space_relationships"] = db_connection.execute(
            "SELECT COUNT(*) FROM SettlementPublicSpaces"
        ).fetchone()[0]

        # Count of addresses with public space references
        metrics["addresses_with_public_space_refs"] = db_connection.execute(
            "SELECT COUNT(*) FROM Address WHERE PublicSpaceName_ID IS NOT NULL"
        ).fetchone()[0]

    except Exception as e:
        logger.warning(f"Could not get public space extraction metrics: {e}")
        metrics["error"] = str(e)

    return metrics
