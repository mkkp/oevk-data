"""
Release workflow orchestrator.

Coordinates the complete release process including validation, packaging,
and GitHub integration.
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.utils.pipeline_logging import PipelineLogger, PipelineMetrics
from src.release.models import ReleasePackage, ReleaseArtifact, ReleaseMetadata
from src.release.validation import DataValidator
from src.release.packaging import FilePackager
from src.release.github import GitHubIntegration
from src.release.common import ReleaseUtils


class ReleaseWorkflow:
    """Orchestrates the complete release workflow."""

    def __init__(
        self,
        repo_owner: str,
        repo_name: str,
        github_token: Optional[str] = None,
        staging_dir: str = "data/staging",
        exports_dir: str = "exports",
        temp_dir: str = "data/temp",
    ):
        """Initialize release workflow."""
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.staging_dir = Path(staging_dir)
        self.exports_dir = Path(exports_dir)
        self.temp_dir = Path(temp_dir)

        # Create directories
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.logger = ReleaseUtils.create_logger("workflow")
        self.metrics = PipelineMetrics("release.workflow")
        self.validator = DataValidator(str(self.staging_dir))
        self.packager = FilePackager(str(self.temp_dir))
        self.github = GitHubIntegration(repo_owner, repo_name, github_token)

    def validate_release_data(self) -> ReleaseMetadata:
        """Validate release data before packaging."""
        self.logger.log_start("release data validation")

        # Run comprehensive validation on exports directory (where all files are located)
        exports_validator = DataValidator(str(self.exports_dir))
        exports_validation = exports_validator.validate_all()

        # Get file information for metadata
        export_files = []

        # Check for PostgreSQL CSV files and schema
        postgresql_dir = self.exports_dir / "postgresql"
        schema_file = self.exports_dir / "schema.sql"
        import_script = self.exports_dir / "import_postgresql.sql"

        # Count CSV files in postgresql directory
        csv_file_count = 0
        if postgresql_dir.exists():
            csv_files = list(postgresql_dir.glob("*.csv"))
            csv_file_count = len(csv_files)
            export_files.extend([f"postgresql/{f.name}" for f in csv_files])

        # Add schema and import script if they exist
        if schema_file.exists():
            export_files.append("schema.sql")
        if import_script.exists():
            export_files.append("import_postgresql.sql")

        total_files = len(export_files)
        total_size = sum(
            (self.exports_dir / f).stat().st_size
            for f in ["schema.sql", "import_postgresql.sql"]
            if (self.exports_dir / f).exists()
        )
        if postgresql_dir.exists():
            total_size += sum(f.stat().st_size for f in postgresql_dir.glob("*.csv"))

        # Ensure we have minimum value for total_size
        if total_size == 0:
            total_size = 1

        # Validation passes if we have:
        # - PostgreSQL directory with CSV files (at least 10 tables expected)
        # - schema.sql
        # - import_postgresql.sql
        validation_status = (
            "passed"
            if (csv_file_count >= 10 and schema_file.exists() and import_script.exists())
            else "failed"
        )

        # Collect validation errors
        validation_errors = []
        if csv_file_count < 10:
            validation_errors.append(
                f"Insufficient CSV files in postgresql/: found {csv_file_count}, expected at least 10"
            )
        if not schema_file.exists():
            validation_errors.append("Missing schema.sql in exports directory")
        if not import_script.exists():
            validation_errors.append("Missing import_postgresql.sql in exports directory")

        # Generate a deterministic pipeline run ID
        pipeline_run_id = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create metadata using the correct model structure
        metadata = ReleaseMetadata.create(
            release_id="validation_only",  # This is a validation-only run
            total_files=total_files,
            total_size=total_size,
            validation_status=validation_status,
            validation_errors=validation_errors,
            pipeline_run_id=pipeline_run_id,
        )

        self.logger.log_completion(
            "release data validation", 0, is_valid=(validation_status == "passed")
        )
        return metadata

    def create_release_package(
        self, tag: str, force_rebuild: bool = False
    ) -> tuple[ReleasePackage, list[dict]]:
        """Create a release package with all artifacts.

        Args:
            tag: Release tag
            force_rebuild: If True, rebuild ZIP files even if they exist
        """
        self.logger.log_start("release package creation", tag=tag)

        # Validate data first
        metadata = self.validate_release_data()
        if metadata.validation_status != "passed":
            raise ValueError("Cannot create release: data validation failed")

        # Create artifacts
        artifacts = []

        # Package CSV exports
        csv_artifact = self.packager.package_csv_files(
            self.exports_dir, tag, force=force_rebuild
        )
        artifacts.append(csv_artifact)

        # Package database files - use exports directory which has the database link
        db_artifact = self.packager.package_database(
            self.exports_dir, tag, force=force_rebuild
        )
        artifacts.append(db_artifact)

        # Package PostgreSQL SQL files if they exist
        try:
            postgresql_artifact = self.packager.package_postgresql_files(
                self.exports_dir, tag, force=force_rebuild
            )
            artifacts.append(postgresql_artifact)
            self.logger.logger.info("PostgreSQL artifacts packaged successfully")
        except FileNotFoundError as e:
            self.logger.logger.warning(f"PostgreSQL files not found, skipping: {e}")

        # Package geocoding cache if it exists
        try:
            cache_file = "data/geocoding_cache.db"
            if Path(cache_file).exists():
                geocoding_cache_artifact = self.packager.package_geocoding_cache(
                    cache_file, tag, force=force_rebuild
                )
                artifacts.append(geocoding_cache_artifact)
                self.logger.logger.info("Geocoding cache packaged successfully")
            else:
                self.logger.logger.info("Geocoding cache not found, skipping")
        except Exception as e:
            self.logger.logger.warning(f"Failed to package geocoding cache: {e}")

        # Create release package using the correct model structure
        package = ReleasePackage.create(
            release_tag=tag,
            data_version="1.0.0",  # Default version for now
            change_summary=f"Automated release {tag}",
        )

        self.logger.log_completion(
            "release package creation", 0, artifacts_count=len(artifacts)
        )
        return (package, artifacts)

    def create_github_release(
        self,
        package: ReleasePackage,
        artifacts: list[dict],
        draft: bool = False,
        prerelease: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Create GitHub release and upload artifacts.

        Args:
            package: Release package with artifacts
            artifacts: List of artifact dictionaries
            draft: Whether to create as draft release
            prerelease: Whether to mark as prerelease
            force: If True, overwrite existing release with same tag
        """
        self.logger.log_start(
            "GitHub release creation", tag=package.release_tag, force=force
        )

        # Check if release already exists
        existing_release = self.github.get_release_by_tag(package.release_tag)
        if existing_release:
            if force:
                self.logger.logger.info(
                    f"Force mode: deleting existing release {package.release_tag}"
                )
                self.github.delete_release(existing_release["id"])
            else:
                raise ValueError(
                    f"Release with tag {package.release_tag} already exists"
                )

        # Prepare release body
        release_body = self._generate_release_body(package)

        # Create release
        release = self.github.create_release_with_artifacts(
            tag=package.release_tag,
            title=f"OEVK Data Release {package.release_tag}",
            body=release_body,
            artifacts=artifacts,
            draft=draft,
            prerelease=prerelease,
        )

        self.logger.log_completion(
            "GitHub release creation", 0, release_url=release.get("html_url")
        )
        return release

    def execute_full_release(
        self,
        tag: Optional[str] = None,
        auto_tag: bool = True,
        force: bool = False,
        force_rebuild: bool = False,
        skip_upload: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute the complete release workflow.

        Args:
            tag: Release tag (optional, auto-generated if not provided)
            auto_tag: Whether to auto-generate tag if not provided
            force: If True, overwrite existing release with same tag
            force_rebuild: If True, rebuild ZIP files even if they exist
            skip_upload: If True, skip GitHub upload and only create packages
            **kwargs: Additional arguments for GitHub release creation
        """
        self.metrics.start_pipeline()
        self.logger.log_start(
            "full release workflow", force=force, skip_upload=skip_upload
        )

        # Generate tag if not provided
        if not tag and auto_tag:
            tag = self._generate_release_tag()
        elif not tag:
            raise ValueError("Release tag is required")

        # Validate GitHub connection (only if not skipping upload)
        if not skip_upload:
            self.metrics.log_step_start("github_connection_validation")
            if not self.github.validate_connection():
                raise ValueError("GitHub connection validation failed")
            self.metrics.log_step_completion("github_connection_validation")

        # Create release package
        self.metrics.log_step_start("release_package_creation")
        package, artifacts = self.create_release_package(
            tag, force_rebuild=force_rebuild
        )
        self.metrics.log_step_completion("release_package_creation")

        # Create GitHub release with force option (only if not skipping upload)
        release = None
        if not skip_upload:
            self.metrics.log_step_start("github_release_creation")
            release = self.create_github_release(
                package, artifacts, force=force, **kwargs
            )
            self.metrics.log_step_completion("github_release_creation")
        else:
            self.logger.logger.info("Skipping GitHub upload as requested")

        # Clean up temporary files (only if not skipping upload)
        if not skip_upload:
            self.metrics.log_step_start("temporary_files_cleanup")
            self._cleanup_temp_files(package)
            self.metrics.log_step_completion("temporary_files_cleanup")
        else:
            self.logger.logger.info("Skipping temporary files cleanup as requested")

        self.metrics.end_pipeline()

        if skip_upload:
            self.logger.log_completion(
                "full release workflow", 0, packages_created=len(artifacts)
            )
        else:
            self.logger.log_completion(
                "full release workflow", 0, release_url=release.get("html_url")
            )

        return {
            "release": release,
            "package": {
                "release_id": package.release_id,
                "release_tag": package.release_tag,
                "data_version": package.data_version,
                "status": package.status,
                "change_summary": package.change_summary,
                "github_release_url": package.github_release_url,
            },
            "artifacts": artifacts,
            "success": True,
            "skip_upload": skip_upload,
            "performance_metrics": self._get_performance_summary(),
        }

    def get_release_status(self, tag: str) -> Dict[str, Any]:
        """Get status of a specific release."""
        release = self.github.get_release_by_tag(tag)
        if not release:
            return {"exists": False}

        return {
            "exists": True,
            "tag": release["tag_name"],
            "title": release["name"],
            "draft": release["draft"],
            "prerelease": release["prerelease"],
            "created_at": release["created_at"],
            "published_at": release["published_at"],
            "assets": [
                {
                    "name": asset["name"],
                    "size": asset["size"],
                    "download_count": asset["download_count"],
                }
                for asset in release["assets"]
            ],
        }

    def list_releases(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent releases."""
        return self.github.list_releases(limit)

    def _generate_release_tag(self) -> str:
        """Generate a release tag based on current timestamp."""
        return datetime.now().strftime("%Y%m%d-%H%M")

    def _generate_release_body(self, package: ReleasePackage) -> str:
        """Generate release body text."""
        return f"""Automated OEVK data release {package.release_tag}

This release contains:
- Address data for OEVK (Országos Egységes Választókerületi) districts
- Settlement and county reference data
- Complete database export

Data version: {package.data_version}
Release tag: {package.release_tag}
Generated: {package.created_at.strftime("%Y-%m-%d %H:%M:%S")}

{package.change_summary or "Standard automated release"}
"""

    def _cleanup_temp_files(self, package: ReleasePackage):
        """Clean up temporary files after release."""
        self.logger.log_start("temporary files cleanup")
        # Clean up temporary directory
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.logger.log_completion("temporary files cleanup", 0)

    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary."""
        return self.metrics.get_metrics()
