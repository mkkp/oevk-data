# Tasks for Initial OEVK Transformation App

This document outlines the tasks required to implement the OEVK data transformation application, based on the design documents in `/specs/01-initial-oevk-transformation`.

## Phase 1: Setup and Project Initialization

-   **T001**: **Initialize Project Structure**: Create the directories `src`, `tests`, `data`, and `logs` as defined in the `plan.md`.
-   **T002**: **Install Dependencies**: Create a `requirements.txt` file and add `polars`, `duckdb`, `xxhash`, and `requests`.
-   **T003**: **Setup Linting and Formatting**: Initialize `ruff` for linting and formatting to ensure code quality.
-   **T004**: **Configure Logging**: Implement a basic structured logging setup in `src/utils/logging.py`.

## Phase 2: Contract and Unit Tests (TDD)

-   **T005**: **[P]** **Write Contract Test for Ingestion**: Create `tests/contract/test_ingest.py` with failing tests for the functions `download_sources` and `load_staging_data` as defined in `ingest-contract.json`.
-   **T006**: **[P]** **Write Contract Test for Transformation**: Create `tests/contract/test_transform.py` with a failing test for the `transform_all` function.
-   **T007**: **[P]** **Write Contract Test for Export**: Create `tests/contract/test_export.py` with failing tests for `export_tables_to_csv` and `export_addresses_partitioned`.
-   **T008**: **[P]** **Write Unit Tests for Hashing**: Create `tests/unit/test_hashing.py` to test the deterministic ID generation logic.

## Phase 3: Core Implementation

-   **T009**: **Implement Hashing Logic**: Create `src/etl/hashing.py` with functions to generate `xxhash64` IDs based on the rules in `data-model.md`.
-   **T010**: **Implement Ingestion Logic**: Implement the functions in `src/etl/ingest.py` to download sources and load staging data. This should make the tests in `T005` pass.
-   **T011**: **Define Database Schema**: Create `src/database/schema.sql` with the DDL for all staging and target tables as specified in `docs/FUNCTIONAL_SPECIFICATION.md`.
-   **T012**: **Implement Database Connection**: Create `src/database/connection.py` to manage the DuckDB connection.
-   **T013**: **Implement Transformation Logic**: Implement the `transform_all` function in `src/etl/transform.py`. This will involve creating sub-functions for each of the 8 entities. This should make the test in `T006` pass.
-   **T014**: **Implement Export Logic**: Implement the export functions in `src/etl/export.py`. This should make the tests in `T007` pass.
-   **T015**: **Create CLI**: Implement the command-line interface in `src/cli.py` to orchestrate the ingest, transform, and export steps.

## Phase 4: Integration and Validation

-   **T016**: **Write Integration Tests**: Create `tests/integration/test_pipeline.py` to test the entire ETL pipeline end-to-end with sample data. The test should:
    1.  Call the ingest process.
    2.  Call the transform process.
    3.  Call the export process.
    4.  Validate the output CSV files for correctness and referential integrity.
-   **T017**: **Implement Integration Tests**: Write the code for the integration tests described in `T016`.

## Phase 5: Polish and Finalization

-   **T018**: **Add Configuration**: Implement `src/utils/config.py` to manage settings like URLs and file paths.
-   **T019**: **Refine Logging**: Enhance the logging throughout the application to provide clear, structured output for each stage of the pipeline.
-   **T020**: **Add README**: Create a `README.md` at the project root with instructions on how to set up and run the application.

## Parallel Execution Example

The following tasks from Phase 2 can be run in parallel as they operate on different test files:

```bash
# Run these commands in separate terminals
Task: "Execute T005: Write Contract Test for Ingestion"
Task: "Execute T006: Write Contract Test for Transformation"
Task: "Execute T007: Write Contract Test for Export"
Task: "Execute T008: Write Unit Tests for Hashing"
```
