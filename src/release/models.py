"""
Release data models.

Defines data structures for release packages, artifacts, and metadata.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import xxhash


@dataclass
class ReleasePackage:
    """Represents a packaged release of transformed data ready for distribution."""

    release_id: str
    release_tag: str
    created_at: datetime
    data_version: str
    status: str
    change_summary: Optional[str] = None
    github_release_url: Optional[str] = None

    def __post_init__(self):
        """Validate the release package data."""
        self._validate()

    def _validate(self):
        """Validate release package fields."""
        # Validate release tag format
        import re

        if not re.match(r"^\d{8}-\d{4}$", self.release_tag):
            raise ValueError(f"Invalid release_tag format: {self.release_tag}")

        # Validate status
        valid_statuses = {"pending", "created", "failed"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {self.status}. Must be one of {valid_statuses}"
            )

        # Validate release_id is deterministic hash
        expected_id = self._generate_release_id()
        if self.release_id != expected_id:
            raise ValueError(
                f"Invalid release_id: {self.release_id}. Expected: {expected_id}"
            )

    def _generate_release_id(self) -> str:
        """Generate deterministic release ID using xxhash64."""
        content = f"{self.release_tag}{self.created_at.isoformat()}"
        return f"{xxhash.xxh64(content.encode()).hexdigest()}"

    @classmethod
    def create(
        cls, release_tag: str, data_version: str, change_summary: Optional[str] = None
    ) -> "ReleasePackage":
        """Create a new release package with deterministic ID generation."""
        created_at = datetime.now()
        release_id = cls._generate_id(release_tag, created_at)

        return cls(
            release_id=release_id,
            release_tag=release_tag,
            created_at=created_at,
            data_version=data_version,
            status="pending",
            change_summary=change_summary,
        )

    @staticmethod
    def _generate_id(release_tag: str, created_at: datetime) -> str:
        """Generate deterministic release ID."""
        content = f"{release_tag}{created_at.isoformat()}"
        return f"{xxhash.xxh64(content.encode()).hexdigest()}"


@dataclass
class ReleaseArtifact:
    """Represents individual compressed files within a release package."""

    artifact_id: str
    release_id: str
    artifact_type: str
    file_path: str
    file_size: int
    checksum: str
    created_at: datetime

    def __post_init__(self):
        """Validate the release artifact data."""
        self._validate()

    def _validate(self):
        """Validate release artifact fields."""
        # Validate artifact type
        valid_types = {"csv_archive", "database_archive"}
        if self.artifact_type not in valid_types:
            raise ValueError(
                f"Invalid artifact_type: {self.artifact_type}. Must be one of {valid_types}"
            )

        # Validate file size
        if self.file_size <= 0:
            raise ValueError(
                f"Invalid file_size: {self.file_size}. Must be positive integer"
            )

        # Validate checksum format (SHA-256)
        import re

        if not re.match(r"^[a-f0-9]{64}$", self.checksum):
            raise ValueError(f"Invalid checksum format: {self.checksum}")

        # Validate artifact_id is deterministic hash
        expected_id = self._generate_artifact_id()
        if self.artifact_id != expected_id:
            raise ValueError(
                f"Invalid artifact_id: {self.artifact_id}. Expected: {expected_id}"
            )

    def _generate_artifact_id(self) -> str:
        """Generate deterministic artifact ID using xxhash64."""
        content = f"{self.release_id}{self.artifact_type}{self.file_path}"
        return f"{xxhash.xxh64(content.encode()).hexdigest()}"

    @classmethod
    def create(
        cls,
        release_id: str,
        artifact_type: str,
        file_path: str,
        file_size: int,
        checksum: str,
    ) -> "ReleaseArtifact":
        """Create a new release artifact with deterministic ID generation."""
        created_at = datetime.now()
        artifact_id = cls._generate_id(release_id, artifact_type, file_path)

        return cls(
            artifact_id=artifact_id,
            release_id=release_id,
            artifact_type=artifact_type,
            file_path=file_path,
            file_size=file_size,
            checksum=checksum,
            created_at=created_at,
        )

    @staticmethod
    def _generate_id(release_id: str, artifact_type: str, file_path: str) -> str:
        """Generate deterministic artifact ID."""
        content = f"{release_id}{artifact_type}{file_path}"
        return f"{xxhash.xxh64(content.encode()).hexdigest()}"


@dataclass
class ReleaseMetadata:
    """Stores metadata about the release process and data validation."""

    metadata_id: str
    release_id: str
    total_files: int
    total_size: int
    validation_status: str
    validation_errors: List[str]
    pipeline_run_id: str

    def __post_init__(self):
        """Validate the release metadata data."""
        self._validate()

    def _validate(self):
        """Validate release metadata fields."""
        # Validate validation status
        valid_statuses = {"passed", "failed"}
        if self.validation_status not in valid_statuses:
            raise ValueError(
                f"Invalid validation_status: {self.validation_status}. Must be one of {valid_statuses}"
            )

        # Validate total files
        if self.total_files <= 0:
            raise ValueError(
                f"Invalid total_files: {self.total_files}. Must be positive integer"
            )

        # Validate total size
        if self.total_size <= 0:
            raise ValueError(
                f"Invalid total_size: {self.total_size}. Must be positive integer"
            )

        # Validate metadata_id is deterministic hash
        expected_id = self._generate_metadata_id()
        if self.metadata_id != expected_id:
            raise ValueError(
                f"Invalid metadata_id: {self.metadata_id}. Expected: {expected_id}"
            )

    def _generate_metadata_id(self) -> str:
        """Generate deterministic metadata ID using xxhash64."""
        content = f"{self.release_id}metadata"
        return f"{xxhash.xxh64(content.encode()).hexdigest()}"

    @classmethod
    def create(
        cls,
        release_id: str,
        total_files: int,
        total_size: int,
        validation_status: str,
        validation_errors: List[str],
        pipeline_run_id: str,
    ) -> "ReleaseMetadata":
        """Create new release metadata with deterministic ID generation."""
        metadata_id = cls._generate_id(release_id)

        return cls(
            metadata_id=metadata_id,
            release_id=release_id,
            total_files=total_files,
            total_size=total_size,
            validation_status=validation_status,
            validation_errors=validation_errors,
            pipeline_run_id=pipeline_run_id,
        )

    @staticmethod
    def _generate_id(release_id: str) -> str:
        """Generate deterministic metadata ID."""
        content = f"{release_id}metadata"
        return f"{xxhash.xxh64(content.encode()).hexdigest()}"
