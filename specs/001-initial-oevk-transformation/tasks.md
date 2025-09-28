# Tasks for Initial OEVK Transformation App

This document outlines the tasks required to implement the OEVK data transformation application, based on the design documents in `/specs/001-initial-oevk-transformation`.

## Phase 1: Setup and Project Initialization

-   [X] **T001**: **Initialize Project Structure**: Create the directories `src`, `tests`, `data`, and `logs` as defined in the `plan.md`.
-   [X] **T002**: **Install Dependencies**: Create a `requirements.txt` file and add `polars`, `duckdb`, `xxhash`, and `requests`.
-   [X] **T003**: **Setup Linting and Formatting**: Initialize `ruff` for linting and formatting to ensure code quality.
-   [X] **T004**: **Configure Logging**: Implement a basic structured logging setup in `src/utils/logging.py`.

## Phase 2: Contract and Unit Tests (TDD)

-   [X] **T005**: **[P]** **Write Contract Test for Ingestion**: Create `tests/contract/test_ingest.py` with failing tests for the functions `download_sources` and `load_staging_data` as defined in `ingest-contract.json`.
-   [X] **T006**: **[P]** **Write Contract Test for Transformation**: Create `tests/contract/test_transform.py` with a failing test for the `transform_all` function.
-   [X] **T007**: **[P]** **Write Contract Test for Export**: Create `tests/contract/test_export.py` with failing tests for `export_tables_to_csv` and `export_addresses_partitioned`.
-   [X] **T008**: **[P]** **Write Unit Tests for Hashing**: Create `tests/unit/test_hashing.py` to test the deterministic ID generation logic.

## Phase 3: Core Implementation

-   [X] **T009**: **Implement Hashing Logic**: Create `src/etl/hashing.py` with functions to generate `xxhash64` IDs based on the rules in `data-model.md`.
-   [X] **T010**: **Implement Ingestion Logic**: Implement the functions in `src/etl/ingest.py` to download sources and load staging data. This should make the tests in `T005` pass.
-   [X] **T011**: **Define Database Schema**: Create `src/database/schema.sql` with the DDL for all staging and target tables as specified in `docs/FUNCTIONAL_SPECIFICATION.md`.
-   [X] **T012**: **Implement Database Connection**: Create `src/database/connection.py` to manage the DuckDB connection.
-   [X] **T012a**: **Implement Data Validation Logic**: Create `src/utils/validation.py` to implement data quality and referential integrity checks as described in the functional specification. This utility will be used by the transformation and integration testing steps.
-   [X] **T013**: **Implement Transformation Logic**: Implement the `transform_all` function in `src/etl/transform.py`. This will involve creating sub-functions for each of the 8 entities, following the detailed transformation logic in section 9 of `docs/FUNCTIONAL_SPECIFICATION.md`. This should make the test in `T006` pass.
-   [X] **T014**: **Implement Export Logic**: Implement the export functions in `src/etl/export.py`, including the logic for partitioned address exports. This should make the tests in `T007` pass.
-   [X] **T015**: **Create CLI**: Implement the command-line interface in `src/cli.py` to orchestrate the ingest, transform, and export steps, including the optional flag for the consolidated address file.

## Phase 4: Integration and Validation

-   [X] **T016**: **Write Integration Tests**: Create `tests/integration/test_pipeline_simple.py` to test the entire ETL pipeline end-to-end with sample data. The test should:
    1.  Call the ingest process.
    2.  Call the transform process.
    3.  Call the export process.
    4.  Validate the output CSV files for correctness, including partitioned files.
    5.  Verify referential integrity between the exported CSVs.
    6.  Check for a `rejects` table and ensure it handles invalid data correctly.
-   [X] **T017**: **Implement Integration Tests**: Write the code for the integration tests described in `T016`.

## Phase 5: Polish and Finalization

-   **T018**: **Add Configuration**: Implement `src/utils/config.py` to manage settings like URLs, file paths, and chunk sizes.
-   **T019**: **Refine Logging**: Enhance the logging in `src/utils/logging.py` and across the application to provide clear, structured output for each stage of the pipeline. Logs MUST include start/end times, source file details, row counts for each transformation step, and paths to exported files, in alignment with the constitution.
-   **T020**: **Add README**: Create a `README.md` at the project root with detailed instructions on how to set up, configure, and run the application.
-   **T021**: **[P]** **Validate Performance**: After implementation, run the full pipeline on the sample 3M row dataset and measure the execution time to ensure it meets the NFR-002 target of < 30 minutes.

## Parallel Execution Example

The following tasks from Phase 2 can be run in parallel as they operate on different test files:

```bash
# Run these commands in separate terminals
Task: "Execute T005: Write Contract Test for Ingestion"
Task: "Execute T006: Write Contract Test for Transformation"
Task: "Execute T007: Write Contract Test for Export"
Task: "Execute T008: Write Unit Tests for Hashing"
```
