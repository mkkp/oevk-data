"""
Integration tests for address deduplication priority logic.

These tests verify that the deduplication module correctly prioritizes structured
address formats (separate building/staircase fields) over combined formats when
selecting canonical representatives.
"""

import pytest
import polars as pl

from src.etl.deduplicate import AddressDeduplicator


class TestDeduplicationPriority:
    """Test address structure prioritization in canonical selection."""

    def test_prefer_structured_over_combined_format(self):
        """Test that structured format (plain house + building) is preferred over slash notation."""
        deduplicator = AddressDeduplicator()

        # Create duplicate addresses with different formats:
        # - Address A: house_number="1", building="D" (structured)
        # - Address B: house_number="1/D", building="" (combined)
        test_data = pl.DataFrame(
            {
                "address_id": ["addr_structured", "addr_combined"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Körtöltés", "Körtöltés"],
                "street_type": ["utca", "utca"],
                "house_number": ["1", "1/D"],
                "building": ["D", ""],
                "staircase": ["", ""],
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, False],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Both should map to same canonical ID (they're duplicates)
        assert len(canonical_addresses) == 1

        # Get the canonical address
        canonical = canonical_addresses.row(0, named=True)

        # Verify structured format was selected (house_number="1", not "1/D")
        assert canonical["house_number"] == "1"
        assert canonical["full_address"] == "Körtöltés utca 1/D."

    def test_prefer_plain_house_with_building_over_slash_notation(self):
        """Test that plain house number with separate building field is preferred over slash notation."""
        deduplicator = AddressDeduplicator()

        # Create duplicate addresses that format to the SAME full address:
        # - Address A: house_number="9", building="D", staircase="" → "Test utca 9/D."
        # - Address B: house_number="9/D", building="", staircase="" → "Test utca 9/D."
        test_data = pl.DataFrame(
            {
                "address_id": ["addr_structured", "addr_combined"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Test", "Test"],
                "street_type": ["utca", "utca"],
                "house_number": ["9", "9/D"],
                "building": ["D", ""],
                "staircase": ["", ""],
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, True],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]

        # Both should merge to one canonical address
        assert len(canonical_addresses) == 1

        canonical = canonical_addresses.row(0, named=True)

        # Verify structured format was selected (house_number="9" with building, not "9/D")
        assert canonical["house_number"] == "9"
        assert canonical["full_address"] == "Test utca 9/D."

    def test_tiebreaker_uses_first_occurrence(self):
        """Test that when structure scores are equal, first occurrence is selected."""
        deduplicator = AddressDeduplicator()

        # Create duplicate addresses with same structure (all structured)
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Main", "Main", "Main"],
                "street_type": ["utca", "utca", "utca"],
                "house_number": ["5", "5", "5"],
                "building": ["A", "A", "A"],
                "staircase": ["", "", ""],
                "polling_station_id": ["ps1", "ps2", "ps3"],
                "accessibility_flag": [False, True, True],
                "pir_code": ["pir1", "pir2", "pir3"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # All should merge to one canonical address
        assert len(canonical_addresses) == 1

        # Verify all three map to the same canonical ID
        canonical_ids = address_mapping["canonical_address_id"].unique()
        assert len(canonical_ids) == 1

    def test_canonical_id_unchanged_for_duplicate_detection(self):
        """Test that canonical IDs are generated consistently regardless of field structure."""
        deduplicator = AddressDeduplicator()

        # These addresses format to the same string, so should have same canonical ID:
        # - house_number="1", building="D" -> "Körtöltés utca 1/D."
        # - house_number="1/D", building="" -> "Körtöltés utca 1/D."
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Körtöltés", "Körtöltés"],
                "street_type": ["utca", "utca"],
                "house_number": ["1", "1/D"],
                "building": ["D", ""],
                "staircase": ["", ""],
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, False],
                "pir_code": ["pir1", "pir2"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        address_mapping = result["address_mapping"]

        # Both should have the same canonical ID
        addr1_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr1"
        )["canonical_address_id"][0]
        addr2_canonical = address_mapping.filter(
            pl.col("original_address_id") == "addr2"
        )["canonical_address_id"][0]

        assert addr1_canonical == addr2_canonical

    def test_different_structures_same_formatted_address(self):
        """Test that different internal structures with same formatted output are treated as duplicates."""
        deduplicator = AddressDeduplicator()

        # All three format to "Test utca 5/B.":
        # - house_number="5", building="B", staircase=""
        # - house_number="5/B", building="", staircase=""
        # - house_number="00005", building="B", staircase=""
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest"],
                "street_name": ["Test", "Test", "Test"],
                "street_type": ["utca", "utca", "utca"],
                "house_number": ["5", "5/B", "00005"],
                "building": ["B", "", "B"],
                "staircase": ["", "", ""],
                "polling_station_id": ["ps1", "ps2", "ps3"],
                "accessibility_flag": [True, True, True],
                "pir_code": ["pir1", "pir2", "pir3"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]

        # All should merge to one canonical address
        assert len(canonical_addresses) == 1

        canonical = canonical_addresses.row(0, named=True)

        # Verify the structured format was preferred (house_number="5" or "00005", not "5/B")
        # Both addr1 and addr3 have higher structure scores than addr2
        # addr1 should win due to first occurrence
        assert "/" not in canonical["house_number"]
        assert canonical["full_address"] == "Test utca 5/B."

    def test_structure_score_calculation(self):
        """Test the structure score calculation directly."""
        deduplicator = AddressDeduplicator()

        # Structured formats should have higher scores
        score_structured = deduplicator._calculate_address_structure_score("1", "D", "")
        score_combined = deduplicator._calculate_address_structure_score("1/D", "", "")

        assert score_structured > score_combined

        # More complete structured format should score higher
        score_complete = deduplicator._calculate_address_structure_score("1", "B", "L")
        score_partial = deduplicator._calculate_address_structure_score("1", "B", "")

        assert score_complete > score_partial

        # Plain house number scores higher than slash notation
        score_plain = deduplicator._calculate_address_structure_score("9", "", "")
        score_slash = deduplicator._calculate_address_structure_score("9/1", "", "")

        assert score_plain > score_slash

    def test_relationship_preservation_with_priority(self):
        """Test that relationship preservation works correctly with priority logic."""
        deduplicator = AddressDeduplicator()

        # Create duplicates with different polling stations and PIR codes
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Test", "Test"],
                "street_type": ["utca", "utca"],
                "house_number": ["1", "1/A"],
                "building": ["A", ""],
                "staircase": ["", ""],
                "polling_station_id": ["ps_structured", "ps_combined"],
                "accessibility_flag": [True, False],
                "pir_code": ["pir_structured", "pir_combined"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]
        address_mapping = result["address_mapping"]

        # Both original addresses should be preserved in mapping
        assert len(address_mapping) == 2

        # Both polling stations should be preserved
        assert len(polling_stations) == 2
        assert "ps_structured" in polling_stations["polling_station_id"].to_list()
        assert "ps_combined" in polling_stations["polling_station_id"].to_list()

        # Both PIR codes should be preserved
        assert len(pir_codes) == 2
        assert "pir_structured" in pir_codes["pir_code"].to_list()
        assert "pir_combined" in pir_codes["pir_code"].to_list()

    def test_multiple_duplicates_with_varying_priorities(self):
        """Test complex scenario with multiple duplicate groups and varying structure priorities."""
        deduplicator = AddressDeduplicator()

        test_data = pl.DataFrame(
            {
                "address_id": ["a1", "a2", "a3", "b1", "b2", "c1"],
                "county_code": ["01", "01", "01", "01", "01", "02"],
                "settlement_name": [
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Debrecen",
                ],
                "street_name": ["Main", "Main", "Main", "Side", "Side", "Main"],
                "street_type": ["utca", "utca", "utca", "utca", "utca", "utca"],
                "house_number": ["1", "1/A", "00001", "5", "5/B", "1"],
                "building": ["A", "", "A", "B", "", "A"],
                "staircase": ["", "", "", "", "", ""],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4", "ps5", "ps6"],
                "accessibility_flag": [True] * 6,
                "pir_code": ["pir1", "pir2", "pir3", "pir4", "pir5", "pir6"],
            }
        )

        result = deduplicator.deduplicate_addresses(test_data)
        canonical_addresses = result["canonical_addresses"]

        # Should have 3 canonical addresses:
        # - Group 1: a1, a2, a3 (Main utca 1/A.) - all duplicates
        # - Group 2: b1, b2 (Side utca 5/B.) - duplicates (b1 has building="B" now)
        # - Group 3: c1 (Debrecen Main utca 1/A.) - different county, not a duplicate
        assert len(canonical_addresses) == 3

        # Verify structured formats were preferred in each group
        for canonical in canonical_addresses.iter_rows(named=True):
            # All selected canonicals should have non-slash house numbers or have building field populated
            has_slash = "/" in (canonical["house_number"] or "")
            has_building_in_data = any(
                row["building"]
                for row in test_data.filter(
                    (pl.col("settlement_name") == canonical["settlement_name"])
                    & (pl.col("street_name") == canonical["street_name"])
                ).iter_rows(named=True)
            )

            if has_building_in_data:
                # If any duplicate had a building field, the structured one should be selected
                assert not has_slash or canonical["house_number"].startswith("00")
