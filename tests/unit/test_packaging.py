"""Unit tests for file packaging service."""

import pytest
import tempfile
import zipfile
import hashlib
from pathlib import Path
from src.release.packaging import FilePackager


class TestFilePackager:
    """Unit tests for FilePackager class."""

    def test_packager_initialization(self):
        """Test FilePackager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            packager = FilePackager(temp_dir)
            assert packager.output_dir == Path(temp_dir)
            assert packager.logger.component_name == "release.packaging"

    def test_package_csv_files_success(self):
        """Test packaging CSV files successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory() as data_dir:
                data_path = Path(data_dir)

                # Create timestamped CSV files (like the real ETL process)
                timestamped_files = {
                    "20250929_200611_Settlement.csv": "id,name\n1,Test\n",
                    "20250929_200611_County.csv": "id,name\n1,Test\n",
                    "20250929_200611_NationalIndividualElectoralDistrict.csv": "id,name\n1,Test\n",
                    "20250929_200611_PollingStation.csv": "id,name\n1,Test\n",
                    "20250929_200611_PostalCode.csv": "id,name\n1,Test\n",
                    "20250929_200611_PostalCode_Settlement.csv": "id,name\n1,Test\n",
                    "20250929_200611_SettlementIndividualElectoralDistrict.csv": "id,name\n1,Test\n",
                }

                for filename, content in timestamped_files.items():
                    (data_path / filename).write_text(content)

                # Create symlinks for main files (like the real ETL process)
                (data_path / "settlements.csv").symlink_to(
                    "20250929_200611_Settlement.csv"
                )
                (data_path / "counties.csv").symlink_to("20250929_200611_County.csv")

                # Create address directory with split files (like the real ETL process)
                address_dir = data_path / "20250929_200611_Address"
                address_dir.mkdir()

                # Create split address files
                split_address_files = {
                    "Address_001_Budapest.csv": "id,name\n1,Budapest Address\n",
                    "Address_002_Debrecen.csv": "id,name\n1,Debrecen Address\n",
                    "Address_003_Szeged.csv": "id,name\n1,Szeged Address\n",
                }

                for filename, content in split_address_files.items():
                    (address_dir / filename).write_text(content)

                packager = FilePackager(temp_dir)
                result = packager.package_csv_files(data_dir, "test-release")

                assert result["artifact_type"] == "csv_archive"
                assert "test-release" in result["file_path"]
                assert result["file_size"] > 0
                assert len(result["checksum"]) == 64  # SHA-256 hex digest length
                assert "created_at" in result

                # Verify ZIP file was created and contains expected files
                archive_path = Path(result["file_path"])
                assert archive_path.exists()

                with zipfile.ZipFile(archive_path, "r") as zipf:
                    file_list = zipf.namelist()
                    # Should contain split address files in addresses/ directory
                    assert "addresses/Address_001_Budapest.csv" in file_list
                    assert "addresses/Address_002_Debrecen.csv" in file_list
                    assert "addresses/Address_003_Szeged.csv" in file_list
                    # And other CSV files
                    assert "settlements.csv" in file_list
                    assert "counties.csv" in file_list
                    assert "NationalIndividualElectoralDistrict.csv" in file_list
                    assert "PollingStation.csv" in file_list
                    assert "PostalCode.csv" in file_list
                    assert "PostalCode_Settlement.csv" in file_list
                    assert "SettlementIndividualElectoralDistrict.csv" in file_list

    def test_package_csv_files_missing_files(self):
        """Test packaging CSV files when some files are missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory() as data_dir:
                data_path = Path(data_dir)

                # Create only some timestamped CSV files
                timestamped_files = {
                    "20250929_200611_Settlement.csv": "id,name\n1,Test\n",
                    "20250929_200611_County.csv": "id,name\n1,Test\n",
                }

                for filename, content in timestamped_files.items():
                    (data_path / filename).write_text(content)

                # Create symlinks for main files
                (data_path / "settlements.csv").symlink_to(
                    "20250929_200611_Settlement.csv"
                )
                (data_path / "counties.csv").symlink_to("20250929_200611_County.csv")

                # Create address directory with split files
                address_dir = data_path / "20250929_200611_Address"
                address_dir.mkdir()

                # Create split address files
                split_address_files = {
                    "Address_001_Budapest.csv": "id,name\n1,Budapest Address\n",
                }

                for filename, content in split_address_files.items():
                    (address_dir / filename).write_text(content)

                # Other CSV files are missing

                packager = FilePackager(temp_dir)
                result = packager.package_csv_files(data_dir, "test-release")

                assert result["artifact_type"] == "csv_archive"
                assert result["file_size"] > 0

                # Verify ZIP file contains only the existing files
                archive_path = Path(result["file_path"])
                with zipfile.ZipFile(archive_path, "r") as zipf:
                    file_list = zipf.namelist()
                    assert "addresses/Address_001_Budapest.csv" in file_list
                    assert "settlements.csv" in file_list
                    assert "counties.csv" in file_list
                    # Missing files should not be in the archive
                    assert "NationalIndividualElectoralDistrict.csv" not in file_list
                    assert "PollingStation.csv" not in file_list
                    assert "PostalCode.csv" not in file_list
                    assert "PostalCode_Settlement.csv" not in file_list
                    assert "SettlementIndividualElectoralDistrict.csv" not in file_list

    def test_package_database_success(self):
        """Test packaging database file successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory() as data_dir:
                # Create test database file
                (Path(data_dir) / "database.duckdb").write_text("test database content")

                packager = FilePackager(temp_dir)
                result = packager.package_database(data_dir, "test-release")

                assert result["artifact_type"] == "database_archive"
                assert "test-release" in result["file_path"]
                assert result["file_size"] > 0
                assert len(result["checksum"]) == 64
                assert "created_at" in result

                # Verify ZIP file was created and contains database
                archive_path = Path(result["file_path"])
                assert archive_path.exists()

                with zipfile.ZipFile(archive_path, "r") as zipf:
                    file_list = zipf.namelist()
                    assert "database.duckdb" in file_list

    def test_package_database_missing_file(self):
        """Test packaging database when file is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory() as data_dir:
                # No database file created

                packager = FilePackager(temp_dir)
                result = packager.package_database(data_dir, "test-release")

                assert result["artifact_type"] == "database_archive"
                # Should still create an archive, but it will be empty
                archive_path = Path(result["file_path"])
                assert archive_path.exists()

                with zipfile.ZipFile(archive_path, "r") as zipf:
                    file_list = zipf.namelist()
                    assert len(file_list) == 0  # Empty archive

    def test_package_all_success(self):
        """Test packaging all files successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory() as data_dir:
                # Create all required files
                (Path(data_dir) / "addresses.csv").write_text("id,name\n1,Test\n")
                (Path(data_dir) / "settlements.csv").write_text("id,name\n1,Test\n")
                (Path(data_dir) / "counties.csv").write_text("id,name\n1,Test\n")
                (Path(data_dir) / "NationalIndividualElectoralDistrict.csv").write_text(
                    "id,name\n1,Test\n"
                )
                (Path(data_dir) / "PollingStation.csv").write_text("id,name\n1,Test\n")
                (Path(data_dir) / "PostalCode.csv").write_text("id,name\n1,Test\n")
                (Path(data_dir) / "PostalCode_Settlement.csv").write_text(
                    "id,name\n1,Test\n"
                )
                (
                    Path(data_dir) / "SettlementIndividualElectoralDistrict.csv"
                ).write_text("id,name\n1,Test\n")
                (Path(data_dir) / "database.duckdb").write_text("test database content")

                packager = FilePackager(temp_dir)
                artifacts = packager.package_all(data_dir, "test-release")

                assert len(artifacts) == 2

                # Check CSV artifact
                csv_artifact = next(
                    a for a in artifacts if a["artifact_type"] == "csv_archive"
                )
                assert "test-release" in csv_artifact["file_path"]
                assert csv_artifact["file_size"] > 0

                # Check database artifact
                db_artifact = next(
                    a for a in artifacts if a["artifact_type"] == "database_archive"
                )
                assert "test-release" in db_artifact["file_path"]
                assert db_artifact["file_size"] > 0

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            packager = FilePackager(temp_dir)

            # Create a test file
            test_file = Path(temp_dir) / "test.txt"
            test_content = "test content for checksum"
            test_file.write_text(test_content)

            # Calculate checksum
            checksum = packager._calculate_checksum(test_file)

            # Verify checksum matches expected SHA-256
            expected_checksum = hashlib.sha256(test_content.encode()).hexdigest()
            assert checksum == expected_checksum

    def test_cleanup_artifacts(self):
        """Test cleanup of artifacts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            packager = FilePackager(temp_dir)

            # Create some test artifact files
            test_file1 = Path(temp_dir) / "oevk-data-csv-test-release.zip"
            test_file2 = Path(temp_dir) / "oevk-data-db-test-release.zip"
            test_file3 = Path(temp_dir) / "other-file.txt"  # Should not be deleted

            test_file1.write_text("test content")
            test_file2.write_text("test content")
            test_file3.write_text("test content")

            # Cleanup artifacts for test-release
            packager.cleanup_artifacts("test-release")

            # Verify only release artifacts were deleted
            assert not test_file1.exists()
            assert not test_file2.exists()
            assert test_file3.exists()  # Should still exist

    def test_get_artifact_info(self):
        """Test getting artifact information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            packager = FilePackager(temp_dir)

            # Create test artifact files
            csv_file = Path(temp_dir) / "oevk-data-csv-test-release.zip"
            db_file = Path(temp_dir) / "oevk-data-db-test-release.zip"
            other_file = Path(temp_dir) / "other-file.zip"  # Should not be included

            csv_file.write_text("csv content")
            db_file.write_text("db content")
            other_file.write_text("other content")

            # Get artifact info
            artifacts = packager.get_artifact_info("test-release")

            assert len(artifacts) == 2

            # Check CSV artifact info
            csv_artifact = next(
                a for a in artifacts if a["artifact_type"] == "csv_archive"
            )
            assert csv_artifact["file_path"] == str(csv_file)
            assert csv_artifact["file_size"] > 0
            assert len(csv_artifact["checksum"]) == 64

            # Check database artifact info
            db_artifact = next(
                a for a in artifacts if a["artifact_type"] == "database_archive"
            )
            assert db_artifact["file_path"] == str(db_file)
            assert db_artifact["file_size"] > 0
            assert len(db_artifact["checksum"]) == 64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
