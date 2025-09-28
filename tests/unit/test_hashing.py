"""Unit tests for hashing logic."""

import pytest
from src.etl.hashing import (
    hash_county_id,
    hash_settlement_id,
    hash_oevk_id,
    hash_tevk_id,
    hash_postal_code_id,
    hash_postal_code_settlement_id,
    hash_polling_station_id,
    hash_address_id
)


class TestHashingFunctions:
    """Test cases for hashing functions."""

    def test_hash_county_id(self):
        """Test county ID hashing."""
        county_code = "01"
        
        result = hash_county_id(county_code)
        
        assert isinstance(result, str)
        assert len(result) == 16  # xxhash64 produces 16-character hex string
        # Test that the same input produces the same output
        assert result == hash_county_id(county_code)

    def test_hash_settlement_id(self):
        """Test settlement ID hashing."""
        county_code = "01"
        settlement_code = "001"
        
        result = hash_settlement_id(county_code, settlement_code)
        
        assert isinstance(result, str)
        assert len(result) == 16
        # Test that the same input produces the same output
        assert result == hash_settlement_id(county_code, settlement_code)

    def test_hash_oevk_id(self):
        """Test OEVK ID hashing."""
        county_code = "01"
        oevk = "01"
        
        result = hash_oevk_id(county_code, oevk)
        
        assert isinstance(result, str)
        assert len(result) == 16
        # Test that the same input produces the same output
        assert result == hash_oevk_id(county_code, oevk)

    def test_hash_tevk_id(self):
        """Test TEVK ID hashing."""
        county_code = "01"
        settlement_code = "001"
        tevk = "01"
        oevk = "01"
        
        result = hash_tevk_id(county_code, settlement_code, tevk, oevk)
        
        assert isinstance(result, str)
        assert len(result) == 16
        # Test that the same input produces the same output
        assert result == hash_tevk_id(county_code, settlement_code, tevk, oevk)

    def test_hash_postal_code_id(self):
        """Test postal code ID hashing."""
        postal_code = "1011"
        
        result = hash_postal_code_id(postal_code)
        
        assert isinstance(result, str)
        assert len(result) == 16
        # Test that the same input produces the same output
        assert result == hash_postal_code_id(postal_code)

    def test_hash_postal_code_settlement_id(self):
        """Test postal code settlement ID hashing."""
        postal_code_id = "567890abcdef1234"
        settlement_id = "234567890abcdef1"
        
        result = hash_postal_code_settlement_id(postal_code_id, settlement_id)
        
        assert isinstance(result, str)
        assert len(result) == 16
        # Test that the same input produces the same output
        assert result == hash_postal_code_settlement_id(postal_code_id, settlement_id)

    def test_hash_polling_station_id(self):
        """Test polling station ID hashing."""
        county_code = "01"
        settlement_code = "001"
        oevk = "01"
        tevk = "01"
        polling_station_address = "Main Street 1"
        
        result = hash_polling_station_id(
            county_code, settlement_code, oevk, tevk, polling_station_address
        )
        
        assert isinstance(result, str)
        assert len(result) == 16
        # Test that the same input produces the same output
        assert result == hash_polling_station_id(
            county_code, settlement_code, oevk, tevk, polling_station_address
        )

    def test_hash_address_id(self):
        """Test address ID hashing."""
        address_components = {
            "county_code": "01",
            "settlement_code": "001",
            "public_space_name": "Main Street",
            "public_space_type": "utca",
            "house_number": "1",
            "building": None,
            "staircase": None,
            "postal_code": "1011"
        }
        
        result = hash_address_id(address_components)
        
        assert isinstance(result, str)
        assert len(result) == 16
        # Test that the same input produces the same output
        assert result == hash_address_id(address_components)

    def test_hashing_deterministic(self):
        """Test that hashing produces the same result for same inputs."""
        county_code = "01"
        
        result1 = hash_county_id(county_code)
        result2 = hash_county_id(county_code)
        
        assert result1 == result2

    def test_hashing_different_inputs_produce_different_hashes(self):
        """Test that different inputs produce different hashes."""
        result1 = hash_county_id("01")
        result2 = hash_county_id("02")
        
        assert result1 != result2

    def test_hashing_handles_none_values(self):
        """Test that hashing handles None values appropriately."""
        # Test with None values in TEVK
        result = hash_tevk_id("01", "001", None, "01")
        
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hashing_handles_empty_strings(self):
        """Test that hashing handles empty strings appropriately."""
        result = hash_county_id("")
        
        assert isinstance(result, str)
        assert len(result) == 16