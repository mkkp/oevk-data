"""Integration tests for PostgreSQL verification and dump creation."""

import os
import pytest
import subprocess
from pathlib import Path

from src.utils.docker_postgresql import DockerPostgreSQLManager
from src.etl.postgresql_verify import verify_and_dump_postgresql


@pytest.fixture(scope="module")
def sample_sql_files(tmp_path_factory):
    """Create sample SQL files for testing."""
    test_dir = tmp_path_factory.mktemp("postgresql_verify")

    # Create schema.sql
    schema_sql = """
-- Test schema
CREATE TABLE test_table (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    value INTEGER
);

CREATE INDEX idx_test_name ON test_table(name);
"""
    schema_path = test_dir / "schema.sql"
    schema_path.write_text(schema_sql)

    # Create data.sql
    data_sql = """
-- Test data
INSERT INTO test_table (id, name, value) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'Test 1', 100),
    ('550e8400-e29b-41d4-a716-446655440001', 'Test 2', 200),
    ('550e8400-e29b-41d4-a716-446655440002', 'Test 3', 300)
ON CONFLICT DO NOTHING;
"""
    data_path = test_dir / "data.sql"
    data_path.write_text(data_sql)

    return test_dir


def is_docker_available():
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
class TestDockerPostgreSQLManager:
    """Test Docker PostgreSQL container management."""

    def test_create_and_cleanup_container(self):
        """Test creating and cleaning up a container."""
        manager = DockerPostgreSQLManager(container_name="test-oevk-verify")

        try:
            # Create container
            container_id = manager.create_container()
            assert container_id is not None
            assert len(container_id) > 0

            # Wait for ready
            is_ready = manager.wait_for_ready(timeout=30)
            assert is_ready, "PostgreSQL should become ready"

            # Get connection info
            conn_info = manager.get_connection_info()
            assert conn_info["host"] == "localhost"
            assert conn_info["database"] == "oevk"
            assert conn_info["user"] == "oevk"

        finally:
            # Cleanup
            manager.stop_and_remove_container()

            # Verify cleanup
            container_id = manager._get_container_id()
            assert container_id is None, "Container should be removed"

    def test_container_already_exists(self):
        """Test handling when container already exists."""
        manager = DockerPostgreSQLManager(container_name="test-oevk-verify-2")

        try:
            # Create first container
            manager.create_container()
            manager.wait_for_ready(timeout=30)

            # Try to create again (should remove old and create new)
            container_id = manager.create_container()
            assert container_id is not None

            is_ready = manager.wait_for_ready(timeout=30)
            assert is_ready

        finally:
            manager.stop_and_remove_container()


@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
class TestPostgreSQLVerify:
    """Test PostgreSQL verification and dump creation."""

    def test_verify_and_dump_with_sample_data(self, sample_sql_files):
        """Test verification and dump creation with sample data."""
        dump_path = None

        try:
            # Run verification
            dump_path = verify_and_dump_postgresql(
                exports_dir=str(sample_sql_files),
                container_name="test-verify-sample",
                cleanup=True,
            )

            # Verify dump was created
            assert dump_path is not None
            assert Path(dump_path).exists()
            assert Path(dump_path).suffix == ".gz"
            assert Path(dump_path).stat().st_size > 0

            # Verify filename format
            filename = Path(dump_path).name
            assert filename.startswith("oevk_db_")
            assert filename.endswith(".sql.gz")

        finally:
            # Cleanup dump file
            if dump_path and Path(dump_path).exists():
                Path(dump_path).unlink()

    def test_verify_missing_schema_file(self, tmp_path):
        """Test error handling when schema.sql is missing."""
        # Create directory with only data.sql
        data_sql = "INSERT INTO test (id) VALUES (1);"
        (tmp_path / "data.sql").write_text(data_sql)

        with pytest.raises(FileNotFoundError, match="schema.sql not found"):
            verify_and_dump_postgresql(
                exports_dir=str(tmp_path),
                container_name="test-verify-missing-schema",
                cleanup=True,
            )

    def test_verify_missing_data_file(self, tmp_path):
        """Test error handling when data.sql is missing."""
        # Create directory with only schema.sql
        schema_sql = "CREATE TABLE test (id INTEGER);"
        (tmp_path / "schema.sql").write_text(schema_sql)

        with pytest.raises(FileNotFoundError, match="data.sql not found"):
            verify_and_dump_postgresql(
                exports_dir=str(tmp_path),
                container_name="test-verify-missing-data",
                cleanup=True,
            )


@pytest.mark.skipif(not is_docker_available(), reason="Docker not available")
class TestPostgreSQLVerifyEdgeCases:
    """Test edge cases in PostgreSQL verification."""

    def test_verify_with_empty_data(self, tmp_path):
        """Test verification with schema but no data."""
        # Create schema
        schema_sql = """
CREATE TABLE empty_table (
    id UUID PRIMARY KEY,
    name TEXT
);
"""
        (tmp_path / "schema.sql").write_text(schema_sql)

        # Create empty data file
        data_sql = "-- No data"
        (tmp_path / "data.sql").write_text(data_sql)

        # Should fail because no rows found
        with pytest.raises(RuntimeError, match="No rows found in database"):
            verify_and_dump_postgresql(
                exports_dir=str(tmp_path),
                container_name="test-verify-empty",
                cleanup=True,
            )

    def test_verify_with_large_dataset(self, tmp_path):
        """Test verification with larger dataset."""
        # Create schema
        schema_sql = """
CREATE TABLE large_table (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    value INTEGER
);
"""
        (tmp_path / "schema.sql").write_text(schema_sql)

        # Create data with 1000 rows
        data_lines = ["-- Large dataset"]
        for i in range(1000):
            uuid = f"550e8400-e29b-41d4-a716-{i:012d}"
            data_lines.append(
                f"INSERT INTO large_table (id, name, value) VALUES ('{uuid}', 'Name {i}', {i}) ON CONFLICT DO NOTHING;"
            )

        (tmp_path / "data.sql").write_text("\n".join(data_lines))

        dump_path = None
        try:
            dump_path = verify_and_dump_postgresql(
                exports_dir=str(tmp_path),
                container_name="test-verify-large",
                cleanup=True,
            )

            assert dump_path is not None
            assert Path(dump_path).exists()

        finally:
            if dump_path and Path(dump_path).exists():
                Path(dump_path).unlink()
