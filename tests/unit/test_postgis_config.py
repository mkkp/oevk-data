"""Unit tests for PostGIS configuration."""

import os
import pytest
from src.utils.config import Config, reload_config


class TestPostGISConfiguration:
    """Test suite for POSTGRESQL_USE_POSTGIS configuration."""

    def test_default_value_true(self):
        """Test that PostGIS defaults to enabled (true)."""
        # Create fresh config without environment variable
        if "POSTGRESQL_USE_POSTGIS" in os.environ:
            del os.environ["POSTGRESQL_USE_POSTGIS"]

        config = Config()
        settings = config.get_postgresql_settings()
        assert settings["use_postgis"] is True, "PostGIS should be enabled by default"

    def test_explicit_true(self):
        """Test explicit POSTGRESQL_USE_POSTGIS=true."""
        os.environ["POSTGRESQL_USE_POSTGIS"] = "true"
        config = Config()
        settings = config.get_postgresql_settings()
        assert settings["use_postgis"] is True
        del os.environ["POSTGRESQL_USE_POSTGIS"]

    def test_explicit_false(self):
        """Test explicit POSTGRESQL_USE_POSTGIS=false."""
        os.environ["POSTGRESQL_USE_POSTGIS"] = "false"
        config = Config()
        settings = config.get_postgresql_settings()
        assert settings["use_postgis"] is False
        del os.environ["POSTGRESQL_USE_POSTGIS"]

    def test_case_insensitive_true(self):
        """Test case-insensitive parsing for 'true'."""
        for value in ["True", "TRUE", "tRuE"]:
            os.environ["POSTGRESQL_USE_POSTGIS"] = value
            config = Config()
            settings = config.get_postgresql_settings()
            assert settings["use_postgis"] is True, f"'{value}' should be parsed as true"

        if "POSTGRESQL_USE_POSTGIS" in os.environ:
            del os.environ["POSTGRESQL_USE_POSTGIS"]

    def test_case_insensitive_false(self):
        """Test case-insensitive parsing for 'false'."""
        for value in ["False", "FALSE", "fAlSe"]:
            os.environ["POSTGRESQL_USE_POSTGIS"] = value
            config = Config()
            settings = config.get_postgresql_settings()
            assert settings["use_postgis"] is False, f"'{value}' should be parsed as false"

        if "POSTGRESQL_USE_POSTGIS" in os.environ:
            del os.environ["POSTGRESQL_USE_POSTGIS"]

    def test_invalid_value_defaults_false(self):
        """Test that invalid values are treated as false."""
        for value in ["invalid", "1", "0", "yes", "no"]:
            os.environ["POSTGRESQL_USE_POSTGIS"] = value
            config = Config()
            settings = config.get_postgresql_settings()
            assert settings["use_postgis"] is False, f"'{value}' should default to false"

        if "POSTGRESQL_USE_POSTGIS" in os.environ:
            del os.environ["POSTGRESQL_USE_POSTGIS"]

    def test_get_method_access(self):
        """Test accessing PostGIS setting via get() method."""
        os.environ["POSTGRESQL_USE_POSTGIS"] = "true"
        config = Config()
        assert config.get("postgresql.use_postgis") is True

        os.environ["POSTGRESQL_USE_POSTGIS"] = "false"
        config = Config()
        assert config.get("postgresql.use_postgis") is False

        if "POSTGRESQL_USE_POSTGIS" in os.environ:
            del os.environ["POSTGRESQL_USE_POSTGIS"]

    def test_reload_config(self):
        """Test that reload_config picks up environment changes."""
        # Set to false
        os.environ["POSTGRESQL_USE_POSTGIS"] = "false"
        config = reload_config()
        assert config.get_postgresql_settings()["use_postgis"] is False

        # Change to true
        os.environ["POSTGRESQL_USE_POSTGIS"] = "true"
        config = reload_config()
        assert config.get_postgresql_settings()["use_postgis"] is True

        if "POSTGRESQL_USE_POSTGIS" in os.environ:
            del os.environ["POSTGRESQL_USE_POSTGIS"]
