<!--
DOCUMENT METADATA
=================
Title: OEVK Export and Deduplication Fixes
Type: Specification
Category: Feature
Status: Implemented
Version: 1.0
Created: 2024-10-01
Last Updated: 2024-10-15
Author: System
Change ID: 006

Related Documents:
- README.md

Related Code:
- src/etl/

Dependencies:
- DuckDB
- Polars

Keywords: change-specification, feature, implementation

Summary:
Change specification document for feature implementation.

Audience:
Developers, technical leads.
-->

# OEVK Export and Deduplication Fixes

This document outlines a series of required fixes and improvements for the OEVK data export and deduplication processes.

## 1. Deduplication Logic Enhancement

- **Objective:** Refine the address deduplication logic to prefer structured address formats.
- **Current Issue:** The deduplication process primarily supports house numbers with modifiers (e.g., "1/A", "1/1"), where the building identifier is encoded within the house number string.
- **Required Change:** Modify the logic to prioritize address records that have a plain house number and a separate building number over records where the building number is combined with the house number.

## 2. Data Integrity and Formatting Fixes

### 2.1. Foreign Key Reference Correction

- **Table:** `settlementindividualelectoraldistrict`
- **Issue:** The `settlement_id` and `nationalindividualelectoraldistrict_id` columns are referencing incorrect IDs.
- **Action:** Investigate and correct the data population logic for these columns to ensure they reference the correct entities.

### 2.2. Data Content Correction

- **Table:** `nationalindividualelectoraldistrict`
- **Issue:** The `name` column incorrectly contains settlement names instead of county names. The `county_id` and `oevk` pairs are correct.
- **Action:** Correct the data source or transformation logic to populate the `name` column with the appropriate county names.

### 2.3. Address Component Formatting

- **Issue:** House numbers, building numbers, and staircase numbers may contain leading zeros that need to be trimmed.
- **Action:** Apply trimming logic to the following fields, consistent with the rules used for `fullAddress` generation:
    - `housenumber`
    - `building_number`
    - `staircase_number`

## 3. Feature Enhancements

### 3.1. Coordinate Data Export

- **Issue:** The `center` and `polygon` coordinate columns are not being exported or subsequently loaded back into the database.
- **Action:** Implement the necessary logic to correctly export these geometric data types and ensure they are correctly loaded during the import process.

### 3.2. Script Parameterization

- **Script:** `load_postgresql.py`
- **Issue:** The script fails with an "unrecognized arguments" error when passed a `--database` parameter.
- **Action:** Add support for a `--database` command-line argument to allow specifying the target database.

## 4. Testing Strategy

- **Objective:** Enable faster and more efficient testing of the export/import pipeline.
- **Action:**
    1.  Create a staging process to generate a smaller, representative subset of the main database.
    2.  This "shrinked down" database should contain data for:
        - 3 selected districts from Budapest.
        - 10 other settlements from 3 different counties.
        - All associated addresses for the selected settlements.
    3.  (Optional) Consider adding a parameter to the loading script to limit the number of settlements processed, which can be useful for quick, targeted tests.
