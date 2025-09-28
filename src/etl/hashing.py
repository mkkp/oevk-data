"""Hashing utilities for generating deterministic entity IDs."""

import xxhash


def hash_county_id(county_code: str) -> str:
    """Generate hash ID for County entity.

    Args:
        county_code: The unique county code (e.g., "01")

    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = county_code.encode('utf-8')
    return xxhash.xxh64(data).hexdigest()


def hash_settlement_id(county_code: str, settlement_code: str) -> str:
    """Generate hash ID for Settlement entity.
    
    Args:
        county_code: The unique county code
        settlement_code: The unique settlement code
        
    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{county_code}|{settlement_code}".encode('utf-8')
    return xxhash.xxh64(data).hexdigest()


def hash_oevk_id(county_code: str, oevk: str) -> str:
    """Generate hash ID for NationalIndividualElectoralDistrict (OEVK) entity.
    
    Args:
        county_code: The unique county code
        oevk: The OEVK code
        
    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{county_code}|{oevk}".encode('utf-8')
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
    data = f"{county_code}|{settlement_code}|{tevk_str}|{oevk}".encode('utf-8')
    return xxhash.xxh64(data).hexdigest()


def hash_postal_code_id(postal_code: str) -> str:
    """Generate hash ID for PostalCode entity.
    
    Args:
        postal_code: The postal code string
        
    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = postal_code.encode('utf-8')
    return xxhash.xxh64(data).hexdigest()


def hash_postal_code_settlement_id(postal_code_id: str, settlement_id: str) -> str:
    """Generate hash ID for PostalCode_Settlement entity.
    
    Args:
        postal_code_id: The hash ID of the postal code
        settlement_id: The hash ID of the settlement
        
    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    data = f"{postal_code_id}|{settlement_id}".encode('utf-8')
    return xxhash.xxh64(data).hexdigest()


def hash_polling_station_id(
    county_code: str,
    settlement_code: str,
    oevk: str,
    tevk: str,
    polling_station_address: str
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
    data = f"{county_code}|{settlement_code}|{oevk}|{tevk_str}|{polling_station_address}".encode('utf-8')
    return xxhash.xxh64(data).hexdigest()


def hash_address_id(address_components: dict) -> str:
    """Generate hash ID for Address entity.
    
    Args:
        address_components: Dictionary containing address components:
            - county_code: The unique county code
            - settlement_code: The unique settlement code
            - public_space_name: Public space name
            - public_space_type: Public space type
            - house_number: House number
            - building: Building identifier (can be None)
            - staircase: Staircase identifier (can be None)
            - postal_code: Postal code
        
    Returns:
        Hexadecimal string representation of xxhash64 digest
    """
    # Extract components with None handling
    county_code = address_components.get('county_code', '')
    settlement_code = address_components.get('settlement_code', '')
    public_space_name = address_components.get('public_space_name', '')
    public_space_type = address_components.get('public_space_type', '')
    house_number = address_components.get('house_number', '')
    building = str(address_components.get('building', '')) if address_components.get('building') is not None else ""
    staircase = str(address_components.get('staircase', '')) if address_components.get('staircase') is not None else ""
    postal_code = address_components.get('postal_code', '')
    
    data = (
        f"{county_code}|{settlement_code}|{public_space_name}|{public_space_type}|"
        f"{house_number}|{building}|{staircase}|{postal_code}"
    ).encode('utf-8')

    return xxhash.xxh64(data).hexdigest()
