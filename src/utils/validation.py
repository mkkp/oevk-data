"""Data validation utilities for the OEVK data transformation pipeline."""

from typing import Dict, List, Optional, Any
from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


def validate_county_data(county_data: Dict[str, Any]) -> List[str]:
    """Validate county data structure and content.
    
    Args:
        county_data: Dictionary containing county data.
        
    Returns:
        List of validation error messages, empty if valid.
    """
    errors = []
    
    # Required fields
    required_fields = ['CountyCode', 'CountyName']
    for field in required_fields:
        if field not in county_data:
            errors.append(f"Missing required field: {field}")
        elif not county_data[field]:
            errors.append(f"Empty required field: {field}")
    
    # CountyCode format validation (should be 2-digit string)
    if 'CountyCode' in county_data and county_data['CountyCode']:
        county_code = str(county_data['CountyCode'])
        if not county_code.isdigit() or len(county_code) != 2:
            errors.append(f"Invalid CountyCode format: {county_code}")
    
    return errors


def validate_settlement_data(settlement_data: Dict[str, Any]) -> List[str]:
    """Validate settlement data structure and content.
    
    Args:
        settlement_data: Dictionary containing settlement data.
        
    Returns:
        List of validation error messages, empty if valid.
    """
    errors = []
    
    # Required fields
    required_fields = ['SettlementCode', 'SettlementName', 'CountyCode']
    for field in required_fields:
        if field not in settlement_data:
            errors.append(f"Missing required field: {field}")
        elif not settlement_data[field]:
            errors.append(f"Empty required field: {field}")
    
    # SettlementCode format validation
    if 'SettlementCode' in settlement_data and settlement_data['SettlementCode']:
        settlement_code = str(settlement_data['SettlementCode'])
        if not settlement_code.isdigit():
            errors.append(f"Invalid SettlementCode format: {settlement_code}")
    
    # CountyCode format validation
    if 'CountyCode' in settlement_data and settlement_data['CountyCode']:
        county_code = str(settlement_data['CountyCode'])
        if not county_code.isdigit() or len(county_code) != 2:
            errors.append(f"Invalid CountyCode format: {county_code}")
    
    return errors


def validate_oevk_data(oevk_data: Dict[str, Any]) -> List[str]:
    """Validate OEVK (National Individual Electoral District) data.
    
    Args:
        oevk_data: Dictionary containing OEVK data.
        
    Returns:
        List of validation error messages, empty if valid.
    """
    errors = []
    
    # Required fields
    required_fields = ['OEVK', 'CountyCode']
    for field in required_fields:
        if field not in oevk_data:
            errors.append(f"Missing required field: {field}")
        elif not oevk_data[field]:
            errors.append(f"Empty required field: {field}")
    
    # OEVK format validation
    if 'OEVK' in oevk_data and oevk_data['OEVK']:
        oevk = str(oevk_data['OEVK'])
        if not oevk.isdigit():
            errors.append(f"Invalid OEVK format: {oevk}")
    
    # CountyCode format validation
    if 'CountyCode' in oevk_data and oevk_data['CountyCode']:
        county_code = str(oevk_data['CountyCode'])
        if not county_code.isdigit() or len(county_code) != 2:
            errors.append(f"Invalid CountyCode format: {county_code}")
    
    return errors


def validate_tevk_data(tevk_data: Dict[str, Any]) -> List[str]:
    """Validate TEVK (Settlement Individual Electoral District) data.
    
    Args:
        tevk_data: Dictionary containing TEVK data.
        
    Returns:
        List of validation error messages, empty if valid.
    """
    errors = []
    
    # Required fields
    required_fields = ['CountyCode', 'SettlementCode', 'OEVK']
    for field in required_fields:
        if field not in tevk_data:
            errors.append(f"Missing required field: {field}")
        elif not tevk_data[field]:
            errors.append(f"Empty required field: {field}")
    
    # CountyCode format validation
    if 'CountyCode' in tevk_data and tevk_data['CountyCode']:
        county_code = str(tevk_data['CountyCode'])
        if not county_code.isdigit() or len(county_code) != 2:
            errors.append(f"Invalid CountyCode format: {county_code}")
    
    # SettlementCode format validation
    if 'SettlementCode' in tevk_data and tevk_data['SettlementCode']:
        settlement_code = str(tevk_data['SettlementCode'])
        if not settlement_code.isdigit():
            errors.append(f"Invalid SettlementCode format: {settlement_code}")
    
    # OEVK format validation
    if 'OEVK' in tevk_data and tevk_data['OEVK']:
        oevk = str(tevk_data['OEVK'])
        if not oevk.isdigit():
            errors.append(f"Invalid OEVK format: {oevk}")
    
    return errors


def validate_postal_code_data(postal_code_data: Dict[str, Any]) -> List[str]:
    """Validate postal code data.
    
    Args:
        postal_code_data: Dictionary containing postal code data.
        
    Returns:
        List of validation error messages, empty if valid.
    """
    errors = []
    
    # Required fields
    required_fields = ['PostalCode']
    for field in required_fields:
        if field not in postal_code_data:
            errors.append(f"Missing required field: {field}")
        elif not postal_code_data[field]:
            errors.append(f"Empty required field: {field}")
    
    # PostalCode format validation (4-digit Hungarian postal code)
    if 'PostalCode' in postal_code_data and postal_code_data['PostalCode']:
        postal_code = str(postal_code_data['PostalCode'])
        if not postal_code.isdigit() or len(postal_code) != 4:
            errors.append(f"Invalid PostalCode format: {postal_code}")
    
    return errors


def validate_polling_station_data(polling_station_data: Dict[str, Any]) -> List[str]:
    """Validate polling station data.
    
    Args:
        polling_station_data: Dictionary containing polling station data.
        
    Returns:
        List of validation error messages, empty if valid.
    """
    errors = []
    
    # Required fields
    required_fields = ['PollingStationAddress', 'CountyCode', 'SettlementCode', 'OEVK']
    for field in required_fields:
        if field not in polling_station_data:
            errors.append(f"Missing required field: {field}")
        elif not polling_station_data[field]:
            errors.append(f"Empty required field: {field}")
    
    # CountyCode format validation
    if 'CountyCode' in polling_station_data and polling_station_data['CountyCode']:
        county_code = str(polling_station_data['CountyCode'])
        if not county_code.isdigit() or len(county_code) != 2:
            errors.append(f"Invalid CountyCode format: {county_code}")
    
    return errors


def validate_address_data(address_data: Dict[str, Any]) -> List[str]:
    """Validate address data.
    
    Args:
        address_data: Dictionary containing address data.
        
    Returns:
        List of validation error messages, empty if valid.
    """
    errors = []
    
    # Required fields
    required_fields = [
        'PublicSpaceName', 'PublicSpaceType', 'HouseNumber',
        'CountyCode', 'SettlementCode', 'OEVK', 'PostalCode'
    ]
    for field in required_fields:
        if field not in address_data:
            errors.append(f"Missing required field: {field}")
        elif not address_data[field]:
            errors.append(f"Empty required field: {field}")
    
    # CountyCode format validation
    if 'CountyCode' in address_data and address_data['CountyCode']:
        county_code = str(address_data['CountyCode'])
        if not county_code.isdigit() or len(county_code) != 2:
            errors.append(f"Invalid CountyCode format: {county_code}")
    
    # PostalCode format validation
    if 'PostalCode' in address_data and address_data['PostalCode']:
        postal_code = str(address_data['PostalCode'])
        if not postal_code.isdigit() or len(postal_code) != 4:
            errors.append(f"Invalid PostalCode format: {postal_code}")
    
    return errors


def log_validation_errors(entity_type: str, errors: List[str], data_id: Optional[str] = None) -> None:
    """Log validation errors in a structured way.
    
    Args:
        entity_type: Type of entity being validated (e.g., 'County', 'Settlement').
        errors: List of validation error messages.
        data_id: Optional identifier for the data being validated.
    """
    if errors:
        id_info = f" (ID: {data_id})" if data_id else ""
        logger.warning(f"Validation failed for {entity_type}{id_info}: {', '.join(errors)}")
    else:
        logger.debug(f"Validation passed for {entity_type}")


def validate_data_batch(entity_type: str, data_batch: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Validate a batch of data entities.
    
    Args:
        entity_type: Type of entities being validated.
        data_batch: List of data dictionaries to validate.
        
    Returns:
        Dictionary mapping entity identifiers to lists of error messages.
    """
    validation_functions = {
        'County': validate_county_data,
        'Settlement': validate_settlement_data,
        'NationalIndividualElectoralDistrict': validate_oevk_data,
        'SettlementIndividualElectoralDistrict': validate_tevk_data,
        'PostalCode': validate_postal_code_data,
        'PollingStation': validate_polling_station_data,
        'Address': validate_address_data
    }
    
    if entity_type not in validation_functions:
        raise ValueError(f"Unknown entity type: {entity_type}")
    
    validation_func = validation_functions[entity_type]
    results = {}
    
    for i, data in enumerate(data_batch):
        # Generate a simple identifier for logging
        data_id = f"{entity_type}_{i}"
        if 'CountyCode' in data:
            data_id = f"{entity_type}_{data.get('CountyCode', 'unknown')}"
        
        errors = validation_func(data)
        results[data_id] = errors
        log_validation_errors(entity_type, errors, data_id)
    
    return results