"""Unit tests for public space hashing functions."""

import pytest
from src.etl.hashing import (
    hash_public_space_name_id,
    hash_public_space_type_id,
    hash_settlement_public_spaces_id,
)


class TestPublicSpaceHashing:
    """Test public space hashing functions."""

    def test_hash_public_space_name_id_basic(self):
        """Test basic public space name hashing."""
        name = "Kossuth"
        result = hash_public_space_name_id(name)

        assert isinstance(result, str)
        assert len(result) == 16  # xxhash64 produces 16-character hex string
        assert result == hash_public_space_name_id(name)  # deterministic

    def test_hash_public_space_name_id_empty(self):
        """Test public space name hashing with empty string."""
        result = hash_public_space_name_id("")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_public_space_name_id_none(self):
        """Test public space name hashing with None."""
        result = hash_public_space_name_id(None)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_public_space_name_id_hungarian_chars(self):
        """Test public space name hashing with Hungarian characters."""
        name = "Árpád"
        result = hash_public_space_name_id(name)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_public_space_type_id_basic(self):
        """Test basic public space type hashing."""
        space_type = "utca"
        result = hash_public_space_type_id(space_type)

        assert isinstance(result, str)
        assert len(result) == 16
        assert result == hash_public_space_type_id(space_type)  # deterministic

    def test_hash_public_space_type_id_empty(self):
        """Test public space type hashing with empty string."""
        result = hash_public_space_type_id("")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_public_space_type_id_none(self):
        """Test public space type hashing with None."""
        result = hash_public_space_type_id(None)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_public_space_type_id_various_types(self):
        """Test public space type hashing with various Hungarian types."""
        types = ["utca", "tér", "köz", "út", "sétány", "park"]

        for space_type in types:
            result = hash_public_space_type_id(space_type)
            assert isinstance(result, str)
            assert len(result) == 16

    def test_hash_settlement_public_spaces_id_basic(self):
        """Test basic settlement public spaces hashing."""
        settlement_id = "abc123"
        public_space_name_id = "def456"
        public_space_type_id = "ghi789"

        result = hash_settlement_public_spaces_id(
            settlement_id, public_space_name_id, public_space_type_id
        )

        assert isinstance(result, str)
        assert len(result) == 16
        assert result == hash_settlement_public_spaces_id(
            settlement_id, public_space_name_id, public_space_type_id
        )  # deterministic

    def test_hash_settlement_public_spaces_id_empty(self):
        """Test settlement public spaces hashing with empty strings."""
        result = hash_settlement_public_spaces_id("", "", "")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_settlement_public_spaces_id_none(self):
        """Test settlement public spaces hashing with None values."""
        result = hash_settlement_public_spaces_id(None, None, None)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_settlement_public_spaces_id_partial_none(self):
        """Test settlement public spaces hashing with partial None values."""
        result = hash_settlement_public_spaces_id("abc123", None, "ghi789")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_consistency_across_functions(self):
        """Test that hashing is consistent across different function calls."""
        name = "Petőfi"
        space_type = "utca"
        settlement_id = "settlement_123"

        name_hash1 = hash_public_space_name_id(name)
        name_hash2 = hash_public_space_name_id(name)

        type_hash1 = hash_public_space_type_id(space_type)
        type_hash2 = hash_public_space_type_id(space_type)

        relationship_hash1 = hash_settlement_public_spaces_id(
            settlement_id, name_hash1, type_hash1
        )
        relationship_hash2 = hash_settlement_public_spaces_id(
            settlement_id, name_hash2, type_hash2
        )

        assert name_hash1 == name_hash2
        assert type_hash1 == type_hash2
        assert relationship_hash1 == relationship_hash2
