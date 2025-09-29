"""Unit tests for release workflow orchestrator."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

from src.release.workflow import ReleaseWorkflow
from src.release.models import ReleasePackage, ReleaseArtifact, ReleaseMetadata


class TestReleaseWorkflow:
    """Test release workflow orchestrator."""

    def test_initialization(self):
        """Test workflow initialization."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        assert workflow.repo_owner == "test-owner"
        assert workflow.repo_name == "test-repo"
        assert workflow.staging_dir == Path("data/staging")
        assert workflow.exports_dir == Path("exports")
        assert workflow.validator is not None
        assert workflow.packager is not None
        assert workflow.github is not None

    @patch("src.release.workflow.FilePackager")
    @patch("src.release.workflow.DataValidator")
    @patch("src.release.workflow.GitHubIntegration")
    def test_initialization_with_custom_directories(
        self, mock_github, mock_validator, mock_packager
    ):
        """Test workflow initialization with custom directories."""
        # Mock the packager to avoid directory creation issues
        mock_packager_instance = MagicMock()
        mock_packager.return_value = mock_packager_instance

        workflow = ReleaseWorkflow(
            "test-owner",
            "test-repo",
            "test-token",
            staging_dir="/custom/staging",
            exports_dir="/custom/exports",
        )

        assert workflow.staging_dir == Path("/custom/staging")
        assert workflow.exports_dir == Path("/custom/exports")

    @patch("src.release.workflow.DataValidator")
    @patch("src.release.workflow.FilePackager")
    @patch("src.release.workflow.GitHubIntegration")
    def test_validate_release_data_success(
        self, mock_github, mock_packager, mock_validator
    ):
        """Test successful release data validation."""
        # Mock validator
        mock_validator_instance = MagicMock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_staging_data.return_value = {
            "files_checked": 5,
            "issues_found": 0,
            "is_valid": True,
        }
        mock_validator_instance.validate_export_files.return_value = {
            "files_checked": 3,
            "issues_found": 0,
            "is_valid": True,
        }

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        # Mock directory existence using patch on Path class
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            metadata = workflow.validate_release_data()

        assert metadata.validation_status == "passed"
        assert metadata.total_files == 8  # 5 + 3
        assert len(metadata.validation_errors) == 0

    @patch("src.release.workflow.DataValidator")
    def test_validate_release_data_missing_staging_dir(self, mock_validator):
        """Test validation with missing staging directory."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            with pytest.raises(ValueError, match="Staging directory not found"):
                workflow.validate_release_data()

    @patch("src.release.workflow.DataValidator")
    def test_validate_release_data_missing_exports_dir(self, mock_validator):
        """Test validation with missing exports directory."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with patch("pathlib.Path.exists") as mock_exists:
            # First call returns True (staging exists), second call returns False (exports doesn't exist)
            mock_exists.side_effect = [True, False]
            with pytest.raises(ValueError, match="Exports directory not found"):
                workflow.validate_release_data()

    @patch("src.release.workflow.ReleaseWorkflow.validate_release_data")
    @patch("src.release.workflow.FilePackager")
    def test_create_release_package_success(self, mock_packager, mock_validate):
        """Test successful release package creation."""
        # Mock validation
        mock_validate.return_value = ReleaseMetadata.create(
            release_id="test-release",
            total_files=8,
            total_size=1024,
            validation_status="passed",
            validation_errors=[],
            pipeline_run_id="test-pipeline",
        )

        # Mock packager
        mock_packager_instance = MagicMock()
        mock_packager.return_value = mock_packager_instance
        mock_packager_instance.package_csv_exports.return_value = (
            ReleaseArtifact.create(
                release_id="test-release",
                artifact_type="csv_archive",
                file_path="/tmp/test-csv.zip",
                file_size=1024,
                checksum="a" * 64,  # SHA-256 format
            )
        )
        mock_packager_instance.package_database_files.return_value = (
            ReleaseArtifact.create(
                release_id="test-release",
                artifact_type="database_archive",
                file_path="/tmp/test-db.zip",
                file_size=2048,
                checksum="b" * 64,  # SHA-256 format
            )
        )

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        package = workflow.create_release_package("20250101-1200")

        assert package.release_tag == "20250101-1200"
        assert package.status == "pending"
        assert package.data_version == "1.0.0"
        mock_validate.assert_called_once()

    @patch("src.release.workflow.ReleaseWorkflow.validate_release_data")
    def test_create_release_package_validation_failed(self, mock_validate):
        """Test release package creation with failed validation."""
        # Mock failed validation
        mock_validate.return_value = ReleaseMetadata.create(
            release_id="test-release",
            total_files=8,
            total_size=1024,
            validation_status="failed",
            validation_errors=["Staging data validation failed"],
            pipeline_run_id="test-pipeline",
        )

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with pytest.raises(
            ValueError, match="Cannot create release: data validation failed"
        ):
            workflow.create_release_package("20250101-1200")

    @patch("src.release.workflow.GitHubIntegration")
    def test_create_github_release_success(self, mock_github):
        """Test successful GitHub release creation."""
        # Mock GitHub integration
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.get_release_by_tag.return_value = None
        mock_github_instance.create_release_with_artifacts.return_value = {
            "id": 123,
            "html_url": "https://github.com/test-owner/test-repo/releases/20250101-1200",
            "tag_name": "20250101-1200",
        }

        # Create test package
        package = ReleasePackage.create(
            release_tag="20250101-1200",
            data_version="1.0.0",
            change_summary="Test release",
        )

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        release = workflow.create_github_release(package)

        assert release["id"] == 123
        assert release["tag_name"] == "20250101-1200"
        mock_github_instance.create_release_with_artifacts.assert_called_once()

    @patch("src.release.workflow.GitHubIntegration")
    def test_create_github_release_existing_tag(self, mock_github):
        """Test GitHub release creation with existing tag."""
        # Mock existing release
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.get_release_by_tag.return_value = {
            "id": 456,
            "tag_name": "20250101-1200",
        }

        # Create test package
        package = ReleasePackage.create(
            release_tag="20250101-1200",
            data_version="1.0.0",
            change_summary="Test release",
        )

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with pytest.raises(
            ValueError, match="Release with tag 20250101-1200 already exists"
        ):
            workflow.create_github_release(package)

    @patch("src.release.workflow.GitHubIntegration")
    def test_create_github_release_force_mode(self, mock_github):
        """Test GitHub release creation with force mode."""
        # Mock existing release
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.get_release_by_tag.return_value = {
            "id": 456,
            "tag_name": "20250101-1200",
        }
        mock_github_instance.create_release_with_artifacts.return_value = {
            "id": 123,
            "html_url": "https://github.com/test-owner/test-repo/releases/20250101-1200",
        }

        # Create test package
        package = ReleasePackage.create(
            release_tag="20250101-1200",
            data_version="1.0.0",
            change_summary="Test release",
        )

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        release = workflow.create_github_release(package, force=True)

        assert release["id"] == 123
        mock_github_instance.delete_release.assert_called_once_with(456)
        mock_github_instance.create_release_with_artifacts.assert_called_once()

    @patch("src.release.workflow.ReleaseWorkflow.create_release_package")
    @patch("src.release.workflow.ReleaseWorkflow.create_github_release")
    @patch("src.release.workflow.GitHubIntegration")
    def test_execute_full_release_success(
        self, mock_github, mock_create_release, mock_create_package
    ):
        """Test successful full release execution."""
        # Mock GitHub connection
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.validate_connection.return_value = True

        # Mock package creation
        mock_package = MagicMock()
        mock_package.release_tag = "test-tag"
        mock_package.to_dict.return_value = {"release_tag": "test-tag"}
        mock_create_package.return_value = mock_package

        # Mock release creation
        mock_create_release.return_value = {
            "id": 123,
            "html_url": "https://github.com/test-owner/test-repo/releases/test-tag",
        }

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        result = workflow.execute_full_release(tag="test-tag")

        assert result["success"] is True
        assert result["release"]["id"] == 123
        assert result["package"]["release_tag"] == "test-tag"
        mock_github_instance.validate_connection.assert_called_once()
        mock_create_package.assert_called_once_with("test-tag")
        mock_create_release.assert_called_once_with(mock_package, force=False)

    @patch("src.release.workflow.GitHubIntegration")
    def test_execute_full_release_github_connection_failed(self, mock_github):
        """Test full release execution with failed GitHub connection."""
        # Mock failed GitHub connection
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.validate_connection.return_value = False

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with pytest.raises(ValueError, match="GitHub connection validation failed"):
            workflow.execute_full_release(tag="test-tag")

    @patch("src.release.workflow.GitHubIntegration")
    def test_execute_full_release_auto_tag(self, mock_github):
        """Test full release execution with auto-generated tag."""
        # Mock GitHub connection
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.validate_connection.return_value = True

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with patch.object(workflow, "create_release_package") as mock_create_package:
            with patch.object(workflow, "create_github_release") as mock_create_release:
                mock_package = MagicMock()
                mock_package.to_dict.return_value = {"tag": "20240101-1200"}
                mock_create_package.return_value = mock_package
                mock_create_release.return_value = {"id": 123}

                result = workflow.execute_full_release(auto_tag=True)

                assert result["success"] is True
                mock_create_package.assert_called_once()
                mock_create_release.assert_called_once()

    def test_execute_full_release_no_tag(self):
        """Test full release execution without tag and auto_tag disabled."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with pytest.raises(ValueError, match="Release tag is required"):
            workflow.execute_full_release(auto_tag=False)

    @patch("src.release.workflow.GitHubIntegration")
    def test_get_release_status_found(self, mock_github):
        """Test getting release status when found."""
        # Mock existing release
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.get_release_by_tag.return_value = {
            "id": 123,
            "tag_name": "test-tag",
            "assets": [{"name": "artifact1.zip"}, {"name": "artifact2.zip"}],
            "published_at": "2024-01-01T00:00:00Z",
            "draft": False,
            "prerelease": False,
        }

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        status = workflow.get_release_status("test-tag")

        assert status["exists"] is True
        assert status["tag"] == "test-tag"
        assert status["artifacts"] == 2
        assert status["published_at"] == "2024-01-01T00:00:00Z"

    @patch("src.release.workflow.GitHubIntegration")
    def test_get_release_status_not_found(self, mock_github):
        """Test getting release status when not found."""
        # Mock non-existent release
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.get_release_by_tag.return_value = None

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        status = workflow.get_release_status("nonexistent-tag")

        assert status["exists"] is False
        assert status["tag"] == "nonexistent-tag"

    @patch("src.release.workflow.GitHubIntegration")
    def test_list_releases(self, mock_github):
        """Test listing releases."""
        # Mock releases
        mock_github_instance = MagicMock()
        mock_github.return_value = mock_github_instance
        mock_github_instance.list_releases.return_value = [
            {"id": 1, "tag_name": "v1.0.0"},
            {"id": 2, "tag_name": "v1.1.0"},
        ]

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        releases = workflow.list_releases(limit=5)

        assert len(releases) == 2
        assert releases[0]["tag_name"] == "v1.0.0"
        assert releases[1]["tag_name"] == "v1.1.0"
        mock_github_instance.list_releases.assert_called_once_with(5)

    def test_generate_release_tag(self):
        """Test release tag generation."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        with patch("src.release.workflow.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 30, 45)
            tag = workflow._generate_release_tag()

        assert tag == "20240101-1230"

    def test_generate_release_body(self):
        """Test release body generation."""
        # Create test package
        package = ReleasePackage.create(
            release_tag="20250101-1200",
            data_version="1.0.0",
            change_summary="Test release with updated data",
        )

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")
        body = workflow._generate_release_body(package)

        assert "# OEVK Data Release 20250101-1200" in body
        assert "Release ID" in body
        assert "Data Version" in body
        assert "Status" in body
        assert "Change Summary" in body

    def test_cleanup_temp_files(self):
        """Test temporary files cleanup."""
        # Create test package
        package = ReleasePackage.create(
            release_tag="20250101-1200",
            data_version="1.0.0",
            change_summary="Test release",
        )

        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        # Cleanup should complete without errors (currently a no-op)
        workflow._cleanup_temp_files(package)

        # No assertions needed since cleanup is currently a no-op

    def test_get_performance_summary(self):
        """Test performance summary generation."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        # Mock metrics
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

        assert summary["total_duration_seconds"] == 600
        assert summary["within_15_minute_target"] is True
        assert summary["slowest_step"] == "release_package_creation"
        assert summary["slowest_step_duration"] == 300
        assert summary["performance_status"] == "PASS"

    def test_get_performance_summary_exceeds_target(self):
        """Test performance summary when exceeding target."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        # Mock metrics exceeding 15 minutes
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

        assert summary["total_duration_seconds"] == 1000
        assert summary["within_15_minute_target"] is False
        assert summary["performance_status"] == "FAIL"

    @patch("src.release.workflow.PipelineLogger")
    def test_trigger_etl_pipeline_success(self, mock_logger):
        """Test ETL pipeline trigger success."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        # Mock ETL methods
        with patch.object(workflow, "_get_database_connection", return_value=None):
            with patch.object(
                workflow, "_download_sources", return_value={"file1": "path1"}
            ):
                with patch.object(workflow, "_load_staging_data"):
                    with patch.object(workflow, "_transform_data"):
                        with patch.object(workflow, "_export_data"):
                            result = workflow.trigger_etl_pipeline(
                                {"oevk_json": "url1", "korzet_csv": "url2"}, "test-run"
                            )

        assert result["success"] is True
        assert result["run_tag"] == "test-run"
        assert result["staging_files"] == 1

    @patch("src.release.workflow.PipelineLogger")
    def test_trigger_etl_pipeline_failure(self, mock_logger):
        """Test ETL pipeline trigger failure."""
        workflow = ReleaseWorkflow("test-owner", "test-repo", "test-token")

        # Mock ETL methods with exception
        with patch.object(
            workflow, "_get_database_connection", side_effect=Exception("DB error")
        ):
            result = workflow.trigger_etl_pipeline(
                {"oevk_json": "url1", "korzet_csv": "url2"}, "test-run"
            )

        assert result["success"] is False
        assert result["run_tag"] == "test-run"
        assert "DB error" in result["error"]
