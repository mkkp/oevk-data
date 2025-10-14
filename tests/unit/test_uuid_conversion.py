"""Unit tests for xxhash64 to UUIDv3 conversion."""

import pytest
import uuid
from src.etl.export import to_uuid3, OEVK_NAMESPACE
from src.etl.export_canonical_v3 import (
    to_uuid3 as to_uuid3_v3,
    OEVK_NAMESPACE as OEVK_NAMESPACE_V3,
)


class TestUUIDConversion:
    """Test UUID v3 conversion from xxhash64 hashes."""

    def test_oevk_namespace_consistency(self):
        """Test that OEVK namespace is consistent across modules."""
        # Both modules should use the same namespace
        assert OEVK_NAMESPACE == OEVK_NAMESPACE_V3

        # Namespace should be derived from 'oevk.hu'
        expected = uuid.uuid3(uuid.NAMESPACE_DNS, "oevk.hu")
        assert OEVK_NAMESPACE == expected

    def test_to_uuid3_with_valid_hash(self):
        """Test UUID v3 generation with valid xxhash64 hash."""
        # Test with a sample xxhash64 hash
        test_hash = "a1b2c3d4e5f6g7h8"
        result = to_uuid3(test_hash)

        # Result should be a valid UUID string
        assert result is not None
        assert isinstance(result, str)

        # Should be parseable as UUID
        parsed = uuid.UUID(result)
        assert parsed.version == 3  # UUID v3

    def test_to_uuid3_with_none(self):
        """Test UUID v3 generation with None value."""
        result = to_uuid3(None)
        assert result is None

    def test_to_uuid3_with_empty_string(self):
        """Test UUID v3 generation with empty string."""
        result = to_uuid3("")
        assert result is None

    def test_to_uuid3_consistency(self):
        """Test that same input always produces same UUID."""
        test_hash = "test123456789abc"

        result1 = to_uuid3(test_hash)
        result2 = to_uuid3(test_hash)

        assert result1 == result2

    def test_to_uuid3_different_inputs(self):
        """Test that different inputs produce different UUIDs."""
        hash1 = "a1b2c3d4e5f6g7h8"
        hash2 = "h8g7f6e5d4c3b2a1"

        result1 = to_uuid3(hash1)
        result2 = to_uuid3(hash2)

        assert result1 != result2

    def test_to_uuid3_v3_consistency(self):
        """Test that export_canonical_v3 module has consistent UUID conversion."""
        test_hash = "canonical123abc"

        result_v3 = to_uuid3_v3(test_hash)
        result_export = to_uuid3(test_hash)

        # Both modules should produce the same UUID
        assert result_v3 == result_export

    def test_to_uuid3_with_numeric_string(self):
        """Test UUID v3 generation with numeric string."""
        test_hash = "1234567890123456"
        result = to_uuid3(test_hash)

        assert result is not None
        assert isinstance(result, str)
        uuid.UUID(result)  # Should not raise

    def test_to_uuid3_output_format(self):
        """Test that UUID output is in standard format."""
        test_hash = "test_hash_value"
        result = to_uuid3(test_hash)

        # Standard UUID format: 8-4-4-4-12
        parts = result.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_to_uuid3_with_integer(self):
        """Test UUID v3 generation with integer input."""
        test_int = 123456
        result = to_uuid3(test_int)

        assert result is not None
        assert isinstance(result, str)
        uuid.UUID(result)  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
