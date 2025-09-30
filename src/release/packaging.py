"""
File packaging service.

Handles compression and packaging of release artifacts.
"""

import os
import zipfile
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
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

        # Get all CSV files to include
        csv_files_to_package = self._get_all_csv_files(data_path)

        archive_name = ReleaseUtils.generate_archive_name("csv_archive", release_tag)
        archive_path = self.output_dir / archive_name

        # Create ZIP archive
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for csv_file, source_path in csv_files_to_package.items():
                if source_path.exists():
                    zipf.write(source_path, csv_file)

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

    def _get_all_csv_files(self, data_path: Path) -> Dict[str, Path]:
        """Get all CSV files to include in the package.

        Returns a dictionary mapping target filename to source file path.
        """
        csv_files = {}

        # First, add files from symlinks (these are the latest versions)
        symlink_files = ["settlements.csv", "counties.csv"]
        for symlink_file in symlink_files:
            symlink_path = data_path / symlink_file
            if symlink_path.exists() and symlink_path.is_symlink():
                # Use the symlink target as the source
                target_path = symlink_path.resolve()
                csv_files[symlink_file] = target_path

        # Add split address files instead of consolidated addresses.csv
        self._add_split_address_files(data_path, csv_files)

        # Add other important CSV files (find latest versions)
        additional_tables = [
            "NationalIndividualElectoralDistrict",
            "PollingStation",
            "PostalCode",
            "PostalCode_Settlement",
            "SettlementIndividualElectoralDistrict",
        ]

        for table in additional_tables:
            latest_file = self._find_latest_csv_file(data_path, table)
            if latest_file:
                csv_files[f"{table}.csv"] = latest_file

        return csv_files

    def _add_split_address_files(
        self, data_path: Path, csv_files: Dict[str, Path]
    ) -> None:
        """Add split address files to the package instead of consolidated addresses.csv.

        Looks for directories matching *_Address pattern and includes all CSV files
        from those directories.
        """
        # Find all address directories (e.g., 20250929-2101_Address)
        address_dirs = list(data_path.glob("*_Address"))

        if not address_dirs:
            # Fallback to consolidated addresses.csv if no split files found
            symlink_path = data_path / "addresses.csv"
            if symlink_path.exists() and symlink_path.is_symlink():
                target_path = symlink_path.resolve()
                csv_files["addresses.csv"] = target_path
            return

        # Use the latest address directory (by modification time)
        latest_address_dir = max(address_dirs, key=lambda p: p.stat().st_mtime)

        # Add all CSV files from the address directory
        for address_file in latest_address_dir.glob("*.csv"):
            if address_file.is_file():
                # Keep the original filename for the split files
                csv_files[f"addresses/{address_file.name}"] = address_file

    def _find_latest_csv_file(self, data_path: Path, table_name: str) -> Optional[Path]:
        """Find the latest version of a CSV file for a given table."""
        pattern = f"*_{table_name}.csv"
        matching_files = []

        for file_path in data_path.glob(pattern):
            if file_path.is_file():
                matching_files.append(file_path)

        if not matching_files:
            return None

        # Return the file with the latest modification time
        return max(matching_files, key=lambda p: p.stat().st_mtime)

    def package_database(self, data_dir: str, release_tag: str) -> Dict[str, Any]:
        """Package database file into a compressed archive."""
        data_path = Path(data_dir)

        # Try multiple database file locations in order of preference
        # Prioritize the main data/oevk.db file first
        db_files_to_try = [
            "../data/oevk.db",  # Main database in data directory (highest priority)
            "database.duckdb",  # Primary database file
            "oevk.db",  # Main transformed database
            "oevk_data.duckdb",  # Staging database
        ]

        archive_name = ReleaseUtils.generate_archive_name(
            "database_archive", release_tag
        )
        archive_path = self.output_dir / archive_name

        # Find and package the first available database file
        db_file_used = None

        # First try files in the current data directory
        for db_file in db_files_to_try:
            db_path = data_path / db_file
            if db_path.exists():
                db_file_used = db_file
                # Use consistent name in archive - always name it oevk.db
                archive_db_name = "oevk.db"
                # Create ZIP archive containing the database
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(db_path, archive_db_name)
                self.logger.logger.info(
                    f"Packaged database file: {db_file} as {archive_db_name} ({db_path.stat().st_size} bytes)"
                )
                break

        if not db_file_used:
            raise FileNotFoundError(
                f"No database file found. Tried: {', '.join(db_files_to_try)}"
            )

        # Calculate file size and checksum
        file_size = archive_path.stat().st_size
        checksum = self._calculate_checksum(archive_path)

        return {
            "artifact_type": "database_archive",
            "file_path": str(archive_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
            "database_file": db_file_used,  # Track which database file was used
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
