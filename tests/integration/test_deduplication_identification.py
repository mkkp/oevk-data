"""
Integration tests for address duplicate identification.

These tests verify that the deduplication module correctly identifies duplicate addresses
in realistic scenarios with larger datasets.
"""

import pytest
import polars as pl
import tempfile
import os

from src.etl.deduplicate import AddressDeduplicator


class TestDeduplicationIdentification:
    """Test duplicate identification functionality."""

    def test_identify_simple_duplicates(self):
        """Test identification of simple duplicate addresses."""
        deduplicator = AddressDeduplicator()

        # Create test data with obvious duplicates
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
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Verify duplicates are identified and merged
        # addr1+addr2 merged (same street/house), addr3 separate (different street), addr4 separate (different county)
        assert len(canonical_addresses) == 3

        # Verify addr1 and addr2 map to same canonical ID
        addr1_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr1"
        )["canonical_address_id"][0]
        addr2_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr2"
        )["canonical_address_id"][0]
        assert addr1_canonical == addr2_canonical

        # Verify addr3 and addr4 have different canonical IDs
        addr3_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr3"
        )["canonical_address_id"][0]
        addr4_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr4"
        )["canonical_address_id"][0]
        assert addr3_canonical != addr4_canonical

    def test_identify_case_insensitive_duplicates(self):
        """Test identification of duplicates with different casing."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with same addresses but different casing
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "BUDAPEST"],
                "street_name": ["Main Street", "main street"],
                "house_number": ["1", "1"],
                "building": ["A", "A"],
                "staircase": ["1", "1"],
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, True],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Verify case-insensitive duplicates are identified
        assert len(canonical_addresses) == 1

        # Both addresses should map to same canonical ID
        addr1_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr1"
        )["canonical_address_id"][0]
        addr2_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr2"
        )["canonical_address_id"][0]
        assert addr1_canonical == addr2_canonical

        # Once implemented, test case-insensitive duplicate detection
        # deduplicator = AddressDeduplicator()
        #
        # # Create test data with same addresses but different casing
        # test_data = pl.DataFrame({
        #     'address_id': ['addr1', 'addr2'],
        #     'county_code': ['01', '01'],
        #     'settlement_name': ['Budapest', 'BUDAPEST'],
        #     'street_name': ['Main Street', 'main street'],
        #     'house_number': ['1', '1'],
        #     'building': ['A', 'A'],
        #     'staircase': ['1', '1'],
        #     'polling_station_id': ['ps1', 'ps2'],
        #     'accessibility_flag': [True, True],
        #     'pir_code': ['pir1', 'pir2']
        # })
        #
        # result = deduplicator.deduplicate_addresses(test_data)
        # canonical_addresses = result['canonical_addresses']
        # address_mapping = result['address_mapping']
        #
        # # Verify case-insensitive duplicates are identified
        # assert len(canonical_addresses) == 1
        #
        # # Both addresses should map to same canonical ID
        # addr1_canonical = address_mapping.filter(
        #     pl.col('original_address_id') == 'addr1'
        # )['canonical_address_id'][0]
        # addr2_canonical = address_mapping.filter(
        #     pl.col('original_address_id') == 'addr2'
        # )['canonical_address_id'][0]
        # assert addr1_canonical == addr2_canonical

    def test_identify_whitespace_duplicates(self):
        """Test identification of duplicates with different whitespace."""
        # Test the actual implementation
        deduplicator = AddressDeduplicator()

        # Create test data with same addresses but different whitespace
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Main Street", "Main  Street"],  # Extra space
                "house_number": ["1", "1"],
                "building": ["A", "A"],
                "staircase": ["1", "1"],
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, True],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Debug: print the canonical addresses to see what's happening
        print("Canonical addresses:")
        print(canonical_addresses)
        print("\nAddress mapping:")
        print(address_mapping)

        # Verify whitespace-insensitive duplicates are identified
        assert len(canonical_addresses) == 1

        # Both addresses should map to same canonical ID
        addr1_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr1"
        )["canonical_address_id"][0]
        addr2_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr2"
        )["canonical_address_id"][0]
        assert addr1_canonical == addr2_canonical

        # Once implemented, test whitespace-insensitive duplicate detection
        # deduplicator = AddressDeduplicator()
        #
        # # Create test data with same addresses but different whitespace
        # test_data = pl.DataFrame({
        #     'address_id': ['addr1', 'addr2'],
        #     'county_code': ['01', '01'],
        #     'settlement_name': ['Budapest', 'Budapest'],
        #     'street_name': ['Main Street', 'Main  Street'],  # Extra space
        #     'house_number': ['1', '1'],
        #     'building': ['A', 'A'],
        #     'staircase': ['1', '1'],
        #     'polling_station_id': ['ps1', 'ps2'],
        #     'accessibility_flag': [True, True],
        #     'pir_code': ['pir1', 'pir2']
        # })
        #
        # result = deduplicator.deduplicate_addresses(test_data)
        # canonical_addresses = result['canonical_addresses']
        # address_mapping = result['address_mapping']
        #
        # # Verify whitespace-insensitive duplicates are identified
        # assert len(canonical_addresses) == 1
        #
        # # Both addresses should map to same canonical ID
        # addr1_canonical = address_mapping.filter(
        #     pl.col('original_address_id') == 'addr1'
        # )['canonical_address_id'][0]
        # addr2_canonical = address_mapping.filter(
        #     pl.col('original_address_id') == 'addr2'
        # )['canonical_address_id'][0]
        # assert addr1_canonical == addr2_canonical

    def test_identify_partial_duplicates(self):
        """Test identification of partial duplicates (same street/house, different details)."""
        deduplicator = AddressDeduplicator()

        # Create test data with same street/house but different building/staircase
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street", "Main Street"],
                "house_number": ["1", "1", "1"],
                "building": ["A", "B", None],  # Different buildings
                "staircase": ["1", "2", None],  # Different staircases
                "polling_station_id": ["ps1", "ps2", "ps3"],
                "accessibility_flag": [True, True, True],
                "pir_code": ["pir1", "pir2", "pir3"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Verify addresses are treated as distinct due to building/staircase differences
        assert len(canonical_addresses) == 3

        # All addresses should have different canonical IDs
        canonical_ids = address_mapping["canonical_address_id"].unique()
        assert len(canonical_ids) == 3

    def test_identify_duplicates_with_null_values(self):
        """Test identification of duplicates with null values in optional fields."""
        deduplicator = AddressDeduplicator()

        # Create test data with null values in optional fields
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street", "Other Street"],
                "house_number": ["1", "1", "2"],
                "building": ["A", None, None],  # One with building, one without
                "staircase": ["1", None, None],  # One with staircase, one without
                "polling_station_id": ["ps1", "ps2", "ps3"],
                "accessibility_flag": [True, True, True],
                "pir_code": ["pir1", "pir2", "pir3"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Verify addr1 and addr2 are treated as distinct due to building/staircase differences
        assert len(canonical_addresses) == 3  # addr1, addr2, addr3 all separate

        # addr1 and addr2 should map to different canonical IDs
        addr1_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr1"
        )["canonical_address_id"][0]
        addr2_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr2"
        )["canonical_address_id"][0]
        assert addr1_canonical != addr2_canonical


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
