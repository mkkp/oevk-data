"""
Integration tests for deduplication pipeline integration.

Tests that deduplication works correctly when integrated into the transformation pipeline.
"""

import pytest
import duckdb
import polars as pl
from src.etl.transform_optimized import deduplicate_addresses_in_pipeline
from src.utils.config import get_config


class TestDeduplicationPipelineIntegration:
    """Test deduplication integration with transformation pipeline."""

    def test_deduplicate_addresses_in_pipeline_with_sample_data(self, tmp_path):
        """Test deduplication pipeline with sample staging data."""
        # Create temporary database
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        # Register hash functions
        from src.etl.transform_optimized import register_hash_functions

        register_hash_functions(conn)

        # Create staging table with all required columns
        conn.execute("""
            CREATE TABLE staging_korzet (
                run_tag VARCHAR,
                county_code VARCHAR,
                county_name VARCHAR,
                settlement_code VARCHAR,
                settlement_name VARCHAR,
                oevk_code VARCHAR,
                tevk_code VARCHAR,
                polling_station_address VARCHAR,
                postal_code VARCHAR,
                street_name VARCHAR,
                street_type VARCHAR,
                house_number VARCHAR,
                building VARCHAR,
                staircase VARCHAR,
                accessible_flag VARCHAR
            )
        """)

        # Insert sample data with duplicates
        conn.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Test County', '001', 'Test City', '01', '01', 'PS1', '1000', 'Main', 'Street', '1', 'A', NULL, 'I'),
            ('test_run', '01', 'Test County', '001', 'Test City', '01', '01', 'PS2', '1000', 'Main', 'Street', '1', 'A', NULL, 'N'),
            ('test_run', '01', 'Test County', '001', 'Test City', '01', '01', 'PS3', '1001', 'Other', 'Avenue', '2', NULL, NULL, 'I')
        """)

        # Apply schema
        from src.etl.transform_optimized import apply_target_schema

        apply_target_schema(conn)

        # Run deduplication
        result = deduplicate_addresses_in_pipeline(
            conn, "test_run", enable_deduplication=True
        )

        # Verify results
        assert result is not None
        assert "canonical_addresses" in result
        assert "address_mapping" in result
        assert "address_polling_stations" in result
        assert "address_pir_codes" in result

        # Check canonical addresses count
        canonical_count = conn.execute(
            "SELECT COUNT(*) FROM CanonicalAddress"
        ).fetchone()[0]
        assert canonical_count == 2  # Two unique addresses

        # Check address mapping
        mapping_count = conn.execute("SELECT COUNT(*) FROM AddressMapping").fetchone()[
            0
        ]
        assert mapping_count == 3  # All 3 original addresses mapped

        # Check polling stations preserved
        polling_count = conn.execute(
            "SELECT COUNT(*) FROM AddressPollingStations"
        ).fetchone()[0]
        assert polling_count == 3  # All 3 polling stations preserved

        # Check report was generated
        if "deduplication_report" in result:
            report = result["deduplication_report"]
            assert report.total_addresses == 3
            assert report.canonical_addresses_created == 2
            assert report.duplicates_found == 1
            assert report.status == "completed"

        conn.close()

    def test_deduplicate_addresses_disabled(self, tmp_path):
        """Test that deduplication can be disabled."""
        # Create temporary database
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        # Register hash functions
        from src.etl.transform_optimized import register_hash_functions

        register_hash_functions(conn)

        # Create staging table with sample data
        conn.execute("""
            CREATE TABLE staging_korzet (
                run_tag VARCHAR,
                county_code VARCHAR,
                settlement_code VARCHAR,
                settlement_name VARCHAR,
                oevk_code VARCHAR,
                tevk_code VARCHAR,
                polling_station_address VARCHAR,
                postal_code VARCHAR,
                street_name VARCHAR,
                street_type VARCHAR,
                house_number VARCHAR,
                building VARCHAR,
                staircase VARCHAR,
                accessible_flag VARCHAR
            )
        """)

        conn.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', '001', 'Test City', '01', '01', 'PS1', '1000', 'Main', 'Street', '1', NULL, NULL, 'I')
        """)

        # Apply schema
        from src.etl.transform_optimized import apply_target_schema

        apply_target_schema(conn)

        # Run with deduplication disabled
        result = deduplicate_addresses_in_pipeline(
            conn, "test_run", enable_deduplication=False
        )

        # Verify results
        assert result is None

        # Verify deduplication tables are empty
        canonical_count = conn.execute(
            "SELECT COUNT(*) FROM CanonicalAddress"
        ).fetchone()[0]
        assert canonical_count == 0

        conn.close()

    def test_deduplication_with_configuration(self, tmp_path):
        """Test that deduplication respects configuration settings."""
        # Get configuration
        config = get_config()
        dedup_config = config.get_deduplication_settings()

        # Verify configuration exists
        assert dedup_config is not None
        assert "hash_seed" in dedup_config
        assert "enable_logging" in dedup_config
        assert "generate_reports" in dedup_config

        # Verify defaults
        assert dedup_config["hash_seed"] == 20241012
        assert dedup_config["enable_logging"] is True
        assert dedup_config["generate_reports"] is True

    def test_deduplication_accessibility_flag_mapping(self, tmp_path):
        """Test that accessibility flags are correctly mapped."""
        # Create temporary database
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        # Register hash functions
        from src.etl.transform_optimized import register_hash_functions

        register_hash_functions(conn)

        # Create staging table
        conn.execute("""
            CREATE TABLE staging_korzet (
                run_tag VARCHAR,
                county_code VARCHAR,
                settlement_code VARCHAR,
                settlement_name VARCHAR,
                oevk_code VARCHAR,
                tevk_code VARCHAR,
                polling_station_address VARCHAR,
                postal_code VARCHAR,
                street_name VARCHAR,
                street_type VARCHAR,
                house_number VARCHAR,
                building VARCHAR,
                staircase VARCHAR,
                accessible_flag VARCHAR
            )
        """)

        # Insert data with different accessibility flags
        conn.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', '001', 'Test City', '01', '01', 'PS1', '1000', 'Main', 'Street', '1', NULL, NULL, 'I'),
            ('test_run', '01', '001', 'Test City', '01', '01', 'PS2', '1000', 'Main', 'Street', '1', NULL, NULL, 'N')
        """)

        # Apply schema
        from src.etl.transform_optimized import apply_target_schema

        apply_target_schema(conn)

        # Run deduplication
        result = deduplicate_addresses_in_pipeline(
            conn, "test_run", enable_deduplication=True
        )

        # Check that accessibility flag is 'I' (accessible) - prioritizes accessible
        accessibility = conn.execute("""
            SELECT AccessibilityFlag FROM CanonicalAddress WHERE StreetName = 'Main'
        """).fetchone()[0]

        assert accessibility == "I"

        conn.close()

    def test_deduplication_report_generation(self, tmp_path):
        """Test that deduplication report is generated and stored."""
        # Create temporary database
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        # Register hash functions
        from src.etl.transform_optimized import register_hash_functions

        register_hash_functions(conn)

        # Create staging table
        conn.execute("""
            CREATE TABLE staging_korzet (
                run_tag VARCHAR,
                county_code VARCHAR,
                settlement_code VARCHAR,
                settlement_name VARCHAR,
                oevk_code VARCHAR,
                tevk_code VARCHAR,
                polling_station_address VARCHAR,
                postal_code VARCHAR,
                street_name VARCHAR,
                street_type VARCHAR,
                house_number VARCHAR,
                building VARCHAR,
                staircase VARCHAR,
                accessible_flag VARCHAR
            )
        """)

        # Insert sample data
        conn.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', '001', 'Test City', '01', '01', 'PS1', '1000', 'Main', 'Street', '1', NULL, NULL, 'I'),
            ('test_run', '01', '001', 'Test City', '01', '01', 'PS2', '1000', 'Main', 'Street', '1', NULL, NULL, 'N'),
            ('test_run', '01', '001', 'Test City', '01', '01', 'PS3', '1001', 'Other', 'Avenue', '2', NULL, NULL, 'I')
        """)

        # Apply schema
        from src.etl.transform_optimized import apply_target_schema

        apply_target_schema(conn)

        # Run deduplication
        result = deduplicate_addresses_in_pipeline(
            conn, "test_run", enable_deduplication=True
        )

        # Verify report was stored in database
        report_count = conn.execute(
            "SELECT COUNT(*) FROM DeduplicationReport"
        ).fetchone()[0]
        assert report_count == 1

        # Verify report contents
        report_data = conn.execute("""
            SELECT TotalAddresses, DuplicatesFound, CanonicalAddressesCreated, Status
            FROM DeduplicationReport
        """).fetchone()

        assert report_data[0] == 3  # TotalAddresses
        assert report_data[1] == 1  # DuplicatesFound
        assert report_data[2] == 2  # CanonicalAddressesCreated
        assert report_data[3] == "completed"  # Status

        conn.close()


    def test_deduplication_preserves_building_and_staircase_fields(self, tmp_path):
        """Test that building and staircase fields are preserved in canonical addresses."""
        # Create temporary database
        db_path = tmp_path / "test.db"
        conn = duckdb.connect(str(db_path))

        # Register hash functions
        from src.etl.transform_optimized import register_hash_functions

        register_hash_functions(conn)

        # Create staging table
        conn.execute("""
            CREATE TABLE staging_korzet (
                run_tag VARCHAR,
                county_code VARCHAR,
                settlement_code VARCHAR,
                settlement_name VARCHAR,
                oevk_code VARCHAR,
                tevk_code VARCHAR,
                polling_station_address VARCHAR,
                postal_code VARCHAR,
                street_name VARCHAR,
                street_type VARCHAR,
                house_number VARCHAR,
                building VARCHAR,
                staircase VARCHAR,
                accessible_flag VARCHAR
            )
        """)

        # Insert data with building and staircase fields
        conn.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', '001', 'Budapest', '01', '01', 'PS1', '1000', 'Fő', 'utca', '1', 'A', '2', 'I'),
            ('test_run', '01', '001', 'Budapest', '01', '01', 'PS2', '1000', 'Fő', 'utca', '1', 'A', '2', 'N'),
            ('test_run', '01', '001', 'Budapest', '01', '01', 'PS3', '1000', 'Fő', 'utca', '1', 'B', '3', 'I')
        """)

        # Apply schema
        from src.etl.transform_optimized import apply_target_schema

        apply_target_schema(conn)

        # Run deduplication
        result = deduplicate_addresses_in_pipeline(
            conn, "test_run", enable_deduplication=True
        )

        # Verify we have 2 canonical addresses (Building A/Staircase 2 and Building B/Staircase 3)
        canonical_count = conn.execute(
            "SELECT COUNT(*) FROM CanonicalAddress"
        ).fetchone()[0]
        assert canonical_count == 2

        # Verify building and staircase fields are preserved in canonical addresses
        addresses = conn.execute("""
            SELECT Building, Staircase FROM CanonicalAddress ORDER BY Building
        """).fetchall()

        assert len(addresses) == 2
        # First canonical address: Building A, Staircase 2
        assert addresses[0][0] == "A"
        assert addresses[0][1] == "2"
        # Second canonical address: Building B, Staircase 3
        assert addresses[1][0] == "B"
        assert addresses[1][1] == "3"

        # Verify all 3 polling stations are preserved
        polling_count = conn.execute(
            "SELECT COUNT(*) FROM AddressPollingStations"
        ).fetchone()[0]
        assert polling_count == 3

        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
