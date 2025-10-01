"""
Contract tests for the public space transformation module.

These tests verify that the public space transformation module implements the contract defined in
`specs/003-extract-publicspacename-and/contracts/transform-contract.json`.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import inspect
import sys
import os

# Add the project root to Python path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

# Import the module under test
from src.etl.transform_public_spaces import extract_public_space_entities


class TestPublicSpaceTransformation:
    """Test the public space extraction transformation functions."""

    def test_extract_public_spaces_function_exists(self):
        """Test that extract_public_space_entities function exists and has correct signature."""
        # Verify function exists and has correct signature
        assert callable(extract_public_space_entities)
        sig = inspect.signature(extract_public_space_entities)
        assert "db_connection" in sig.parameters
        assert sig.return_annotation is None

    def test_extract_public_spaces_creates_new_tables(self):
        """Test that extract_public_space_entities creates the 3 new public space tables."""
        import duckdb

        # Use in-memory database to avoid file issues
        conn = duckdb.connect(":memory:")

        # Apply base schema first
        from src.database.connection import apply_schema

        apply_schema(conn)

        extract_public_space_entities(conn)

        # Verify all 3 new tables exist
        new_tables = [
            "PublicSpaceName",
            "PublicSpaceType",
            "SettlementPublicSpaces",
        ]
        for table in new_tables:
            result = conn.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = '{table}'
            """).fetchone()
            assert result[0] == 1, f"Table {table} should exist"

    def test_extract_public_spaces_populates_public_space_name_table(self):
        """Test that PublicSpaceName table is populated with unique names."""
        import duckdb

        # Use in-memory database
        conn = duckdb.connect(":memory:")

        # Create minimal schema for testing
        conn.execute("""
            CREATE TABLE Settlement (
                ID TEXT PRIMARY KEY
            )
        """)

        # Create minimal Settlement entries
        conn.execute("INSERT INTO Settlement VALUES ('sett1')")
        conn.execute("INSERT INTO Settlement VALUES ('sett2')")

        conn.execute("""
            CREATE TABLE Address (
                ID TEXT PRIMARY KEY,
                PublicSpaceName TEXT NOT NULL,
                PublicSpaceType TEXT NOT NULL,
                Settlement_ID TEXT NOT NULL,
                HouseNumber TEXT NOT NULL,
                FullAddress TEXT NOT NULL
            )
        """)

        # Insert test addresses with various public space names
        test_addresses = [
            ("addr1", "Kossuth", "utca", "sett1", "1", "Kossuth utca 1"),
            ("addr2", "Petőfi", "utca", "sett1", "2", "Petőfi utca 2"),
            (
                "addr3",
                "Kossuth",
                "utca",
                "sett2",
                "3",
                "Kossuth utca 3",
            ),  # Same name, different settlement
            ("addr4", "Béke", "tér", "sett1", "4", "Béke tér 4"),
        ]

        for addr in test_addresses:
            conn.execute("INSERT INTO Address VALUES (?, ?, ?, ?, ?, ?)", addr)

        # Mock the hashing functions to avoid dependencies
        # These will be registered by extract_public_space_entities

        # Create the PublicSpaceName table first
        conn.execute("""
            CREATE TABLE PublicSpaceName (
                ID VARCHAR PRIMARY KEY,
                PublicSpaceName VARCHAR NOT NULL UNIQUE
            )
        """)

        # Call the main function which sets up the temporary view
        extract_public_space_entities(conn)

        # Verify PublicSpaceName table has unique names
        result = conn.execute("SELECT COUNT(*) FROM PublicSpaceName").fetchone()
        assert result[0] == 3, "Should have 3 unique public space names"

        names = conn.execute(
            "SELECT PublicSpaceName FROM PublicSpaceName ORDER BY PublicSpaceName"
        ).fetchall()
        expected_names = ["Béke", "Kossuth", "Petőfi"]
        assert [name[0] for name in names] == expected_names

    def test_extract_public_spaces_populates_public_space_type_table(self):
        """Test that PublicSpaceType table is populated with unique types."""
        import duckdb

        # Use in-memory database
        conn = duckdb.connect(":memory:")

        # Create minimal schema for testing
        conn.execute("""
            CREATE TABLE Settlement (
                ID TEXT PRIMARY KEY
            )
        """)

        # Create minimal Settlement entries
        conn.execute("INSERT INTO Settlement VALUES ('sett1')")
        conn.execute("INSERT INTO Settlement VALUES ('sett2')")

        conn.execute("""
            CREATE TABLE Address (
                ID TEXT PRIMARY KEY,
                PublicSpaceName TEXT NOT NULL,
                PublicSpaceType TEXT NOT NULL,
                Settlement_ID TEXT NOT NULL,
                HouseNumber TEXT NOT NULL,
                FullAddress TEXT NOT NULL
            )
        """)

        # Insert test addresses with various public space types
        test_addresses = [
            ("addr1", "Kossuth", "utca", "sett1", "1", "Kossuth utca 1"),
            ("addr2", "Petőfi", "utca", "sett1", "2", "Petőfi utca 2"),
            ("addr3", "Béke", "tér", "sett1", "3", "Béke tér 3"),
            ("addr4", "Fő", "út", "sett2", "4", "Fő út 4"),
        ]

        for addr in test_addresses:
            conn.execute("INSERT INTO Address VALUES (?, ?, ?, ?, ?, ?)", addr)

        # Hashing functions will be registered by the main function

        # Create the PublicSpaceType table first
        conn.execute("""
            CREATE TABLE PublicSpaceType (
                ID VARCHAR PRIMARY KEY,
                PublicSpaceType VARCHAR NOT NULL UNIQUE
            )
        """)

        # Call the main function which sets up the temporary view and extracts all entities
        from src.etl.transform_public_spaces import extract_public_space_entities

        extract_public_space_entities(conn)

        # Verify PublicSpaceType table has unique types
        result = conn.execute("SELECT COUNT(*) FROM PublicSpaceType").fetchone()
        assert result[0] == 3, "Should have 3 unique public space types"

        types = conn.execute("SELECT PublicSpaceType FROM PublicSpaceType").fetchall()
        actual_types = sorted([type[0] for type in types])
        expected_types = sorted(["tér", "út", "utca"])
        assert actual_types == expected_types

    def test_extract_public_spaces_creates_settlement_lookup_table(self):
        """Test that SettlementPublicSpaces table is created with correct relationships."""
        import duckdb

        # Use in-memory database
        conn = duckdb.connect(":memory:")

        # Create minimal schema for testing
        conn.execute("""
            CREATE TABLE Address (
                ID TEXT PRIMARY KEY,
                PublicSpaceName TEXT NOT NULL,
                PublicSpaceType TEXT NOT NULL,
                Settlement_ID TEXT NOT NULL,
                HouseNumber TEXT NOT NULL,
                FullAddress TEXT NOT NULL
            )
        """)

        # Create Settlement table for foreign key reference
        conn.execute("""
            CREATE TABLE Settlement (
                ID TEXT PRIMARY KEY
            )
        """)

        # Insert test settlements
        conn.execute("INSERT INTO Settlement VALUES ('sett1')")
        conn.execute("INSERT INTO Settlement VALUES ('sett2')")

        # Insert test addresses with various public space names/types
        test_addresses = [
            ("addr1", "Kossuth", "utca", "sett1", "1", "Kossuth utca 1"),
            ("addr2", "Petőfi", "utca", "sett1", "2", "Petőfi utca 2"),
            (
                "addr3",
                "Kossuth",
                "utca",
                "sett2",
                "3",
                "Kossuth utca 3",
            ),  # Same name/type, different settlement
            ("addr4", "Béke", "tér", "sett1", "4", "Béke tér 4"),
        ]

        for addr in test_addresses:
            conn.execute("INSERT INTO Address VALUES (?, ?, ?, ?, ?, ?)", addr)

        # Hashing functions and tables will be created by the main function

        # Call the main function which sets up the temporary view and extracts all entities
        from src.etl.transform_public_spaces import extract_public_space_entities

        extract_public_space_entities(conn)

        # Verify SettlementPublicSpaces table has correct relationships
        result = conn.execute("SELECT COUNT(*) FROM SettlementPublicSpaces").fetchone()
        assert result[0] == 4, (
            "Should have 4 unique settlement-public space combinations"
        )

        # Verify each combination is unique
        combinations = conn.execute("""
            SELECT Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID
            FROM SettlementPublicSpaces
            ORDER BY Settlement_ID
        """).fetchall()
        assert len(combinations) == len(set(combinations)), (
            "All combinations should be unique"
        )

        # Verify specific combinations exist by checking the count and uniqueness
        # We expect 4 unique combinations:
        # - sett1 + Kossuth + utca
        # - sett1 + Petőfi + utca
        # - sett1 + Béke + tér
        # - sett2 + Kossuth + utca
        assert len(combinations) == 4, "Should have exactly 4 unique combinations"

    def test_extract_public_spaces_generates_correct_hash_ids(self):
        """Test that xxhash64 IDs are generated correctly for public space entities."""
        import duckdb

        # Use in-memory database
        conn = duckdb.connect(":memory:")

        # Create minimal schema for testing
        conn.execute("""
            CREATE TABLE Address (
                ID TEXT PRIMARY KEY,
                PublicSpaceName TEXT NOT NULL,
                PublicSpaceType TEXT NOT NULL,
                Settlement_ID TEXT NOT NULL,
                HouseNumber TEXT NOT NULL,
                FullAddress TEXT
            )
        """)

        # Create Settlement table for foreign key reference
        conn.execute("""
            CREATE TABLE Settlement (
                ID TEXT PRIMARY KEY
            )
        """)

        # Insert test settlement
        conn.execute("INSERT INTO Settlement VALUES ('sett1')")

        # Insert test address
        test_addresses = [("addr1", "Kossuth", "utca", "sett1", "1", None)]

        for addr in test_addresses:
            conn.execute("INSERT INTO Address VALUES (?, ?, ?, ?, ?, ?)", addr)

        # Import the actual hashing functions for verification
        from src.etl.hashing import (
            hash_public_space_name_id,
            hash_public_space_type_id,
            hash_settlement_public_spaces_id,
        )

        # Create the public space tables
        conn.execute("""
            CREATE TABLE PublicSpaceName (
                ID VARCHAR PRIMARY KEY,
                PublicSpaceName VARCHAR NOT NULL UNIQUE
            )
        """)

        conn.execute("""
            CREATE TABLE PublicSpaceType (
                ID VARCHAR PRIMARY KEY,
                PublicSpaceType VARCHAR NOT NULL UNIQUE
            )
        """)

        conn.execute("""
            CREATE TABLE SettlementPublicSpaces (
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

        # Call the main function to test the complete flow
        from src.etl.transform_public_spaces import extract_public_space_entities

        extract_public_space_entities(conn)

        # Verify hash IDs are generated correctly
        # Check PublicSpaceName ID
        name_result = conn.execute(
            "SELECT ID, PublicSpaceName FROM PublicSpaceName"
        ).fetchone()
        expected_name_id = hash_public_space_name_id("Kossuth")
        assert name_result[0] == expected_name_id
        assert name_result[1] == "Kossuth"

        # Check PublicSpaceType ID
        type_result = conn.execute(
            "SELECT ID, PublicSpaceType FROM PublicSpaceType"
        ).fetchone()
        expected_type_id = hash_public_space_type_id("utca")
        assert type_result[0] == expected_type_id
        assert type_result[1] == "utca"

        # Check SettlementPublicSpaces ID
        lookup_result = conn.execute("""
            SELECT ID, Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID 
            FROM SettlementPublicSpaces
        """).fetchone()

        expected_lookup_id = hash_settlement_public_spaces_id(
            "sett1", expected_name_id, expected_type_id
        )
        assert lookup_result[0] == expected_lookup_id
        assert lookup_result[1] == "sett1"
        assert lookup_result[2] == expected_name_id
        assert lookup_result[3] == expected_type_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
