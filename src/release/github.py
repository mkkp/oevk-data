"""
GitHub integration service.

Manages GitHub releases, tags, and artifact uploads.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class GitHubIntegration:
    """Handles GitHub releases, tags, and artifact uploads."""

    def __init__(self, repo_owner: str, repo_name: str, token: Optional[str] = None):
        """Initialize GitHub integration."""
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.token = token or os.getenv("GITHUB_TOKEN")

        if not self.token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable."
            )

    def create_release(
        self,
        tag: str,
        title: str,
        body: str,
        draft: bool = False,
        prerelease: bool = False,
    ) -> Dict[str, Any]:
        """Create a GitHub release."""
        # Use gh release create command instead of direct API for better boolean handling
        cmd = [
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            f"{self.repo_owner}/{self.repo_name}",
            "--title",
            title,
            "--notes",
            body,
        ]

        if draft:
            cmd.append("--draft")
        if prerelease:
            cmd.append("--prerelease")

        self._run_gh_command(cmd)

        # Get the created release details
        release = self.get_release_by_tag(tag)
        if not release:
            raise RuntimeError(f"Failed to retrieve created release with tag {tag}")
        return release

    def upload_artifact(
        self, release_id: str, artifact_path: str, artifact_name: str
    ) -> Dict[str, Any]:
        """Upload an artifact to a GitHub release."""
        # Get the release to find the tag
        release = self.get_release_by_id(release_id)
        if not release:
            raise ValueError(f"Release with ID {release_id} not found")

        tag = release["tag_name"]

        # Use gh release upload command instead of direct API for better organization repo support
        cmd = [
            "gh",
            "release",
            "upload",
            tag,
            artifact_path,
            "--repo",
            f"{self.repo_owner}/{self.repo_name}",
            "--clobber",
        ]

        self._run_gh_command(cmd)

        # Get the uploaded asset details
        updated_release = self.get_release_by_id(release_id)
        if updated_release:
            for asset in updated_release.get("assets", []):
                if asset["name"] == artifact_name:
                    return asset

        # Return basic info if we can't find the asset
        return {
            "name": artifact_name,
            "state": "uploaded",
            "browser_download_url": f"https://github.com/{self.repo_owner}/{self.repo_name}/releases/download/{tag}/{artifact_name}",
        }

    def get_release_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get release information by tag."""
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo_owner}/{self.repo_name}/releases/tags/{tag}",
            "-H",
            "Accept: application/vnd.github.v3+json",
        ]

        try:
            result = self._run_gh_command(cmd)
            return json.loads(result)
        except subprocess.CalledProcessError:
            return None

    def get_release_by_id(self, release_id: str) -> Optional[Dict[str, Any]]:
        """Get release information by ID."""
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo_owner}/{self.repo_name}/releases/{release_id}",
            "-H",
            "Accept: application/vnd.github.v3+json",
        ]

        try:
            result = self._run_gh_command(cmd)
            return json.loads(result)
        except subprocess.CalledProcessError:
            return None

    def delete_release(self, release_id: str) -> bool:
        """Delete a GitHub release."""
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo_owner}/{self.repo_name}/releases/{release_id}",
            "-X",
            "DELETE",
            "-H",
            "Accept: application/vnd.github.v3+json",
        ]

        try:
            self._run_gh_command(cmd)
            return True
        except subprocess.CalledProcessError:
            return False

    def list_releases(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent releases."""
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo_owner}/{self.repo_name}/releases",
            "-H",
            "Accept: application/vnd.github.v3+json",
            "--paginate",
            "--jq",
            f".[:{limit}]",
        ]

        result = self._run_gh_command(cmd)
        return json.loads(result)

    def create_release_with_artifacts(
        self,
        tag: str,
        title: str,
        body: str,
        artifacts: List[Dict[str, str]],
        draft: bool = False,
        prerelease: bool = False,
    ) -> Dict[str, Any]:
        """Create a release and upload multiple artifacts."""
        # Create the release
        release = self.create_release(tag, title, body, draft, prerelease)
        release_id = release["id"]

        # Upload artifacts
        uploaded_artifacts = []
        for artifact in artifacts:
            artifact_path = artifact["file_path"]
            artifact_name = Path(artifact_path).name

            try:
                upload_result = self.upload_artifact(
                    release_id, artifact_path, artifact_name
                )
                uploaded_artifacts.append(
                    {
                        "name": artifact_name,
                        "url": upload_result.get("browser_download_url"),
                        "size": upload_result.get("size"),
                    }
                )
            except Exception as e:
                print(f"Warning: Failed to upload {artifact_name}: {e}")

        # Update release with artifact information
        release["uploaded_artifacts"] = uploaded_artifacts
        return release

    def _run_gh_command(self, cmd: List[str]) -> str:
        """Run a GitHub CLI command with authentication."""
        env = os.environ.copy()
        if self.token:
            env["GITHUB_TOKEN"] = self.token

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, env=env, check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"GitHub command failed: {e}")
            logger.error(f"Command: {' '.join(cmd)}")
            logger.error(f"Return code: {e.returncode}")
            logger.error(f"Stdout: {e.stdout}")
            logger.error(f"Stderr: {e.stderr}")
            raise

    def validate_connection(self) -> bool:
        """Validate GitHub connection and permissions."""
        try:
            cmd = [
                "gh",
                "api",
                f"repos/{self.repo_owner}/{self.repo_name}",
                "-H",
                "Accept: application/vnd.github.v3+json",
            ]
            self._run_gh_command(cmd)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_latest_release(self) -> Optional[Dict[str, Any]]:
        """Get the latest release."""
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo_owner}/{self.repo_name}/releases/latest",
            "-H",
            "Accept: application/vnd.github.v3+json",
        ]

        try:
            result = self._run_gh_command(cmd)
            return json.loads(result)
        except subprocess.CalledProcessError:
            return None
