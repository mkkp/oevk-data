"""
Integration tests for address merging functionality.

These tests verify that the deduplication module correctly merges duplicate addresses
in realistic scenarios with larger datasets and complex merging scenarios.
"""

import pytest
import polars as pl
import tempfile
import os

from src.etl.deduplicate import AddressDeduplicator


class TestDeduplicationMerging:
    """Test address merging functionality."""

    def test_merge_duplicates_with_conflicting_accessibility(self):
        """Test merging duplicates with conflicting accessibility flags."""
        deduplicator = AddressDeduplicator()

        # Create test data with conflicting accessibility flags
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4"],
                "county_code": ["01", "01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest", "Budapest"],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Other Street",
                ],
                "house_number": ["1", "1", "1", "2"],
                "building": ["A", "A", "B", None],
                "staircase": ["1", "1", "1", None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4"],
                "accessibility_flag": [True, False, True, False],  # Conflicting flags
                "pir_code": ["pir1", "pir2", "pir3", "pir4"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Verify duplicates are merged correctly
        # addr1+addr2 should be merged (same building/staircase)
        # addr3 should be separate (different building)
        # addr4 should be separate (different street)
        assert len(canonical_addresses) == 3

        # Verify accessibility flag is resolved correctly (should prioritize True)
        main_street_canonicals = canonical_addresses.filter(
            pl.col("street_name") == "Main Street"
        )
        # Check that at least one Main Street canonical has accessibility=True
        assert main_street_canonicals["accessibility_flag"].any()

        # Verify all original addresses are mapped
        assert len(address_mapping) == 4
        assert set(address_mapping["original_address_id"].to_list()) == {
            "addr1",
            "addr2",
            "addr3",
            "addr4",
        }

    def test_merge_duplicates_with_multiple_polling_stations(self):
        """Test merging duplicates that have multiple polling station assignments."""
        deduplicator = AddressDeduplicator()

        # Create test data with same address but different polling stations
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street", "Main Street"],
                "house_number": ["1", "1", "1"],
                "building": ["A", "A", "A"],
                "staircase": ["1", "1", "1"],
                "polling_station_id": [
                    "ps1",
                    "ps2",
                    "ps3",
                ],  # Different polling stations
                "accessibility_flag": [True, True, True],
                "pir_code": ["pir1", "pir1", "pir1"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        polling_stations = result["address_polling_stations"]

        # Verify all addresses are merged into one canonical address
        assert len(canonical_addresses) == 1

        # Verify all polling stations are preserved
        unique_stations = polling_stations["polling_station_id"].unique()
        assert len(unique_stations) == 3
        assert "ps1" in unique_stations
        assert "ps2" in unique_stations
        assert "ps3" in unique_stations

    def test_merge_duplicates_with_multiple_pir_codes(self):
        """Test merging duplicates that have multiple PIR codes."""
        deduplicator = AddressDeduplicator()

        # Create test data with same address but different PIR codes
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street", "Main Street"],
                "house_number": ["1", "1", "1"],
                "building": ["A", "A", "A"],
                "staircase": ["1", "1", "1"],
                "polling_station_id": ["ps1", "ps1", "ps1"],
                "accessibility_flag": [True, True, True],
                "pir_code": ["pir1", "pir2", "pir3"],  # Different PIR codes
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        pir_codes = result["address_pir_codes"]

        # Verify all addresses are merged into one canonical address
        assert len(canonical_addresses) == 1

        # Verify all PIR codes are preserved
        unique_pirs = pir_codes["pir_code"].unique()
        assert len(unique_pirs) == 3
        assert "pir1" in unique_pirs
        assert "pir2" in unique_pirs
        assert "pir3" in unique_pirs

    def test_merge_complex_scenario_with_all_relationships(self):
        """Test complex merging scenario with all relationship types."""
        deduplicator = AddressDeduplicator()

        # Create complex test data with multiple duplicates and relationships
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4", "addr5"],
                "county_code": ["01", "01", "01", "02", "02"],
                "settlement_name": [
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Debrecen",
                    "Debrecen",
                ],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Other Street",
                ],
                "house_number": ["1", "1", "1", "1", "2"],
                "building": ["A", "B", None, None, None],
                "staircase": ["1", "2", None, None, None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4", "ps5"],
                "accessibility_flag": [True, False, True, False, True],
                "pir_code": ["pir1", "pir2", "pir3", "pir4", "pir5"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        # Verify merging logic:
        # - addr1 (building=A, staircase=1) separate
        # - addr2 (building=B, staircase=2) separate
        # - addr3 (no building/staircase) separate
        # - addr4 separate (different county)
        # - addr5 separate (different street)
        assert len(canonical_addresses) == 5

        # Verify all original addresses are mapped
        assert len(address_mapping) == 5
        assert set(address_mapping["original_address_id"].to_list()) == {
            "addr1",
            "addr2",
            "addr3",
            "addr4",
            "addr5",
        }

        # Verify all polling stations are preserved
        unique_stations = polling_stations["polling_station_id"].unique()
        assert len(unique_stations) == 5
        assert "ps1" in unique_stations
        assert "ps2" in unique_stations
        assert "ps3" in unique_stations
        assert "ps4" in unique_stations
        assert "ps5" in unique_stations

        # Verify all PIR codes are preserved
        unique_pirs = pir_codes["pir_code"].unique()
        assert len(unique_pirs) == 5
        assert "pir1" in unique_pirs
        assert "pir2" in unique_pirs
        assert "pir3" in unique_pirs
        assert "pir4" in unique_pirs
        assert "pir5" in unique_pirs

        # Verify accessibility flag resolution for merged addresses
        # Main Street in Budapest should have at least one with accessibility=True (prioritize accessibility)
        budapest_main = canonical_addresses.filter(
            (pl.col("county_code") == "01") & (pl.col("street_name") == "Main Street")
        )
        assert (
            len(budapest_main) == 3
        )  # All addresses distinct due to building/staircase differences
        assert budapest_main[
            "accessibility_flag"
        ].any()  # At least one should have accessibility=True

    def test_merge_large_dataset_performance(self):
        """Test merging performance with larger dataset."""
        deduplicator = AddressDeduplicator()

        # Create larger test dataset with known duplicates
        addresses = []
        for i in range(1000):
            # Create groups of 5 duplicates each
            group_id = i // 5
            county_code = f"{group_id % 20:02d}"
            settlement = f"Settlement_{group_id}"
            street = f"Street_{group_id}"
            house = f"{group_id + 1}"

            addresses.append(
                {
                    "address_id": f"addr_{i:04d}",
                    "county_code": county_code,
                    "settlement_name": settlement,
                    "street_name": street,
                    "house_number": house,
                    "building": "A" if i % 2 == 0 else "B",
                    "staircase": "1" if i % 3 == 0 else "2",
                    "polling_station_id": f"ps_{i % 50:02d}",
                    "accessibility_flag": i % 4 == 0,  # 25% accessible
                    "pir_code": f"pir_{i % 100:03d}",
                }
            )

        test_data = pl.DataFrame(addresses)

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Verify deduplication occurred (should have fewer canonical addresses)
        assert len(canonical_addresses) < len(test_data)

        # Verify all original addresses are mapped
        assert len(address_mapping) == len(test_data)

        # Verify no data loss in relationships
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        # All polling stations should be preserved
        original_stations = test_data["polling_station_id"].unique()
        result_stations = polling_stations["polling_station_id"].unique()
        assert len(original_stations) == len(result_stations)

        # All PIR codes should be preserved
        original_pirs = test_data["pir_code"].unique()
        result_pirs = pir_codes["pir_code"].unique()
        assert len(original_pirs) == len(result_pirs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
