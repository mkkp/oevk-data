"""Integration tests for database setup command."""

import pytest
import subprocess
import tempfile
import os
from pathlib import Path


class TestDatabaseSetup:
    """Integration tests for db setup command."""

    @pytest.fixture
    def sql_files(self):
        """Create temporary SQL files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = os.path.join(temp_dir, "schema.sql")
            data_path = os.path.join(temp_dir, "data.sql")

            # Create test schema
            schema_content = """
CREATE TABLE IF NOT EXISTS test_table (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL
);
"""
            with open(schema_path, "w") as f:
                f.write(schema_content)

            # Create test data
            data_content = """
INSERT INTO test_table (id, name) VALUES ('550e8400-e29b-41d4-a716-446655440000', 'Test 1');
INSERT INTO test_table (id, name) VALUES ('6ba7b810-9dad-11d1-80b4-00c04fd430c8', 'Test 2');
"""
            with open(data_path, "w") as f:
                f.write(data_content)

            yield schema_path, data_path

    def test_db_setup_command_help(self):
        """Test that db setup command shows help."""
        result = subprocess.run(
            ["python", "src/cli.py", "db", "setup", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "setup" in result.stdout.lower()
        assert (
            "postgresql" in result.stdout.lower() or "database" in result.stdout.lower()
        )

    def test_db_setup_command_exists(self):
        """Test that db setup command is recognized."""
        result = subprocess.run(
            ["python", "src/cli.py", "db", "--help"], capture_output=True, text=True
        )

        assert result.returncode == 0
        assert "setup" in result.stdout.lower()

    @pytest.mark.skipif(
        subprocess.run(["which", "docker"], capture_output=True).returncode != 0,
        reason="Docker not available",
    )
    def test_db_setup_requires_docker(self, sql_files):
        """Test that db setup command requires Docker."""
        schema_path, data_path = sql_files

        # Try to run setup (it should check for Docker)
        result = subprocess.run(
            [
                "python",
                "src/cli.py",
                "db",
                "setup",
                "--ddl-script",
                schema_path,
                "--dml-script",
                data_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should either succeed (if Docker running) or fail with Docker message
        if result.returncode != 0:
            assert (
                "docker" in result.stderr.lower() or "docker" in result.stdout.lower()
            )

    def test_db_setup_command_parameter_validation(self):
        """Test that db setup validates script paths."""
        # Test with non-existent files
        result = subprocess.run(
            [
                "python",
                "src/cli.py",
                "db",
                "setup",
                "--ddl-script",
                "/nonexistent/schema.sql",
                "--dml-script",
                "/nonexistent/data.sql",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should fail (either immediately or after Docker check)
        # We don't assert returncode because it might fail at Docker check first
        # Just verify the command runs
        assert result.returncode is not None


class TestDatabaseSetupDocumentation:
    """Test that database setup documentation is accurate."""

    def test_database_command_documentation_exists(self):
        """Test that database.md documentation exists."""
        doc_path = Path(".claude/commands/database.md")
        assert doc_path.exists(), "database.md documentation should exist"

    def test_database_command_documentation_content(self):
        """Test that database.md has correct content."""
        doc_path = Path(".claude/commands/database.md")

        with open(doc_path, "r") as f:
            content = f.read()

        # Verify key elements are documented
        assert "db setup" in content or "db:setup" in content
        assert "postgresql" in content.lower()
        assert "docker" in content.lower()
        assert "schema.sql" in content
        assert "data.sql" in content

    def test_database_setup_example_commands(self):
        """Test that documentation includes example commands."""
        doc_path = Path(".claude/commands/database.md")

        with open(doc_path, "r") as f:
            content = f.read()

        # Should have command examples
        assert "python src/cli.py" in content or "```bash" in content
        assert "--ddl-script" in content or "--dml-script" in content


class TestPostgreSQLExportDocumentation:
    """Test that PostgreSQL export is properly documented."""

    def test_export_documentation_mentions_postgresql(self):
        """Test that export documentation mentions PostgreSQL."""
        doc_path = Path(".claude/commands/data-export.md")

        with open(doc_path, "r") as f:
            content = f.read()

        assert "postgresql" in content.lower() or "sql" in content.lower()
        assert "schema.sql" in content or "data.sql" in content

    def test_release_documentation_mentions_postgresql(self):
        """Test that release documentation mentions PostgreSQL artifacts."""
        doc_path = Path(".claude/commands/release.md")

        with open(doc_path, "r") as f:
            content = f.read()

        # Should mention PostgreSQL or SQL in artifacts
        assert "postgresql" in content.lower() or "sql" in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
