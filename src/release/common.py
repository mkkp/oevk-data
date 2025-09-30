"""
Common utilities and shared functionality for release modules.

Consolidates duplicated code patterns across release workflow components.
"""

import os
from pathlib import Path
from typing import List, Dict, Any

from src.utils.pipeline_logging import PipelineLogger


class ReleaseUtils:
    """Common utilities for release workflow components."""

    @staticmethod
    def get_required_files() -> List[str]:
        """Get list of required files for release validation."""
        return [
            "addresses.csv",
            "settlements.csv",
            "counties.csv",
            "database.duckdb",
        ]

    @staticmethod
    def get_csv_files() -> List[str]:
        """Get list of CSV files for packaging."""
        return [
            "addresses.csv",
            "settlements.csv",
            "counties.csv",
            "NationalIndividualElectoralDistrict.csv",
            "PollingStation.csv",
            "PostalCode.csv",
            "PostalCode_Settlement.csv",
            "SettlementIndividualElectoralDistrict.csv",
        ]

    @staticmethod
    def validate_directory_exists(directory: Path, name: str) -> None:
        """Validate that a directory exists."""
        if not directory.exists():
            raise ValueError(f"{name} directory not found: {directory}")

    @staticmethod
    def get_file_size_limits() -> Dict[str, int]:
        """Get minimum file size limits for validation."""
        return {
            "addresses.csv": 1000,  # 1KB minimum
            "settlements.csv": 100,  # 100B minimum
            "counties.csv": 50,  # 50B minimum
            "database.duckdb": 1000,  # 1KB minimum
        }

    @staticmethod
    def create_logger(module_name: str) -> PipelineLogger:
        """Create a standardized logger for release modules."""
        return PipelineLogger(f"release.{module_name}")

    @staticmethod
    def generate_archive_name(artifact_type: str, release_tag: str) -> str:
        """Generate standardized archive name."""
        if artifact_type == "csv_archive":
            return f"oevk-data-csv-{release_tag}.zip"
        elif artifact_type == "database_archive":
            return f"oevk-data-db-{release_tag}.zip"
        else:
            raise ValueError(f"Unknown artifact type: {artifact_type}")

    @staticmethod
    def check_file_existence(
        directory: Path, file_names: List[str]
    ) -> tuple[List[str], List[str]]:
        """Check which files exist in a directory."""
        existing_files = []
        missing_files = []

        for file_name in file_names:
            file_path = directory / file_name
            if file_path.exists():
                existing_files.append(file_name)
            else:
                missing_files.append(file_name)

        return existing_files, missing_files
