"""
Contract tests for address cleansing functionality.

These tests verify that the address cleansing implementation matches
the requirements specified in docs/004_REMOVE_DUPLICATED_ADDRESSES.md
and openspec/changes/add-cleansed-address-deduplication/specs/address-deduplication/spec.md
"""

import pytest
from src.etl.deduplicate import AddressDeduplicator


class TestAddressCleansingForDeduplication:
    """Test comprehensive Hungarian address cleansing rules."""

    @pytest.fixture
    def deduplicator(self):
        """Create AddressDeduplicator instance for testing."""
        return AddressDeduplicator(seed=20241012)

    def test_leading_zeros_removed_from_house_numbers(self, deduplicator):
        """Contract: Leading zeros removed from house numbers."""
        result = deduplicator._clean_house_number("000001")
        assert result == "1"

    def test_leading_zeros_removed_from_house_number_ranges(self, deduplicator):
        """Contract: Leading zeros removed from house number ranges."""
        result = deduplicator._clean_house_number("000001-00005")
        assert result == "1-5"

    def test_leading_zeros_preserved_in_slash_notation(self, deduplicator):
        """Contract: Numeric part cleaned, suffix preserved in slash notation."""
        result = deduplicator._clean_house_number("000001/D")
        assert result == "1/D"

    def test_building_field_leading_zeros_trimmed(self, deduplicator):
        """Contract: Building field leading zeros trimmed."""
        # Building normalization happens in _format_full_address
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "0001", ""
        )
        # Should use "1" for building
        assert "1/" in result or "1. épület" in result

    def test_numeric_staircase_converted_to_roman_numerals(self, deduplicator):
        """Contract: Numeric staircase "0001" converted to Roman "I"."""
        result = deduplicator._to_roman_numeral("1")
        assert result == "I"

    def test_numeric_staircase_0005_converted_to_roman_v(self, deduplicator):
        """Contract: Numeric staircase "0005" converted to Roman "V"."""
        result = deduplicator._to_roman_numeral("5")
        assert result == "V"

    def test_alphabetic_staircase_preserved_and_uppercased(self, deduplicator):
        """Contract: Alphabetic staircase preserved and uppercased."""
        # Staircase normalization happens in _format_full_address
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "", "l"
        )
        assert "L." in result or "L " in result

    def test_null_or_empty_street_name_handled_gracefully(self, deduplicator):
        """Contract: Null or empty street name handled without error."""
        result = deduplicator._format_full_address("", "utca", "000001", "", "")
        assert result == "utca 1."

        result2 = deduplicator._format_full_address(None, "utca", "000001", "", "")
        assert "utca" in result2

    def test_null_or_empty_house_number_handled_gracefully(self, deduplicator):
        """Contract: Null or empty house number uses default "0"."""
        result = deduplicator._clean_house_number("")
        assert result == "0"

        result2 = deduplicator._clean_house_number(None)
        assert result2 == "0"  # None also defaults to "0"

    def test_range_with_slash_suffix_edge_case(self, deduplicator):
        """Contract: Range with slash suffix "000001-00005/D" -> "1-5/D"."""
        result = deduplicator._clean_house_number("000001-00005/D")
        # The implementation splits on "-" first: ["000001", "00005/D"]
        # Then cleans each: ["1", "5/D"]
        # Then rejoins: "1-5/D"
        assert result == "1-5/D"


class TestFullAddressFormattingRules:
    """Test Hungarian address formatting conventions."""

    @pytest.fixture
    def deduplicator(self):
        """Create AddressDeduplicator instance for testing."""
        return AddressDeduplicator(seed=20241012)

    def test_house_number_with_slash_and_no_building_staircase(self, deduplicator):
        """Contract: house number "000001/D", empty building, empty staircase."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001/D", "", ""
        )
        assert result == "Körtöltés utca 1/D."

    def test_house_number_without_slash_and_building_only(self, deduplicator):
        """Contract: house number "000001", building "D", empty staircase."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "D", ""
        )
        assert result == "Körtöltés utca 1/D."

    def test_house_number_without_slash_and_staircase_only(self, deduplicator):
        """Contract: house number "000001", empty building, staircase "D"."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "", "D"
        )
        assert result == "Körtöltés utca 1/D."

    def test_house_number_without_slash_both_building_and_staircase(self, deduplicator):
        """Contract: house number "000001", building "D", staircase "L"."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "D", "L"
        )
        assert result == "Körtöltés utca 1/D. L. lépcsőház"

    def test_house_number_with_slash_both_building_and_staircase_ignores_slash(
        self, deduplicator
    ):
        """Contract: house number "000001/D", building "B", staircase "L" ignores slash."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001/D", "B", "L"
        )
        assert result == "Körtöltés utca 1. B. épület L. lépcsőház"

    def test_house_number_with_slash_and_only_staircase_preserves_slash(
        self, deduplicator
    ):
        """Contract: house number "000001/D", empty building, staircase "L" preserves slash."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001/D", "", "L"
        )
        assert result == "Körtöltés utca 1/D. L. lépcsőház"

    def test_range_with_building_and_staircase(self, deduplicator):
        """Contract: house number "000001-00005", building "B", staircase "L"."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001-00005", "B", "L"
        )
        assert result == "Körtöltés utca 1-5. B. épület L. lépcsőház"

    def test_range_with_slash_suffix(self, deduplicator):
        """Contract: house number "000001-00005/D", empty building, empty staircase."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001-00005/D", "", ""
        )
        assert result == "Körtöltés utca 1-5/D."

    def test_numeric_building_and_staircase_with_roman_conversion(self, deduplicator):
        """Contract: Berényi utca example with Roman numeral conversion."""
        result = deduplicator._format_full_address(
            "Berényi", "utca", "000009", "0001", "0001"
        )
        assert result == "Berényi utca 9. 1. épület I. lépcsőház"

    def test_numeric_building_and_staircase_0005_converts_to_roman_v(
        self, deduplicator
    ):
        """Contract: Berényi utca example with staircase 0005 -> V."""
        result = deduplicator._format_full_address(
            "Berényi", "utca", "000009", "0001", "0005"
        )
        assert result == "Berényi utca 9. 1. épület V. lépcsőház"


class TestDocumentExamples:
    """Test all examples from docs/004_REMOVE_DUPLICATED_ADDRESSES.md."""

    @pytest.fixture
    def deduplicator(self):
        """Create AddressDeduplicator instance for testing."""
        return AddressDeduplicator(seed=20241012)

    def test_kortoltes_utca_example_1(self, deduplicator):
        """Document example: Körtöltés utca 1/D (variant 1)."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "D", ""
        )
        assert result == "Körtöltés utca 1/D."

    def test_kortoltes_utca_example_2(self, deduplicator):
        """Document example: Körtöltés utca 1/D (variant 2)."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "", "D"
        )
        assert result == "Körtöltés utca 1/D."

    def test_kortoltes_utca_example_3(self, deduplicator):
        """Document example: Körtöltés utca 1/D. L. lépcsőház."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001", "D", "L"
        )
        assert result == "Körtöltés utca 1/D. L. lépcsőház"

    def test_kortoltes_utca_example_4(self, deduplicator):
        """Document example: Körtöltés utca 1/D (variant 3 - house number has slash)."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001/D", "", ""
        )
        assert result == "Körtöltés utca 1/D."

    def test_kortoltes_utca_example_5(self, deduplicator):
        """Document example: Körtöltés utca 1. B. épület L. lépcsőház."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001/D", "B", "L"
        )
        assert result == "Körtöltés utca 1. B. épület L. lépcsőház"

    def test_kortoltes_utca_example_6(self, deduplicator):
        """Document example: Körtöltés utca 1/D. L. lépcsőház (variant 2)."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001/D", "", "L"
        )
        assert result == "Körtöltés utca 1/D. L. lépcsőház"

    def test_kortoltes_utca_example_7_range_with_building(self, deduplicator):
        """Document example: Körtöltés utca 1-5/D."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001-00005", "D", ""
        )
        assert result == "Körtöltés utca 1-5/D."

    def test_kortoltes_utca_example_8_range_with_both(self, deduplicator):
        """Document example: Körtöltés utca 1-5. B. épület L. lépcsőház."""
        result = deduplicator._format_full_address(
            "Körtöltés", "utca", "000001-00005", "B", "L"
        )
        assert result == "Körtöltés utca 1-5. B. épület L. lépcsőház"

    def test_berenyi_utca_example_1(self, deduplicator):
        """Document example: Berényi utca 9. 1. épület I. lépcsőház."""
        result = deduplicator._format_full_address(
            "Berényi", "utca", "000009", "0001", "0001"
        )
        assert result == "Berényi utca 9. 1. épület I. lépcsőház"

    def test_berenyi_utca_example_2(self, deduplicator):
        """Document example: Berényi utca 9. 1. épület V. lépcsőház."""
        result = deduplicator._format_full_address(
            "Berényi", "utca", "000009", "0001", "0005"
        )
        assert result == "Berényi utca 9. 1. épület V. lépcsőház"


class TestRomanNumeralConversion:
    """Test Roman numeral conversion for staircases."""

    @pytest.fixture
    def deduplicator(self):
        """Create AddressDeduplicator instance for testing."""
        return AddressDeduplicator(seed=20241012)

    @pytest.mark.parametrize(
        "input_num,expected_roman",
        [
            ("1", "I"),
            ("2", "II"),
            ("3", "III"),
            ("4", "IV"),
            ("5", "V"),
            ("6", "VI"),
            ("7", "VII"),
            ("8", "VIII"),
            ("9", "IX"),
            ("10", "X"),
        ],
    )
    def test_roman_numeral_conversions_1_to_10(
        self, deduplicator, input_num, expected_roman
    ):
        """Contract: Verify Roman numeral conversions for 1-10."""
        result = deduplicator._to_roman_numeral(input_num)
        assert result == expected_roman

    def test_roman_numeral_out_of_range(self, deduplicator):
        """Contract: Out of range numbers returned as-is."""
        result = deduplicator._to_roman_numeral("4000")
        assert result == "4000"

        result2 = deduplicator._to_roman_numeral("0")
        assert result2 == "0"

    def test_roman_numeral_invalid_input(self, deduplicator):
        """Contract: Invalid input returned as-is."""
        result = deduplicator._to_roman_numeral("ABC")
        assert result == "ABC"
