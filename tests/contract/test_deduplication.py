"""
Contract tests for the address deduplication module.

These tests verify that the deduplication module implements the contract defined in
`specs/004-cleanup-duplicated-addresses/contracts/deduplication-contract.json`.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import inspect

# Import the module under test
from src.etl.deduplicate import AddressDeduplicator


class TestDeduplicateAddresses:
    """Test the deduplicate_addresses function."""

    def test_deduplicate_addresses_exists(self):
        """Test that deduplicate_addresses method exists and has correct signature."""
        deduplicator = AddressDeduplicator()
        assert hasattr(deduplicator, "deduplicate_addresses")
        assert callable(deduplicator.deduplicate_addresses)
        sig = inspect.signature(deduplicator.deduplicate_addresses)
        assert "addresses_df" in sig.parameters
        assert sig.return_annotation is not None

    def test_deduplicate_addresses_returns_expected_outputs(self):
        """Test that deduplicate_addresses returns all expected outputs from contract."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data
        import polars as pl

        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4"],
                "county_code": ["01", "01", "01", "02"],
                "settlement_name": ["Budapest", "Budapest", "Budapest", "Debrecen"],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Other Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "2", "1"],
                "building": ["A", "A", None, None],
                "staircase": ["1", "1", None, None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4"],
                "accessibility_flag": [True, False, True, False],
                "pir_code": ["pir1", "pir2", "pir3", "pir4"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify all expected outputs exist
        assert "canonical_addresses" in result
        assert "address_polling_stations" in result
        assert "address_pir_codes" in result
        assert "address_mapping" in result

        # Verify output schemas match contract
        canonical_schema = result["canonical_addresses"].schema
        assert "canonical_address_id" in canonical_schema
        assert "county_code" in canonical_schema
        assert "settlement_name" in canonical_schema
        assert "street_name" in canonical_schema
        assert "house_number" in canonical_schema
        assert "accessibility_flag" in canonical_schema

        mapping_schema = result["address_mapping"].schema
        assert "original_address_id" in mapping_schema
        assert "canonical_address_id" in mapping_schema

        # Once implemented, test output structure
        # import polars as pl
        #
        # # Create test data with duplicates
        # test_data = pl.DataFrame({
        #     'address_id': ['addr1', 'addr2', 'addr3', 'addr4'],
        #     'county_code': ['01', '01', '01', '02'],
        #     'settlement_name': ['Budapest', 'Budapest', 'Budapest', 'Debrecen'],
        #     'street_name': ['Main Street', 'Main Street', 'Other Street', 'Main Street'],
        #     'house_number': ['1', '1', '2', '1'],
        #     'building': ['A', 'A', None, None],
        #     'staircase': ['1', '1', None, None],
        #     'polling_station_id': ['ps1', 'ps2', 'ps3', 'ps4'],
        #     'accessibility_flag': [True, False, True, False],
        #     'pir_code': ['pir1', 'pir2', 'pir3', 'pir4']
        # })
        #
        # result = deduplicate_addresses(test_data)
        #
        # # Verify all expected outputs exist
        # assert 'canonical_addresses' in result
        # assert 'address_polling_stations' in result
        # assert 'address_pir_codes' in result
        # assert 'address_mapping' in result
        #
        # # Verify output schemas match contract
        # canonical_schema = result['canonical_addresses'].schema
        # assert 'canonical_address_id' in canonical_schema
        # assert 'county_code' in canonical_schema
        # assert 'settlement_name' in canonical_schema
        # assert 'street_name' in canonical_schema
        # assert 'house_number' in canonical_schema
        # assert 'accessibility_flag' in canonical_schema
        #
        # mapping_schema = result['address_mapping'].schema
        # assert 'original_address_id' in mapping_schema
        # assert 'canonical_address_id' in mapping_schema

    def test_deduplicate_addresses_identifies_duplicates(self):
        """Test that deduplicate_addresses correctly identifies duplicate addresses."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with clear duplicates
        import polars as pl

        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street", "Other Street"],
                "house_number": ["1", "1", "2"],
                "building": ["A", "A", None],
                "staircase": ["1", "1", None],
                "polling_station_id": ["ps1", "ps2", "ps3"],
                "accessibility_flag": [True, False, True],
                "pir_code": ["pir1", "pir2", "pir3"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Verify duplicates are identified and merged (addr1 and addr2 should be same)
        assert len(canonical_addresses) == 2  # addr1+addr2 merged, addr3 separate

        # Verify addr1 and addr2 map to same canonical ID
        addr1_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr1"
        )["canonical_address_id"][0]
        addr2_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr2"
        )["canonical_address_id"][0]
        assert addr1_canonical == addr2_canonical

        # Verify addr3 has different canonical ID
        addr3_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr3"
        )["canonical_address_id"][0]
        assert addr3_canonical != addr1_canonical

        # Once implemented, test duplicate detection
        # import polars as pl
        #
        # # Create test data with clear duplicates
        # test_data = pl.DataFrame({
        #     'address_id': ['addr1', 'addr2', 'addr3'],
        #     'county_code': ['01', '01', '01'],
        #     'settlement_name': ['Budapest', 'Budapest', 'Budapest'],
        #     'street_name': ['Main Street', 'Main Street', 'Other Street'],
        #     'house_number': ['1', '1', '2'],
        #     'building': ['A', 'A', None],
        #     'staircase': ['1', '1', None],
        #     'polling_station_id': ['ps1', 'ps2', 'ps3'],
        #     'accessibility_flag': [True, False, True],
        #     'pir_code': ['pir1', 'pir2', 'pir3']
        # })
        #
        # result = deduplicate_addresses(test_data)
        #
        # # Verify duplicates are merged (addr1 and addr2 should map to same canonical)
        # mapping = result['address_mapping']
        # canonical_ids = mapping['canonical_address_id'].unique()
        #
        # # Should have 2 canonical addresses (addr1+addr2 merged, addr3 separate)
        # assert len(canonical_ids) == 2
        #
        # # Verify addr1 and addr2 map to same canonical ID
        # addr1_canonical = mapping.filter(pl.col('original_address_id') == 'addr1')['canonical_address_id'][0]
        # addr2_canonical = mapping.filter(pl.col('original_address_id') == 'addr2')['canonical_address_id'][0]
        # assert addr1_canonical == addr2_canonical

    def test_deduplicate_addresses_preserves_polling_stations(self):
        """Test that deduplicate_addresses preserves all polling station assignments."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with different polling stations for same address
        import polars as pl

        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street"],
                "house_number": ["1", "1"],
                "building": ["A", "A"],
                "staircase": ["1", "1"],
                "polling_station_id": ["ps1", "ps2"],  # Different polling stations
                "accessibility_flag": [True, True],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify both polling stations are preserved
        polling_stations = result["address_polling_stations"]
        unique_stations = polling_stations["polling_station_id"].unique()

        assert len(unique_stations) == 2
        assert "ps1" in unique_stations
        assert "ps2" in unique_stations

        # Once implemented, test polling station preservation
        # import polars as pl
        #
        # # Create test data with different polling stations for same address
        # test_data = pl.DataFrame({
        #     'address_id': ['addr1', 'addr2'],
        #     'county_code': ['01', '01'],
        #     'settlement_name': ['Budapest', 'Budapest'],
        #     'street_name': ['Main Street', 'Main Street'],
        #     'house_number': ['1', '1'],
        #     'building': ['A', 'A'],
        #     'staircase': ['1', '1'],
        #     'polling_station_id': ['ps1', 'ps2'],  # Different polling stations
        #     'accessibility_flag': [True, True],
        #     'pir_code': ['pir1', 'pir2']
        # })
        #
        # result = deduplicate_addresses(test_data)
        #
        # # Verify both polling stations are preserved
        # polling_stations = result['address_polling_stations']
        # unique_stations = polling_stations['polling_station_id'].unique()
        #
        # assert len(unique_stations) == 2
        # assert 'ps1' in unique_stations
        # assert 'ps2' in unique_stations

    def test_deduplicate_addresses_preserves_pir_codes(self):
        """Test that deduplicate_addresses preserves all PIR codes."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with different PIR codes for same address
        import polars as pl

        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street"],
                "house_number": ["1", "1"],
                "building": ["A", "A"],
                "staircase": ["1", "1"],
                "polling_station_id": ["ps1", "ps1"],
                "accessibility_flag": [True, True],
                "pir_code": ["pir1", "pir2"],  # Different PIR codes
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify both PIR codes are preserved
        pir_codes = result["address_pir_codes"]
        unique_pirs = pir_codes["pir_code"].unique()

        assert len(unique_pirs) == 2
        assert "pir1" in unique_pirs
        assert "pir2" in unique_pirs

        # Once implemented, test PIR code preservation
        # import polars as pl
        #
        # # Create test data with different PIR codes for same address
        # test_data = pl.DataFrame({
        #     'address_id': ['addr1', 'addr2'],
        #     'county_code': ['01', '01'],
        #     'settlement_name': ['Budapest', 'Budapest'],
        #     'street_name': ['Main Street', 'Main Street'],
        #     'house_number': ['1', '1'],
        #     'building': ['A', 'A'],
        #     'staircase': ['1', '1'],
        #     'polling_station_id': ['ps1', 'ps1'],
        #     'accessibility_flag': [True, True],
        #     'pir_code': ['pir1', 'pir2']  # Different PIR codes
        # })
        #
        # result = deduplicate_addresses(test_data)
        #
        # # Verify both PIR codes are preserved
        # pir_codes = result['address_pir_codes']
        # unique_pirs = pir_codes['pir_code'].unique()
        #
        # assert len(unique_pirs) == 2
        # assert 'pir1' in unique_pirs
        # assert 'pir2' in unique_pirs

    def test_deduplicate_addresses_merges_conflicting_accessibility_flags(self):
        """Test that deduplicate_addresses handles conflicting accessibility flags correctly."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with conflicting accessibility flags for same address
        import polars as pl

        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street"],
                "house_number": ["1", "1"],
                "building": ["A", "A"],
                "staircase": ["1", "1"],
                "polling_station_id": ["ps1", "ps1"],
                "accessibility_flag": [True, False],  # Conflicting flags
                "pir_code": ["pir1", "pir1"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify accessibility flag is resolved (should be True for accessibility)
        canonical_addresses = result["canonical_addresses"]
        assert len(canonical_addresses) == 1
        assert (
            canonical_addresses["accessibility_flag"][0] == True
        )  # Should prioritize accessibility

    def test_deduplicate_addresses_merges_complex_duplicates(self):
        """Test that deduplicate_addresses handles complex duplicate scenarios."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with multiple duplicates and different relationships
        import polars as pl

        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4"],
                "county_code": ["01", "01", "01", "02"],
                "settlement_name": ["Budapest", "Budapest", "Budapest", "Debrecen"],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "1", "1"],
                "building": ["A", "A", "B", None],
                "staircase": ["1", "1", "1", None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4"],
                "accessibility_flag": [True, False, True, False],
                "pir_code": ["pir1", "pir2", "pir3", "pir4"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify duplicates are merged correctly
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        # Should have 3 canonical addresses:
        # - addr1+addr2 (building=A, staircase=1) - 2 polling stations, 2 PIR codes
        # - addr3 (building=B, staircase=1) - 1 polling station, 1 PIR code
        # - addr4 (different county) - 1 polling station, 1 PIR code
        assert len(canonical_addresses) == 3

        # Verify all polling stations are preserved
        unique_stations = polling_stations["polling_station_id"].unique()
        assert len(unique_stations) == 4
        assert "ps1" in unique_stations
        assert "ps2" in unique_stations
        assert "ps3" in unique_stations
        assert "ps4" in unique_stations

        # Verify all PIR codes are preserved
        unique_pirs = pir_codes["pir_code"].unique()
        assert len(unique_pirs) == 4
        assert "pir1" in unique_pirs
        assert "pir2" in unique_pirs
        assert "pir3" in unique_pirs
        assert "pir4" in unique_pirs

        # Verify address mapping preserves all original addresses
        assert len(address_mapping) == 4
        assert set(address_mapping["original_address_id"].to_list()) == {
            "addr1",
            "addr2",
            "addr3",
            "addr4",
        }

    def test_deduplicate_addresses_preserves_data_integrity(self):
        """Test that deduplicate_addresses maintains referential integrity with other entities."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with relationships to other entities
        import polars as pl

        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4"],
                "county_code": ["01", "01", "01", "02"],
                "settlement_name": ["Budapest", "Budapest", "Budapest", "Debrecen"],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Other Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "2", "1"],
                "building": ["A", "A", None, None],
                "staircase": ["1", "1", None, None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4"],
                "accessibility_flag": [True, False, True, False],
                "pir_code": ["pir1", "pir2", "pir3", "pir4"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify data integrity rules from contract
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        # Rule 1: No data loss - all original addresses must be mapped
        assert len(address_mapping) == len(test_data)
        assert set(address_mapping["original_address_id"].to_list()) == set(
            test_data["address_id"].to_list()
        )

        # Rule 2: Polling station preservation - all polling stations preserved
        input_stations = test_data["polling_station_id"].unique()
        output_stations = polling_stations["polling_station_id"].unique()
        assert len(input_stations) == len(output_stations)
        assert set(input_stations) == set(output_stations)

        # Rule 3: PIR code preservation - all PIR codes preserved
        input_pirs = test_data["pir_code"].unique()
        output_pirs = pir_codes["pir_code"].unique()
        assert len(input_pirs) == len(output_pirs)
        assert set(input_pirs) == set(output_pirs)

        # Rule 4: Deterministic IDs - same input produces same canonical IDs
        result2 = deduplicator.deduplicate_addresses(test_data)
        assert set(
            result["canonical_addresses"]["canonical_address_id"].to_list()
        ) == set(result2["canonical_addresses"]["canonical_address_id"].to_list())

        # Additional integrity checks
        # All canonical IDs in relationships must exist in canonical addresses
        canonical_ids = canonical_addresses["canonical_address_id"].to_list()
        mapping_canonical_ids = (
            address_mapping["canonical_address_id"].unique().to_list()
        )
        polling_canonical_ids = (
            polling_stations["canonical_address_id"].unique().to_list()
        )
        pir_canonical_ids = pir_codes["canonical_address_id"].unique().to_list()

        # Verify all relationship canonical IDs exist in canonical addresses
        for canonical_id in mapping_canonical_ids:
            assert canonical_id in canonical_ids
        for canonical_id in polling_canonical_ids:
            assert canonical_id in canonical_ids
        for canonical_id in pir_canonical_ids:
            assert canonical_id in canonical_ids

        # Verify no duplicate canonical IDs in canonical addresses
        assert len(canonical_addresses["canonical_address_id"].unique()) == len(
            canonical_addresses
        )


    def test_deduplicate_addresses_preserves_building_field(self):
        """Test that building field is preserved in canonical addresses."""
        deduplicator = AddressDeduplicator()
        import polars as pl

        # Create test data with building field
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Fő", "Fő"],
                "street_type": ["utca", "utca"],
                "house_number": ["1", "1"],
                "building": ["A", "A"],  # Building field that should be preserved
                "staircase": ["1", "1"],
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, False],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data, generate_report=False)
        canonical_addresses = result["canonical_addresses"]

        # Verify building field exists in canonical addresses
        assert "building" in canonical_addresses.schema
        # Verify building field value is preserved
        assert canonical_addresses["building"][0] == "A"

    def test_deduplicate_addresses_preserves_staircase_field(self):
        """Test that staircase field is preserved in canonical addresses."""
        deduplicator = AddressDeduplicator()
        import polars as pl

        # Create test data with staircase field
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Fő", "Fő"],
                "street_type": ["utca", "utca"],
                "house_number": ["1", "1"],
                "building": ["A", "A"],
                "staircase": ["2", "2"],  # Staircase field that should be preserved
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, False],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data, generate_report=False)
        canonical_addresses = result["canonical_addresses"]

        # Verify staircase field exists in canonical addresses
        assert "staircase" in canonical_addresses.schema
        # Verify staircase field value is preserved
        assert canonical_addresses["staircase"][0] == "2"

    def test_deduplicate_addresses_preserves_building_and_staircase_together(self):
        """Test that building and staircase fields are preserved together in canonical addresses."""
        deduplicator = AddressDeduplicator()
        import polars as pl

        # Create test data with both building and staircase fields
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Fő", "Fő", "Fő"],
                "street_type": ["utca", "utca", "utca"],
                "house_number": ["1", "1", "2"],
                "building": ["A", "A", "B"],  # Different buildings
                "staircase": ["1", "1", "3"],  # Different staircases
                "polling_station_id": ["ps1", "ps2", "ps3"],
                "accessibility_flag": [True, False, True],
                "pir_code": ["pir1", "pir2", "pir3"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data, generate_report=False)
        canonical_addresses = result["canonical_addresses"]

        # Verify both fields exist
        assert "building" in canonical_addresses.schema
        assert "staircase" in canonical_addresses.schema

        # Verify we have 2 canonical addresses (addr1+addr2 merged, addr3 separate)
        assert len(canonical_addresses) == 2

        # Verify building/staircase combinations are preserved
        canonical_df = canonical_addresses.sort("building")
        assert canonical_df["building"][0] == "A"
        assert canonical_df["staircase"][0] == "1"
        assert canonical_df["building"][1] == "B"
        assert canonical_df["staircase"][1] == "3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
