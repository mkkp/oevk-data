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
    hash_address_id
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


def register_hash_functions(db_connection: duckdb.DuckDBPyConnection) -> None:
    """Register hash functions with DuckDB."""
    db_connection.create_function('hash_county_id', hash_county_id)
    db_connection.create_function('hash_settlement_id', hash_settlement_id)
    db_connection.create_function('hash_oevk_id', hash_oevk_id)
    db_connection.create_function('hash_tevk_id', hash_tevk_id)
    db_connection.create_function('hash_postal_code_id', hash_postal_code_id)
    db_connection.create_function('hash_postal_code_settlement_id', hash_postal_code_settlement_id)
    db_connection.create_function('hash_polling_station_id', hash_polling_station_id)
    db_connection.create_function('hash_address_id', hash_address_id)


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
    with open('src/database/schema.sql', 'r') as f:
        schema_sql = f.read()
    
    # Execute the schema creation
    db_connection.execute(schema_sql)
    logger.info("Target schema applied successfully")


def transform_counties(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into County table."""
    logger.info("Transforming County data")
    
    # Extract unique counties from Korzet CSV data
    db_connection.execute("""
        INSERT INTO County (ID, CountyCode, CountyName)
        SELECT 
            hash_county_id(county_code) as ID,
            county_code,
            MAX(county_name) as CountyName
        FROM staging_korzet
        WHERE run_tag = ?
        GROUP BY county_code
        ON CONFLICT (ID) DO NOTHING
    """, [run_tag])
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM County").fetchone()[0]
    logger.info(f"Transformed {row_count} counties")


def transform_settlements(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into Settlement table."""
    logger.info("Transforming Settlement data")
    
    # Extract unique settlements from Korzet CSV data
    db_connection.execute("""
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
    """, [run_tag])
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM Settlement").fetchone()[0]
    logger.info(f"Transformed {row_count} settlements")


def transform_national_individual_electoral_districts(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into NationalIndividualElectoralDistrict table."""
    logger.info("Transforming NationalIndividualElectoralDistrict data")
    
    # Extract OEVK data from both sources
    db_connection.execute("""
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
    """, [run_tag])
    
    # TODO: Enhance with OEVK JSON data for Center and Polygon
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM NationalIndividualElectoralDistrict").fetchone()[0]
    logger.info(f"Transformed {row_count} national individual electoral districts")


def transform_postal_codes(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into PostalCode table."""
    logger.info("Transforming PostalCode data")
    
    # Extract unique postal codes from Korzet CSV data
    db_connection.execute("""
        INSERT INTO PostalCode (ID, PostalCode)
        SELECT 
            hash_postal_code_id(CAST(postal_code AS VARCHAR)) as ID,
            CAST(postal_code AS VARCHAR) as PostalCode
        FROM staging_korzet
        WHERE run_tag = ? AND postal_code IS NOT NULL AND postal_code != 0
        GROUP BY postal_code
        ON CONFLICT (ID) DO NOTHING
    """, [run_tag])
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM PostalCode").fetchone()[0]
    logger.info(f"Transformed {row_count} postal codes")


def transform_settlement_individual_electoral_districts(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into SettlementIndividualElectoralDistrict table."""
    logger.info("Transforming SettlementIndividualElectoralDistrict data")
    
    # Extract TEVK data from Korzet CSV
    db_connection.execute("""
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
    """, [run_tag])
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM SettlementIndividualElectoralDistrict").fetchone()[0]
    logger.info(f"Transformed {row_count} settlement individual electoral districts")


def transform_polling_stations(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into PollingStation table."""
    logger.info("Transforming PollingStation data")
    
    # Extract unique polling stations from Korzet CSV
    db_connection.execute("""
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
    """, [run_tag])
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM PollingStation").fetchone()[0]
    logger.info(f"Transformed {row_count} polling stations")


def transform_addresses(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms staging data into Address table."""
    logger.info("Transforming Address data")
    
    # Extract addresses from Korzet CSV
    db_connection.execute("""
        INSERT INTO Address (
            ID, Sequence, FullAddress, PublicSpaceName, PublicSpaceType,
            HouseNumber, Building, Staircase, PostalCode_ID, PollingStation_ID,
            SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID,
            NationalIndividualElectoralDistrict_ID
        )
        SELECT 
            hash_address_id({
                'county_code': county_code,
                'settlement_code': settlement_code,
                'public_space_name': street_name,
                'public_space_type': street_type,
                'house_number': house_number,
                'building': building,
                'staircase': staircase,
                'postal_code': CAST(postal_code AS VARCHAR)
            }) as ID,
            ROW_NUMBER() OVER (ORDER BY county_code, settlement_code, oevk_code, tevk_code, postal_code, 
                               street_name, street_type, house_number, building, staircase) as Sequence,
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
        FROM staging_korzet
        WHERE run_tag = ?
        ON CONFLICT (ID) DO NOTHING
    """, [run_tag])
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
    logger.info(f"Transformed {row_count} addresses")


def transform_postal_code_settlement_relationships(db_connection: duckdb.DuckDBPyConnection, run_tag: str) -> None:
    """Transforms postal code to settlement relationships."""
    logger.info("Transforming PostalCode_Settlement relationships")
    
    # Create relationships between postal codes and settlements
    db_connection.execute("""
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
        ON CONFLICT (ID) DO NOTHING
    """, [run_tag])
    
    row_count = db_connection.execute("SELECT COUNT(*) FROM PostalCode_Settlement").fetchone()[0]
    logger.info(f"Transformed {row_count} postal code-settlement relationships")