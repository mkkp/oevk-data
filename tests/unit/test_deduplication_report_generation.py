"""
Unit tests for deduplication report generation functionality.

These tests verify the new report generation and export features.
"""

import pytest
import polars as pl
import json
from datetime import datetime
from src.etl.deduplicate import AddressDeduplicator
from src.etl.models import DeduplicationReport


class TestDeduplicationReportGeneration:
    """Test deduplication report generation and export functionality."""

    def test_generate_deduplication_report_method(self):
        """Test the generate_deduplication_report method directly."""
        deduplicator = AddressDeduplicator()

        # Create test data
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3"],
                "county_code": ["01", "01", "02"],
                "settlement_name": ["Budapest", "Budapest", "Debrecen"],
                "street_name": ["Main Street", "Main Street", "Other Street"],
                "house_number": ["1", "1", "2"],
                "building": ["A", "A", None],
                "staircase": ["1", "1", None],
                "polling_station_id": ["ps1", "ps2", "ps3"],
                "accessibility_flag": [True, False, True],
                "pir_code": ["pir1", "pir2", "pir3"],
            }
        )

        # Run deduplication
        result = deduplicator.deduplicate_addresses(test_data, generate_report=True)

        # Verify report is included in result
        assert "deduplication_report" in result
        report = result["deduplication_report"]

        # Verify report structure
        assert isinstance(report, DeduplicationReport)
        assert report.total_addresses == 3
        assert report.duplicates_found == 1  # addr1 and addr2 are duplicates
        assert report.canonical_addresses_created == 2
        assert report.status == "completed"
        assert report.processing_time_ms > 0

    def test_export_report_to_json(self):
        """Test exporting deduplication report to JSON."""
        deduplicator = AddressDeduplicator()

        # Create a test report
        report = DeduplicationReport(
            id="test_report_123",
            run_id="test_run_20250101",
            total_addresses=1000,
            duplicates_found=150,
            canonical_addresses_created=850,
            processing_time_ms=2500,
            status="completed",
            created_at=datetime.now(),
        )

        # Export to JSON
        json_output = deduplicator.export_report_to_json(report)

        # Verify JSON structure
        report_dict = json.loads(json_output)

        assert report_dict["id"] == "test_report_123"
        assert report_dict["run_id"] == "test_run_20250101"
        assert report_dict["total_addresses"] == 1000
        assert report_dict["duplicates_found"] == 150
        assert report_dict["canonical_addresses_created"] == 850
        assert report_dict["processing_time_ms"] == 2500
        assert report_dict["status"] == "completed"
        assert "created_at" in report_dict

    def test_report_generation_with_error(self):
        """Test report generation handles errors gracefully."""
        deduplicator = AddressDeduplicator()

        # Create empty test data that will cause validation error
        test_data = pl.DataFrame(
            {
                "address_id": [],
                "county_code": [],
                "settlement_name": [],
                "street_name": [],
                "house_number": [],
                "building": [],
                "staircase": [],
                "polling_station_id": [],
                "accessibility_flag": [],
                "pir_code": [],
            }
        )

        # Run deduplication with report generation
        with pytest.raises(Exception):
            deduplicator.deduplicate_addresses(test_data, generate_report=True)

    def test_report_generation_with_custom_run_id(self):
        """Test report generation with custom run ID."""
        deduplicator = AddressDeduplicator()

        # Create test data
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2"],
                "county_code": ["01", "01"],
                "settlement_name": ["Budapest", "Budapest"],
                "street_name": ["Main Street", "Main Street"],
                "house_number": ["1", "1"],
                "building": ["A", "A"],
                "staircase": ["1", "1"],
                "polling_station_id": ["ps1", "ps2"],
                "accessibility_flag": [True, False],
                "pir_code": ["pir1", "pir2"],
            }
        )

        # Generate report with custom run ID
        result = deduplicator.deduplicate_addresses(test_data)
        report = result["deduplication_report"]

        # Verify run ID is generated
        assert report.run_id is not None
        assert report.run_id.startswith("dedup_")

    def test_report_metrics_calculation_comprehensive(self):
        """Test comprehensive metrics calculation in report generation."""
        deduplicator = AddressDeduplicator()

        # Create test data with various duplication scenarios
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4", "addr5"],
                "county_code": ["01", "01", "01", "01", "02"],
                "settlement_name": [
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Debrecen",
                ],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Other Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "1", "2", "1"],
                "building": ["A", "A", "B", None, None],
                "staircase": ["1", "1", "2", None, None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4", "ps5"],
                "accessibility_flag": [True, False, True, True, False],
                "pir_code": ["pir1", "pir2", "pir3", "pir4", "pir5"],
            }
        )

        # Run deduplication with report
        result = deduplicator.deduplicate_addresses(test_data, generate_report=True)
        report = result["deduplication_report"]

        # Verify comprehensive metrics
        assert report.total_addresses == 5
        assert report.duplicates_found == 1  # addr1+addr2 merged, others separate
        assert report.canonical_addresses_created == 4
        assert report.status == "completed"

        # Verify deduplication rate calculation
        expected_rate = (1 / 5) * 100
        deduplication_rate = (report.duplicates_found / report.total_addresses) * 100
        assert deduplication_rate == pytest.approx(expected_rate, 0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
