"""
Address Deduplication Module

This module provides functionality for identifying and merging duplicate addresses
in the OEVK data processing pipeline using deterministic hash IDs.
"""

import logging
from datetime import datetime
from typing import Dict

import polars as pl
import xxhash

from src.etl.models import DeduplicationReport
from src.utils.pipeline_logging import PipelineLogger

logger = logging.getLogger(__name__)


class DeduplicationError(Exception):
    """Base exception for deduplication operations."""

    pass


class DataValidationError(DeduplicationError):
    """Exception for data validation failures."""

    pass


class HashGenerationError(DeduplicationError):
    """Exception for hash generation failures."""

    pass


class RelationshipPreservationError(DeduplicationError):
    """Exception for relationship preservation failures."""

    pass


class AddressDeduplicator:
    """Main class for address deduplication."""

    def __init__(self, seed: int = 20241012, enable_logging: bool = True):
        """
        Initialize deduplicator with hash seed.

        Args:
            seed: Seed for deterministic hash generation
            enable_logging: Whether to enable structured logging
        """
        self.seed = seed
        self.enable_logging = enable_logging

        if enable_logging:
            self.logger = PipelineLogger("deduplication")
        else:
            self.logger = None

    def deduplicate_addresses(
        self, addresses_df: pl.DataFrame, generate_report: bool = True
    ) -> Dict[str, pl.DataFrame | DeduplicationReport]:
        """
        Deduplicate addresses and return canonical records with preserved relationships.

        Args:
            addresses_df: DataFrame with raw addresses
            generate_report: Whether to generate a deduplication report

        Returns:
            Dictionary with canonical addresses, relationships, and optional report

        Raises:
            DataValidationError: If input data validation fails
            HashGenerationError: If hash generation fails
            RelationshipPreservationError: If relationship preservation fails
        """
        import time

        try:
            start_time = time.time()

            if self.logger:
                self.logger.log_start(
                    "address_deduplication", row_count=len(addresses_df)
                )

            logger.info(f"Starting deduplication for {len(addresses_df)} addresses")

            # Step 0: Validate input data
            self._validate_input_data(addresses_df)

            # Step 1: Generate canonical IDs
            logger.debug("Generating canonical IDs")
            addresses_with_ids = self._generate_canonical_ids(addresses_df)
            logger.debug(
                f"Generated {len(addresses_with_ids)} addresses with canonical IDs"
            )

            # Step 2: Create canonical addresses
            logger.debug("Creating canonical addresses")
            canonical_addresses = self._create_canonical_addresses(addresses_with_ids)
            logger.debug(f"Created {len(canonical_addresses)} canonical addresses")

            # Step 3: Preserve relationships
            logger.debug("Preserving relationships")
            relationships = self._preserve_relationships(
                addresses_with_ids, canonical_addresses
            )
            logger.debug("Relationships preserved successfully")

            # Step 4: Validate output
            logger.debug("Validating output")
            self._validate_output(canonical_addresses, relationships)
            logger.debug("Output validation complete")

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Calculate deduplication statistics
            original_count = len(addresses_df)
            canonical_count = len(canonical_addresses)
            deduplication_rate = (
                (1 - canonical_count / original_count) * 100
                if original_count > 0
                else 0
            )

            if self.logger:
                self.logger.log_completion(
                    "address_deduplication",
                    processing_time_ms / 1000,  # Convert milliseconds to seconds
                    canonical_count=canonical_count,
                    original_count=original_count,
                )

            logger.info(
                f"Deduplication complete: {canonical_count} canonical addresses "
                f"(from {original_count} original, {deduplication_rate:.1f}% reduction)"
            )

            result = {"canonical_addresses": canonical_addresses, **relationships}

            # Generate report if requested
            if generate_report:
                report = self.generate_deduplication_report(
                    addresses_df=addresses_df,
                    deduplication_result=result,
                    processing_time_ms=processing_time_ms,
                )
                result["deduplication_report"] = report

            return result

        except Exception as e:
            error_msg = f"Deduplication failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.logger:
                self.logger.log_error("address_deduplication", e)
            raise DeduplicationError(error_msg) from e

    def _validate_input_data(self, addresses_df: pl.DataFrame) -> None:
        """Validate input data before deduplication."""
        if addresses_df is None or len(addresses_df) == 0:
            raise DataValidationError("Input DataFrame is empty or None")

        required_columns = [
            "county_code",
            "settlement_name",
            "street_name",
            "house_number",
        ]
        missing_columns = [
            col for col in required_columns if col not in addresses_df.columns
        ]

        if missing_columns:
            raise DataValidationError(f"Missing required columns: {missing_columns}")

        # Check for null values in required columns
        for col in required_columns:
            null_count = addresses_df[col].null_count()
            if null_count > 0:
                logger.warning(f"Column {col} has {null_count} null values")

    def _validate_output(
        self, canonical_addresses: pl.DataFrame, relationships: Dict[str, pl.DataFrame]
    ) -> None:
        """Validate deduplication output data."""
        if canonical_addresses is None or len(canonical_addresses) == 0:
            raise DataValidationError("No canonical addresses generated")

        # Check for duplicate canonical IDs
        duplicate_ids = (
            canonical_addresses.group_by("canonical_address_id")
            .agg(pl.len().alias("count"))
            .filter(pl.col("count") > 1)
        )

        if len(duplicate_ids) > 0:
            raise DataValidationError(
                f"Found {len(duplicate_ids)} duplicate canonical IDs"
            )

        # Validate relationship tables
        required_relationships = [
            "address_polling_stations",
            "address_pir_codes",
            "address_mapping",
        ]
        for rel_name in required_relationships:
            if rel_name not in relationships:
                raise DataValidationError(f"Missing relationship table: {rel_name}")

        # Validate data preservation
        self._validate_data_preservation(relationships)

    def _validate_data_preservation(
        self, relationships: Dict[str, pl.DataFrame]
    ) -> None:
        """Validate that all original data is preserved in relationships."""
        address_mapping = relationships["address_mapping"]
        polling_stations = relationships["address_polling_stations"]
        pir_codes = relationships["address_pir_codes"]

        # Validate all canonical IDs in relationships exist in canonical addresses
        # (This validation is done in the main _validate_output method)

        # Log validation statistics
        logger.info(
            f"Address mapping: {len(address_mapping)} original addresses mapped"
        )
        logger.info(f"Polling stations: {len(polling_stations)} assignments preserved")
        logger.info(f"PIR codes: {len(pir_codes)} codes preserved")

        # Check for orphaned canonical IDs in relationships
        # (This would require access to canonical_addresses, so it's done in _validate_output)

    def generate_deduplication_report(
        self,
        addresses_df: pl.DataFrame,
        deduplication_result: Dict[str, pl.DataFrame],
        processing_time_ms: int,
        run_id: str | None = None,
    ) -> DeduplicationReport:
        """
        Generate a deduplication report with statistics and metrics.

        Args:
            addresses_df: Original input DataFrame
            deduplication_result: Result from deduplicate_addresses method
            processing_time_ms: Processing time in milliseconds
            run_id: Optional run identifier

        Returns:
            DeduplicationReport object with statistics
        """
        try:
            if run_id is None:
                run_id = f"dedup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Calculate statistics
            total_addresses = len(addresses_df)
            canonical_addresses = deduplication_result["canonical_addresses"]
            canonical_count = len(canonical_addresses)
            duplicates_found = total_addresses - canonical_count

            # Calculate additional metrics
            deduplication_rate = (
                (duplicates_found / total_addresses) * 100 if total_addresses > 0 else 0
            )

            # Get relationship preservation statistics
            polling_stations = deduplication_result["address_polling_stations"]
            pir_codes = deduplication_result["address_pir_codes"]

            unique_polling_stations = len(
                polling_stations["polling_station_id"].unique()
            )
            unique_pir_codes = len(pir_codes["pir_code"].unique())

            # Create report
            report_id = xxhash.xxh64_intdigest(run_id, seed=self.seed)

            report = DeduplicationReport(
                id=str(report_id),
                run_id=run_id,
                total_addresses=total_addresses,
                duplicates_found=duplicates_found,
                canonical_addresses_created=canonical_count,
                processing_time_ms=processing_time_ms,
                status="completed",
                created_at=datetime.now(),
            )

            # Log report generation
            logger.info(
                f"Generated deduplication report: {duplicates_found} duplicates found "
                f"({deduplication_rate:.1f}% deduplication rate)"
            )
            logger.debug(
                f"Report details: {unique_polling_stations} unique polling stations, "
                f"{unique_pir_codes} unique PIR codes preserved"
            )

            return report

        except Exception as e:
            error_msg = f"Report generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Return error report
            return DeduplicationReport(
                id="error_report",
                run_id=run_id or "unknown",
                total_addresses=0,
                duplicates_found=0,
                canonical_addresses_created=0,
                processing_time_ms=processing_time_ms,
                status="failed",
                error_message=error_msg,
                created_at=datetime.now(),
            )

    def export_report_to_json(self, report: DeduplicationReport) -> str:
        """
        Export deduplication report to JSON format.

        Args:
            report: DeduplicationReport object

        Returns:
            JSON string representation of the report
        """
        try:
            import json
            from datetime import datetime

            # Convert report to dictionary
            report_dict = {
                "id": report.id,
                "run_id": report.run_id,
                "total_addresses": report.total_addresses,
                "duplicates_found": report.duplicates_found,
                "canonical_addresses_created": report.canonical_addresses_created,
                "processing_time_ms": report.processing_time_ms,
                "status": report.status,
                "error_message": report.error_message,
                "created_at": (
                    report.created_at.isoformat()
                    if report.created_at
                    else datetime.now().isoformat()
                ),
            }

            # Remove None values
            report_dict = {k: v for k, v in report_dict.items() if v is not None}

            json_output = json.dumps(report_dict, indent=2, ensure_ascii=False)
            logger.info(f"Exported deduplication report to JSON: {report.id}")

            return json_output

        except Exception as e:
            error_msg = f"Report export failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DeduplicationError(error_msg) from e

    def _clean_house_number(self, house_num: str) -> str:
        """
        Clean house number by removing leading zeros.

        IMPORTANT: Returns empty string ("") if the house number consists entirely of zeros
        (e.g., "0000", "00000", "0" -> "") to allow addresses without house numbers but
        with building/staircase identifiers or infrastructure addresses.
        Leading zeros before actual digits are stripped normally.

        Examples - Valid cases (leading zeros stripped):
        - "000001" -> "1"
        - "000001/D" -> "1/D"
        - "000001-00005" -> "1-5"

        Examples - Empty house number (all zeros - returns empty string):
        - "0000" -> "" (no house number - address may still be valid with building/staircase)
        - "00000" -> "" (no house number)
        - "0" -> "" (no house number)
        - "0000/D" -> "" (base number is all zeros, suffix discarded)
        - "0000-0005" -> "" (first part is all zeros, range invalid)
        - "" -> "" (empty input)
        - None -> "" (null input)

        Returns:
            Cleaned house number string, or empty string if no house number
        """
        if not house_num:
            return ""

        house_num = house_num.strip()
        if not house_num:
            return ""

        # Handle ranges (e.g., "000001-00005" -> "1-5")
        if "-" in house_num:
            parts = house_num.split("-")
            cleaned_parts = []
            for part in parts:
                cleaned = part.lstrip("0")
                # If any part becomes empty after stripping zeros, return empty string
                if not cleaned:
                    return ""
                cleaned_parts.append(cleaned)
            return "-".join(cleaned_parts)

        # Handle slash notation (e.g., "000001/D" -> "1/D")
        if "/" in house_num:
            parts = house_num.split("/", 1)
            cleaned_base = parts[0].lstrip("0")
            # If base becomes empty after stripping zeros, return empty string
            if not cleaned_base:
                return ""
            return f"{cleaned_base}/{parts[1]}"

        # Simple number (e.g., "000001" -> "1")
        cleaned = house_num.lstrip("0")
        # If it becomes empty after stripping zeros, return empty string (no house number)
        if not cleaned:
            return ""
        return cleaned

    def _to_roman_numeral(self, num_str: str) -> str:
        """
        Convert numeric string to Roman numeral.

        Examples:
        - "1" -> "I"
        - "5" -> "V"
        - "10" -> "X"
        """
        try:
            num = int(num_str)
            if num <= 0 or num > 3999:
                return num_str  # Return as-is if out of range

            val_map = [
                (1000, "M"),
                (900, "CM"),
                (500, "D"),
                (400, "CD"),
                (100, "C"),
                (90, "XC"),
                (50, "L"),
                (40, "XL"),
                (10, "X"),
                (9, "IX"),
                (5, "V"),
                (4, "IV"),
                (1, "I"),
            ]

            result = ""
            for value, numeral in val_map:
                count = num // value
                result += numeral * count
                num -= value * count

            return result
        except (ValueError, TypeError):
            return num_str  # Return as-is if not a valid number

    def _format_full_address(
        self,
        street_name: str,
        street_type: str,
        house_num: str,
        building: str,
        staircase: str,
    ) -> str:
        """
        Format full address according to Hungarian address format rules.

        IMPORTANT: Now allows addresses without house numbers if building/staircase exists,
        or for infrastructure/area addresses.
        - "0000" with building/staircase -> valid address
        - "0000" without any identifier -> infrastructure/area address (valid)
        Leading zeros before actual digits are stripped normally (e.g., "000001" -> "1").

        Rules:
        1. House number with "/" AND both building+staircase: Ignore "/", use "number. B. épület L. lépcsőház"
        2. House number with "/" AND only staircase: Keep "/", add "number/X. L. lépcsőház"
        3. House number with "/" AND no building/staircase: Use "number/X."
        4. House number without "/" AND both building+staircase: "number/B. L. lépcsőház"
        5. House number without "/" AND only building: "number/B."
        6. House number without "/" AND only staircase: "number/S."
        7. House number without "/" AND no building/staircase: "number."

        Examples:
        - ("Körtöltés utca", "000001", "D", "") -> "Körtöltés utca 1/D."
        - ("Körtöltés utca", "000001", "", "D") -> "Körtöltés utca 1/D."
        - ("Körtöltés utca", "000001", "D", "L") -> "Körtöltés utca 1/D. L. lépcsőház"
        - ("Körtöltés utca", "000001/D", "", "") -> "Körtöltés utca 1/D."
        - ("Körtöltés utca", "000001/D", "B", "L") -> "Körtöltés utca 1. B. épület L. lépcsőház"
        - ("Körtöltés utca", "000001/D", "", "L") -> "Körtöltés utca 1/D. L. lépcsőház"
        - ("Körtöltés utca", "000001-00005", "B", "L") -> "Körtöltés utca 1-5. B. épület L. lépcsőház"
        - ("Gázgyári lakótelep", "0000", "0001", "0001") -> "Gázgyári lakótelep, 1. épület I. lépcsőház"
        - ("Vasútállomás", "0000", "", "") -> "Vasútállomás" (infrastructure address)

        Returns:
            Formatted address string (never None - all addresses can be formatted)
        """
        # Clean house number
        cleaned_house = self._clean_house_number(house_num)

        # Normalize building - trim leading zeros
        building_raw = (building or "").strip()
        building_is_numeric = building_raw and building_raw.isdigit()
        if building_is_numeric:
            building = building_raw.lstrip("0") or "0"
        else:
            building = building_raw.upper() if building_raw else ""

        # Normalize staircase - trim leading zeros and convert numeric to Roman
        staircase_raw = (staircase or "").strip()
        staircase_is_numeric = staircase_raw and staircase_raw.isdigit()
        if staircase_is_numeric:
            staircase_num = staircase_raw.lstrip("0") or "0"
            staircase = self._to_roman_numeral(staircase_num)
        else:
            staircase = staircase_raw.upper() if staircase_raw else ""

        has_slash = "/" in house_num if house_num else False
        has_range = "-" in house_num if house_num else False
        has_building = bool(building)
        has_staircase = bool(staircase)
        has_house_number = bool(cleaned_house)

        # Build street prefix with type
        street_prefix = f"{street_name} {street_type}".strip()

        # Handle addresses without house numbers
        if not has_house_number:
            # Case 1: Has building AND staircase -> "Street Name, B. épület L. lépcsőház"
            if has_building and has_staircase:
                return f"{street_prefix}, {building}. épület {staircase}. lépcsőház"

            # Case 2: Has only building -> "Street Name, B. épület"
            if has_building:
                return f"{street_prefix}, {building}. épület"

            # Case 3: Has only staircase -> "Street Name, L. lépcsőház"
            if has_staircase:
                return f"{street_prefix}, {staircase}. lépcsőház"

            # Case 4: No house number, no building, no staircase -> "Street Name" (infrastructure/area address)
            return street_prefix

        # Rule 1: Has "/" AND both building+staircase -> Ignore "/", use épület format
        if has_slash and has_building and has_staircase:
            # Extract base number from "1/D" -> "1"
            base_num = cleaned_house.split("/")[0]
            return (
                f"{street_prefix} {base_num}. {building}. épület {staircase}. lépcsőház"
            )

        # Rule 2: Has "/" AND only staircase -> Keep "/", add lépcsőház
        if has_slash and not has_building and has_staircase:
            return f"{street_prefix} {cleaned_house}. {staircase}. lépcsőház"

        # Rule 3: Has "/" AND no building/staircase -> Use as-is
        if has_slash and not has_building and not has_staircase:
            return f"{street_prefix} {cleaned_house}."

        # Rule 4a: No "/" AND has RANGE AND both building+staircase -> "1-5. B. épület L. lépcsőház"
        if not has_slash and has_range and has_building and has_staircase:
            return f"{street_prefix} {cleaned_house}. {building}. épület {staircase}. lépcsőház"

        # Rule 4b: No "/" AND simple number AND both building+staircase
        # Special case: if BOTH building and staircase are numeric, use épület format
        if not has_slash and not has_range and has_building and has_staircase:
            if building_is_numeric and staircase_is_numeric:
                return f"{street_prefix} {cleaned_house}. {building}. épület {staircase}. lépcsőház"
            else:
                return f"{street_prefix} {cleaned_house}/{building}. {staircase}. lépcsőház"

        # Rule 5: No "/" AND only building -> "number/B."
        if not has_slash and has_building:
            return f"{street_prefix} {cleaned_house}/{building}."

        # Rule 6: No "/" AND only staircase -> "number/S."
        if not has_slash and has_staircase:
            return f"{street_prefix} {cleaned_house}/{staircase}."

        # Rule 7: No "/" AND no building/staircase -> "number."
        return f"{street_prefix} {cleaned_house}."

    def _generate_canonical_ids(self, addresses_df: pl.DataFrame) -> pl.DataFrame:
        """
        Generate deterministic canonical address IDs based on formatted full address.

        The canonical ID is computed from the FINAL formatted address string to ensure
        that addresses which format to the same string are considered duplicates.

        Format examples:
        - ("000001", "D", "") -> "Körtöltés utca 1/D."
        - ("000001", "", "D") -> "Körtöltés utca 1/D."
        - ("000001/D", "", "") -> "Körtöltés utca 1/D."
        All three above hash to the same canonical ID (they're duplicates).

        - ("000001", "D", "L") -> "Körtöltés utca 1/D. L. lépcsőház"
        - ("000001/D", "B", "L") -> "Körtöltés utca 1. B. épület L. lépcsőház"
        These two are DIFFERENT addresses (different canonical IDs).
        """

        # Format full address for each row using Python UDF
        def format_address_udf(
            street_name: str,
            street_type: str,
            house_num: str,
            building: str,
            staircase: str,
        ) -> str:
            return self._format_full_address(
                street_name or "",
                street_type or "",
                house_num or "",
                building or "",
                staircase or "",
            )

        # Clean house_number column (strip leading zeros)
        def clean_house_number_udf(house_num: str) -> str:
            return self._clean_house_number(house_num or "")

        formatted_df = addresses_df.with_columns(
            pl.col("house_number")
            .map_elements(clean_house_number_udf, return_dtype=pl.Utf8)
            .alias("house_number")
        )

        # Apply formatting to create full_address column
        formatted_df = formatted_df.with_columns(
            pl.struct(
                ["street_name", "street_type", "house_number", "building", "staircase"]
            )
            .map_elements(
                lambda row: format_address_udf(
                    row["street_name"],
                    row["street_type"],
                    row["house_number"],
                    row["building"],
                    row["staircase"],
                ),
                return_dtype=pl.Utf8,
            )
            .alias("full_address")
        )

        # Note: We now allow addresses without house numbers (empty house_number field)
        # These are valid for:
        # 1. Complex buildings with building/staircase identifiers
        # 2. Infrastructure/area addresses (railway stations, landmarks, etc.)
        # All addresses should have full_address generated, so no filtering needed

        # Log statistics about addresses without house numbers for monitoring
        no_house_count = formatted_df.filter(
            (pl.col("house_number").is_null())
            | (pl.col("house_number") == "")
            | (pl.col("house_number") == "0")
        ).height

        if no_house_count > 0:
            with_building = formatted_df.filter(
                ((pl.col("house_number").is_null()) | (pl.col("house_number") == ""))
                & (
                    (pl.col("building").is_not_null() & (pl.col("building") != ""))
                    | (pl.col("staircase").is_not_null() & (pl.col("staircase") != ""))
                )
            ).height

            logger.info(
                f"Addresses without house numbers: {no_house_count:,} "
                f"({with_building:,} with building/staircase, "
                f"{no_house_count - with_building:,} infrastructure/area addresses)"
            )

        # Generate canonical ID hash from: county_code | settlement_name | full_address
        # This ensures addresses that format to the same string get the same canonical ID
        return formatted_df.with_columns(
            [
                (
                    pl.col("county_code")
                    .fill_null("")
                    .str.strip_chars()
                    .str.to_uppercase()
                    + "|"
                    + pl.col("settlement_name")
                    .fill_null("")
                    .str.strip_chars()
                    .str.replace_all(r"\s+", " ")
                    .str.to_uppercase()
                    + "|"
                    + pl.col("full_address")
                    .str.strip_chars()
                    .str.replace_all(r"\s+", " ")
                    .str.to_uppercase()
                )
                .hash(seed=self.seed)
                .alias("canonical_address_id")
            ]
        )

    def _generate_address_hash(self, street_name: str, house_number: str) -> int:
        """Generate deterministic hash for address."""
        normalized_street = self._normalize_text(street_name or "")
        normalized_house = self._normalize_text(house_number or "")

        hash_input = f"{normalized_street}|{normalized_house}"
        return xxhash.xxh64_intdigest(hash_input, seed=self.seed)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent hashing."""
        return text.strip().upper() if text else ""

    def _calculate_address_structure_score(
        self, house_number: str, building: str, staircase: str
    ) -> int:
        """
        Calculate structure quality score for address format prioritization.

        Higher scores indicate more structured/preferred formats:
        - Structured format (plain house number + separate building/staircase): higher score
        - Combined format (house number with slash notation): lower score

        Args:
            house_number: Raw house number field value
            building: Raw building field value
            staircase: Raw staircase field value

        Returns:
            Integer score where higher values indicate better structure

        Examples:
            >>> # Structured formats (higher scores)
            >>> _calculate_address_structure_score("1", "D", "") # house + building
            >>> 100
            >>> _calculate_address_structure_score("1", "1", "1") # house + building + staircase
            >>> 110

            >>> # Combined formats (lower scores)
            >>> _calculate_address_structure_score("1/D", "", "") # slash notation only
            >>> 50
            >>> _calculate_address_structure_score("1/D", "", "L") # slash + staircase
            >>> 60
        """
        house_num = (house_number or "").strip()
        has_slash = "/" in house_num
        has_building = bool((building or "").strip())
        has_staircase = bool((staircase or "").strip())

        # Base score for plain house number (no slash)
        if not has_slash:
            score = 100
            # Bonus for having separate building field
            if has_building:
                score += 10
            # Bonus for having separate staircase field
            if has_staircase:
                score += 10
            return score

        # Lower base score for combined format (with slash)
        score = 50
        # Small bonus for having additional separate fields
        if has_staircase:
            score += 10
        if has_building:
            score += 5

        return score

    def _create_canonical_addresses(self, addresses_df: pl.DataFrame) -> pl.DataFrame:
        """
        Create canonical address records with formatted full address.

        Prioritizes structured address formats (plain house number + separate building/staircase)
        over combined formats (slash notation) when selecting canonical representatives.
        """
        # Check if accessibility_flag column exists
        has_accessibility = "accessibility_flag" in addresses_df.columns

        # Calculate structure score for each address to enable priority-based selection
        def calculate_score_udf(
            house_number: str, building: str, staircase: str
        ) -> int:
            return self._calculate_address_structure_score(
                house_number or "", building or "", staircase or ""
            )

        # Add structure score and row number for deterministic tiebreaking
        addresses_with_score = addresses_df.with_columns(
            [
                pl.struct(["house_number", "building", "staircase"])
                .map_elements(
                    lambda row: calculate_score_udf(
                        row["house_number"], row["building"], row["staircase"]
                    ),
                    return_dtype=pl.Int64,
                )
                .alias("structure_score"),
                # Add row number within each canonical group for deterministic tiebreaking
                pl.col("canonical_address_id")
                .cum_count()
                .over("canonical_address_id")
                .alias("row_order"),
            ]
        )

        # Select best address from each canonical group based on:
        # 1. Highest structure score (prefer structured formats)
        # 2. First occurrence (deterministic tiebreaker when scores equal)
        aggregation_columns = [
            pl.first("county_code").alias("county_code"),
            pl.first("settlement_name").alias("settlement_name"),
            pl.first("street_name").alias("street_name"),
            pl.first("house_number").alias("house_number"),
            pl.first("building").alias("building"),
            pl.first("staircase").alias("staircase"),
            pl.first("full_address").alias("full_address"),
        ]

        # Include accessibility_flag if it exists
        if has_accessibility:
            # For accessibility flag, prioritize True (accessible) over False
            aggregation_columns.append(
                pl.max("accessibility_flag").alias("accessibility_flag")
            )

        # Sort by structure score (descending) and row order (ascending) before grouping
        # This ensures the first address in each group has the highest score
        return (
            addresses_with_score.sort(
                ["canonical_address_id", "structure_score", "row_order"],
                descending=[False, True, False],
            )
            .group_by("canonical_address_id")
            .agg(aggregation_columns)
        )

    def _preserve_relationships(
        self, addresses_df: pl.DataFrame, canonical_df: pl.DataFrame
    ) -> Dict[str, pl.DataFrame]:
        """Preserve all original relationships."""
        # Polling station assignments
        polling_stations = addresses_df.select(
            ["canonical_address_id", "polling_station_id"]
        ).unique()

        # PIR codes
        pir_codes = (
            addresses_df.select(["canonical_address_id", "pir_code"])
            .filter(pl.col("pir_code").is_not_null())
            .unique()
        )

        # Address mapping
        address_mapping = addresses_df.select(
            [pl.col("address_id").alias("original_address_id"), "canonical_address_id"]
        )

        # Log relationship preservation statistics
        logger.debug(
            f"Preserved relationships: "
            f"{len(polling_stations)} polling station assignments, "
            f"{len(pir_codes)} PIR codes, "
            f"{len(address_mapping)} address mappings"
        )

        return {
            "address_polling_stations": polling_stations,
            "address_pir_codes": pir_codes,
            "address_mapping": address_mapping,
        }


def deduplicate_large_dataset(
    addresses_df: pl.DataFrame, chunk_size: int = 100000
) -> Dict[str, pl.DataFrame]:
    """
    Deduplicate large datasets in chunks.

    Args:
        addresses_df: Large DataFrame with addresses
        chunk_size: Number of rows to process per chunk

    Returns:
        Dictionary with deduplicated results
    """
    deduplicator = AddressDeduplicator()

    results = {
        "canonical_addresses": [],
        "address_polling_stations": [],
        "address_pir_codes": [],
        "address_mapping": [],
    }

    for i in range(0, len(addresses_df), chunk_size):
        chunk = addresses_df[i : i + chunk_size]
        chunk_result = deduplicator.deduplicate_addresses(chunk)

        for key in results:
            results[key].append(chunk_result[key])

    # Combine results
    return {key: pl.concat(results[key]) for key in results}
