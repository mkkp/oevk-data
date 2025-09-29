"""
GitHub integration service.

Manages GitHub releases, tags, and artifact uploads.
"""

import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


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
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo_owner}/{self.repo_name}/releases",
            "-X",
            "POST",
            "-H",
            "Accept: application/vnd.github.v3+json",
            "-f",
            f"tag_name={tag}",
            "-f",
            f"name={title}",
            "-f",
            f"body={body}",
            "-f",
            f"draft={str(draft).lower()}",
            "-f",
            f"prerelease={str(prerelease).lower()}",
        ]

        result = self._run_gh_command(cmd)
        return json.loads(result)

    def upload_artifact(
        self, release_id: str, artifact_path: str, artifact_name: str
    ) -> Dict[str, Any]:
        """Upload an artifact to a GitHub release."""
        cmd = [
            "gh",
            "api",
            f"repos/{self.repo_owner}/{self.repo_name}/releases/{release_id}/assets",
            "-X",
            "POST",
            "-H",
            "Accept: application/vnd.github.v3+json",
            "-H",
            "Content-Type: application/octet-stream",
            "-f",
            f"name={artifact_name}",
            "--data-binary",
            f"@{artifact_path}",
        ]

        result = self._run_gh_command(cmd)
        return json.loads(result)

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
        self, tag: str, title: str, body: str, artifacts: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Create a release and upload multiple artifacts."""
        # Create the release
        release = self.create_release(tag, title, body)
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

        result = subprocess.run(
            cmd, capture_output=True, text=True, env=env, check=True
        )

        return result.stdout

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
