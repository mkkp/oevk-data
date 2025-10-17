"""
Integration tests for test subset generation utility.

Tests verify that create_test_subset.py:
- Includes correct number of districts/settlements
- Maintains referential integrity in subset
- Completes processing in under 30 seconds
- Produces deterministic output with same seed
"""

import pytest
import duckdb
import time
from pathlib import Path
from src.utils.create_test_subset import create_test_subset


class TestSubsetGeneration:
    """Test subset generation functionality."""

    @pytest.fixture
    def sample_database(self, tmp_path):
        """Create a minimal sample database for testing."""
        db_path = tmp_path / "sample.db"
        conn = duckdb.connect(str(db_path))

        # Load schema
        schema_sql_path = Path(__file__).parent.parent.parent / "src" / "database" / "schema.sql"
        with open(schema_sql_path, 'r') as f:
            schema_sql = f.read()
        conn.execute(schema_sql)

        # Insert sample data
        # Counties: Budapest + 3 others
        conn.execute("""
            INSERT INTO County (ID, CountyCode, CountyName) VALUES
            ('county-bp', '01', 'Budapest'),
            ('county-ba', '02', 'Baranya'),
            ('county-be', '03', 'Bács-Kiskun'),
            ('county-he', '04', 'Heves')
        """)

        # Settlements: 5 Budapest districts + 15 from other counties (5 each)
        settlements = []
        # Budapest districts
        for i in range(1, 6):
            settlements.append(f"('bp-dist-{i:02d}', 'BP{i:02d}', 'Budapest {i}. kerület', 'county-bp')")

        # Baranya settlements
        for i in range(1, 6):
            settlements.append(f"('ba-settle-{i:02d}', 'BA{i:02d}', 'Baranya település {i}', 'county-ba')")

        # Bács-Kiskun settlements
        for i in range(1, 6):
            settlements.append(f"('be-settle-{i:02d}', 'BE{i:02d}', 'Bács település {i}', 'county-be')")

        # Heves settlements
        for i in range(1, 6):
            settlements.append(f"('he-settle-{i:02d}', 'HE{i:02d}', 'Heves település {i}', 'county-he')")

        conn.execute(f"""
            INSERT INTO Settlement (ID, SettlementCode, SettlementName, County_ID) VALUES
            {', '.join(settlements)}
        """)

        # National districts
        conn.execute("""
            INSERT INTO NationalIndividualElectoralDistrict (ID, OEVK, Name, County_ID) VALUES
            ('oevk-bp', '01', 'Budapest 01', 'county-bp'),
            ('oevk-ba', '02', 'Baranya 02', 'county-ba'),
            ('oevk-be', '03', 'Bács-Kiskun 03', 'county-be'),
            ('oevk-he', '04', 'Heves 04', 'county-he')
        """)

        # Settlement districts
        tevk_data = []
        for i in range(1, 6):
            tevk_data.append(
                f"('tevk-bp-{i:02d}', 'TEVK{i:02d}', 'Budapest {i} TEVK', 'county-bp', 'bp-dist-{i:02d}', 'oevk-bp')"
            )
        for i in range(1, 6):
            tevk_data.append(
                f"('tevk-ba-{i:02d}', 'TEVK{i:02d}', 'Baranya {i} TEVK', 'county-ba', 'ba-settle-{i:02d}', 'oevk-ba')"
            )

        conn.execute(f"""
            INSERT INTO SettlementIndividualElectoralDistrict
            (ID, TEVK, Name, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID) VALUES
            {', '.join(tevk_data)}
        """)

        # Polling stations
        polling_data = []
        for i in range(1, 6):
            polling_data.append(
                f"('polling-bp-{i:02d}', 'Budapest {i} szavazókör', 'tevk-bp-{i:02d}', 'county-bp', 'bp-dist-{i:02d}', 'oevk-bp')"
            )
        for i in range(1, 4):
            polling_data.append(
                f"('polling-ba-{i:02d}', 'Baranya {i} szavazókör', 'tevk-ba-{i:02d}', 'county-ba', 'ba-settle-{i:02d}', 'oevk-ba')"
            )

        conn.execute(f"""
            INSERT INTO PollingStation (ID, PollingStationAddress, SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID) VALUES
            {', '.join(polling_data)}
        """)

        # Postal codes
        conn.execute("""
            INSERT INTO PostalCode (ID, PostalCode) VALUES
            ('pc-1011', '1011'),
            ('pc-1012', '1012'),
            ('pc-7600', '7600'),
            ('pc-6000', '6000')
        """)

        # Postal code-settlement relationships
        conn.execute("""
            INSERT INTO PostalCode_Settlement (ID, PostalCode_ID, Settlement_ID) VALUES
            ('pcs-1', 'pc-1011', 'bp-dist-01'),
            ('pcs-2', 'pc-1012', 'bp-dist-02'),
            ('pcs-3', 'pc-7600', 'ba-settle-01'),
            ('pcs-4', 'pc-6000', 'be-settle-01')
        """)

        # Addresses: Create addresses for each settlement
        address_data = []
        address_id = 1

        # Budapest addresses (10 per district)
        for dist in range(1, 6):
            for addr in range(1, 11):
                seq = address_id
                address_data.append(
                    f"('addr-bp-{dist:02d}-{addr:03d}', {seq}, {seq}, 'Fő utca {addr}', 'Fő', 'utca', '{addr}', '', '', "
                    f"'pc-1011', 'polling-bp-{dist:02d}', 'tevk-bp-{dist:02d}', 'county-bp', 'bp-dist-{dist:02d}', 'oevk-bp')"
                )
                address_id += 1

        # Baranya addresses (5 per settlement)
        for settle in range(1, 6):
            for addr in range(1, 6):
                seq = address_id
                address_data.append(
                    f"('addr-ba-{settle:02d}-{addr:03d}', {seq}, {seq}, 'Kossuth utca {addr}', 'Kossuth', 'utca', '{addr}', '', '', "
                    f"'pc-7600', 'polling-ba-01', 'tevk-ba-{settle:02d}', 'county-ba', 'ba-settle-{settle:02d}', 'oevk-ba')"
                )
                address_id += 1

        conn.execute(f"""
            INSERT INTO Address
            (ID, Sequence, OriginalOrder, FullAddress, PublicSpaceName, PublicSpaceType, HouseNumber, Building, Staircase,
             PostalCode_ID, PollingStation_ID, SettlementIndividualElectoralDistrict_ID, County_ID, Settlement_ID, NationalIndividualElectoralDistrict_ID) VALUES
            {', '.join(address_data)}
        """)

        conn.close()
        return str(db_path)

    def test_subset_includes_correct_number_of_settlements(self, sample_database, tmp_path):
        """Test that subset includes the specified number of Budapest districts and other settlements."""
        output_db = tmp_path / "subset.db"

        # Create subset with 2 Budapest districts and 2 settlements from 2 counties
        create_test_subset(
            input_db_path=sample_database,
            output_db_path=str(output_db),
            budapest_districts=2,
            settlements_per_county=2,
            counties_count=2,
            seed=12345
        )

        # Verify the subset
        conn = duckdb.connect(str(output_db), read_only=True)

        # Check Budapest settlements
        budapest_count = conn.execute("""
            SELECT COUNT(*) FROM Settlement s
            JOIN County c ON s.County_ID = c.ID
            WHERE c.CountyName = 'Budapest'
        """).fetchone()[0]

        assert budapest_count == 2, f"Expected 2 Budapest districts, got {budapest_count}"

        # Check total settlements (2 Budapest + 2*2 from other counties = 6)
        total_settlements = conn.execute("SELECT COUNT(*) FROM Settlement").fetchone()[0]
        assert total_settlements == 6, f"Expected 6 total settlements, got {total_settlements}"

        # Check counties (Budapest + 2 others = 3)
        total_counties = conn.execute("SELECT COUNT(*) FROM County").fetchone()[0]
        assert total_counties == 3, f"Expected 3 counties, got {total_counties}"

        conn.close()

    def test_referential_integrity_maintained(self, sample_database, tmp_path):
        """Test that all foreign key relationships are maintained in the subset."""
        output_db = tmp_path / "subset.db"

        create_test_subset(
            input_db_path=sample_database,
            output_db_path=str(output_db),
            budapest_districts=2,
            settlements_per_county=2,
            counties_count=2
        )

        conn = duckdb.connect(str(output_db), read_only=True)

        # Test 1: All settlements have valid county references
        orphan_settlements = conn.execute("""
            SELECT COUNT(*) FROM Settlement s
            WHERE NOT EXISTS (SELECT 1 FROM County c WHERE c.ID = s.County_ID)
        """).fetchone()[0]
        assert orphan_settlements == 0, "Found settlements without valid county reference"

        # Test 2: All addresses have valid settlement references
        orphan_addresses = conn.execute("""
            SELECT COUNT(*) FROM Address a
            WHERE NOT EXISTS (SELECT 1 FROM Settlement s WHERE s.ID = a.Settlement_ID)
        """).fetchone()[0]
        assert orphan_addresses == 0, "Found addresses without valid settlement reference"

        # Test 3: All addresses have valid polling station references
        orphan_polling = conn.execute("""
            SELECT COUNT(*) FROM Address a
            WHERE NOT EXISTS (SELECT 1 FROM PollingStation p WHERE p.ID = a.PollingStation_ID)
        """).fetchone()[0]
        assert orphan_polling == 0, "Found addresses without valid polling station reference"

        # Test 4: All addresses have valid postal code references
        orphan_postal = conn.execute("""
            SELECT COUNT(*) FROM Address a
            WHERE NOT EXISTS (SELECT 1 FROM PostalCode pc WHERE pc.ID = a.PostalCode_ID)
        """).fetchone()[0]
        assert orphan_postal == 0, "Found addresses without valid postal code reference"

        # Test 5: All settlement districts have valid references
        orphan_tevk = conn.execute("""
            SELECT COUNT(*) FROM SettlementIndividualElectoralDistrict t
            WHERE NOT EXISTS (SELECT 1 FROM Settlement s WHERE s.ID = t.Settlement_ID)
               OR NOT EXISTS (SELECT 1 FROM County c WHERE c.ID = t.County_ID)
               OR NOT EXISTS (SELECT 1 FROM NationalIndividualElectoralDistrict n WHERE n.ID = t.NationalIndividualElectoralDistrict_ID)
        """).fetchone()[0]
        assert orphan_tevk == 0, "Found settlement districts with invalid references"

        conn.close()

    def test_subset_processing_performance(self, sample_database, tmp_path):
        """Test that subset processing completes in under 30 seconds."""
        output_db = tmp_path / "subset.db"

        start_time = time.time()

        create_test_subset(
            input_db_path=sample_database,
            output_db_path=str(output_db),
            budapest_districts=3,
            settlements_per_county=3,
            counties_count=3
        )

        elapsed_time = time.time() - start_time

        assert elapsed_time < 30, f"Subset generation took {elapsed_time:.2f}s, expected < 30s"

        # Also verify the subset was actually created
        assert output_db.exists(), "Output database was not created"
        assert output_db.stat().st_size > 0, "Output database is empty"

    def test_subset_is_deterministic(self, sample_database, tmp_path):
        """Test that subset generation is deterministic with the same seed."""
        output_db1 = tmp_path / "subset1.db"
        output_db2 = tmp_path / "subset2.db"

        seed = 42

        # Generate first subset
        create_test_subset(
            input_db_path=sample_database,
            output_db_path=str(output_db1),
            budapest_districts=2,
            settlements_per_county=2,
            counties_count=2,
            seed=seed
        )

        # Generate second subset with same seed
        create_test_subset(
            input_db_path=sample_database,
            output_db_path=str(output_db2),
            budapest_districts=2,
            settlements_per_county=2,
            counties_count=2,
            seed=seed
        )

        # Compare the subsets
        conn1 = duckdb.connect(str(output_db1), read_only=True)
        conn2 = duckdb.connect(str(output_db2), read_only=True)

        # Compare settlement IDs
        settlements1 = set([row[0] for row in conn1.execute("SELECT ID FROM Settlement ORDER BY ID").fetchall()])
        settlements2 = set([row[0] for row in conn2.execute("SELECT ID FROM Settlement ORDER BY ID").fetchall()])

        assert settlements1 == settlements2, "Subsets with same seed should have identical settlements"

        # Compare address counts
        address_count1 = conn1.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
        address_count2 = conn2.execute("SELECT COUNT(*) FROM Address").fetchone()[0]

        assert address_count1 == address_count2, "Subsets with same seed should have same address count"

        conn1.close()
        conn2.close()

    def test_subset_includes_all_addresses_from_selected_settlements(self, sample_database, tmp_path):
        """Test that ALL addresses from selected settlements are included (not a sample)."""
        output_db = tmp_path / "subset.db"

        # First, count addresses in source database for specific settlement
        source_conn = duckdb.connect(sample_database, read_only=True)
        source_settlement_id = source_conn.execute("""
            SELECT ID FROM Settlement
            WHERE SettlementName = 'Budapest 1. kerület'
        """).fetchone()[0]

        source_address_count = source_conn.execute(f"""
            SELECT COUNT(*) FROM Address
            WHERE Settlement_ID = '{source_settlement_id}'
        """).fetchone()[0]
        source_conn.close()

        # Create subset that includes this settlement
        create_test_subset(
            input_db_path=sample_database,
            output_db_path=str(output_db),
            budapest_districts=3,  # Should include district 1
            settlements_per_county=2,
            counties_count=2
        )

        # Count addresses in subset for the same settlement
        subset_conn = duckdb.connect(str(output_db), read_only=True)

        # Check if settlement exists in subset
        settlement_exists = subset_conn.execute(f"""
            SELECT COUNT(*) FROM Settlement WHERE ID = '{source_settlement_id}'
        """).fetchone()[0] > 0

        if settlement_exists:
            subset_address_count = subset_conn.execute(f"""
                SELECT COUNT(*) FROM Address
                WHERE Settlement_ID = '{source_settlement_id}'
            """).fetchone()[0]

            assert subset_address_count == source_address_count, \
                f"Subset should include ALL addresses from selected settlement " \
                f"(expected {source_address_count}, got {subset_address_count})"

        subset_conn.close()


class TestSubsetUtilityExists:
    """Test that the subset generation utility exists and is properly structured."""

    def test_utility_script_exists(self):
        """Test that create_test_subset.py exists."""
        script_path = Path(__file__).parent.parent.parent / "src" / "utils" / "create_test_subset.py"
        assert script_path.exists(), "create_test_subset.py should exist"
        assert script_path.stat().st_size > 0, "create_test_subset.py should not be empty"

    def test_utility_has_main_function(self):
        """Test that the utility has a create_test_subset function."""
        from src.utils.create_test_subset import create_test_subset
        assert callable(create_test_subset), "create_test_subset should be a callable function"

    def test_utility_can_be_imported(self):
        """Test that the utility can be imported without errors."""
        try:
            from src.utils import create_test_subset
            assert hasattr(create_test_subset, 'create_test_subset')
        except ImportError as e:
            pytest.fail(f"Could not import create_test_subset: {e}")
