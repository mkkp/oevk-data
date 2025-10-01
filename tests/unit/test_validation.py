"""Unit tests for data validation utilities."""

import pytest
import tempfile
import os
from pathlib import Path
from src.utils.validation import (
    validate_county_data,
    validate_settlement_data,
    validate_oevk_data,
    validate_tevk_data,
    validate_postal_code_data,
    validate_polling_station_data,
    validate_address_data,
    validate_data_batch,
    log_validation_errors,
)
from src.release.validation import DataValidator, ValidationResult, ValidationSummary


class TestCountyValidation:
    """Test county data validation."""

    def test_valid_county_data(self):
        """Test validation of valid county data."""
        data = {"CountyCode": "01", "CountyName": "Budapest"}
        errors = validate_county_data(data)
        assert errors == []

    def test_missing_required_field(self):
        """Test validation with missing required field."""
        data = {
            "CountyCode": "01"
            # Missing CountyName
        }
        errors = validate_county_data(data)
        assert "Missing required field: CountyName" in errors

    def test_empty_required_field(self):
        """Test validation with empty required field."""
        data = {"CountyCode": "01", "CountyName": ""}
        errors = validate_county_data(data)
        assert "Empty required field: CountyName" in errors

    def test_invalid_county_code_format(self):
        """Test validation with invalid county code format."""
        data = {
            "CountyCode": "A1",  # Not all digits
            "CountyName": "Budapest",
        }
        errors = validate_county_data(data)
        assert "Invalid CountyCode format: A1" in errors


class TestSettlementValidation:
    """Test settlement data validation."""

    def test_valid_settlement_data(self):
        """Test validation of valid settlement data."""
        data = {
            "SettlementCode": "001",
            "SettlementName": "Budapest I. kerület",
            "CountyCode": "01",
        }
        errors = validate_settlement_data(data)
        assert errors == []

    def test_invalid_settlement_code_format(self):
        """Test validation with invalid settlement code format."""
        data = {
            "SettlementCode": "A01",  # Not all digits
            "SettlementName": "Budapest I. kerület",
            "CountyCode": "01",
        }
        errors = validate_settlement_data(data)
        assert "Invalid SettlementCode format: A01" in errors


class TestOEVKValidation:
    """Test OEVK data validation."""

    def test_valid_oevk_data(self):
        """Test validation of valid OEVK data."""
        data = {"OEVK": "01", "CountyCode": "01"}
        errors = validate_oevk_data(data)
        assert errors == []

    def test_invalid_oevk_format(self):
        """Test validation with invalid OEVK format."""
        data = {
            "OEVK": "A1",  # Not all digits
            "CountyCode": "01",
        }
        errors = validate_oevk_data(data)
        assert "Invalid OEVK format: A1" in errors


class TestTEVKValidation:
    """Test TEVK data validation."""

    def test_valid_tevk_data(self):
        """Test validation of valid TEVK data."""
        data = {"CountyCode": "01", "SettlementCode": "001", "OEVK": "01", "TEVK": "01"}
        errors = validate_tevk_data(data)
        assert errors == []

    def test_tevk_without_optional_field(self):
        """Test validation of TEVK data without optional TEVK field."""
        data = {
            "CountyCode": "01",
            "SettlementCode": "001",
            "OEVK": "01",
            # TEVK is optional
        }
        errors = validate_tevk_data(data)
        assert errors == []


class TestPostalCodeValidation:
    """Test postal code data validation."""

    def test_valid_postal_code_data(self):
        """Test validation of valid postal code data."""
        data = {"PostalCode": "1011"}
        errors = validate_postal_code_data(data)
        assert errors == []

    def test_invalid_postal_code_format(self):
        """Test validation with invalid postal code format."""
        data = {
            "PostalCode": "101",  # Wrong length
        }
        errors = validate_postal_code_data(data)
        assert "Invalid PostalCode format: 101" in errors


class TestPollingStationValidation:
    """Test polling station data validation."""

    def test_valid_polling_station_data(self):
        """Test validation of valid polling station data."""
        data = {
            "PollingStationAddress": "Vár utca 1.",
            "CountyCode": "01",
            "SettlementCode": "001",
            "OEVK": "01",
        }
        errors = validate_polling_station_data(data)
        assert errors == []


class TestAddressValidation:
    """Test address data validation."""

    def test_valid_address_data(self):
        """Test validation of valid address data."""
        data = {
            "PublicSpaceName": "Vár",
            "PublicSpaceType": "utca",
            "HouseNumber": "1",
            "CountyCode": "01",
            "SettlementCode": "001",
            "OEVK": "01",
            "PostalCode": "1011",
        }
        errors = validate_address_data(data)
        assert errors == []

    def test_address_with_optional_fields(self):
        """Test validation of address data with optional fields."""
        data = {
            "PublicSpaceName": "Vár",
            "PublicSpaceType": "utca",
            "HouseNumber": "1",
            "Building": "A",
            "Staircase": "1",
            "CountyCode": "01",
            "SettlementCode": "001",
            "OEVK": "01",
            "PostalCode": "1011",
        }
        errors = validate_address_data(data)
        assert errors == []


class TestBatchValidation:
    """Test batch validation functionality."""

    def test_valid_county_batch(self):
        """Test validation of a batch of valid county data."""
        batch = [
            {"CountyCode": "01", "CountyName": "Budapest"},
            {"CountyCode": "02", "CountyName": "Pest"},
        ]
        results = validate_data_batch("County", batch)

        # All should have no errors
        for errors in results.values():
            assert errors == []

    def test_mixed_batch_validation(self):
        """Test validation of a batch with mixed valid and invalid data."""
        batch = [
            {"CountyCode": "01", "CountyName": "Budapest"},  # Valid
            {"CountyCode": "A1", "CountyName": "Invalid"},  # Invalid county code
            {"CountyCode": "02"},  # Missing CountyName
        ]
        results = validate_data_batch("County", batch)

        # Check that we have results for all items
        assert len(results) == 3

        # First should be valid
        assert results["County_01"] == []

        # Second should have format error
        assert "Invalid CountyCode format: A1" in results["County_A1"]

        # Third should have missing field error
        assert "Missing required field: CountyName" in results["County_02"]

    def test_unknown_entity_type(self):
        """Test validation with unknown entity type."""
        batch = [{"Test": "data"}]

        with pytest.raises(ValueError, match="Unknown entity type: UnknownType"):
            validate_data_batch("UnknownType", batch)


class TestLogging:
    """Test validation error logging."""

    def test_log_validation_errors_with_errors(self, caplog):
        """Test logging when there are validation errors."""
        errors = ["Missing required field: CountyName", "Invalid CountyCode format"]
        log_validation_errors("County", errors, "01")

        # Check that warning was logged
        assert "Validation failed for County (ID: 01)" in caplog.text
        assert "Missing required field: CountyName" in caplog.text

    def test_log_validation_errors_no_errors(self, caplog):
        """Test logging when there are no validation errors."""
        # Set logging level to DEBUG to capture debug messages
        import logging

        caplog.set_level(logging.DEBUG)

        errors = []
        log_validation_errors("County", errors, "01")

        # Check that debug was logged
        assert "Validation passed for County" in caplog.text


class TestReleaseDataValidator:
    """Unit tests for DataValidator class in release module."""

    def test_validation_result_creation(self):
        """Test ValidationResult dataclass creation."""
        result = ValidationResult(
            check_name="test_check", status="passed", message="Test message"
        )
        assert result.check_name == "test_check"
        assert result.status == "passed"
        assert result.message == "Test message"

    def test_validation_summary_creation(self):
        """Test ValidationSummary dataclass creation."""
        checks = [
            ValidationResult("check1", "passed", "Message 1"),
            ValidationResult("check2", "failed", "Message 2"),
        ]
        summary = ValidationSummary(valid=False, checks=checks)
        assert summary.valid is False
        assert len(summary.checks) == 2

    def test_validator_initialization(self):
        """Test DataValidator initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            validator = DataValidator(temp_dir)
            assert validator.data_dir == Path(temp_dir)
            assert validator.logger.component_name == "release.validation"

    def test_validate_file_existence_all_files_present(self):
        """Test file existence validation when all files are present."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create required files
            for file_name in [
                "addresses.csv",
                "settlements.csv",
                "counties.csv",
                "database.duckdb",
                "PublicSpaceName.csv",
                "PublicSpaceType.csv",
                "SettlementPublicSpaces.csv",
            ]:
                (Path(temp_dir) / file_name).touch()

            validator = DataValidator(temp_dir)
            result = validator._validate_file_existence()

            assert result.check_name == "file_existence"
            assert result.status == "passed"
            assert "All required files exist" in result.message

    def test_validate_file_existence_missing_files(self):
        """Test file existence validation when files are missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create only some files
            (Path(temp_dir) / "addresses.csv").touch()

            validator = DataValidator(temp_dir)
            result = validator._validate_file_existence()

            assert result.check_name == "file_existence"
            assert result.status == "failed"
            assert "Missing required files" in result.message
            assert "settlements.csv" in result.message
            assert "counties.csv" in result.message
            assert "database.duckdb" in result.message

    def test_validate_file_sizes_all_files_adequate(self):
        """Test file size validation when all files meet minimum sizes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with adequate sizes
            (Path(temp_dir) / "addresses.csv").write_text("x" * 2000)
            (Path(temp_dir) / "settlements.csv").write_text("x" * 200)
            (Path(temp_dir) / "counties.csv").write_text("x" * 100)
            (Path(temp_dir) / "database.duckdb").write_text("x" * 2000)

            validator = DataValidator(temp_dir)
            result = validator._validate_file_sizes()

            assert result.check_name == "file_sizes"
            assert result.status == "passed"
            assert "All files have reasonable sizes" in result.message

    def test_validate_file_sizes_small_files(self):
        """Test file size validation when files are too small."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files that are too small
            (Path(temp_dir) / "addresses.csv").write_text("x")  # 1 byte
            (Path(temp_dir) / "settlements.csv").write_text("x" * 50)  # 50 bytes
            (Path(temp_dir) / "counties.csv").write_text("x" * 25)  # 25 bytes
            (Path(temp_dir) / "database.duckdb").write_text("x" * 500)  # 500 bytes

            validator = DataValidator(temp_dir)
            result = validator._validate_file_sizes()

            assert result.check_name == "file_sizes"
            assert result.status == "failed"
            assert "Files too small" in result.message

    def test_validate_file_integrity_readable_files(self):
        """Test file integrity validation with readable files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create readable CSV files
            (Path(temp_dir) / "addresses.csv").write_text("id,name\n1,Test\n")
            (Path(temp_dir) / "settlements.csv").write_text("id,name\n1,Test\n")
            (Path(temp_dir) / "counties.csv").write_text("id,name\n1,Test\n")

            validator = DataValidator(temp_dir)
            result = validator._validate_file_integrity()

            assert result.check_name == "file_integrity"
            assert result.status == "passed"
            assert "All files are readable and non-empty" in result.message

    def test_validate_file_integrity_empty_file(self):
        """Test file integrity validation with empty file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty file
            (Path(temp_dir) / "addresses.csv").touch()

            validator = DataValidator(temp_dir)
            result = validator._validate_file_integrity()

            assert result.check_name == "file_integrity"
            assert result.status == "failed"
            assert "File appears empty" in result.message

    def test_validate_data_completeness_with_headers(self):
        """Test data completeness validation with proper headers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create CSV files with headers
            (Path(temp_dir) / "addresses.csv").write_text("id,name\n1,Test\n")
            (Path(temp_dir) / "settlements.csv").write_text("id,name\n1,Test\n")
            (Path(temp_dir) / "counties.csv").write_text("id,name\n1,Test\n")

            validator = DataValidator(temp_dir)
            result = validator._validate_data_completeness()

            assert result.check_name == "data_completeness"
            assert result.status == "passed"
            assert "Basic data completeness checks passed" in result.message

    def test_validate_data_completeness_missing_header(self):
        """Test data completeness validation with missing header."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create all CSV files, but one with empty first line
            (Path(temp_dir) / "addresses.csv").write_text(
                "\n1,Test\n"
            )  # Empty first line
            (Path(temp_dir) / "settlements.csv").write_text("id,name\n1,Test\n")
            (Path(temp_dir) / "counties.csv").write_text("id,name\n1,Test\n")

            validator = DataValidator(temp_dir)
            result = validator._validate_data_completeness()

            assert result.check_name == "data_completeness"
            assert result.status == "failed"
            assert "Missing header" in result.message

    def test_validate_all_successful(self):
        """Test comprehensive validation when all checks pass."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create all required files with proper content and adequate sizes
            (Path(temp_dir) / "addresses.csv").write_text(
                "id,name\n" + "1,Test\n" * 1000
            )  # Make it larger
            (Path(temp_dir) / "settlements.csv").write_text(
                "id,name\n" + "1,Test\n" * 100
            )
            (Path(temp_dir) / "counties.csv").write_text("id,name\n" + "1,Test\n" * 50)
            (Path(temp_dir) / "database.duckdb").write_text("x" * 2000)
            (Path(temp_dir) / "PublicSpaceName.csv").write_text(
                "id,name\n" + "1,Test\n" * 10
            )
            (Path(temp_dir) / "PublicSpaceType.csv").write_text(
                "id,name\n" + "1,Test\n" * 10
            )
            (Path(temp_dir) / "SettlementPublicSpaces.csv").write_text(
                "id,name\n" + "1,Test\n" * 10
            )

            validator = DataValidator(temp_dir)
            summary = validator.validate_all()

            assert summary.valid is True
            assert len(summary.checks) == 6
            assert all(check.status == "passed" for check in summary.checks)

    def test_validate_all_with_failures(self):
        """Test comprehensive validation when some checks fail."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create only some files
            (Path(temp_dir) / "addresses.csv").write_text("id,name\n1,Test\n")

            validator = DataValidator(temp_dir)
            summary = validator.validate_all()

            assert summary.valid is False
            assert len(summary.checks) == 6
            # Should have some failed checks
            failed_checks = [
                check for check in summary.checks if check.status == "failed"
            ]
            assert len(failed_checks) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
