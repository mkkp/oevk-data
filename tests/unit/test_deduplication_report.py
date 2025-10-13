"""
Unit tests for deduplication report generation.

These tests verify the report generation functionality for deduplication operations.
"""

import pytest
import polars as pl
from datetime import datetime
from src.etl.deduplicate import AddressDeduplicator
from src.etl.models import DeduplicationReport


class TestDeduplicationReport:
    """Test deduplication report generation."""

    def test_generate_deduplication_report(self):
        """Test that deduplication report is generated with correct statistics."""
        deduplicator = AddressDeduplicator()

        # Create test data with duplicates
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4"],
                "county_code": ["01", "01", "01", "02"],
                "settlement_name": ["Budapest", "Budapest", "Budapest", "Debrecen"],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Other Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "2", "1"],
                "building": ["A", "A", None, None],
                "staircase": ["1", "1", None, None],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4"],
                "accessibility_flag": [True, False, True, False],
                "pir_code": ["pir1", "pir2", "pir3", "pir4"],
            }
        )

        # Run deduplication
        result = deduplicator.deduplicate_addresses(test_data)

        # Verify report statistics can be calculated
        canonical_addresses = result["canonical_addresses"]
        address_mapping = result["address_mapping"]

        # Calculate expected statistics
        total_addresses = len(test_data)
        canonical_count = len(canonical_addresses)
        duplicates_found = total_addresses - canonical_count

        # Verify statistics are reasonable
        assert total_addresses == 4
        assert (
            canonical_count == 3
        )  # addr1+addr2 merged, addr3 separate, addr4 separate
        assert duplicates_found == 1

        # Verify report model can be created
        report = DeduplicationReport(
            id="test_report_id",
            run_id="test_run",
            total_addresses=total_addresses,
            duplicates_found=duplicates_found,
            canonical_addresses_created=canonical_count,
            processing_time_ms=100,
            status="completed",
            created_at=datetime.now(),
        )

        # Verify report structure
        assert report.total_addresses == 4
        assert report.duplicates_found == 1
        assert report.canonical_addresses_created == 3
        assert report.status == "completed"

    def test_report_generation_with_empty_data(self):
        """Test report generation with empty input data."""
        deduplicator = AddressDeduplicator()

        # Create empty test data
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

        # Verify empty data validation
        with pytest.raises(Exception):
            deduplicator.deduplicate_addresses(test_data)

        # Verify report model can be created for empty data scenario
        report = DeduplicationReport(
            id="empty_report_id",
            run_id="empty_run",
            total_addresses=0,
            duplicates_found=0,
            canonical_addresses_created=0,
            processing_time_ms=50,
            status="failed",
            error_message="Input DataFrame is empty or None",
            created_at=datetime.now(),
        )

        # Verify report structure for empty data
        assert report.total_addresses == 0
        assert report.duplicates_found == 0
        assert report.canonical_addresses_created == 0
        assert report.status == "failed"
        assert report.error_message == "Input DataFrame is empty or None"

    def test_report_generation_with_all_duplicates(self):
        """Test report generation when all addresses are duplicates."""
        deduplicator = AddressDeduplicator()

        # Create test data where all addresses are duplicates
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4"],
                "county_code": ["01", "01", "01", "01"],
                "settlement_name": ["Budapest", "Budapest", "Budapest", "Budapest"],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "1", "1"],
                "building": ["A", "A", "A", "A"],
                "staircase": ["1", "1", "1", "1"],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4"],
                "accessibility_flag": [True, False, True, False],
                "pir_code": ["pir1", "pir2", "pir3", "pir4"],
            }
        )

        # Run deduplication
        result = deduplicator.deduplicate_addresses(test_data)

        # Verify report statistics for all duplicates
        canonical_addresses = result["canonical_addresses"]

        # Calculate expected statistics
        total_addresses = len(test_data)
        canonical_count = len(canonical_addresses)
        duplicates_found = total_addresses - canonical_count

        # Verify statistics for all duplicates
        assert total_addresses == 4
        assert canonical_count == 1  # All addresses merged into one
        assert duplicates_found == 3

        # Verify report model can be created for all duplicates
        report = DeduplicationReport(
            id="all_duplicates_report_id",
            run_id="all_duplicates_run",
            total_addresses=total_addresses,
            duplicates_found=duplicates_found,
            canonical_addresses_created=canonical_count,
            processing_time_ms=150,
            status="completed",
            created_at=datetime.now(),
        )

        # Verify report structure for all duplicates
        assert report.total_addresses == 4
        assert report.duplicates_found == 3
        assert report.canonical_addresses_created == 1
        assert report.status == "completed"

    def test_report_metrics_calculation(self):
        """Test calculation of deduplication metrics and statistics."""
        deduplicator = AddressDeduplicator()

        # Create test data with mixed duplicates
        test_data = pl.DataFrame(
            {
                "address_id": ["addr1", "addr2", "addr3", "addr4", "addr5", "addr6"],
                "county_code": ["01", "01", "01", "01", "02", "02"],
                "settlement_name": [
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Budapest",
                    "Debrecen",
                    "Debrecen",
                ],
                "street_name": [
                    "Main Street",
                    "Main Street",
                    "Main Street",
                    "Other Street",
                    "Main Street",
                    "Main Street",
                ],
                "house_number": ["1", "1", "1", "2", "1", "1"],
                "building": ["A", "A", "B", None, None, "C"],
                "staircase": ["1", "1", "2", None, None, "3"],
                "polling_station_id": ["ps1", "ps2", "ps3", "ps4", "ps5", "ps6"],
                "accessibility_flag": [True, False, True, True, False, True],
                "pir_code": ["pir1", "pir2", "pir3", "pir4", "pir5", "pir6"],
            }
        )

        # Run deduplication
        result = deduplicator.deduplicate_addresses(test_data)

        # Calculate metrics
        canonical_addresses = result["canonical_addresses"]
        polling_stations = result["address_polling_stations"]
        pir_codes = result["address_pir_codes"]

        total_addresses = len(test_data)
        canonical_count = len(canonical_addresses)
        duplicates_found = total_addresses - canonical_count
        deduplication_rate = (
            (duplicates_found / total_addresses) * 100 if total_addresses > 0 else 0
        )

        # Verify metrics are calculated correctly
        assert total_addresses == 6
        # Expected: 5 canonical addresses (all addresses distinct due to building/staircase differences)
        assert canonical_count == 5
        assert duplicates_found == 1
        assert deduplication_rate == pytest.approx(16.67, 0.01)

        # Verify relationship preservation metrics
        unique_polling_stations = len(polling_stations["polling_station_id"].unique())
        unique_pir_codes = len(pir_codes["pir_code"].unique())

        assert unique_polling_stations == 6  # All polling stations preserved
        assert unique_pir_codes == 6  # All PIR codes preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
