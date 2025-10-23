"""Unit tests for PostGIS coordinate conversion functions."""

import pytest
from src.etl.export import convert_center_to_point, convert_polygon_to_wkt


class TestCenterConversion:
    """Test suite for convert_center_to_point() function."""

    def test_valid_conversion(self):
        """Test valid center point conversion with coordinate swap."""
        result = convert_center_to_point("47.4979 19.0402")
        assert result == "POINT(19.0402 47.4979)", "Should swap lat/lon to lon/lat"

    def test_coordinate_swap(self):
        """Test that coordinates are swapped correctly (lon first)."""
        result = convert_center_to_point("47.0 19.0")
        assert result is not None
        assert result.startswith("POINT(19.0"), "Longitude should come first"
        assert "47.0" in result, "Latitude should be second"

    def test_null_handling(self):
        """Test NULL and empty string handling."""
        assert convert_center_to_point(None) is None
        assert convert_center_to_point("") is None
        assert convert_center_to_point("   ") is None

    def test_invalid_format_single_value(self):
        """Test invalid format with single value."""
        assert convert_center_to_point("47.0") is None

    def test_invalid_format_text(self):
        """Test invalid format with non-numeric text."""
        assert convert_center_to_point("invalid") is None

    def test_invalid_format_too_many_values(self):
        """Test invalid format with too many values."""
        assert convert_center_to_point("47.0 19.0 10.0") is None

    def test_out_of_range_latitude_high(self):
        """Test latitude > 90 is rejected."""
        assert convert_center_to_point("91.0 19.0") is None

    def test_out_of_range_latitude_low(self):
        """Test latitude < -90 is rejected."""
        assert convert_center_to_point("-91.0 19.0") is None

    def test_out_of_range_longitude_high(self):
        """Test longitude > 180 is rejected."""
        assert convert_center_to_point("47.0 181.0") is None

    def test_out_of_range_longitude_low(self):
        """Test longitude < -180 is rejected."""
        assert convert_center_to_point("47.0 -181.0") is None

    def test_boundary_values_lat(self):
        """Test boundary values for latitude."""
        assert convert_center_to_point("90.0 0.0") == "POINT(0.0 90.0)"
        assert convert_center_to_point("-90.0 0.0") == "POINT(0.0 -90.0)"

    def test_boundary_values_lon(self):
        """Test boundary values for longitude."""
        assert convert_center_to_point("0.0 180.0") == "POINT(180.0 0.0)"
        assert convert_center_to_point("0.0 -180.0") == "POINT(-180.0 0.0)"

    def test_decimal_precision(self):
        """Test that decimal precision is preserved."""
        result = convert_center_to_point("47.123456 19.654321")
        assert "19.654321" in result
        assert "47.123456" in result

    def test_whitespace_handling(self):
        """Test handling of extra whitespace."""
        result = convert_center_to_point("  47.0   19.0  ")
        assert result == "POINT(19.0 47.0)"


class TestPolygonConversion:
    """Test suite for convert_polygon_to_wkt() function."""

    def test_valid_conversion(self):
        """Test valid polygon conversion with coordinate swap."""
        result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
        assert result is not None
        assert result.startswith("POLYGON((")
        assert result.endswith("))")
        # Verify coordinate swap (lon before lat)
        assert "19.0 47.5" in result
        assert "19.1 47.5" in result
        assert "19.1 47.4" in result

    def test_auto_close_polygon(self):
        """Test polygon auto-closing when first != last."""
        result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.4 19.1")
        # Should be closed with first point repeated at end
        assert result.endswith("19.0 47.5))")

    def test_already_closed_polygon(self):
        """Test that already-closed polygon is not duplicated."""
        result = convert_polygon_to_wkt("47.5 19.0,47.5 19.1,47.5 19.0")
        # Should have exactly 2 occurrences of "19.0 47.5" (first and last)
        assert result.count("19.0 47.5") == 2

    def test_minimum_points_valid(self):
        """Test polygon with exactly 3 points (minimum valid)."""
        result = convert_polygon_to_wkt("47.0 19.0,47.1 19.1,47.0 19.1")
        assert result is not None
        assert "POLYGON((" in result

    def test_minimum_points_invalid(self):
        """Test polygon with less than 3 points is rejected."""
        assert convert_polygon_to_wkt("47.0 19.0,47.1 19.1") is None

    def test_single_point(self):
        """Test polygon with single point is rejected."""
        assert convert_polygon_to_wkt("47.0 19.0") is None

    def test_null_handling(self):
        """Test NULL and empty string handling."""
        assert convert_polygon_to_wkt(None) is None
        assert convert_polygon_to_wkt("") is None
        assert convert_polygon_to_wkt("   ") is None

    def test_invalid_coordinate_pair(self):
        """Test handling of invalid coordinate pairs."""
        # Only one valid pair - should fail
        result = convert_polygon_to_wkt("47.0 19.0,invalid,47.1 19.1")
        # Should log warning but only use valid coords - too few points
        assert result is None

    def test_out_of_range_coordinates(self):
        """Test that out-of-range coordinates are skipped."""
        # First coord out of range, remaining should be too few
        result = convert_polygon_to_wkt("91.0 19.0,47.0 19.0,47.1 19.1")
        assert result is None  # Only 2 valid points remain

    def test_complex_polygon(self):
        """Test complex polygon with many points."""
        coords = ",".join([f"47.{i} 19.{i}" for i in range(10)])
        result = convert_polygon_to_wkt(coords)
        assert result is not None
        # Should have 11 points (10 original + 1 auto-close)
        assert result.count(",") == 10

    def test_decimal_precision(self):
        """Test that decimal precision is preserved."""
        result = convert_polygon_to_wkt("47.123456 19.654321,47.234567 19.765432,47.345678 19.876543")
        assert "19.654321 47.123456" in result
        assert "19.765432 47.234567" in result
        assert "19.876543 47.345678" in result

    def test_whitespace_handling(self):
        """Test handling of extra whitespace in coordinates."""
        result = convert_polygon_to_wkt("  47.0   19.0  ,  47.1   19.1  ,  47.0   19.1  ")
        assert result is not None
        assert "19.0 47.0" in result


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_center_with_commas(self):
        """Test center point with comma separator (invalid)."""
        assert convert_center_to_point("47.0, 19.0") is None

    def test_polygon_with_space_separator(self):
        """Test polygon with only space separators (invalid)."""
        # Polygon needs comma-separated pairs
        result = convert_polygon_to_wkt("47.0 19.0 47.1 19.1 47.0 19.1")
        # This would be parsed as a single invalid pair
        assert result is None

    def test_negative_coordinates(self):
        """Test negative coordinates (valid for southern/western hemispheres)."""
        center = convert_center_to_point("-45.0 -120.0")
        assert center == "POINT(-120.0 -45.0)"

    def test_zero_coordinates(self):
        """Test zero coordinates (valid)."""
        center = convert_center_to_point("0.0 0.0")
        assert center == "POINT(0.0 0.0)"

    def test_scientific_notation(self):
        """Test coordinates in scientific notation."""
        # Python float() should handle scientific notation
        center = convert_center_to_point("4.74979e1 1.90402e1")
        assert center is not None
        assert "19.0402" in center or "1.90402" in center
