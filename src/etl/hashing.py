"""Hashing utilities for generating deterministic entity IDs."""

import xxhash


def hash_county_id(county_code: str) -> str:
    """Generate hash ID for County entity.

    Args:
        county_code: The unique county code (e.g., "01")

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = county_code.encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_settlement_id(county_code: str, settlement_code: str) -> str:
    """Generate hash ID for Settlement entity.

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{county_code}|{settlement_code}".encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_oevk_id(county_code: str, oevk: str) -> str:
    """Generate hash ID for NationalIndividualElectoralDistrict (OEVK) entity.

    Args:
        county_code: The unique county code
        oevk: The OEVK code

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{county_code}|{oevk}".encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_tevk_id(county_code: str, settlement_code: str, tevk: str, oevk: str) -> str:
    """Generate hash ID for SettlementIndividualElectoralDistrict (TEVK) entity.

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code
        tevk: The TEVK code (can be None)
        oevk: The OEVK code

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values for TEVK
    tevk_str = str(tevk) if tevk is not None else ""
    data = f"{county_code}|{settlement_code}|{tevk_str}|{oevk}".encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_postal_code_id(postal_code: str) -> str:
    """Generate hash ID for PostalCode entity.

    Args:
        postal_code: The postal code string

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = postal_code.encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_postal_code_settlement_id(postal_code_id: str, settlement_id: str) -> str:
    """Generate hash ID for PostalCode_Settlement entity.

    Args:
        postal_code_id: The hash ID of the postal code
        settlement_id: The hash ID of the settlement

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{postal_code_id}|{settlement_id}".encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_polling_station_id(
    county_code: str,
    settlement_code: str,
    oevk: str,
    tevk: str,
    polling_station_address: str,
) -> str:
    """Generate hash ID for PollingStation entity.

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code
        oevk: The OEVK code
        tevk: The TEVK code (can be None)
        polling_station_address: The address of the polling station

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values for TEVK
    tevk_str = str(tevk) if tevk is not None else ""
    data = f"{county_code}|{settlement_code}|{oevk}|{tevk_str}|{polling_station_address}".encode(
        "utf-8"
    )
    return xxhash.xxh64(data).hexdigest()


def hash_public_space_type_id(public_space_type: str | None) -> str:
    """Generate hash ID for PublicSpaceType entity.

    Args:
        public_space_type: The public space type (e.g., "utca", "tér")

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values
    public_space_type = public_space_type if public_space_type is not None else ""
    data = public_space_type.encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_public_space_name_id(public_space_name: str | None) -> str:
    """Generate hash ID for PublicSpaceName entity.

    Args:
        public_space_name: The public space name (e.g., "Kossuth", "Petőfi")

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values
    public_space_name = public_space_name if public_space_name is not None else ""
    data = public_space_name.encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_settlement_public_spaces_id(
    settlement_id: str | None,
    public_space_name_id: str | None,
    public_space_type_id: str | None,
) -> str:
    """Generate hash ID for SettlementPublicSpaces entity.

    Args:
        settlement_id: The hash ID of the settlement
        public_space_name_id: The hash ID of the public space name
        public_space_type_id: The hash ID of the public space type

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values
    settlement_id = settlement_id if settlement_id is not None else ""
    public_space_name_id = (
        public_space_name_id if public_space_name_id is not None else ""
    )
    public_space_type_id = (
        public_space_type_id if public_space_type_id is not None else ""
    )

    data = f"{settlement_id}|{public_space_name_id}|{public_space_type_id}".encode(
        "utf-8"
    )
    return xxhash.xxh64(data).hexdigest()


def hash_address_id(
    county_code: str,
    settlement_code: str,
    public_space_name: str,
    public_space_type: str,
    house_number: str,
    building: str,
    staircase: str,
    postal_code: str,
) -> str:
    """Generate hash ID for Address entity.

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
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values from DuckDB - convert all None to empty strings
    county_code = county_code if county_code is not None else ""
    settlement_code = settlement_code if settlement_code is not None else ""
    public_space_name = public_space_name if public_space_name is not None else ""
    public_space_type = public_space_type if public_space_type is not None else ""
    house_number = house_number if house_number is not None else ""
    building = building if building is not None else ""
    staircase = staircase if staircase is not None else ""
    postal_code = postal_code if postal_code is not None else ""

    data = (
        f"{county_code}|{settlement_code}|{public_space_name}|{public_space_type}|"
        f"{house_number}|{building}|{staircase}|{postal_code}"
    ).encode("utf-8")

    return xxhash.xxh64(data).hexdigest()
