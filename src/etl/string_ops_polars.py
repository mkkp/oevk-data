"""Polars-compatible string operations for address transformation.

This module provides string manipulation functions optimized for use with Polars DataFrames.
Functions can be used with Polars map_elements() for row-wise operations.
"""

import re
from typing import Optional


def trim_leading_zeros_polars(value: Optional[str]) -> str:
    """Trim leading zeros from address component strings (Polars-compatible).

    This function handles various Hungarian address formatting patterns:
    - Range notation: "000001-00005" → "1-5"
    - Slash notation: "000001/D" → "1/D"
    - Numeric only: "000001" → "1"
    - Mixed/non-numeric: returned as-is

    Args:
        value: Address component string (house number, building, or staircase)

    Returns:
        Formatted string with leading zeros removed

    Examples:
        >>> trim_leading_zeros_polars("000001")
        "1"
        >>> trim_leading_zeros_polars("000001-00005")
        "1-5"
        >>> trim_leading_zeros_polars("000001/D")
        "1/D"
        >>> trim_leading_zeros_polars("0000")
        "0"
        >>> trim_leading_zeros_polars(None)
        ""
    """
    if not value or value is None:
        return ""

    # Convert to string if not already
    value = str(value)

    # Handle range notation (e.g., "000001-00005" -> "1-5")
    if '-' in value:
        parts = value.split('-', 1)
        if len(parts) == 2:
            left = parts[0].lstrip('0') or '0'
            right = parts[1].lstrip('0') or '0'
            return f"{left}-{right}"

    # Handle slash notation (e.g., "000001/D" -> "1/D")
    if '/' in value:
        match = re.match(r'^(0*)(\d+)(/.*)?$', value)
        if match:
            num = match.group(2) or '0'
            suffix = match.group(3) or ''
            return num + suffix

    # Handle numeric only (e.g., "000001" -> "1")
    if value.isdigit():
        return value.lstrip('0') or '0'

    # Non-numeric or mixed: return as-is
    return value


def format_full_address_polars(
    street_name: Optional[str],
    street_type: Optional[str],
    house_number: Optional[str],
    building: Optional[str],
    staircase: Optional[str],
) -> str:
    """Format full address string from components (Polars-compatible).

    Concatenates address components with proper spacing and handles None values.

    Args:
        street_name: Street name (e.g., "Kossuth")
        street_type: Street type (e.g., "utca", "tér")
        house_number: House number (already trimmed)
        building: Building identifier (already trimmed, optional)
        staircase: Staircase identifier (already trimmed, optional)

    Returns:
        Formatted full address string

    Examples:
        >>> format_full_address_polars("Kossuth", "tér", "1", None, None)
        "Kossuth tér 1"
        >>> format_full_address_polars("Petőfi", "utca", "10", "A", None)
        "Petőfi utca 10 A"
        >>> format_full_address_polars("Berényi", "utca", "9", "1", "I")
        "Berényi utca 9 1 I"
    """
    components = []

    if street_name:
        components.append(str(street_name))

    if street_type:
        components.append(str(street_type))

    if house_number:
        components.append(str(house_number))

    if building:
        components.append(str(building))

    if staircase:
        components.append(str(staircase))

    return ' '.join(components).strip()


# Polars expression helpers

def apply_trim_leading_zeros(value):
    """Wrapper for trim_leading_zeros_polars for use with Polars map_elements().

    Args:
        value: Input value (can be str, int, float, or None)

    Returns:
        Trimmed string
    """
    return trim_leading_zeros_polars(value)


def apply_format_full_address(row):
    """Apply format_full_address_polars to a Polars row/struct.

    This function is designed to work with Polars map_elements() on struct columns.

    Args:
        row: A Polars row or dict-like object with address components

    Returns:
        Formatted full address string
    """
    return format_full_address_polars(
        street_name=row.get("street_name"),
        street_type=row.get("street_type"),
        house_number=row.get("HouseNumber"),  # Already trimmed
        building=row.get("Building"),  # Already trimmed
        staircase=row.get("Staircase"),  # Already trimmed
    )
