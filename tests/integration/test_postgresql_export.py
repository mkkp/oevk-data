"""Integration tests for PostgreSQL export functionality."""

import pytest
import tempfile
import os
import shutil
import duckdb
from pathlib import Path
from src.etl.export import export_tables_to_csv, generate_postgresql_schema, to_uuid3
from src.etl.export_canonical_v3 import export_canonical_addresses_optimized


class TestPostgreSQLExportIntegration:
    """Integration tests for end-to-end PostgreSQL export."""

    @pytest.fixture
    def test_database(self):
        """Create a temporary test database with sample data."""
        # Create a temp directory and database path
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")

        conn = duckdb.connect(db_path)

        # Create test tables
        conn.execute("""
            CREATE TABLE County (
                ID TEXT PRIMARY KEY,
                CountyCode TEXT UNIQUE NOT NULL,
                CountyName TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE Settlement (
                ID TEXT PRIMARY KEY,
                SettlementCode TEXT NOT NULL,
                SettlementName TEXT NOT NULL,
                County_ID TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE CanonicalAddress (
                ID TEXT PRIMARY KEY,
                CountyCode TEXT NOT NULL,
                SettlementName TEXT NOT NULL,
                StreetName TEXT NOT NULL,
                HouseNumber TEXT NOT NULL,
                FullAddress TEXT NOT NULL,
                AccessibilityFlag TEXT
            )
        """)

        # Insert test data
        conn.execute("""
            INSERT INTO County VALUES
            ('county1', '01', 'Test County 1'),
            ('county2', '02', 'Test County 2')
        """)

        conn.execute("""
            INSERT INTO Settlement VALUES
            ('settlement1', '001', 'Test Settlement 1', 'county1'),
            ('settlement2', '002', 'Test Settlement 2', 'county2')
        """)

        conn.execute("""
            INSERT INTO CanonicalAddress VALUES
            ('addr1', '01', 'Test Settlement 1', 'Main Street', '1', 'Main Street 1', 'A'),
            ('addr2', '01', 'Test Settlement 1', 'Main Street', '2', 'Main Street 2', 'A')
        """)

        yield conn, db_path

        conn.close()
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_postgresql_schema_generation(self):
        """Test that PostgreSQL schema is generated with UUID types."""
        schema = generate_postgresql_schema()

        # Verify schema is not empty
        assert len(schema) > 0

        # Verify UUID conversion (snake_case column names)
        assert "id UUID PRIMARY KEY" in schema
        assert "county_id UUID" in schema
        assert "settlement_id UUID" in schema

        # Verify PostgreSQL header
        assert "PostgreSQL Schema" in schema
        assert "UUID type" in schema

        # Verify trigram extension and indexes for text search
        assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in schema
        assert "idx_address_full_address_trgm" in schema
        assert "gin_trgm_ops" in schema

        # Verify index comments mention substring search
        assert "LIKE/ILIKE" in schema or "substring" in schema.lower()

    def test_export_tables_csv_and_postgresql(self, test_database):
        """Test exporting tables to both CSV and PostgreSQL formats."""
        conn, db_path = test_database

        with tempfile.TemporaryDirectory() as temp_dir:
            run_tag = "test_run"

            # Export to both formats
            export_tables_to_csv(conn, temp_dir, run_tag, formats=["csv", "postgresql"])

            # Verify CSV files exist
            assert os.path.exists(os.path.join(temp_dir, f"{run_tag}_County.csv"))
            assert os.path.exists(os.path.join(temp_dir, f"{run_tag}_Settlement.csv"))

            # Verify PostgreSQL files exist
            assert os.path.exists(os.path.join(temp_dir, "schema.sql"))
            assert os.path.exists(os.path.join(temp_dir, "data.sql"))

            # Verify schema.sql content
            with open(os.path.join(temp_dir, "schema.sql"), "r") as f:
                schema_content = f.read()
                assert "CREATE TABLE" in schema_content
                assert "ID UUID PRIMARY KEY" in schema_content

            # Verify data.sql content
            with open(os.path.join(temp_dir, "data.sql"), "r") as f:
                data_content = f.read()
                assert "INSERT INTO County" in data_content
                assert "INSERT INTO Settlement" in data_content

                # Verify UUID format in INSERTs
                assert "VALUES (" in data_content
                # UUIDs should be in format like '550e8400-e29b-41d4-a716-446655440000'
                import re

                uuid_pattern = (
                    r"'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'"
                )
                assert re.search(uuid_pattern, data_content) is not None

    def test_export_only_postgresql(self, test_database):
        """Test exporting only PostgreSQL format (no CSV)."""
        conn, db_path = test_database

        with tempfile.TemporaryDirectory() as temp_dir:
            run_tag = "test_run"

            # Export only PostgreSQL
            export_tables_to_csv(conn, temp_dir, run_tag, formats=["postgresql"])

            # Verify CSV files do NOT exist
            assert not os.path.exists(os.path.join(temp_dir, f"{run_tag}_County.csv"))

            # Verify PostgreSQL files exist
            assert os.path.exists(os.path.join(temp_dir, "schema.sql"))
            assert os.path.exists(os.path.join(temp_dir, "data.sql"))

    def test_export_only_csv(self, test_database):
        """Test exporting only CSV format (no PostgreSQL)."""
        conn, db_path = test_database

        with tempfile.TemporaryDirectory() as temp_dir:
            run_tag = "test_run"

            # Export only CSV
            export_tables_to_csv(conn, temp_dir, run_tag, formats=["csv"])

            # Verify CSV files exist
            assert os.path.exists(os.path.join(temp_dir, f"{run_tag}_County.csv"))

            # Verify PostgreSQL files do NOT exist
            assert not os.path.exists(os.path.join(temp_dir, "schema.sql"))
            assert not os.path.exists(os.path.join(temp_dir, "data.sql"))

    def test_uuid_conversion_in_data(self, test_database):
        """Test that IDs are properly converted to UUIDs in data.sql."""
        conn, db_path = test_database

        with tempfile.TemporaryDirectory() as temp_dir:
            run_tag = "test_run"

            export_tables_to_csv(conn, temp_dir, run_tag, formats=["postgresql"])

            # Read data.sql
            with open(os.path.join(temp_dir, "data.sql"), "r") as f:
                data_content = f.read()

            # Verify that original IDs are converted
            # 'county1' should be converted to UUID
            uuid_county1 = to_uuid3("county1")
            assert uuid_county1 in data_content

            # 'county2' should be converted to UUID
            uuid_county2 = to_uuid3("county2")
            assert uuid_county2 in data_content

            # Original IDs should NOT appear as-is in the data
            # (they might appear in comments, but not in VALUES clauses)
            import re

            values_pattern = r"VALUES \([^)]*\)"
            values_matches = re.findall(values_pattern, data_content)

            for match in values_matches:
                if "County" in data_content[: data_content.find(match)]:
                    # In County inserts, should not have literal 'county1'
                    assert "'county1'" not in match
                    assert "'county2'" not in match


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
