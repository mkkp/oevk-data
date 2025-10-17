"""
Simplified integration tests for coordinate data export schema.

Phase 3 of fix-export-inconsistencies validates that:
1. Schema includes Center and Polygon columns in SettlementIndividualElectoralDistrict table
2. PostgreSQL export schema includes coordinate columns for polling districts (TEVK)
3. Schema is ready for coordinate data (columns exist, accept TEXT/NULL values)

Note: Actual coordinate data population from staging is not yet implemented.
This is intentional - the schema is being prepared for future coordinate data.
"""

import os
import tempfile
import shutil
import duckdb
import pytest

from src.etl.transform_optimized import transform_all_optimized
from src.etl.export import generate_postgresql_schema


class TestCoordinateExportSchema:
    """Test that coordinate export schema is properly set up for polling districts."""

    @pytest.fixture
    def test_database(self):
        """Create a temporary test database with minimal data."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_coordinate_schema.db")

        try:
            db_connection = duckdb.connect(db_path)

            # Create minimal staging table
            db_connection.execute("""
                CREATE TABLE staging_korzet (
                    run_tag VARCHAR,
                    county_code VARCHAR,
                    county_name VARCHAR,
                    settlement_code VARCHAR,
                    settlement_name VARCHAR,
                    oevk_code VARCHAR,
                    tevk_code VARCHAR,
                    postal_code INTEGER,
                    street_name VARCHAR,
                    street_type VARCHAR,
                    house_number VARCHAR,
                    building VARCHAR,
                    staircase VARCHAR,
                    accessible VARCHAR,
                    polling_station_address VARCHAR
                )
            """)

            # Insert minimal test data
            db_connection.execute("""
                INSERT INTO staging_korzet VALUES
                ('test_run', '01', 'Budapest', '00001', 'Budapest I. kerület', '01', '001', 1011,
                 'Fő', 'utca', '1', '', '', 'I', 'Test Polling Station')
            """)

            db_connection.commit()
            yield db_connection

        finally:
            db_connection.close()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_settlement_district_has_coordinate_columns(self, test_database):
        """Test that SettlementIndividualElectoralDistrict table includes Center and Polygon columns."""
        # Transform the data to create schema
        transform_all_optimized(test_database, "test_run", enable_deduplication=False)

        # Check SettlementIndividualElectoralDistrict table schema
        schema_info = test_database.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'SettlementIndividualElectoralDistrict'
            ORDER BY column_name
        """).fetchall()

        column_names = [col[0] for col in schema_info]
        column_types = {col[0]: col[1] for col in schema_info}

        # Verify coordinate columns exist for polling district boundaries
        assert 'Center' in column_names, "SettlementIndividualElectoralDistrict should have 'Center' column"
        assert 'Polygon' in column_names, "SettlementIndividualElectoralDistrict should have 'Polygon' column"

        # Verify column types are TEXT/VARCHAR (compatible with WKT format)
        assert column_types['Center'] == 'VARCHAR', "Center should be VARCHAR type for WKT data"
        assert column_types['Polygon'] == 'VARCHAR', "Polygon should be VARCHAR type for WKT data"

    def test_postgresql_export_schema_includes_coordinates(self, test_database):
        """Test that PostgreSQL export schema includes coordinate columns in SettlementIndividualElectoralDistrict."""
        # Generate PostgreSQL schema (reads from schema.sql file, no db connection needed)
        schema_content = generate_postgresql_schema()

        # Verify schema contains SettlementIndividualElectoralDistrict table
        assert 'SettlementIndividualElectoralDistrict' in schema_content, \
            "PostgreSQL schema should include SettlementIndividualElectoralDistrict table"

        # Verify schema contains coordinate columns
        assert 'Center' in schema_content or 'center' in schema_content, \
            "PostgreSQL schema should include Center column"
        assert 'Polygon' in schema_content or 'polygon' in schema_content, \
            "PostgreSQL schema should include Polygon column"

        # Verify TEXT type is used
        assert 'TEXT' in schema_content, "Schema should use TEXT type for coordinate columns"

    def test_coordinate_columns_accept_null(self, test_database):
        """Test that coordinate columns can accept NULL values (for districts without coordinate data)."""
        # Transform to create SettlementIndividualElectoralDistrict records
        transform_all_optimized(test_database, "test_run", enable_deduplication=False)

        # SettlementIndividualElectoralDistrict table should exist and have at least one record
        count = test_database.execute("SELECT COUNT(*) FROM SettlementIndividualElectoralDistrict").fetchone()[0]
        assert count >= 1, "Should have at least one polling district"

        # Coordinate columns should accept NULL (they're not populated from staging yet)
        result = test_database.execute("""
            SELECT Center, Polygon
            FROM SettlementIndividualElectoralDistrict
            LIMIT 1
        """).fetchone()

        center, polygon = result
        # Coordinates may be NULL since they're not populated from staging yet
        # This is expected - the schema is ready but data population is a future enhancement
        assert center is None or isinstance(center, str), "Center should be NULL or string"
        assert polygon is None or isinstance(polygon, str), "Polygon should be NULL or string"

    def test_canonical_address_no_coordinate_columns(self, test_database):
        """Test that CanonicalAddress table does NOT have coordinate columns (they're in TEVK table)."""
        # Transform with deduplication to create CanonicalAddress
        transform_all_optimized(test_database, "test_run", enable_deduplication=True)

        # Check CanonicalAddress table schema
        schema_info = test_database.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'CanonicalAddress'
            ORDER BY column_name
        """).fetchall()

        column_names = [col[0] for col in schema_info]

        # Verify coordinate columns do NOT exist in CanonicalAddress
        # (coordinates are for polling districts, not individual addresses)
        assert 'Center' not in column_names, "CanonicalAddress should NOT have 'Center' column"
        assert 'Polygon' not in column_names, "CanonicalAddress should NOT have 'Polygon' column"

    def test_national_district_no_coordinate_columns(self, test_database):
        """Test that NationalIndividualElectoralDistrict does NOT have coordinate columns."""
        # Transform the data
        transform_all_optimized(test_database, "test_run", enable_deduplication=False)

        # Check NationalIndividualElectoralDistrict table schema
        schema_info = test_database.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'NationalIndividualElectoralDistrict'
            ORDER BY column_name
        """).fetchall()

        column_names = [col[0] for col in schema_info]

        # Verify coordinate columns do NOT exist (only in TEVK, not OEVK)
        assert 'Center' not in column_names, "NationalIndividualElectoralDistrict should NOT have 'Center' column"
        assert 'Polygon' not in column_names, "NationalIndividualElectoralDistrict should NOT have 'Polygon' column"
