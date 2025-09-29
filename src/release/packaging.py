"""
File packaging service.

Handles compression and packaging of release artifacts.
"""

import os
import zipfile
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from src.utils.pipeline_logging import PipelineLogger
from src.release.common import ReleaseUtils


class FilePackager:
    """Handles compression and packaging of release artifacts."""

    def __init__(self, output_dir: str):
        """Initialize packager with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = ReleaseUtils.create_logger("packaging")

    def package_csv_files(self, data_dir: str, release_tag: str) -> Dict[str, Any]:
        """Package CSV files into a compressed archive."""
        data_path = Path(data_dir)
        csv_files = ReleaseUtils.get_csv_files()

        archive_name = ReleaseUtils.generate_archive_name("csv_archive", release_tag)
        archive_path = self.output_dir / archive_name

        # Create ZIP archive
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for csv_file in csv_files:
                file_path = data_path / csv_file
                if file_path.exists():
                    zipf.write(file_path, csv_file)

        # Calculate file size and checksum
        file_size = archive_path.stat().st_size
        checksum = self._calculate_checksum(archive_path)

        return {
            "artifact_type": "csv_archive",
            "file_path": str(archive_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
        }

    def package_database(self, data_dir: str, release_tag: str) -> Dict[str, Any]:
        """Package database file into a compressed archive."""
        data_path = Path(data_dir)
        db_file = "database.duckdb"

        archive_name = ReleaseUtils.generate_archive_name(
            "database_archive", release_tag
        )
        archive_path = self.output_dir / archive_name

        # Create ZIP archive containing the database
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            db_path = data_path / db_file
            if db_path.exists():
                zipf.write(db_path, db_file)

        # Calculate file size and checksum
        file_size = archive_path.stat().st_size
        checksum = self._calculate_checksum(archive_path)

        return {
            "artifact_type": "database_archive",
            "file_path": str(archive_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
        }

    def package_all(self, data_dir: str, release_tag: str) -> List[Dict[str, Any]]:
        """Package all data files into compressed archives."""
        artifacts = []

        # Package CSV files
        csv_artifact = self.package_csv_files(data_dir, release_tag)
        artifacts.append(csv_artifact)

        # Package database
        db_artifact = self.package_database(data_dir, release_tag)
        artifacts.append(db_artifact)

        return artifacts

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def cleanup_artifacts(self, release_tag: str) -> None:
        """Remove packaged artifacts for a specific release."""
        pattern = f"*{release_tag}*"

        for file_path in self.output_dir.glob(pattern):
            try:
                file_path.unlink()
            except Exception as e:
                print(f"Warning: Could not delete {file_path}: {e}")

    def get_artifact_info(self, release_tag: str) -> List[Dict[str, Any]]:
        """Get information about existing artifacts for a release."""
        artifacts = []
        pattern = f"*{release_tag}*"

        for file_path in self.output_dir.glob(pattern):
            if file_path.is_file():
                artifact_type = (
                    "csv_archive" if "csv" in file_path.name else "database_archive"
                )

                artifacts.append(
                    {
                        "artifact_type": artifact_type,
                        "file_path": str(file_path),
                        "file_size": file_path.stat().st_size,
                        "checksum": self._calculate_checksum(file_path),
                        "created_at": datetime.fromtimestamp(file_path.stat().st_mtime),
                    }
                )

        return artifacts
