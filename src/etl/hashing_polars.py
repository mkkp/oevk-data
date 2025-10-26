"""Polars-compatible hashing utilities for generating deterministic entity IDs.

This module provides hash functions optimized for use with Polars DataFrames.
The hash functions are designed to work with Polars map_elements() or as
standalone Python functions for vectorized operations.

All functions use MD5 hash (first 16 characters) to maintain compatibility with the
SQL macros used in DuckDB transformation.
"""

import hashlib
from typing import Optional


def hash_county_id_polars(county_code: Optional[str]) -> str:
    """Generate hash ID for County entity (Polars-compatible).

    Args:
        county_code: The unique county code (e.g., "01")

    Returns:
        First 16 characters of MD5 hash (lowercase hex)
    """
    if county_code is None:
        county_code = ""
    data = str(county_code).encode("utf-8")
    return hashlib.md5(data).hexdigest()[:16].lower()


def hash_settlement_id_polars(county_code: Optional[str], settlement_code: Optional[str]) -> str:
    """Generate hash ID for Settlement entity (Polars-compatible).

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code

    Returns:
        First 16 characters of MD5 hash (lowercase hex)
    """
    county_code = str(county_code) if county_code is not None else ""
    settlement_code = str(settlement_code) if settlement_code is not None else ""
    data = f"{county_code}|{settlement_code}".encode("utf-8")
    return hashlib.md5(data).hexdigest()[:16].lower()


def hash_oevk_id_polars(county_code: Optional[str], oevk: Optional[str]) -> str:
    """Generate hash ID for NationalIndividualElectoralDistrict (OEVK) entity (Polars-compatible).

    Args:
        county_code: The unique county code
        oevk: The OEVK code

    Returns:
        First 16 characters of MD5 hash (lowercase hex)
    """
    county_code = str(county_code) if county_code is not None else ""
    oevk = str(oevk) if oevk is not None else ""
    data = f"{county_code}|{oevk}".encode("utf-8")
    return hashlib.md5(data).hexdigest()[:16].lower()


def hash_tevk_id_polars(county_code: Optional[str], settlement_code: Optional[str], tevk: Optional[str]) -> str:
    """Generate hash ID for SettlementIndividualElectoralDistrict (TEVK) entity (Polars-compatible).

    TEVK is independent of OEVK - they are parallel electoral systems, not hierarchical.
    TEVK is defined by county, settlement, and TEVK code only.

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code
        tevk: The TEVK code (can be None)

    Returns:
        First 16 characters of MD5 hash (lowercase hex)
    """
    county_code = str(county_code) if county_code is not None else ""
    settlement_code = str(settlement_code) if settlement_code is not None else ""
    tevk_str = str(tevk) if tevk is not None else ""
    data = f"{county_code}|{settlement_code}|{tevk_str}".encode("utf-8")
    return hashlib.md5(data).hexdigest()[:16].lower()


def hash_postal_code_id_polars(postal_code: Optional[str]) -> str:
    """Generate hash ID for PostalCode entity (Polars-compatible).

    Args:
        postal_code: The postal code string

    Returns:
        First 16 characters of MD5 hash (lowercase hex)
    """
    postal_code = str(postal_code) if postal_code is not None else ""
    data = postal_code.encode("utf-8")
    return hashlib.md5(data).hexdigest()[:16].lower()


def hash_polling_station_id_polars(
    county_code: Optional[str],
    settlement_code: Optional[str],
    oevk: Optional[str],
    tevk: Optional[str],
    polling_station_address: Optional[str],
) -> str:
    """Generate hash ID for PollingStation entity (Polars-compatible).

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code
        oevk: The OEVK code
        tevk: The TEVK code (can be None)
        polling_station_address: The address of the polling station

    Returns:
        First 16 characters of MD5 hash (lowercase hex)
    """
    county_code = str(county_code) if county_code is not None else ""
    settlement_code = str(settlement_code) if settlement_code is not None else ""
    oevk = str(oevk) if oevk is not None else ""
    tevk_str = str(tevk) if tevk is not None else ""
    polling_station_address = str(polling_station_address) if polling_station_address is not None else ""

    data = f"{county_code}|{settlement_code}|{oevk}|{tevk_str}|{polling_station_address}".encode("utf-8")
    return hashlib.md5(data).hexdigest()[:16].lower()


def hash_address_id_polars(
    county_code: Optional[str],
    settlement_code: Optional[str],
    public_space_name: Optional[str],
    public_space_type: Optional[str],
    house_number: Optional[str],
    building: Optional[str],
    staircase: Optional[str],
    postal_code: Optional[str],
) -> str:
    """Generate hash ID for Address entity (Polars-compatible).

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code
        public_space_name: Public space name
        public_space_type: Public space type
        house_number: House number
        building: Building identifier (can be None)
        staircase: Staircase identifier (can be None)
        postal_code: Postal code

    Returns:
        First 16 characters of MD5 hash (lowercase hex)
    """
    # Handle None values - convert all None to empty strings
    county_code = str(county_code) if county_code is not None else ""
    settlement_code = str(settlement_code) if settlement_code is not None else ""
    public_space_name = str(public_space_name) if public_space_name is not None else ""
    public_space_type = str(public_space_type) if public_space_type is not None else ""
    house_number = str(house_number) if house_number is not None else ""
    building = str(building) if building is not None else ""
    staircase = str(staircase) if staircase is not None else ""
    postal_code = str(postal_code) if postal_code is not None else ""

    data = (
        f"{county_code}|{settlement_code}|{public_space_name}|{public_space_type}|"
        f"{house_number}|{building}|{staircase}|{postal_code}"
    ).encode("utf-8")

    return hashlib.md5(data).hexdigest()[:16].lower()


# Helper functions for applying hash functions to Polars struct columns

def apply_hash_address_id(row):
    """Apply hash_address_id_polars to a Polars row/struct.

    This function is designed to work with Polars map_elements() on struct columns.

    Args:
        row: A Polars row or dict-like object with address components

    Returns:
        Hexadecimal string hash ID
    """
    return hash_address_id_polars(
        county_code=row.get("county_code"),
        settlement_code=row.get("settlement_code"),
        public_space_name=row.get("street_name"),
        public_space_type=row.get("street_type"),
        house_number=row.get("house_number"),
        building=row.get("building"),
        staircase=row.get("staircase"),
        postal_code=str(row.get("postal_code")) if row.get("postal_code") is not None else "",
    )


def apply_hash_county_id(county_code):
    """Apply hash_county_id_polars to a single value.

    Wrapper for use with Polars map_elements().

    Args:
        county_code: County code value

    Returns:
        Hexadecimal string hash ID
    """
    return hash_county_id_polars(county_code)


def apply_hash_settlement_id(row):
    """Apply hash_settlement_id_polars to a Polars row/struct.

    Args:
        row: A Polars row or dict-like object with county_code and settlement_code

    Returns:
        Hexadecimal string hash ID
    """
    return hash_settlement_id_polars(
        county_code=row.get("county_code"),
        settlement_code=row.get("settlement_code")
    )


def apply_hash_oevk_id(row):
    """Apply hash_oevk_id_polars to a Polars row/struct.

    Args:
        row: A Polars row or dict-like object with county_code and oevk_code

    Returns:
        Hexadecimal string hash ID
    """
    return hash_oevk_id_polars(
        county_code=row.get("county_code"),
        oevk=row.get("oevk_code")
    )


def apply_hash_tevk_id(row):
    """Apply hash_tevk_id_polars to a Polars row/struct.

    Args:
        row: A Polars row or dict-like object with county_code, settlement_code, tevk_code

    Returns:
        Hexadecimal string hash ID
    """
    return hash_tevk_id_polars(
        county_code=row.get("county_code"),
        settlement_code=row.get("settlement_code"),
        tevk=row.get("tevk_code")
    )


def apply_hash_postal_code_id(postal_code):
    """Apply hash_postal_code_id_polars to a single value.

    Args:
        postal_code: Postal code value

    Returns:
        Hexadecimal string hash ID
    """
    return hash_postal_code_id_polars(str(postal_code) if postal_code is not None else "")


def apply_hash_polling_station_id(row):
    """Apply hash_polling_station_id_polars to a Polars row/struct.

    Args:
        row: A Polars row or dict-like object with polling station data

    Returns:
        Hexadecimal string hash ID
    """
    return hash_polling_station_id_polars(
        county_code=row.get("county_code"),
        settlement_code=row.get("settlement_code"),
        oevk=row.get("oevk_code"),
        tevk=row.get("tevk_code"),
        polling_station_address=row.get("polling_station_address")
    )
