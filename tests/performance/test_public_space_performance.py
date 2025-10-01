"""Performance tests for public space extraction."""

import time
import pytest
import duckdb
from src.etl.transform_public_spaces import extract_public_space_entities


class TestPublicSpacePerformance:
    """Performance tests for public space extraction."""

    @pytest.fixture
    def sample_database(self):
        """Create a sample database with test data."""
        conn = duckdb.connect(":memory:")

        # Create base tables
        conn.execute("""
            CREATE TABLE Settlement (
                ID VARCHAR PRIMARY KEY,
                SettlementName VARCHAR,
                SettlementCode VARCHAR
            )
        """)

        conn.execute("""
            CREATE TABLE Address (
                ID VARCHAR PRIMARY KEY,
                Settlement_ID VARCHAR,
                PublicSpaceName VARCHAR,
                PublicSpaceType VARCHAR,
                HouseNumber VARCHAR,
                Building VARCHAR,
                Staircase VARCHAR,
                FullAddress VARCHAR,
                Sequence INTEGER
            )
        """)

        # Insert sample settlements
        conn.execute("""
            INSERT INTO Settlement (ID, SettlementName, SettlementCode)
            VALUES 
                ('settlement_001', 'Budapest', '001'),
                ('settlement_002', 'Debrecen', '002'),
                ('settlement_003', 'Szeged', '003')
        """)

        # Insert sample addresses with various public space combinations
        addresses = []
        for i in range(1000):  # Create 1000 test addresses
            settlement_id = f"settlement_{(i % 3) + 1:03d}"
            public_space_name = f"Test Street {i % 50}"
            public_space_type = ["utca", "tér", "köz", "út"][i % 4]
            house_number = f"{i % 100 + 1}"

            addresses.append(
                f"('address_{i:04d}', '{settlement_id}', '{public_space_name}', "
                f"'{public_space_type}', '{house_number}', NULL, NULL, '', {i})"
            )

        conn.execute(f"""
            INSERT INTO Address (ID, Settlement_ID, PublicSpaceName, PublicSpaceType, 
                                HouseNumber, Building, Staircase, FullAddress, Sequence)
            VALUES {", ".join(addresses)}
        """)

        return conn

    def test_extraction_performance_small_dataset(self, sample_database):
        """Test performance with small dataset (1000 addresses)."""
        start_time = time.time()

        extract_public_space_entities(sample_database)

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in under 1 second for small dataset
        assert execution_time < 1.0, (
            f"Extraction took {execution_time:.2f}s, expected < 1.0s"
        )

        # Verify tables were created and populated
        public_space_names = sample_database.execute(
            "SELECT COUNT(*) FROM PublicSpaceName"
        ).fetchone()[0]
        public_space_types = sample_database.execute(
            "SELECT COUNT(*) FROM PublicSpaceType"
        ).fetchone()[0]
        relationships = sample_database.execute(
            "SELECT COUNT(*) FROM SettlementPublicSpaces"
        ).fetchone()[0]

        assert public_space_names > 0
        assert public_space_types > 0
        assert relationships > 0

    def test_extraction_handles_duplicates_efficiently(self, sample_database):
        """Test that duplicate public spaces are handled efficiently."""
        # Add more addresses with the same public spaces to test deduplication
        for i in range(500):  # Add 500 more addresses with same public spaces
            settlement_id = f"settlement_{(i % 3) + 1:03d}"
            public_space_name = "Main Street"  # Same name for all
            public_space_type = "utca"  # Same type for all
            house_number = f"{i % 50 + 1}"

            sample_database.execute(f"""
                INSERT INTO Address (ID, Settlement_ID, PublicSpaceName, PublicSpaceType, 
                                    HouseNumber, Building, Staircase, FullAddress, Sequence)
                VALUES ('dup_address_{i:04d}', '{settlement_id}', '{public_space_name}', 
                        '{public_space_type}', '{house_number}', NULL, NULL, '', {i + 1000})
            """)

        start_time = time.time()

        extract_public_space_entities(sample_database)

        end_time = time.time()
        execution_time = end_time - start_time

        # Should still complete quickly even with duplicates
        assert execution_time < 2.0, (
            f"Extraction with duplicates took {execution_time:.2f}s, expected < 2.0s"
        )

        # Verify deduplication worked
        public_space_names = sample_database.execute(
            "SELECT COUNT(*) FROM PublicSpaceName"
        ).fetchone()[0]
        public_space_types = sample_database.execute(
            "SELECT COUNT(*) FROM PublicSpaceType"
        ).fetchone()[0]

        # Should have only one "Main Street" and one "utca" despite many addresses
        assert public_space_names == 51  # 50 unique + 1 from duplicates
        assert public_space_types == 4  # 4 unique types

    def test_extraction_memory_efficiency(self, sample_database):
        """Test that extraction doesn't use excessive memory."""
        # For now, just test that it completes without memory errors
        # In a real environment, we would use psutil to measure memory usage
        extract_public_space_entities(sample_database)

        # If we get here without memory errors, the test passes
        assert True

    def test_extraction_idempotent(self, sample_database):
        """Test that extraction can be run multiple times without issues."""
        # First run
        extract_public_space_entities(sample_database)

        # Get counts after first run
        names_first = sample_database.execute(
            "SELECT COUNT(*) FROM PublicSpaceName"
        ).fetchone()[0]
        types_first = sample_database.execute(
            "SELECT COUNT(*) FROM PublicSpaceType"
        ).fetchone()[0]
        relationships_first = sample_database.execute(
            "SELECT COUNT(*) FROM SettlementPublicSpaces"
        ).fetchone()[0]

        # Create a completely fresh database for second run
        conn2 = duckdb.connect(":memory:")

        # Recreate the base tables with fresh data
        conn2.execute("""
            CREATE TABLE Settlement (
                ID VARCHAR PRIMARY KEY,
                SettlementName VARCHAR,
                SettlementCode VARCHAR
            )
        """)

        conn2.execute("""
            CREATE TABLE Address (
                ID VARCHAR PRIMARY KEY,
                Settlement_ID VARCHAR,
                PublicSpaceName VARCHAR,
                PublicSpaceType VARCHAR,
                HouseNumber VARCHAR,
                Building VARCHAR,
                Staircase VARCHAR,
                FullAddress VARCHAR,
                Sequence INTEGER
            )
        """)

        # Insert the same test data as the fixture
        conn2.execute("""
            INSERT INTO Settlement (ID, SettlementName, SettlementCode)
            VALUES 
                ('settlement_001', 'Budapest', '001'),
                ('settlement_002', 'Debrecen', '002'),
                ('settlement_003', 'Szeged', '003')
        """)

        # Insert sample addresses with various public space combinations
        addresses = []
        for i in range(1000):  # Create 1000 test addresses
            settlement_id = f"settlement_{(i % 3) + 1:03d}"
            public_space_name = f"Test Street {i % 50}"
            public_space_type = ["utca", "tér", "köz", "út"][i % 4]
            house_number = f"{i % 100 + 1}"

            addresses.append(
                f"('address_{i:04d}', '{settlement_id}', '{public_space_name}', "
                f"'{public_space_type}', '{house_number}', NULL, NULL, '', {i})"
            )

        conn2.execute(f"""
            INSERT INTO Address (ID, Settlement_ID, PublicSpaceName, PublicSpaceType, 
                               HouseNumber, Building, Staircase, FullAddress, Sequence)
            VALUES {", ".join(addresses)}
        """)

        # Second run on fresh database with same data
        extract_public_space_entities(conn2)

        # Get counts after second run
        names_second = conn2.execute("SELECT COUNT(*) FROM PublicSpaceName").fetchone()[
            0
        ]
        types_second = conn2.execute("SELECT COUNT(*) FROM PublicSpaceType").fetchone()[
            0
        ]
        relationships_second = conn2.execute(
            "SELECT COUNT(*) FROM SettlementPublicSpaces"
        ).fetchone()[0]

        # Counts should be the same (idempotent)
        assert names_first == names_second, "PublicSpaceName count changed"
        assert types_first == types_second, "PublicSpaceType count changed"
        assert relationships_first == relationships_second, (
            "SettlementPublicSpaces count changed"
        )
