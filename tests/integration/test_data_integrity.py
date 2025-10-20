"""
Integration tests for data integrity fixes.

These tests verify that:
1. Foreign key references in electoral district tables point to correct entities
2. National district names contain county names (not settlement names)
3. Leading zeros are trimmed from address components consistently
"""

import pytest
import duckdb
import tempfile
import os

from src.etl.transform_optimized import (
    transform_all_optimized,
    register_hash_functions,
)


class TestDataIntegrity:
    """Test data integrity fixes."""

    @pytest.fixture
    def db_connection(self):
        """Create temporary database with test data."""
        db = duckdb.connect(":memory:")

        # Create staging table
        db.execute("""
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
                polling_station_address VARCHAR
            )
        """)

        # Register hash functions
        register_hash_functions(db)

        yield db
        db.close()

    def test_national_district_name_contains_county_name(self, db_connection):
        """Test that national district names contain county names, not settlement names."""
        # Insert test data with county and settlement
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest I. kerület', '01', '001', 1011,
             'Fő', 'utca', '1', '', '', 'Test Polling Station')
        """)

        # Transform data
        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        # Verify national district name contains county name
        result = db_connection.execute("""
            SELECT n.Name, c.CountyName
            FROM NationalIndividualElectoralDistrict n
            JOIN County c ON n.County_ID = c.ID
        """).fetchall()

        assert len(result) > 0
        name, county_name = result[0]

        # Name should contain county name, not settlement name
        assert county_name in name
        assert "Budapest I. kerület" not in name or county_name == "Budapest"

    def test_leading_zeros_trimmed_from_house_number(self, db_connection):
        """Test that leading zeros are trimmed from house numbers."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '000001', '', '', 'Test Polling Station'),
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '000042', '', '', 'Test Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        # Check that house numbers have leading zeros trimmed
        result = db_connection.execute("""
            SELECT DISTINCT HouseNumber
            FROM Address
            ORDER BY HouseNumber
        """).fetchall()

        house_numbers = [r[0] for r in result]
        assert "1" in house_numbers
        assert "42" in house_numbers
        assert "000001" not in house_numbers
        assert "000042" not in house_numbers

    def test_leading_zeros_trimmed_from_building(self, db_connection):
        """Test that leading zeros are trimmed from building numbers."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '5', '0001', '', 'Test Polling Station'),
            ('test_run', '01', 'Budapest', '002', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '10', '00B', '', 'Test Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        result = db_connection.execute("""
            SELECT DISTINCT Building
            FROM Address
            WHERE Building IS NOT NULL AND Building != ''
            ORDER BY Building
        """).fetchall()

        buildings = [r[0] for r in result]
        assert "1" in buildings
        assert "B" in buildings or "00B" in buildings  # Non-numeric kept as-is
        assert "0001" not in buildings

    def test_leading_zeros_trimmed_from_staircase(self, db_connection):
        """Test that leading zeros are trimmed from staircase numbers."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '5', '', '001', 'Test Polling Station'),
            ('test_run', '01', 'Budapest', '002', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '10', '', '0003', 'Test Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        result = db_connection.execute("""
            SELECT DISTINCT Staircase
            FROM Address
            WHERE Staircase IS NOT NULL AND Staircase != ''
            ORDER BY Staircase
        """).fetchall()

        staircases = [r[0] for r in result]
        assert "1" in staircases
        assert "3" in staircases
        assert "001" not in staircases
        assert "0003" not in staircases

    def test_range_notation_preserved_with_trimming(self, db_connection):
        """Test that range notation is preserved with both parts trimmed."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '000001-00005', '', '', 'Test Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        result = db_connection.execute("""
            SELECT HouseNumber
            FROM Address
        """).fetchone()

        assert result[0] == "1-5"

    def test_slash_notation_preserved_with_trimming(self, db_connection):
        """Test that slash notation is preserved with numeric part trimmed."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '000001/D', '', '', 'Test Polling Station'),
            ('test_run', '01', 'Budapest', '002', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '00042/A', '', '', 'Test Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        result = db_connection.execute("""
            SELECT HouseNumber
            FROM Address
            ORDER BY HouseNumber
        """).fetchall()

        house_numbers = [r[0] for r in result]
        assert "1/D" in house_numbers
        assert "42/A" in house_numbers

    def test_non_numeric_values_preserved(self, db_connection):
        """Test that non-numeric values in building/staircase are preserved."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '5', 'A', 'L', 'Test Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        result = db_connection.execute("""
            SELECT Building, Staircase
            FROM Address
        """).fetchone()

        building, staircase = result
        assert building == "A"
        assert staircase == "L"

    def test_settlement_individual_electoral_district_references(self, db_connection):
        """Test that settlement individual electoral district has correct foreign keys."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest I. kerület', '01', '001', 1011,
             'Test', 'utca', '1', '', '', 'Test Polling Station'),
            ('test_run', '01', 'Budapest', '002', 'Budapest II. kerület', '01', '002', 1021,
             'Other', 'utca', '2', '', '', 'Other Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        # Verify that SettlementIndividualElectoralDistrict references correct settlement
        result = db_connection.execute("""
            SELECT
                si.Name as district_name,
                s.SettlementName as settlement_name,
                si.Settlement_ID,
                s.ID
            FROM SettlementIndividualElectoralDistrict si
            JOIN Settlement s ON si.Settlement_ID = s.ID
        """).fetchall()

        assert len(result) >= 2

        # Each district should reference the correct settlement
        for district_name, settlement_name, district_settlement_id, settlement_id in result:
            assert district_settlement_id == settlement_id
            # District name should contain settlement name
            assert settlement_name.split()[0] in district_name

    def test_county_id_oevk_pair_correctness(self, db_connection):
        """Test that county_id and OEVK pairs correctly identify electoral districts."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '1', '', '', 'Test Polling Station'),
            ('test_run', '02', 'Hajdú-Bihar', '001', 'Debrecen', '02', '001', 4000,
             'Other', 'utca', '1', '', '', 'Other Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        # Verify unique county_id and OEVK pairs
        result = db_connection.execute("""
            SELECT
                n.County_ID,
                n.OEVK,
                c.CountyName,
                COUNT(*) as count
            FROM NationalIndividualElectoralDistrict n
            JOIN County c ON n.County_ID = c.ID
            GROUP BY n.County_ID, n.OEVK, c.CountyName
        """).fetchall()

        # Each county_id + OEVK pair should be unique
        for county_id, oevk, county_name, count in result:
            assert count == 1
            assert county_id is not None
            assert oevk is not None

    def test_all_zeros_becomes_zero(self, db_connection):
        """Test that strings with all zeros become '0'."""
        db_connection.execute("""
            INSERT INTO staging_korzet VALUES
            ('test_run', '01', 'Budapest', '001', 'Budapest', '01', '001', 1011,
             'Test', 'utca', '0000', '00', '000', 'Test Polling Station')
        """)

        transform_all_optimized(
            db_connection, "test_run", enable_deduplication=False
        )

        result = db_connection.execute("""
            SELECT HouseNumber, Building, Staircase
            FROM Address
        """).fetchone()

        house_number, building, staircase = result
        assert house_number == "0"
        assert building == "0"
        assert staircase == "0"
