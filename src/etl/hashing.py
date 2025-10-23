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


def hash_tevk_id(county_code: str, settlement_code: str, tevk: str) -> str:
    """Generate hash ID for SettlementIndividualElectoralDistrict (TEVK) entity.

    TEVK is independent of OEVK - they are parallel electoral systems, not hierarchical.
    TEVK is defined by county, settlement, and TEVK code only.

    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code
        tevk: The TEVK code (can be None)

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values for TEVK
    tevk_str = str(tevk) if tevk is not None else ""
    data = f"{county_code}|{settlement_code}|{tevk_str}".encode("utf-8")
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
    county_code: str | None,
    settlement_code: str | None,
    public_space_name: str | None,
    public_space_type: str | None,
    house_number: str | None,
    building: str | None,
    staircase: str | None,
    postal_code: str | None,
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


def hash_canonical_address_id(
    county_code: str | None,
    settlement_name: str | None,
    street_name: str | None,
    house_number: str | None,
) -> str:
    """Generate hash ID for CanonicalAddress entity.

    Args:
        county_code: The unique county code
        settlement_name: The settlement name
        street_name: The street name
        house_number: The house number

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Handle None values
    county_code = county_code if county_code is not None else ""
    settlement_name = settlement_name if settlement_name is not None else ""
    street_name = street_name if street_name is not None else ""
    house_number = house_number if house_number is not None else ""

    data = f"{county_code}|{settlement_name}|{street_name}|{house_number}".encode(
        "utf-8"
    )
    return xxhash.xxh64(data).hexdigest()


def hash_address_mapping_id(original_address_id: str, canonical_address_id: str) -> str:
    """Generate hash ID for AddressMapping entity.

    Args:
        original_address_id: The hash ID of the original address
        canonical_address_id: The hash ID of the canonical address

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{original_address_id}|{canonical_address_id}".encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_address_polling_stations_id(
    canonical_address_id: str, polling_station_id: str
) -> str:
    """Generate hash ID for AddressPollingStations entity.

    Args:
        canonical_address_id: The hash ID of the canonical address
        polling_station_id: The hash ID of the polling station

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{canonical_address_id}|{polling_station_id}".encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_address_pir_codes_id(canonical_address_id: str, pir_code: str) -> str:
    """Generate hash ID for AddressPIRCodes entity.

    Args:
        canonical_address_id: The hash ID of the canonical address
        pir_code: The PIR code

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{canonical_address_id}|{pir_code}".encode("utf-8")
    return xxhash.xxh64(data).hexdigest()


def hash_deduplication_report_id(run_id: str) -> str:
    """Generate hash ID for DeduplicationReport entity.

    Args:
        run_id: The unique run identifier

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = run_id.encode("utf-8")
    return xxhash.xxh64(data).hexdigest()
