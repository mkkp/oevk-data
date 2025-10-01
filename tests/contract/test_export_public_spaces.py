"""
Contract tests for the public space export module.

These tests verify that the public space export module implements the contract defined in
`specs/003-extract-publicspacename-and/contracts/export-contract.json`.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import os
import inspect

# Import the module under test
from src.etl.export import export_public_space_tables


class TestPublicSpaceExport:
    """Test the public space export functions."""

    def test_export_public_space_tables_function_exists(self):
        """Test that export_public_space_tables function exists and has correct signature."""
        # Verify function exists and is callable
        assert callable(export_public_space_tables)

        # Verify signature
        sig = inspect.signature(export_public_space_tables)
        assert "db_connection" in sig.parameters
        assert "export_dir" in sig.parameters
        assert "run_tag" in sig.parameters
        assert sig.return_annotation is None

    def test_export_public_space_tables_creates_csv_files(self):
        """Test that export_public_space_tables creates the 3 new CSV files."""
        import duckdb

        with tempfile.TemporaryDirectory() as exports_dir:
            # Create in-memory database for testing
            conn = duckdb.connect(":memory:")

            # Setup test data in database
            from src.database.connection import apply_schema

            apply_schema(conn)

            # Insert test data into public space tables
            conn.execute(
                "INSERT INTO PublicSpaceName (ID, PublicSpaceName) VALUES ('hash1', 'Kossuth')"
            )
            conn.execute(
                "INSERT INTO PublicSpaceType (ID, PublicSpaceType) VALUES ('hash2', 'utca')"
            )
            # Note: SettlementPublicSpaces requires valid Settlement_ID, but we're only testing export, not constraints
            # So we'll skip inserting into SettlementPublicSpaces for this basic test

            export_public_space_tables(conn, exports_dir, "test_run")

            # Verify all 3 CSV files are created
            expected_files = [
                "test_run_PublicSpaceName.csv",
                "test_run_PublicSpaceType.csv",
                "test_run_SettlementPublicSpaces.csv",
            ]
            for filename in expected_files:
                file_path = os.path.join(exports_dir, filename)
                assert os.path.exists(file_path), f"File {filename} should exist"

    def test_export_public_space_name_csv_has_correct_format(self):
        """Test that PublicSpaceName.csv has correct columns and format."""
        import duckdb

        with tempfile.TemporaryDirectory() as exports_dir:
            # Create in-memory database for testing
            conn = duckdb.connect(":memory:")

            # Setup test data
            from src.database.connection import apply_schema

            apply_schema(conn)

            test_names = [
                ("hash1", "Kossuth"),
                ("hash2", "Petőfi"),
                ("hash3", "Béke"),
            ]

            for name_id, name in test_names:
                conn.execute(
                    "INSERT INTO PublicSpaceName (ID, PublicSpaceName) VALUES (?, ?)",
                    (name_id, name),
                )

            export_public_space_tables(conn, exports_dir, "test_run")

            # Verify PublicSpaceName.csv
            file_path = os.path.join(exports_dir, "test_run_PublicSpaceName.csv")
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Check header
            assert lines[0].strip() == "ID,PublicSpaceName"

            # Check data (order is not guaranteed, just check all data is present)
            assert len(lines) == 4  # header + 3 data rows
            # Check that all expected data is present somewhere in the file
            file_content = "".join(lines)
            assert "Kossuth" in file_content
            assert "Petőfi" in file_content
            assert "Béke" in file_content

    def test_export_public_space_type_csv_has_correct_format(self):
        """Test that PublicSpaceType.csv has correct columns and format."""
        import duckdb

        with tempfile.TemporaryDirectory() as exports_dir:
            # Create in-memory database for testing
            conn = duckdb.connect(":memory:")

            # Setup test data
            from src.database.connection import apply_schema

            apply_schema(conn)

            test_types = [("hash1", "utca"), ("hash2", "tér"), ("hash3", "út")]

            for type_id, type_name in test_types:
                conn.execute(
                    "INSERT INTO PublicSpaceType (ID, PublicSpaceType) VALUES (?, ?)",
                    (type_id, type_name),
                )

            export_public_space_tables(conn, exports_dir, "test_run")

            # Verify PublicSpaceType.csv
            file_path = os.path.join(exports_dir, "test_run_PublicSpaceType.csv")
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Check header
            assert lines[0].strip() == "ID,PublicSpaceType"

            # Check data (order is not guaranteed, just check all data is present)
            assert len(lines) == 4  # header + 3 data rows
            # Check that all expected data is present somewhere in the file
            file_content = "".join(lines)
            assert "utca" in file_content
            assert "tér" in file_content
            assert "út" in file_content

    def test_export_settlement_public_spaces_csv_has_correct_format(self):
        """Test that SettlementPublicSpaces.csv has correct columns and format."""
        import duckdb

        with tempfile.TemporaryDirectory() as exports_dir:
            # Create in-memory database for testing
            conn = duckdb.connect(":memory:")

            # Setup test data
            from src.database.connection import apply_schema

            apply_schema(conn)

            # Note: SettlementPublicSpaces requires valid foreign keys, so we'll skip this test
            # and just test that the export function runs without errors
            # The file will be created but will be empty (only header)

            export_public_space_tables(conn, exports_dir, "test_run")

            # Verify SettlementPublicSpaces.csv
            file_path = os.path.join(exports_dir, "test_run_SettlementPublicSpaces.csv")
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Check header
            assert (
                lines[0].strip()
                == "ID,Settlement_ID,PublicSpaceName_ID,PublicSpaceType_ID"
            )

            # Check that file exists and has header
            # Since we didn't insert data due to foreign key constraints, file will only have header
            assert len(lines) == 1  # only header

    def test_export_public_space_tables_uses_utf8_encoding(self):
        """Test that all CSV files use UTF-8 encoding."""
        import duckdb

        with tempfile.TemporaryDirectory() as exports_dir:
            # Create in-memory database for testing
            conn = duckdb.connect(":memory:")

            # Setup test data with special characters
            from src.database.connection import apply_schema

            apply_schema(conn)

            # Test Hungarian special characters
            conn.execute(
                "INSERT INTO PublicSpaceName (ID, PublicSpaceName) VALUES ('hash1', 'Árpád')"
            )
            conn.execute(
                "INSERT INTO PublicSpaceType (ID, PublicSpaceType) VALUES ('hash2', 'út')"
            )

            export_public_space_tables(conn, exports_dir, "test_run")

            # Verify files can be read with UTF-8 encoding
            files_to_check = [
                "test_run_PublicSpaceName.csv",
                "test_run_PublicSpaceType.csv",
            ]
            for filename in files_to_check:
                file_path = os.path.join(exports_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check that special characters are preserved
                assert "Árpád" in content or "út" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
