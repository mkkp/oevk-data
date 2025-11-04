#!/usr/bin/env python3
"""Test NULL house number handling."""

import sys

sys.path.insert(0, "src")

from etl.deduplicate import AddressDeduplicator


def test_clean_house_number():
    """Test _clean_house_number() with various inputs."""
    dedup = AddressDeduplicator()

    test_cases = [
        # (input, expected_output, description)
        ("000001", "1", "Leading zeros stripped"),
        ("000000", "", "All zeros returns empty string"),
        ("0000", "", "All zeros returns empty string"),
        ("0", "", "Single zero returns empty string"),
        ("", "", "Empty input returns empty string"),
        (None, "", "None input returns empty string"),
        ("000001/D", "1/D", "Leading zeros with slash"),
        ("000000/D", "", "All zeros with slash returns empty"),
        ("000001-00005", "1-5", "Range with leading zeros"),
        ("000000-00005", "", "All zeros in range returns empty"),
        ("000000 5", " 5", "Space-separated preserves space and number"),
    ]

    print("Testing _clean_house_number():")
    print("=" * 80)

    all_passed = True
    for input_val, expected, description in test_cases:
        result = dedup._clean_house_number(input_val)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"{status} {description}")
        print(f"   Input: {repr(input_val)}")
        print(f"   Expected: {repr(expected)}")
        print(f"   Got: {repr(result)}")
        if result != expected:
            print(f"   ❌ FAILED")
        print()

    return all_passed


def test_format_full_address():
    """Test _format_full_address() with various inputs."""
    dedup = AddressDeduplicator()

    test_cases = [
        # (street_name, street_type, house_num, building, staircase, expected_contains, description)
        (
            "Kossuth",
            "utca",
            "000001",
            "",
            "",
            "Kossuth utca 1.",
            "Normal address with house number",
        ),
        (
            "Gázgyári",
            "lakótelep",
            "000000",
            "0001",
            "0001",
            "Gázgyári lakótelep, 1. épület I. lépcsőház",
            "No house number, with building and staircase",
        ),
        (
            "Gázgyári",
            "lakótelep",
            "000000",
            "0001",
            "",
            "Gázgyári lakótelep, 1. épület",
            "No house number, only building",
        ),
        (
            "Gázgyári",
            "lakótelep",
            "000000",
            "",
            "0001",
            "Gázgyári lakótelep, I. lépcsőház",
            "No house number, only staircase",
        ),
        (
            "Vasútállomás",
            "",
            "000000",
            "",
            "",
            "Vasútállomás",
            "Infrastructure address - no house, no building",
        ),
        (
            "Kossuth",
            "utca",
            "000001",
            "A",
            "B",
            "Kossuth utca 1/A. B. lépcsőház",
            "House number with building and staircase",
        ),
    ]

    print("\n" + "=" * 80)
    print("Testing _format_full_address():")
    print("=" * 80)

    all_passed = True
    for (
        street_name,
        street_type,
        house_num,
        building,
        staircase,
        expected_contains,
        description,
    ) in test_cases:
        result = dedup._format_full_address(
            street_name, street_type, house_num, building, staircase
        )

        # Check if result contains expected substring or equals it
        passed = (
            expected_contains in result if expected_contains else result is not None
        )
        status = "✓" if passed else "✗"

        if not passed:
            all_passed = False

        print(f"{status} {description}")
        print(
            f"   Input: street={street_name} {street_type}, house={repr(house_num)}, bldg={repr(building)}, stair={repr(staircase)}"
        )
        print(f"   Expected (contains): {repr(expected_contains)}")
        print(f"   Got: {repr(result)}")
        if not passed:
            print(f"   ❌ FAILED")
        print()

    return all_passed


def test_real_world_addresses():
    """Test with real addresses from the invalid CSV."""
    dedup = AddressDeduplicator()

    print("\n" + "=" * 80)
    print("Testing Real-World Addresses:")
    print("=" * 80)

    real_addresses = [
        {
            "street_name": "Gázgyári",
            "street_type": "lakótelep",
            "house_number": "000000",
            "building": "0001",
            "staircase": "0001",
            "expected_pattern": "Gázgyári lakótelep, 1. épület I. lépcsőház",
        },
        {
            "street_name": "Fazekas",
            "street_type": "utca",
            "house_number": "000000",
            "building": "",
            "staircase": "",
            "expected_pattern": "Fazekas utca",
        },
        {
            "street_name": "Rákos MÁV",
            "street_type": "telep",
            "house_number": "000000",
            "building": "0005",
            "staircase": "",
            "expected_pattern": "Rákos MÁV telep, 5. épület",
        },
        {
            "street_name": "József Attila",
            "street_type": "lakótelep",
            "house_number": "000000",
            "building": "A",
            "staircase": "",
            "expected_pattern": "József Attila lakótelep, A. épület",
        },
    ]

    all_passed = True
    for addr in real_addresses:
        result = dedup._format_full_address(
            addr["street_name"],
            addr["street_type"],
            addr["house_number"],
            addr["building"],
            addr["staircase"],
        )

        expected = addr["expected_pattern"]
        passed = result == expected
        status = "✓" if passed else "✗"

        if not passed:
            all_passed = False

        print(
            f"{status} {addr['street_name']} {addr['street_type']} {addr['house_number']}"
        )
        print(
            f"   Building: {repr(addr['building'])}, Staircase: {repr(addr['staircase'])}"
        )
        print(f"   Expected: {repr(expected)}")
        print(f"   Got:      {repr(result)}")
        if not passed:
            print(f"   ❌ FAILED")
        print()

    return all_passed


if __name__ == "__main__":
    print("Testing NULL House Number Handling")
    print("=" * 80)
    print()

    test1 = test_clean_house_number()
    test2 = test_format_full_address()
    test3 = test_real_world_addresses()

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"_clean_house_number(): {'✓ PASSED' if test1 else '✗ FAILED'}")
    print(f"_format_full_address(): {'✓ PASSED' if test2 else '✗ FAILED'}")
    print(f"Real-world addresses: {'✓ PASSED' if test3 else '✗ FAILED'}")
    print()

    if test1 and test2 and test3:
        print("✓ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
