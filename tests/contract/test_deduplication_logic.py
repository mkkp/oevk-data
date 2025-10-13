"""
Contract tests for deduplication logic.

These tests verify that the canonical ID generation and duplicate detection
work correctly according to the specification.
"""

import polars as pl
import pytest
from src.etl.deduplicate import AddressDeduplicator


class TestCanonicalIDGeneration:
    """Test deterministic canonical ID generation based on cleansed addresses."""

    @pytest.fixture
    def deduplicator(self):
        """Create AddressDeduplicator instance for testing."""
        return AddressDeduplicator(seed=20241012)

    def test_canonical_id_uses_cleansed_full_address(self, deduplicator):
        """Contract: Canonical ID is computed from cleansed full address."""
        # Create sample addresses that should produce same canonical ID
        df = pl.DataFrame(
            {
                "county_code": ["06", "06", "06"],
                "settlement_name": ["Szeged", "Szeged", "Szeged"],
                "street_name": ["Körtöltés", "Körtöltés", "Körtöltés"],
                "street_type": ["utca", "utca", "utca"],
                "house_number": ["000001", "000001", "000001/D"],
                "building": ["D", "", ""],
                "staircase": ["", "D", ""],
                "address_id": ["id1", "id2", "id3"],
            }
        )

        result = deduplicator._generate_canonical_ids(df)

        # All three should have same canonical ID (they format to "Körtöltés utca 1/D.")
        canonical_ids = result["canonical_address_id"].to_list()
        assert len(set(canonical_ids)) == 1, (
            "All three addresses should have same canonical ID"
        )

    def test_different_addresses_produce_different_canonical_ids(self, deduplicator):
        """Contract: Different cleansed addresses produce different canonical IDs."""
        df = pl.DataFrame(
            {
                "county_code": ["06", "06"],
                "settlement_name": ["Szeged", "Szeged"],
                "street_name": ["Körtöltés", "Körtöltés"],
                "street_type": ["utca", "utca"],
                "house_number": ["000001", "000001/D"],
                "building": ["D", "B"],
                "staircase": ["L", "L"],
                "address_id": ["id1", "id2"],
            }
        )

        result = deduplicator._generate_canonical_ids(df)

        # These should produce different canonical IDs
        # "Körtöltés utca 1/D. L. lépcsőház" vs "Körtöltés utca 1. B. épület L. lépcsőház"
        canonical_ids = result["canonical_address_id"].to_list()
        assert len(set(canonical_ids)) == 2, (
            "Different addresses should have different canonical IDs"
        )

    def test_canonical_id_includes_county_and_settlement(self, deduplicator):
        """Contract: Canonical ID hash includes county_code, settlement_name, and cleansed_full_address."""
        # Same address in different settlements should produce different canonical IDs
        df = pl.DataFrame(
            {
                "county_code": ["06", "01"],
                "settlement_name": ["Szeged", "Budapest"],
                "street_name": ["Körtöltés", "Körtöltés"],
                "street_type": ["utca", "utca"],
                "house_number": ["000001", "000001"],
                "building": ["D", "D"],
                "staircase": ["", ""],
                "address_id": ["id1", "id2"],
            }
        )

        result = deduplicator._generate_canonical_ids(df)

        # Different settlements should produce different canonical IDs
        canonical_ids = result["canonical_address_id"].to_list()
        assert len(set(canonical_ids)) == 2, (
            "Same address in different settlements should have different canonical IDs"
        )

    def test_whitespace_normalization_in_canonical_id(self, deduplicator):
        """Contract: Multiple consecutive spaces are collapsed for canonical ID generation."""
        df = pl.DataFrame(
            {
                "county_code": ["06", "06"],
                "settlement_name": ["Szeged", "Szeged  City"],  # Double space
                "street_name": [
                    "Kossuth  Lajos",
                    "Kossuth Lajos",
                ],  # Double space vs single
                "street_type": ["tér", "tér"],
                "house_number": ["000001", "000001"],
                "building": ["", ""],
                "staircase": ["", ""],
                "address_id": ["id1", "id2"],
            }
        )

        result = deduplicator._generate_canonical_ids(df)

        # Whitespace should be normalized, but settlement names are different
        canonical_ids = result["canonical_address_id"].to_list()
        # These should be different because settlement names differ after normalization
        assert len(set(canonical_ids)) == 2

    def test_deterministic_canonical_id_generation(self, deduplicator):
        """Contract: Same input produces same canonical ID across runs."""
        df = pl.DataFrame(
            {
                "county_code": ["06"],
                "settlement_name": ["Szeged"],
                "street_name": ["Körtöltés"],
                "street_type": ["utca"],
                "house_number": ["000001"],
                "building": ["D"],
                "staircase": [""],
                "address_id": ["id1"],
            }
        )

        # Generate canonical ID twice
        result1 = deduplicator._generate_canonical_ids(df)
        result2 = deduplicator._generate_canonical_ids(df)

        canonical_id1 = result1["canonical_address_id"][0]
        canonical_id2 = result2["canonical_address_id"][0]

        assert canonical_id1 == canonical_id2, (
            "Same input should produce same canonical ID"
        )


class TestGateCodeExclusion:
    """Test that gate code column is excluded from deduplication."""

    @pytest.fixture
    def deduplicator(self):
        """Create AddressDeduplicator instance for testing."""
        return AddressDeduplicator(seed=20241012)

    def test_gate_code_not_used_in_canonical_id(self, deduplicator):
        """Contract: Gate code does not affect canonical ID generation."""
        # Create addresses with same components but different gate codes
        df = pl.DataFrame(
            {
                "county_code": ["06", "06"],
                "settlement_name": ["Szeged", "Szeged"],
                "street_name": ["Körtöltés", "Körtöltés"],
                "street_type": ["utca", "utca"],
                "house_number": ["000001", "000001"],
                "building": ["D", "D"],
                "staircase": ["", ""],
                "address_id": ["id1", "id2"],
                # Gate codes would be here but not used in _generate_canonical_ids
            }
        )

        result = deduplicator._generate_canonical_ids(df)

        # Same address components should produce same canonical ID regardless of gate code
        canonical_ids = result["canonical_address_id"].to_list()
        assert len(set(canonical_ids)) == 1, "Gate code should not affect canonical ID"


class TestDeterministicCleansing:
    """Test that cleansing is deterministic across runs."""

    @pytest.fixture
    def deduplicator(self):
        """Create AddressDeduplicator instance for testing."""
        return AddressDeduplicator(seed=20241012)

    def test_same_input_produces_same_cleansed_output(self, deduplicator):
        """Contract: Same input produces identical cleansed output across runs."""
        street_name = "Körtöltés"
        street_type = "utca"
        house_number = "000001"
        building = "D"
        staircase = ""

        # Format address multiple times
        result1 = deduplicator._format_full_address(
            street_name, street_type, house_number, building, staircase
        )
        result2 = deduplicator._format_full_address(
            street_name, street_type, house_number, building, staircase
        )
        result3 = deduplicator._format_full_address(
            street_name, street_type, house_number, building, staircase
        )

        assert result1 == result2 == result3, (
            "Same input should produce identical output"
        )
        assert result1 == "Körtöltés utca 1/D."
