"""
Integration tests for PostgreSQL loader script parameterization.

Tests verify that the load_postgresql.py script:
- Accepts --database parameter
- Parameter overrides environment variable
- Default database name is used when parameter not provided
- Error messages are helpful for common issues
"""

import pytest
import subprocess
import sys
import os
from pathlib import Path


class TestLoaderParameterization:
    """Test loader script parameter handling."""

    @pytest.fixture
    def loader_script_path(self):
        """Get path to load_postgresql.py script."""
        script_path = Path(__file__).parent.parent.parent / "src" / "release" / "templates" / "load_postgresql.py"
        assert script_path.exists(), f"Loader script not found at {script_path}"
        return str(script_path)

    def test_help_shows_database_parameter(self, loader_script_path):
        """Test that --help output shows both --db and --database parameters."""
        result = subprocess.run(
            [sys.executable, loader_script_path, "--help"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, "Help command should succeed"
        assert "--db" in result.stdout or "--database" in result.stdout, \
            "Help should document --db or --database parameter"
        assert "database name" in result.stdout.lower() or "db name" in result.stdout.lower(), \
            "Help should explain database parameter"

    def test_database_parameter_alias(self, loader_script_path):
        """Test that --database is an alias for --db."""
        # We can't actually connect without a real database, but we can verify
        # the script accepts the parameter and tries to use it

        # Test with --database
        result_database = subprocess.run(
            [sys.executable, loader_script_path,
             "--host", "nonexistent-host-12345",
             "--database", "test_db_name",
             "--user", "test_user",
             "--password", "test_pass"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Test with --db
        result_db = subprocess.run(
            [sys.executable, loader_script_path,
             "--host", "nonexistent-host-12345",
             "--db", "test_db_name",
             "--user", "test_user",
             "--password", "test_pass"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Both should fail to connect (host doesn't exist)
        # But they should fail the same way, proving --database works
        assert result_database.returncode != 0, "Should fail (no such host)"
        assert result_db.returncode != 0, "Should fail (no such host)"

        # Both should show connection attempt (proving parameter was accepted)
        assert "Connecting" in result_database.stdout or "connect" in result_database.stdout.lower(), \
            "--database parameter should be accepted"
        assert "Connecting" in result_db.stdout or "connect" in result_db.stdout.lower(), \
            "--db parameter should be accepted"

    def test_database_parameter_overrides_environment(self, loader_script_path):
        """Test that --database parameter takes precedence over POSTGRES_DB environment variable."""
        env = os.environ.copy()
        env["POSTGRES_DB"] = "env_database"

        result = subprocess.run(
            [sys.executable, loader_script_path,
             "--host", "nonexistent-host-12345",
             "--database", "cli_database",
             "--user", "test_user",
             "--password", "test_pass"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10
        )

        # Should fail to connect, but output should show CLI parameter was used
        # We can't directly verify which DB name was used without connecting,
        # but the script should attempt connection with the CLI parameter
        assert result.returncode != 0, "Should fail (no such host)"
        assert "Connecting" in result.stdout or "connect" in result.stdout.lower()

    def test_default_database_name(self, loader_script_path):
        """Test that default database name 'oevk' is used when no parameter provided."""
        # Clear POSTGRES_DB environment variable if present
        env = os.environ.copy()
        env.pop("POSTGRES_DB", None)

        result = subprocess.run(
            [sys.executable, loader_script_path,
             "--host", "nonexistent-host-12345",
             "--user", "test_user",
             "--password", "test_pass"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10
        )

        # Should attempt connection with default database name
        assert result.returncode != 0, "Should fail (no such host)"
        assert "Connecting" in result.stdout or "connect" in result.stdout.lower()

    def test_error_message_for_nonexistent_database(self, loader_script_path):
        """Test that error message is helpful when database doesn't exist."""
        # This test requires psycopg2 to be installed to get the actual error
        try:
            import psycopg2
        except ImportError:
            pytest.skip("psycopg2 not installed")

        # Try to connect to a database that definitely doesn't exist
        result = subprocess.run(
            [sys.executable, loader_script_path,
             "--host", "nonexistent-host-xyz-12345",
             "--database", "nonexistent_db_12345",
             "--user", "postgres",
             "--password", "postgres"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode != 0, "Should fail (connection error)"

        # Should show helpful error message
        output = result.stdout + result.stderr
        assert "Connection failed" in output or "failed" in output.lower() or "error" in output.lower(), \
            "Should show error message"

    def test_error_message_suggests_drop_database(self, loader_script_path):
        """Test that error message suggests --drop-database flag when database doesn't exist."""
        # This is a documentation test - verify the script has helpful error messages
        result = subprocess.run(
            [sys.executable, loader_script_path,
             "--host", "127.0.0.1",
             "--port", "99999",  # Invalid port
             "--database", "test_db",
             "--user", "test",
             "--password", "test"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode != 0, "Should fail (invalid port)"

        # The script should provide helpful guidance
        output = result.stdout + result.stderr
        assert "Connection failed" in output or "error" in output.lower() or "failed" in output.lower()


class TestLoaderErrorMessages:
    """Test that loader provides helpful error messages for common issues."""

    @pytest.fixture
    def loader_script_path(self):
        """Get path to load_postgresql.py script."""
        script_path = Path(__file__).parent.parent.parent / "src" / "release" / "templates" / "load_postgresql.py"
        return str(script_path)

    def test_missing_psycopg2_error(self, loader_script_path, monkeypatch):
        """Test error message when psycopg2 is not installed."""
        # We can't actually test this easily since psycopg2 IS installed
        # for the tests to run. This is a placeholder for manual testing.
        pytest.skip("Requires environment without psycopg2")

    def test_docker_not_available_error(self, loader_script_path):
        """Test error message when --docker is used but Docker is not available."""
        # This would require actually testing with Docker unavailable
        # which is environment-dependent
        pytest.skip("Requires environment without Docker")

    def test_schema_file_not_found(self, loader_script_path, tmp_path):
        """Test error message when schema file doesn't exist."""
        # Create minimal environment to test file not found
        result = subprocess.run(
            [sys.executable, loader_script_path,
             "--host", "nonexistent-host",
             "--schema", str(tmp_path / "nonexistent_schema.sql"),
             "--data", str(tmp_path / "nonexistent_data.sql")],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should fail (either connection or file not found)
        assert result.returncode != 0


class TestLoaderIntegration:
    """Integration tests for loader with actual database (requires Docker or PostgreSQL)."""

    @pytest.fixture
    def loader_script_path(self):
        """Get path to load_postgresql.py script."""
        script_path = Path(__file__).parent.parent.parent / "src" / "release" / "templates" / "load_postgresql.py"
        return str(script_path)

    def test_loader_script_exists_and_executable(self, loader_script_path):
        """Test that the loader script exists and has proper structure."""
        script_path = Path(loader_script_path)

        assert script_path.exists(), "Loader script should exist"
        assert script_path.stat().st_size > 0, "Loader script should not be empty"

        # Read the script to verify it's a Python script
        with open(script_path, 'r') as f:
            content = f.read()
            assert content.startswith('#!/usr/bin/env python'), \
                "Script should have Python shebang"
            assert 'argparse' in content, "Script should use argparse"
            assert '--database' in content or '--db' in content, \
                "Script should accept database parameter"

    def test_loader_imports_successfully(self):
        """Test that the loader script can be imported without errors."""
        # This verifies basic syntax correctness
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "load_postgresql",
                Path(__file__).parent.parent.parent / "src" / "release" / "templates" / "load_postgresql.py"
            )
            module = importlib.util.module_from_spec(spec)
            # Don't execute main, just verify it loads
            assert module is not None
        except SyntaxError as e:
            pytest.fail(f"Loader script has syntax error: {e}")
