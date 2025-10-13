"""
Integration tests for data integrity preservation during address deduplication.

These tests verify that deduplication maintains referential integrity with other
data entities and preserves all relationships.
"""

import pytest
import polars as pl
from src.etl.deduplicate import AddressDeduplicator


class TestDeduplicationIntegrity:
    """Test data integrity preservation during deduplication."""

    def test_preserve_foreign_key_relationships(self):
        """Test that foreign key relationships remain valid after deduplication."""
        deduplicator = AddressDeduplicator()

        # Create test data with relationships to other entities
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
                    "Other Street",
                    "Main Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "2", "1", "1"],
                "building": ["A", "A", None, None, "B"],
                "staircase": ["1", "1", None, None, "2"],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4", "ps5"],
                "accessibility_flag": [True, False, True, False, True],
                "pir_code": ["pir1", "pir2", "pir3", "pir4", "pir5"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify all foreign key relationships are preserved
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        # Rule 1: All original addresses are mapped
        assert len(address_mapping) == len(test_data)
        assert set(address_mapping["original_address_id"].to_list()) == set(
            test_data["address_id"].to_list()
        )

        # Rule 2: All polling station assignments are preserved
        input_stations = test_data["polling_station_id"].unique()
        output_stations = polling_stations["polling_station_id"].unique()
        assert len(input_stations) == len(output_stations)
        assert set(input_stations) == set(output_stations)

        # Rule 3: All PIR codes are preserved
        input_pirs = test_data["pir_code"].unique()
        output_pirs = pir_codes["pir_code"].unique()
        assert len(input_pirs) == len(output_pirs)
        assert set(input_pirs) == set(output_pirs)

        # Rule 4: No orphaned relationships
        canonical_ids = canonical_addresses["canonical_address_id"].to_list()

        # All canonical IDs in relationships must exist in canonical addresses
        for relationship_df in [address_mapping, polling_stations, pir_codes]:
            relationship_canonical_ids = (
                relationship_df["canonical_address_id"].unique().to_list()
            )
            for canonical_id in relationship_canonical_ids:
                assert canonical_id in canonical_ids

    def test_preserve_complex_relationships(self):
        """Test preservation of complex many-to-many relationships."""
        deduplicator = AddressDeduplicator()

        # Create test data with complex relationships
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4", "addr5", "addr6"],
                "county_code": ["01", "01", "01", "01", "02", "02"],
                "settlement_name": [
                    "Budapest",
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
                    "Other Street",
                    "Main Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "1", "2", "1", "1"],
                "building": ["A", "A", "B", None, None, "C"],
                "staircase": ["1", "1", "2", None, None, "3"],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4", "ps5", "ps6"],
                "accessibility_flag": [True, False, True, True, False, True],
                "pir_code": ["pir1", "pir2", "pir3", "pir4", "pir5", "pir6"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify complex relationships are preserved
        canonical_addresses = result["canonical_addresses"]
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        # Verify multiple polling stations for same canonical address are preserved
        canonical_polling_counts = (
            polling_stations.group_by("canonical_address_id")
            .agg(pl.len().alias("station_count"))
            .filter(pl.col("station_count") > 1)
        )

        # Should have at least one canonical address with multiple polling stations
        assert len(canonical_polling_counts) >= 1

        # Verify multiple PIR codes for same canonical address are preserved
        canonical_pir_counts = (
            pir_codes.group_by("canonical_address_id")
            .agg(pl.len().alias("pir_count"))
            .filter(pl.col("pir_count") > 1)
        )

        # Should have at least one canonical address with multiple PIR codes
        assert len(canonical_pir_counts) >= 1

    def test_consolidate_polling_station_assignments(self):
        """Test that polling station assignments are properly consolidated."""
        deduplicator = AddressDeduplicator()

        # Create test data where multiple addresses with same canonical ID
        # have different polling station assignments
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4"],
                "county_code": ["01", "01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest", "Budapest"],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "1", "1"],
                "building": ["A", "A", "B", "B"],
                "staircase": ["1", "1", "2", "2"],
                "polling_station_id": ["ps1", "ps2", "ps1", "ps3"],
                "accessibility_flag": [True, False, True, True],
                "pir_code": ["pir1", "pir2", "pir1", "pir3"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify polling station consolidation
        polling_stations = result["address_polling_stations"]

        # All polling stations should be preserved
        unique_stations = polling_stations["polling_station_id"].unique()
        assert len(unique_stations) == 3
        assert "ps1" in unique_stations
        assert "ps2" in unique_stations
        assert "ps3" in unique_stations

        # Verify no duplicate polling station assignments for same canonical address
        canonical_station_duplicates = (
            polling_stations.group_by(["canonical_address_id", "polling_station_id"])
            .agg(pl.len().alias("count"))
            .filter(pl.col("count") > 1)
        )
        assert len(canonical_station_duplicates) == 0

    def test_preserve_pir_code_relationships(self):
        """Test that PIR code relationships are properly preserved."""
        deduplicator = AddressDeduplicator()

        # Create test data with complex PIR code relationships
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4", "addr5"],
                "county_code": ["01", "01", "01", "01", "02"],
                "settlement_name": [
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Debrecen",
                ],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Other Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "1", "2", "1"],
                "building": ["A", "A", "B", None, None],
                "staircase": ["1", "1", "2", None, None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4", "ps5"],
                "accessibility_flag": [True, False, True, True, False],
                "pir_code": ["pir1", "pir2", "pir3", "pir4", "pir5"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify PIR code preservation
        pir_codes = result["address_pir_codes"]

        # All PIR codes should be preserved
        unique_pirs = pir_codes["pir_code"].unique()
        assert len(unique_pirs) == 5
        assert "pir1" in unique_pirs
        assert "pir2" in unique_pirs
        assert "pir3" in unique_pirs
        assert "pir4" in unique_pirs
        assert "pir5" in unique_pirs

        # Verify no duplicate PIR code assignments for same canonical address
        canonical_pir_duplicates = (
            pir_codes.group_by(["canonical_address_id", "pir_code"])
            .agg(pl.len().alias("count"))
            .filter(pl.col("count") > 1)
        )
        assert len(canonical_pir_duplicates) == 0

    def test_integration_with_transformation_pipeline(self):
        """Test that deduplication integrates properly with transformation pipeline."""
        deduplicator = AddressDeduplicator()

        # Create realistic test data that would come from transformation pipeline
        test_data = pl.DataFrame(
            {
                "address_id": [f"addr_{i}" for i in range(1, 11)],
                "county_code": ["01"] * 5 + ["02"] * 5,
                "settlement_name": ["Budapest"] * 5 + ["Debrecen"] * 5,
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Other Street",
                    "Other Street",
                    "Main Street",
                    "Main Street",
                    "Park Street",
                    "Park Street",
                    "Park Street",
                ],
                "house_number": ["1", "1", "2", "1", "1", "1", "1", "1", "1", "2"],
                "building": ["A", "A", None, "B", "B", None, None, "C", "C", None],
                "staircase": ["1", "1", None, "2", "2", None, None, "3", "3", None],
                "polling_station_id": [f"ps_{i}" for i in range(1, 11)],
                "accessibility_flag": [
                    True,
                    False,
                    True,
                    True,
                    False,
                    False,
                    True,
                    True,
                    False,
                    True,
                ],
                "pir_code": [f"pir_{i}" for i in range(1, 11)],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)

        # Verify integration requirements
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        # All outputs should be valid DataFrames
        assert isinstance(canonical_addresses, pl.DataFrame)
        assert isinstance(address_mapping, pl.DataFrame)
        assert isinstance(polling_stations, pl.DataFrame)
        assert isinstance(pir_codes, pl.DataFrame)

        # All outputs should have expected columns
        expected_canonical_cols = [
            "canonical_address_id",
            "county_code",
            "settlement_name",
            "street_name",
            "house_number",
            "accessibility_flag",
        ]
        assert all(
            col in canonical_addresses.columns for col in expected_canonical_cols
        )

        # Data should be properly deduplicated
        assert len(canonical_addresses) < len(test_data)

        # All relationships should be preserved
        assert len(address_mapping) == len(test_data)
        assert len(polling_stations) >= len(test_data["polling_station_id"].unique())
        assert len(pir_codes) >= len(test_data["pir_code"].unique())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
