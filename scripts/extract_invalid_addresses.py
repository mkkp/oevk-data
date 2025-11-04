#!/usr/bin/env python3
"""Extract addresses with all-zero house numbers that were filtered out."""

import polars as pl
from pathlib import Path


def is_all_zeros(house_num: str) -> bool:
    """Check if house number is all zeros (invalid)."""
    if not house_num:
        return False

    house_num = house_num.strip()
    if not house_num:
        return False

    # Handle ranges (e.g., "0000-0005")
    if "-" in house_num:
        parts = house_num.split("-")
        for part in parts:
            cleaned = part.strip().lstrip("0")
            if not cleaned:  # Part is all zeros
                return True
        return False

    # Handle slash notation (e.g., "0000/D")
    if "/" in house_num:
        parts = house_num.split("/", 1)
        cleaned_base = parts[0].strip().lstrip("0")
        if not cleaned_base:  # Base is all zeros
            return True
        return False

    # Simple number
    cleaned = house_num.lstrip("0")
    return not cleaned  # All zeros if nothing left after stripping


def extract_invalid_addresses():
    """Extract and save addresses with all-zero house numbers."""

    # Read the Korzet CSV file
    korzet_file = Path(
        "data/staging/korzet_extracted/Korzet_levalogatas20250702__ORSZAGOS.csv"
    )

    if not korzet_file.exists():
        print(f"Error: Source file not found: {korzet_file}")
        return

    print(f"Reading source file: {korzet_file}")

    # Read CSV with proper delimiter (semicolon)
    df = pl.read_csv(
        korzet_file, separator=";", encoding="utf-8", quote_char='"', null_values=[""]
    )

    print(f"Total addresses loaded: {len(df):,}")
    print(f"Columns: {df.columns}")

    # The house number column is "Házszám"
    house_number_col = "Házszám"

    if house_number_col not in df.columns:
        print(f"Error: Column '{house_number_col}' not found")
        print(f"Available columns: {df.columns}")
        return

    # Filter for all-zero house numbers
    print("\nFiltering addresses with all-zero house numbers...")

    invalid_mask = df[house_number_col].map_elements(
        is_all_zeros, return_dtype=pl.Boolean
    )

    invalid_df = df.filter(invalid_mask)

    print(f"Found {len(invalid_df):,} addresses with all-zero house numbers")

    if len(invalid_df) == 0:
        print("No invalid addresses found!")
        return

    # Create output directory
    output_dir = Path("exports/invalid_addresses")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    output_file = output_dir / "invalid_addresses_all_zero_house_numbers.csv"

    print(f"\nSaving to: {output_file}")

    invalid_df.write_csv(output_file, separator=",")

    print(f"✓ Saved {len(invalid_df):,} invalid addresses to CSV")

    # Print statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)

    # Count by house number pattern
    house_number_counts = (
        invalid_df.group_by(house_number_col)
        .agg(pl.count().alias("count"))
        .sort("count", descending=True)
    )

    print(f"\nHouse number patterns (top 20):")
    print(house_number_counts.head(20))

    # Count by settlement
    settlement_counts = (
        invalid_df.group_by("Település")
        .agg(pl.count().alias("count"))
        .sort("count", descending=True)
    )

    print(f"\nTop 10 settlements with invalid addresses:")
    print(settlement_counts.head(10))

    # Show sample records
    print(f"\nSample invalid addresses:")
    sample_cols = [
        "Település",
        "Közterület név",
        "Közterület jelleg",
        house_number_col,
        "Épület",
        "Lépcsőház",
        "Szavazókör cím",
    ]
    if all(col in invalid_df.columns for col in sample_cols):
        print(invalid_df.select(sample_cols).head(10))

    print("\n" + "=" * 80)
    print(f"Output file: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    extract_invalid_addresses()
