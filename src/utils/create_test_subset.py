#!/usr/bin/env python3
"""
Create Test Subset Database

This utility creates a representative subset of the OEVK database for faster testing.
The subset includes:
- 3 Budapest districts (deterministic selection)
- 10 settlements from 3 other counties (deterministic selection)
- All addresses for selected settlements
- All related entities (counties, districts, polling stations, etc.)

Usage:
    python -m src.utils.create_test_subset --input data/oevk.db --output data/oevk_test.db
    python -m src.utils.create_test_subset --input data/oevk.db --output data/oevk_test.db --seed 42
    python -m src.utils.create_test_subset --budapest-districts 5 --settlements-per-county 5
"""

import argparse
import duckdb
import sys
from pathlib import Path

from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


def create_test_subset(
    input_db_path: str,
    output_db_path: str,
    budapest_districts: int = 3,
    settlements_per_county: int = 10,
    counties_count: int = 3,
    seed: int = 20241016,
):
    """
    Create a test subset database from the full OEVK database.

    Args:
        input_db_path: Path to input database file
        output_db_path: Path to output subset database file
        budapest_districts: Number of Budapest districts to include (default: 3)
        settlements_per_county: Number of settlements per county to include (default: 10)
        counties_count: Number of non-Budapest counties to include (default: 3)
        seed: Random seed for deterministic selection (default: 20241016)
    """
    logger.info(f"Creating test subset from {input_db_path}")
    logger.info(f"Configuration: {budapest_districts} Budapest districts, "
                f"{settlements_per_county} settlements from {counties_count} counties")

    # Connect to input database (read-only)
    input_conn = duckdb.connect(input_db_path, read_only=True)

    # Connect to output database (will be created)
    output_path = Path(output_db_path)
    if output_path.exists():
        logger.warning(f"Output database {output_db_path} already exists, will be overwritten")
        output_path.unlink()

    output_conn = duckdb.connect(output_db_path)

    try:
        # Step 1: Select Budapest districts
        logger.info("Selecting Budapest districts...")
        budapest_settlements = input_conn.execute(f"""
            SELECT ID, SettlementCode, SettlementName, County_ID
            FROM Settlement
            WHERE County_ID = (SELECT ID FROM County WHERE CountyName = 'Budapest')
            ORDER BY SettlementCode
            LIMIT {budapest_districts}
        """).fetchall()

        logger.info(f"Selected {len(budapest_settlements)} Budapest districts: "
                   f"{', '.join([s[2] for s in budapest_settlements])}")

        # Step 2: Select other counties (excluding Budapest)
        logger.info(f"Selecting {counties_count} other counties...")
        other_counties = input_conn.execute(f"""
            SELECT ID, CountyCode, CountyName
            FROM County
            WHERE CountyName != 'Budapest'
            ORDER BY CountyCode
            LIMIT {counties_count}
        """).fetchall()

        logger.info(f"Selected counties: {', '.join([c[2] for c in other_counties])}")

        # Step 3: Select settlements from other counties
        logger.info(f"Selecting {settlements_per_county} settlements per county...")
        other_settlements = []
        for county_id, county_code, county_name in other_counties:
            settlements = input_conn.execute(f"""
                SELECT ID, SettlementCode, SettlementName, County_ID
                FROM Settlement
                WHERE County_ID = '{county_id}'
                ORDER BY SettlementCode
                LIMIT {settlements_per_county}
            """).fetchall()
            other_settlements.extend(settlements)
            logger.info(f"  {county_name}: {len(settlements)} settlements")

        # Combine all selected settlements
        all_settlements = budapest_settlements + other_settlements
        settlement_ids = [s[0] for s in all_settlements]
        settlement_id_list = "', '".join(settlement_ids)

        logger.info(f"Total settlements selected: {len(all_settlements)}")

        # Step 4: Copy schema to output database
        logger.info("Copying database schema...")
        schema_sql_path = Path(__file__).parent.parent / "database" / "schema.sql"
        with open(schema_sql_path, "r") as f:
            schema_sql = f.read()
        output_conn.execute(schema_sql)

        # Step 5: Copy counties
        logger.info("Copying counties...")
        county_ids = list(set([s[3] for s in all_settlements]))
        county_id_list = "', '".join(county_ids)

        output_conn.execute(f"""
            INSERT INTO County
            SELECT * FROM duckdb_scan('{input_db_path}', 'County')
            WHERE ID IN ('{county_id_list}')
        """)

        county_count = output_conn.execute("SELECT COUNT(*) FROM County").fetchone()[0]
        logger.info(f"Copied {county_count} counties")

        # Step 6: Copy settlements
        logger.info("Copying settlements...")
        output_conn.execute(f"""
            INSERT INTO Settlement
            SELECT * FROM duckdb_scan('{input_db_path}', 'Settlement')
            WHERE ID IN ('{settlement_id_list}')
        """)

        settlement_count = output_conn.execute("SELECT COUNT(*) FROM Settlement").fetchone()[0]
        logger.info(f"Copied {settlement_count} settlements")

        # Step 7: Copy national individual electoral districts
        logger.info("Copying national individual electoral districts...")
        output_conn.execute(f"""
            INSERT INTO NationalIndividualElectoralDistrict
            SELECT * FROM duckdb_scan('{input_db_path}', 'NationalIndividualElectoralDistrict')
            WHERE County_ID IN ('{county_id_list}')
        """)

        oevk_count = output_conn.execute("SELECT COUNT(*) FROM NationalIndividualElectoralDistrict").fetchone()[0]
        logger.info(f"Copied {oevk_count} national districts")

        # Step 8: Copy settlement individual electoral districts
        logger.info("Copying settlement individual electoral districts...")
        output_conn.execute(f"""
            INSERT INTO SettlementIndividualElectoralDistrict
            SELECT * FROM duckdb_scan('{input_db_path}', 'SettlementIndividualElectoralDistrict')
            WHERE Settlement_ID IN ('{settlement_id_list}')
        """)

        tevk_count = output_conn.execute("SELECT COUNT(*) FROM SettlementIndividualElectoralDistrict").fetchone()[0]
        logger.info(f"Copied {tevk_count} settlement districts")

        # Step 9: Copy polling stations
        logger.info("Copying polling stations...")
        output_conn.execute(f"""
            INSERT INTO PollingStation
            SELECT * FROM duckdb_scan('{input_db_path}', 'PollingStation')
            WHERE Settlement_ID IN ('{settlement_id_list}')
        """)

        polling_count = output_conn.execute("SELECT COUNT(*) FROM PollingStation").fetchone()[0]
        logger.info(f"Copied {polling_count} polling stations")

        # Step 10: Copy postal codes (all that are referenced by selected addresses)
        logger.info("Copying postal codes...")
        output_conn.execute(f"""
            INSERT INTO PostalCode
            SELECT DISTINCT pc.*
            FROM duckdb_scan('{input_db_path}', 'PostalCode') pc
            WHERE EXISTS (
                SELECT 1 FROM duckdb_scan('{input_db_path}', 'Address') a
                WHERE a.PostalCode_ID = pc.ID
                AND a.Settlement_ID IN ('{settlement_id_list}')
            )
        """)

        postal_count = output_conn.execute("SELECT COUNT(*) FROM PostalCode").fetchone()[0]
        logger.info(f"Copied {postal_count} postal codes")

        # Step 11: Copy addresses
        logger.info("Copying addresses...")
        output_conn.execute(f"""
            INSERT INTO Address
            SELECT * FROM duckdb_scan('{input_db_path}', 'Address')
            WHERE Settlement_ID IN ('{settlement_id_list}')
        """)

        address_count = output_conn.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
        logger.info(f"Copied {address_count} addresses")

        # Step 12: Copy PostalCode_Settlement relationships
        logger.info("Copying postal code-settlement relationships...")
        output_conn.execute(f"""
            INSERT INTO PostalCode_Settlement
            SELECT * FROM duckdb_scan('{input_db_path}', 'PostalCode_Settlement')
            WHERE Settlement_ID IN ('{settlement_id_list}')
        """)

        pc_settlement_count = output_conn.execute("SELECT COUNT(*) FROM PostalCode_Settlement").fetchone()[0]
        logger.info(f"Copied {pc_settlement_count} postal code-settlement relationships")

        # Step 13: Copy deduplication tables if they exist
        logger.info("Copying deduplication data...")

        # Check if CanonicalAddress table exists
        canonical_exists = input_conn.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = 'CanonicalAddress'
        """).fetchone()[0] > 0

        if canonical_exists:
            # Copy canonical addresses for selected settlements
            output_conn.execute(f"""
                INSERT INTO CanonicalAddress
                SELECT DISTINCT ca.*
                FROM duckdb_scan('{input_db_path}', 'CanonicalAddress') ca
                WHERE EXISTS (
                    SELECT 1 FROM duckdb_scan('{input_db_path}', 'Address') a
                    JOIN duckdb_scan('{input_db_path}', 'AddressMapping') am
                        ON a.ID = am.OriginalAddressID
                    WHERE am.CanonicalAddressID = ca.ID
                    AND a.Settlement_ID IN ('{settlement_id_list}')
                )
            """)

            canonical_count = output_conn.execute("SELECT COUNT(*) FROM CanonicalAddress").fetchone()[0]
            logger.info(f"Copied {canonical_count} canonical addresses")

            # Copy address mappings
            output_conn.execute(f"""
                INSERT INTO AddressMapping
                SELECT DISTINCT am.*
                FROM duckdb_scan('{input_db_path}', 'AddressMapping') am
                WHERE EXISTS (
                    SELECT 1 FROM duckdb_scan('{input_db_path}', 'Address') a
                    WHERE a.ID = am.OriginalAddressID
                    AND a.Settlement_ID IN ('{settlement_id_list}')
                )
            """)

            mapping_count = output_conn.execute("SELECT COUNT(*) FROM AddressMapping").fetchone()[0]
            logger.info(f"Copied {mapping_count} address mappings")

            # Copy address polling stations
            output_conn.execute(f"""
                INSERT INTO AddressPollingStations
                SELECT DISTINCT aps.*
                FROM duckdb_scan('{input_db_path}', 'AddressPollingStations') aps
                WHERE EXISTS (
                    SELECT 1 FROM duckdb_scan('{input_db_path}', 'AddressMapping') am
                    JOIN duckdb_scan('{input_db_path}', 'Address') a
                        ON am.OriginalAddressID = a.ID
                    WHERE am.CanonicalAddressID = aps.CanonicalAddressID
                    AND a.Settlement_ID IN ('{settlement_id_list}')
                )
            """)

            aps_count = output_conn.execute("SELECT COUNT(*) FROM AddressPollingStations").fetchone()[0]
            logger.info(f"Copied {aps_count} address-polling station relationships")

            # Copy address PIR codes
            output_conn.execute(f"""
                INSERT INTO AddressPIRCodes
                SELECT DISTINCT apc.*
                FROM duckdb_scan('{input_db_path}', 'AddressPIRCodes') apc
                WHERE EXISTS (
                    SELECT 1 FROM duckdb_scan('{input_db_path}', 'AddressMapping') am
                    JOIN duckdb_scan('{input_db_path}', 'Address') a
                        ON am.OriginalAddressID = a.ID
                    WHERE am.CanonicalAddressID = apc.CanonicalAddressID
                    AND a.Settlement_ID IN ('{settlement_id_list}')
                )
            """)

            pir_count = output_conn.execute("SELECT COUNT(*) FROM AddressPIRCodes").fetchone()[0]
            logger.info(f"Copied {pir_count} address PIR codes")

        logger.info(f"✓ Test subset created successfully: {output_db_path}")
        logger.info(f"  Total addresses: {address_count:,}")
        logger.info(f"  Total settlements: {settlement_count}")
        logger.info(f"  Total counties: {county_count}")

    finally:
        input_conn.close()
        output_conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create a test subset of the OEVK database for faster testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to input database file"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to output subset database file"
    )

    parser.add_argument(
        "--budapest-districts",
        type=int,
        default=3,
        help="Number of Budapest districts to include (default: 3)"
    )

    parser.add_argument(
        "--settlements-per-county",
        type=int,
        default=10,
        help="Number of settlements per county to include (default: 10)"
    )

    parser.add_argument(
        "--counties",
        type=int,
        default=3,
        help="Number of non-Budapest counties to include (default: 3)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20241016,
        help="Random seed for deterministic selection (default: 20241016)"
    )

    args = parser.parse_args()

    try:
        create_test_subset(
            input_db_path=args.input,
            output_db_path=args.output,
            budapest_districts=args.budapest_districts,
            settlements_per_county=args.settlements_per_county,
            counties_count=args.counties,
            seed=args.seed,
        )
        return 0
    except Exception as e:
        logger.error(f"Failed to create test subset: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
