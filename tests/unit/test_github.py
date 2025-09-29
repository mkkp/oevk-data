"""Unit tests for GitHub integration service."""

import pytest
import json
import subprocess
from unittest.mock import patch, MagicMock
from src.release.github import GitHubIntegration


class TestGitHubIntegration:
    """Test GitHub integration service."""

    def test_initialization_with_token(self):
        """Test initialization with explicit token."""
        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        assert github.repo_owner == "test-owner"
        assert github.repo_name == "test-repo"
        assert github.token == "test-token"

    def test_initialization_with_env_token(self):
        """Test initialization with environment variable token."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            github = GitHubIntegration("test-owner", "test-repo")
            assert github.token == "env-token"

    def test_initialization_without_token(self):
        """Test initialization without token raises error."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="GitHub token is required"):
                GitHubIntegration("test-owner", "test-repo")

    @patch("subprocess.run")
    def test_create_release_success(self, mock_subprocess):
        """Test successful release creation."""
        # Mock successful subprocess result
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "id": 123,
                "tag_name": "v1.0.0",
                "name": "Release v1.0.0",
                "body": "Test release",
            }
        )
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.create_release(
            tag="v1.0.0", title="Release v1.0.0", body="Test release"
        )

        assert result["id"] == 123
        assert result["tag_name"] == "v1.0.0"
        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_create_release_with_draft_and_prerelease(self, mock_subprocess):
        """Test release creation with draft and prerelease flags."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"id": 456})
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        github.create_release(
            tag="v1.0.0",
            title="Release v1.0.0",
            body="Test release",
            draft=True,
            prerelease=True,
        )

        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_upload_artifact_success(self, mock_subprocess):
        """Test successful artifact upload."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "id": 789,
                "name": "artifact.zip",
                "size": 1024,
                "browser_download_url": "https://example.com/artifact.zip",
            }
        )
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.upload_artifact(
            release_id="123",
            artifact_path="/path/to/artifact.zip",
            artifact_name="artifact.zip",
        )

        assert result["id"] == 789
        assert result["name"] == "artifact.zip"
        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_get_release_by_tag_found(self, mock_subprocess):
        """Test getting release by tag when found."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {"id": 123, "tag_name": "v1.0.0", "name": "Release v1.0.0"}
        )
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.get_release_by_tag("v1.0.0")

        assert result["id"] == 123
        assert result["tag_name"] == "v1.0.0"

    @patch("subprocess.run")
    def test_get_release_by_tag_not_found(self, mock_subprocess):
        """Test getting release by tag when not found."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gh", "api"], output="Release not found"
        )

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.get_release_by_tag("nonexistent")

        assert result is None

    @patch("subprocess.run")
    def test_delete_release_success(self, mock_subprocess):
        """Test successful release deletion."""
        mock_result = MagicMock()
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.delete_release("123")

        assert result is True
        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_delete_release_failure(self, mock_subprocess):
        """Test failed release deletion."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gh", "api"], output="Delete failed"
        )

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.delete_release("123")

        assert result is False

    @patch("subprocess.run")
    def test_list_releases(self, mock_subprocess):
        """Test listing releases."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            [{"id": 1, "tag_name": "v1.0.0"}, {"id": 2, "tag_name": "v1.1.0"}]
        )
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.list_releases(limit=5)

        assert len(result) == 2
        assert result[0]["tag_name"] == "v1.0.0"
        assert result[1]["tag_name"] == "v1.1.0"

    @patch("src.release.github.GitHubIntegration.upload_artifact")
    @patch("src.release.github.GitHubIntegration.create_release")
    def test_create_release_with_artifacts_success(self, mock_create, mock_upload):
        """Test creating release with multiple artifacts."""
        # Mock release creation
        mock_create.return_value = {
            "id": 123,
            "tag_name": "v1.0.0",
            "name": "Release v1.0.0",
        }

        # Mock artifact upload
        mock_upload.return_value = {
            "browser_download_url": "https://example.com/artifact1.zip",
            "size": 1024,
        }

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        artifacts = [
            {"file_path": "/path/to/artifact1.zip"},
            {"file_path": "/path/to/artifact2.zip"},
        ]

        result = github.create_release_with_artifacts(
            tag="v1.0.0",
            title="Release v1.0.0",
            body="Test release with artifacts",
            artifacts=artifacts,
        )

        assert result["id"] == 123
        assert len(result["uploaded_artifacts"]) == 2
        assert mock_create.call_count == 1
        assert mock_upload.call_count == 2

    @patch("src.release.github.GitHubIntegration.upload_artifact")
    @patch("src.release.github.GitHubIntegration.create_release")
    def test_create_release_with_artifacts_partial_failure(
        self, mock_create, mock_upload
    ):
        """Test creating release with partial artifact upload failure."""
        mock_create.return_value = {"id": 123}

        # First upload succeeds, second fails
        mock_upload.side_effect = [
            {"browser_download_url": "https://example.com/artifact1.zip", "size": 1024},
            Exception("Upload failed"),
        ]

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        artifacts = [
            {"file_path": "/path/to/artifact1.zip"},
            {"file_path": "/path/to/artifact2.zip"},
        ]

        result = github.create_release_with_artifacts(
            tag="v1.0.0",
            title="Release v1.0.0",
            body="Test release",
            artifacts=artifacts,
        )

        assert len(result["uploaded_artifacts"]) == 1
        assert result["uploaded_artifacts"][0]["name"] == "artifact1.zip"

    @patch("subprocess.run")
    def test_validate_connection_success(self, mock_subprocess):
        """Test successful connection validation."""
        mock_result = MagicMock()
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.validate_connection()

        assert result is True

    @patch("subprocess.run")
    def test_validate_connection_failure(self, mock_subprocess):
        """Test failed connection validation."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gh", "api"], output="Connection failed"
        )

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.validate_connection()

        assert result is False

    @patch("subprocess.run")
    def test_get_latest_release_found(self, mock_subprocess):
        """Test getting latest release when found."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {"id": 999, "tag_name": "v2.0.0", "name": "Latest Release"}
        )
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.get_latest_release()

        assert result["id"] == 999
        assert result["tag_name"] == "v2.0.0"

    @patch("subprocess.run")
    def test_get_latest_release_not_found(self, mock_subprocess):
        """Test getting latest release when not found."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gh", "api"], output="No releases found"
        )

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.get_latest_release()

        assert result is None

    @patch("subprocess.run")
    def test_run_gh_command_with_token(self, mock_subprocess):
        """Test running GitHub CLI command with token."""
        mock_result = MagicMock()
        mock_result.stdout = '{"result": "success"}'
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github._run_gh_command(["gh", "api", "test"])

        assert result == '{"result": "success"}'
        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_run_gh_command_failure(self, mock_subprocess):
        """Test running GitHub CLI command that fails."""
        mock_subprocess.side_effect = Exception("Command failed")

        github = GitHubIntegration("test-owner", "test-repo", "test-token")

        with pytest.raises(Exception, match="Command failed"):
            github._run_gh_command(["gh", "api", "test"])


class TestGitHubIntegrationEdgeCases:
    """Test edge cases for GitHub integration."""

    @patch("subprocess.run")
    def test_create_release_with_special_characters(self, mock_subprocess):
        """Test release creation with special characters in title and body."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"id": 123})
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        github.create_release(
            tag="v1.0.0",
            title="Release v1.0.0 🚀",
            body="Test release with emoji 🎉 and special chars!",
        )

        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_upload_artifact_with_spaces_in_path(self, mock_subprocess):
        """Test artifact upload with spaces in file path."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"id": 456})
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        github.upload_artifact(
            release_id="123",
            artifact_path="/path/with spaces/artifact.zip",
            artifact_name="artifact with spaces.zip",
        )

        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_list_releases_with_zero_limit(self, mock_subprocess):
        """Test listing releases with zero limit."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps([])
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.list_releases(limit=0)

        assert result == []

    @patch("subprocess.run")
    def test_get_release_by_tag_with_special_chars(self, mock_subprocess):
        """Test getting release by tag with special characters."""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"id": 789})
        mock_subprocess.return_value = mock_result

        github = GitHubIntegration("test-owner", "test-repo", "test-token")
        result = github.get_release_by_tag("v1.0.0-beta+special")

        assert result["id"] == 789
