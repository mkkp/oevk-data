"""Ingestion logic for downloading and loading OEVK data into staging tables."""

import os
import zipfile
from typing import Dict

import duckdb
import requests

from src.utils.logging import get_logger

logger = get_logger(__name__)


def download_sources(sources: Dict[str, str], staging_dir: str) -> Dict[str, str]:
    """Downloads the OEVK JSON and the Address ZIP file from their source URLs.

    Args:
        sources: A dictionary containing the URLs for 'oevk_json' and 'korzet_zip'.
        staging_dir: The directory path to save the downloaded files.

    Returns:
        A dictionary with the local file paths for 'oevk_json' and 'korzet_zip'.
    """
    logger.info("Starting download of source files")

    # Create staging directory if it doesn't exist
    os.makedirs(staging_dir, exist_ok=True)

    file_paths = {}

    # Download OEVK JSON file
    oevk_url = sources.get('oevk_json')
    if oevk_url:
        oevk_filename = os.path.basename(oevk_url)
        oevk_path = os.path.join(staging_dir, oevk_filename)

        logger.info(f"Downloading OEVK JSON from {oevk_url}")
        response = requests.get(oevk_url, stream=True)
        response.raise_for_status()

        with open(oevk_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        file_paths['oevk_json'] = oevk_path
        logger.info(f"OEVK JSON downloaded to {oevk_path}")

    # Download and extract Korzet ZIP file
    korzet_url = sources.get('korzet_zip')
    if korzet_url:
        korzet_filename = os.path.basename(korzet_url)
        korzet_zip_path = os.path.join(staging_dir, korzet_filename)

        logger.info(f"Downloading Korzet ZIP from {korzet_url}")
        response = requests.get(korzet_url, stream=True)
        response.raise_for_status()

        with open(korzet_zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract ZIP file
        extract_dir = os.path.join(staging_dir, 'korzet_extracted')
        os.makedirs(extract_dir, exist_ok=True)

        logger.info(f"Extracting Korzet ZIP to {extract_dir}")
        with zipfile.ZipFile(korzet_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        # Find the CSV file in the extracted directory
        csv_files = [f for f in os.listdir(extract_dir) if f.endswith('.csv')]
        if csv_files:
            korzet_csv_path = os.path.join(extract_dir, csv_files[0])
            file_paths['korzet_csv'] = korzet_csv_path
            logger.info(f"Korzet CSV extracted to {korzet_csv_path}")
        else:
            logger.warning("No CSV file found in Korzet ZIP archive")

    logger.info("Download and extraction completed")
    return file_paths


def load_staging_data(db_connection: duckdb.DuckDBPyConnection,
                     file_paths: Dict[str, str],
                     run_tag: str) -> None:
    """Loads the downloaded and unzipped data into staging tables in DuckDB.

    Args:
        db_connection: An active DuckDB connection.
        file_paths: A dictionary with local paths to 'oevk_json' and the unzipped address CSV.
        run_tag: A tag (e.g., timestamp) to identify the current run in the staging tables.
    """
    logger.info(f"Loading staging data with run_tag: {run_tag}")

    # Create staging tables if they don't exist
    create_staging_tables(db_connection)

    # Load OEVK JSON data
    oevk_json_path = file_paths.get('oevk_json')
    if oevk_json_path and os.path.exists(oevk_json_path):
        logger.info(f"Loading OEVK JSON data from {oevk_json_path}")

        # Load JSON data into a temporary table
        db_connection.execute("""
            CREATE TEMPORARY TABLE temp_oevk AS
            SELECT * FROM read_json(?, format='array')
        """, [oevk_json_path])

        # Insert into staging table with run_tag
        db_connection.execute("""
            INSERT INTO staging_oevk (run_tag, data)
            SELECT ?, row_to_json(temp_oevk) FROM temp_oevk
        """, [run_tag])

        # Drop temporary table
        db_connection.execute("DROP TABLE temp_oevk")

        row_count = db_connection.execute("""
            SELECT COUNT(*) FROM staging_oevk WHERE run_tag = ?
        """, [run_tag]).fetchone()[0]

        logger.info(f"Loaded {row_count} OEVK records")

    # Load Korzet CSV data
    korzet_csv_path = file_paths.get('korzet_csv')
    if korzet_csv_path and os.path.exists(korzet_csv_path):
        logger.info(f"Loading Korzet CSV data from {korzet_csv_path}")

        # Load CSV data into a temporary table
        db_connection.execute("""
            CREATE TEMPORARY TABLE temp_korzet AS
            SELECT * FROM read_csv(?, header=true, delim=';', ignore_errors=true, sample_size=-1)
        """, [korzet_csv_path])

        # Insert into staging table with run_tag
        db_connection.execute("""
            INSERT INTO staging_korzet (
                run_tag, county_code, county_name, oevk_code, settlement_code, 
                settlement_name, tevk_code, polling_station_code, polling_station_address,
                counting_designated, accessible, postal_code, street_name, street_type,
                house_number, building, staircase, gate_code, additional_info
            )
            SELECT ?, "Vármegye kód", "Vármegye", "OEVK", "Település kód", 
                   "Település", "TEVK", "Szavazókör", "Szavazókör cím",
                   "Számlálásra kijelölt", "Akadálymentesített", "PIR", "Közterület név", "Közterület jelleg",
                   "Házszám", "Épület", "Lépcsőház", "Kapukód", "column17"
            FROM temp_korzet
        """, [run_tag])

        # Drop temporary table
        db_connection.execute("DROP TABLE temp_korzet")

        row_count = db_connection.execute("""
            SELECT COUNT(*) FROM staging_korzet WHERE run_tag = ?
        """, [run_tag]).fetchone()[0]

        logger.info(f"Loaded {row_count} Korzet records")

    logger.info("Staging data loading completed")


def create_staging_tables(db_connection: duckdb.DuckDBPyConnection) -> None:
    """Create staging tables if they don't exist.

    Args:
        db_connection: An active DuckDB connection.
    """
    # Create staging table for OEVK JSON data
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS staging_oevk (
            run_tag TEXT,
            data JSON
        )
    """)

    # Create staging table for Korzet CSV data
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS staging_korzet (
            run_tag TEXT,
            county_code TEXT,
            county_name TEXT,
            oevk_code TEXT,
            settlement_code TEXT,
            settlement_name TEXT,
            tevk_code TEXT,
            polling_station_code TEXT,
            polling_station_address TEXT,
            counting_designated TEXT,
            accessible TEXT,
            postal_code INTEGER,
            street_name TEXT,
            street_type TEXT,
            house_number TEXT,
            building TEXT,
            staircase TEXT,
            gate_code TEXT,
            additional_info TEXT
        )
    """)

    logger.info("Staging tables created/verified")
