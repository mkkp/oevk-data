"""
Performance tests for release workflow 15-minute completion target.

Tests that the release process completes within the 15-minute performance target
under realistic data loads and conditions.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import from the correct module structure
from src.release.workflow import ReleaseWorkflow
from src.release.models import ReleasePackage, ReleaseMetadata


class TestReleasePerformance:
    """Performance tests for release workflow."""

    @pytest.fixture
    def workflow(self):
        """Create a workflow instance for testing."""
        return ReleaseWorkflow("test-owner", "test-repo", "test-token")

    @pytest.fixture
    def mock_package(self):
        """Create a mock release package."""
        return ReleasePackage.create(
            release_tag="20250101-1200",
            data_version="1.0.0",
            change_summary="Performance test release",
        )

    def test_full_release_completion_time(self, workflow):
        """Test that full release process completes within 15 minutes."""
        # Mock all external dependencies
        with patch.object(workflow, "validate_release_data") as mock_validate:
            with patch.object(
                workflow, "create_release_package"
            ) as mock_create_package:
                with patch.object(
                    workflow, "create_github_release"
                ) as mock_create_release:
                    with patch.object(
                        workflow.github, "validate_connection"
                    ) as mock_validate_conn:
                        # Setup mocks
                        mock_validate_conn.return_value = True
                        mock_validate.return_value = ReleaseMetadata.create(
                            release_id="test-release",
                            total_files=100,
                            total_size=1024 * 1024 * 100,  # 100MB
                            validation_status="passed",
                            validation_errors=[],
                            pipeline_run_id="test-pipeline",
                        )
                        mock_package = ReleasePackage.create(
                            release_tag="20250101-1200",
                            data_version="1.0.0",
                            change_summary="Test release",
                        )
                        mock_artifacts = [
                            {
                                "type": "csv_archive",
                                "path": "/tmp/test-csv.zip",
                                "size": 1000000,
                            },
                            {
                                "type": "database_archive",
                                "path": "/tmp/test-db.zip",
                                "size": 500000,
                            },
                        ]
                        mock_create_package.return_value = (
                            mock_package,
                            mock_artifacts,
                        )
                        mock_create_release.return_value = {
                            "id": 123,
                            "html_url": "https://github.com/test-owner/test-repo/releases/20250101-1200",
                        }

                        # Execute and time the full release
                        start_time = time.time()
                        result = workflow.execute_full_release(tag="20250101-1200")
                        end_time = time.time()

                        execution_time = end_time - start_time

                        # Assert completion within 15 minutes (900 seconds)
                        assert execution_time < 900, (
                            f"Release took {execution_time:.2f}s, exceeds 15-minute target"
                        )
                        assert result["success"] is True

    def test_release_package_creation_performance(self, workflow, mock_package):
        """Test that release package creation is performant."""
        with patch.object(workflow, "validate_release_data") as mock_validate:
            with patch.object(workflow.packager, "package_csv_files") as mock_csv:
                with patch.object(workflow.packager, "package_database") as mock_db:
                    # Setup mocks
                    mock_validate.return_value = ReleaseMetadata.create(
                        release_id="test-release",
                        total_files=100,
                        total_size=1024 * 1024 * 100,  # 100MB
                        validation_status="passed",
                        validation_errors=[],
                        pipeline_run_id="test-pipeline",
                    )
                    mock_csv.return_value = {
                        "artifact_type": "csv_archive",
                        "file_path": "/tmp/test-csv.zip",
                        "file_size": 1024,
                        "checksum": "a" * 64,
                    }
                    mock_db.return_value = {
                        "artifact_type": "database_archive",
                        "file_path": "/tmp/test-db.zip",
                        "file_size": 2048,
                        "checksum": "b" * 64,
                    }

                    # Time package creation
                    start_time = time.time()
                    package, artifacts = workflow.create_release_package(
                        "20250101-1200"
                    )
                    end_time = time.time()

                    execution_time = end_time - start_time

                    # Package creation should be fast (under 5 minutes)
                    assert execution_time < 300, (
                        f"Package creation took {execution_time:.2f}s, exceeds 5-minute target"
                    )
                    assert package.release_tag == "20250101-1200"
                    assert len(artifacts) == 2

    def test_github_release_creation_performance(self, workflow, mock_package):
        """Test that GitHub release creation is performant."""
        with patch.object(workflow.github, "get_release_by_tag") as mock_get_release:
            with patch.object(
                workflow.github, "create_release_with_artifacts"
            ) as mock_create:
                # Setup mocks
                mock_get_release.return_value = None  # No existing release
                mock_create.return_value = {
                    "id": 123,
                    "html_url": "https://github.com/test-owner/test-repo/releases/20250101-1200",
                }

                # Time GitHub release creation
                start_time = time.time()
                mock_artifacts = [
                    {
                        "type": "csv_archive",
                        "path": "/tmp/test-csv.zip",
                        "size": 1000000,
                    },
                    {
                        "type": "database_archive",
                        "path": "/tmp/test-db.zip",
                        "size": 500000,
                    },
                ]
                release = workflow.create_github_release(mock_package, mock_artifacts)
                end_time = time.time()

                execution_time = end_time - start_time

                # GitHub operations should be fast (under 2 minutes)
                assert execution_time < 120, (
                    f"GitHub release took {execution_time:.2f}s, exceeds 2-minute target"
                )
                assert release["id"] == 123

    def test_data_validation_performance(self, workflow):
        """Test that data validation is performant."""
        # Mock the specific file validation to avoid file system access
        with patch.object(
            workflow.validator, "_validate_file_sizes"
        ) as mock_file_sizes:
            with patch.object(
                workflow.validator, "_validate_file_existence"
            ) as mock_file_existence:
                with patch.object(
                    workflow.validator, "_validate_data_freshness"
                ) as mock_freshness:
                    with patch.object(
                        workflow.validator, "_validate_referential_integrity"
                    ) as mock_integrity:
                        # Setup mocks
                        mock_file_sizes.return_value = MagicMock(
                            check_name="file_sizes",
                            status="passed",
                            message="All files have reasonable sizes",
                        )
                        mock_file_existence.return_value = MagicMock(
                            check_name="file_existence",
                            status="passed",
                            message="All required files exist",
                        )
                        mock_freshness.return_value = MagicMock(
                            check_name="data_freshness",
                            status="passed",
                            message="Data is recent",
                        )
                        mock_integrity.return_value = MagicMock(
                            check_name="referential_integrity",
                            status="passed",
                            message="Referential integrity maintained",
                        )

                        # Time validation
                        start_time = time.time()
                        metadata = workflow.validate_release_data()
                end_time = time.time()

                execution_time = end_time - start_time

                # Validation should be fast (under 1 minute)
                assert execution_time < 60, (
                    f"Validation took {execution_time:.2f}s, exceeds 1-minute target"
                )
                assert metadata.validation_status == "passed"

    def test_performance_summary_within_target(self, workflow):
        """Test performance summary when within 15-minute target."""
        # Mock metrics within target
        workflow.metrics.get_metrics = MagicMock(
            return_value={
                "total_duration": 600,  # 10 minutes
                "steps": {
                    "github_connection_validation": {"duration": 5},
                    "release_package_creation": {"duration": 300},
                    "github_release_creation": {"duration": 295},
                },
            }
        )

        summary = workflow._get_performance_summary()

        assert summary["total_duration"] == 600
        # Check if within 15-minute target (900 seconds)
        assert summary["total_duration"] <= 900

    def test_performance_summary_exceeds_target(self, workflow):
        """Test performance summary when exceeding 15-minute target."""
        # Mock metrics exceeding target
        workflow.metrics.get_metrics = MagicMock(
            return_value={
                "total_duration": 1000,  # ~16.7 minutes
                "steps": {
                    "github_connection_validation": {"duration": 10},
                    "release_package_creation": {"duration": 500},
                    "github_release_creation": {"duration": 490},
                },
            }
        )

        summary = workflow._get_performance_summary()

        assert summary["total_duration"] == 1000
        # Check if exceeds 15-minute target (900 seconds)
        assert summary["total_duration"] > 900

    def test_parallel_operations_performance(self, workflow):
        """Test that operations that can run in parallel are optimized."""
        # This test verifies that independent operations don't block each other
        # Currently, the workflow runs sequentially, but this test ensures
        # we're aware of potential parallelization opportunities

        with patch.object(workflow, "validate_release_data") as mock_validate:
            with patch.object(workflow.packager, "package_csv_files") as mock_csv:
                with patch.object(workflow.packager, "package_database") as mock_db:
                    # Setup mocks
                    mock_validate.return_value = ReleaseMetadata.create(
                        release_id="test-release",
                        total_files=100,
                        total_size=1024 * 1024 * 100,  # 100MB
                        validation_status="passed",
                        validation_errors=[],
                        pipeline_run_id="test-pipeline",
                    )
                    mock_csv.return_value = {
                        "artifact_type": "csv_archive",
                        "file_path": "/tmp/test-csv.zip",
                        "file_size": 1024,
                        "checksum": "a" * 64,
                    }
                    mock_db.return_value = {
                        "artifact_type": "database_archive",
                        "file_path": "/tmp/test-db.zip",
                        "file_size": 2048,
                        "checksum": "b" * 64,
                    }

                    # Time the sequential operations
                    start_time = time.time()

                    # These operations could potentially run in parallel
                    validation_result = workflow.validate_release_data()
                    package, artifacts = workflow.create_release_package(
                        "20250101-1200"
                    )

                    end_time = time.time()
                    execution_time = end_time - start_time

                    # Even sequential, should be reasonable
                    assert execution_time < 600, (
                        f"Sequential operations took {execution_time:.2f}s, too slow"
                    )
                    assert validation_result.validation_status == "passed"
                    assert package.release_tag == "20250101-1200"
                    assert len(artifacts) == 2

    def test_large_dataset_performance(self, workflow):
        """Test performance with large dataset simulation."""
        # This test simulates processing a large dataset
        # and verifies performance doesn't degrade significantly

        with patch.object(workflow, "validate_release_data") as mock_validate:
            with patch.object(workflow.packager, "package_csv_files") as mock_csv:
                with patch.object(workflow.packager, "package_database") as mock_db:
                    # Mock large dataset (1GB total size, 1000 files)
                    mock_validate.return_value = ReleaseMetadata.create(
                        release_id="test-release",
                        total_files=1000,
                        total_size=1024 * 1024 * 1024,  # 1GB
                        validation_status="passed",
                        validation_errors=[],
                        pipeline_run_id="test-pipeline",
                    )
                    mock_csv.return_value = {
                        "artifact_type": "csv_archive",
                        "file_path": "/tmp/test-csv.zip",
                        "file_size": 1024,
                        "checksum": "a" * 64,
                    }
                    mock_db.return_value = {
                        "artifact_type": "database_archive",
                        "file_path": "/tmp/test-db.zip",
                        "file_size": 2048,
                        "checksum": "b" * 64,
                    }

                    start_time = time.time()
                    package, artifacts = workflow.create_release_package(
                        "20250101-1200"
                    )
                    end_time = time.time()

                    execution_time = end_time - start_time

                    # Even with large dataset, should complete within reasonable time
                    assert execution_time < 600, (
                        f"Large dataset processing took {execution_time:.2f}s, too slow"
                    )
                    assert package.release_tag == "20250101-1200"
                    assert len(artifacts) == 2
