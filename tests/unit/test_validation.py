"""Unit tests for data validation utilities."""

import pytest
from src.utils.validation import (
    validate_county_data, validate_settlement_data, validate_oevk_data,
    validate_tevk_data, validate_postal_code_data, validate_polling_station_data,
    validate_address_data, validate_data_batch, log_validation_errors
)


class TestCountyValidation:
    """Test county data validation."""
    
    def test_valid_county_data(self):
        """Test validation of valid county data."""
        data = {
            'CountyCode': '01',
            'CountyName': 'Budapest'
        }
        errors = validate_county_data(data)
        assert errors == []
    
    def test_missing_required_field(self):
        """Test validation with missing required field."""
        data = {
            'CountyCode': '01'
            # Missing CountyName
        }
        errors = validate_county_data(data)
        assert 'Missing required field: CountyName' in errors
    
    def test_empty_required_field(self):
        """Test validation with empty required field."""
        data = {
            'CountyCode': '01',
            'CountyName': ''
        }
        errors = validate_county_data(data)
        assert 'Empty required field: CountyName' in errors
    
    def test_invalid_county_code_format(self):
        """Test validation with invalid county code format."""
        data = {
            'CountyCode': 'A1',  # Not all digits
            'CountyName': 'Budapest'
        }
        errors = validate_county_data(data)
        assert 'Invalid CountyCode format: A1' in errors


class TestSettlementValidation:
    """Test settlement data validation."""
    
    def test_valid_settlement_data(self):
        """Test validation of valid settlement data."""
        data = {
            'SettlementCode': '001',
            'SettlementName': 'Budapest I. kerület',
            'CountyCode': '01'
        }
        errors = validate_settlement_data(data)
        assert errors == []
    
    def test_invalid_settlement_code_format(self):
        """Test validation with invalid settlement code format."""
        data = {
            'SettlementCode': 'A01',  # Not all digits
            'SettlementName': 'Budapest I. kerület',
            'CountyCode': '01'
        }
        errors = validate_settlement_data(data)
        assert 'Invalid SettlementCode format: A01' in errors


class TestOEVKValidation:
    """Test OEVK data validation."""
    
    def test_valid_oevk_data(self):
        """Test validation of valid OEVK data."""
        data = {
            'OEVK': '01',
            'CountyCode': '01'
        }
        errors = validate_oevk_data(data)
        assert errors == []
    
    def test_invalid_oevk_format(self):
        """Test validation with invalid OEVK format."""
        data = {
            'OEVK': 'A1',  # Not all digits
            'CountyCode': '01'
        }
        errors = validate_oevk_data(data)
        assert 'Invalid OEVK format: A1' in errors


class TestTEVKValidation:
    """Test TEVK data validation."""
    
    def test_valid_tevk_data(self):
        """Test validation of valid TEVK data."""
        data = {
            'CountyCode': '01',
            'SettlementCode': '001',
            'OEVK': '01',
            'TEVK': '01'
        }
        errors = validate_tevk_data(data)
        assert errors == []
    
    def test_tevk_without_optional_field(self):
        """Test validation of TEVK data without optional TEVK field."""
        data = {
            'CountyCode': '01',
            'SettlementCode': '001',
            'OEVK': '01'
            # TEVK is optional
        }
        errors = validate_tevk_data(data)
        assert errors == []


class TestPostalCodeValidation:
    """Test postal code data validation."""
    
    def test_valid_postal_code_data(self):
        """Test validation of valid postal code data."""
        data = {
            'PostalCode': '1011'
        }
        errors = validate_postal_code_data(data)
        assert errors == []
    
    def test_invalid_postal_code_format(self):
        """Test validation with invalid postal code format."""
        data = {
            'PostalCode': '101',  # Wrong length
        }
        errors = validate_postal_code_data(data)
        assert 'Invalid PostalCode format: 101' in errors


class TestPollingStationValidation:
    """Test polling station data validation."""
    
    def test_valid_polling_station_data(self):
        """Test validation of valid polling station data."""
        data = {
            'PollingStationAddress': 'Vár utca 1.',
            'CountyCode': '01',
            'SettlementCode': '001',
            'OEVK': '01'
        }
        errors = validate_polling_station_data(data)
        assert errors == []


class TestAddressValidation:
    """Test address data validation."""
    
    def test_valid_address_data(self):
        """Test validation of valid address data."""
        data = {
            'PublicSpaceName': 'Vár',
            'PublicSpaceType': 'utca',
            'HouseNumber': '1',
            'CountyCode': '01',
            'SettlementCode': '001',
            'OEVK': '01',
            'PostalCode': '1011'
        }
        errors = validate_address_data(data)
        assert errors == []
    
    def test_address_with_optional_fields(self):
        """Test validation of address data with optional fields."""
        data = {
            'PublicSpaceName': 'Vár',
            'PublicSpaceType': 'utca',
            'HouseNumber': '1',
            'Building': 'A',
            'Staircase': '1',
            'CountyCode': '01',
            'SettlementCode': '001',
            'OEVK': '01',
            'PostalCode': '1011'
        }
        errors = validate_address_data(data)
        assert errors == []


class TestBatchValidation:
    """Test batch validation functionality."""
    
    def test_valid_county_batch(self):
        """Test validation of a batch of valid county data."""
        batch = [
            {'CountyCode': '01', 'CountyName': 'Budapest'},
            {'CountyCode': '02', 'CountyName': 'Pest'}
        ]
        results = validate_data_batch('County', batch)
        
        # All should have no errors
        for errors in results.values():
            assert errors == []
    
    def test_mixed_batch_validation(self):
        """Test validation of a batch with mixed valid and invalid data."""
        batch = [
            {'CountyCode': '01', 'CountyName': 'Budapest'},  # Valid
            {'CountyCode': 'A1', 'CountyName': 'Invalid'},   # Invalid county code
            {'CountyCode': '02'},                            # Missing CountyName
        ]
        results = validate_data_batch('County', batch)
        
        # Check that we have results for all items
        assert len(results) == 3
        
        # First should be valid
        assert results['County_01'] == []
        
        # Second should have format error
        assert 'Invalid CountyCode format: A1' in results['County_A1']
        
        # Third should have missing field error
        assert 'Missing required field: CountyName' in results['County_02']
    
    def test_unknown_entity_type(self):
        """Test validation with unknown entity type."""
        batch = [{'Test': 'data'}]
        
        with pytest.raises(ValueError, match="Unknown entity type: UnknownType"):
            validate_data_batch('UnknownType', batch)


class TestLogging:
    """Test validation error logging."""
    
    def test_log_validation_errors_with_errors(self, caplog):
        """Test logging when there are validation errors."""
        errors = ['Missing required field: CountyName', 'Invalid CountyCode format']
        log_validation_errors('County', errors, '01')
        
        # Check that warning was logged
        assert 'Validation failed for County (ID: 01)' in caplog.text
        assert 'Missing required field: CountyName' in caplog.text
    
    def test_log_validation_errors_no_errors(self, caplog):
        """Test logging when there are no validation errors."""
        # Set logging level to DEBUG to capture debug messages
        import logging
        caplog.set_level(logging.DEBUG)
        
        errors = []
        log_validation_errors('County', errors, '01')
        
        # Check that debug was logged
        assert 'Validation passed for County' in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])