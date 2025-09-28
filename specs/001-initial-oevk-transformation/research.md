# Research: Initial OEVK Transformation App

This document records the technical decisions for the OEVK data processing application, based on the requirements in `docs/FUNCTIONAL_SPECIFICATION.md` and the project constitution.

## Technology Stack Decisions

### 1. Data Processing Engine
*   **Decision**: **Polars**
*   **Rationale**: The functional specification recommends Polars or DuckDB for handling over 3 million rows. Polars is chosen for its high performance in CSV reading and in-memory transformations, its expressive and intuitive API for data manipulation, and its excellent memory management, which are critical for this project's scale.
*   **Alternatives considered**:
    *   **DuckDB**: A strong alternative, especially for SQL-centric transformations. However, Polars' DataFrame API is better suited for the complex, step-by-step data shaping and feature engineering required here.
    *   **Pandas**: Rejected due to known performance and memory limitations with datasets of this size.

### 2. Database for Staging & Target
*   **Decision**: **DuckDB**
*   **Rationale**: DuckDB is a fast, file-based analytical database. It is perfect for both staging raw data and storing the final transformed tables. Its ability to efficiently query Polars DataFrames and CSV files directly makes it an ideal component in the ETL pipeline, allowing for powerful SQL-based validation and joins.
*   **Alternatives considered**:
    *   **SQLite**: While viable and simple, DuckDB offers superior analytical performance and a richer SQL dialect for the types of queries needed in the transformation logic.

### 3. Hashing Algorithm for IDs
*   **Decision**: **xxhash (via `xxhash` library)**
*   **Rationale**: The constitution and functional specification mandate deterministic, non-cryptographic hash IDs. `xxhash` is extremely fast and is the recommended implementation (`xxhash64`) for ensuring idempotent data processing.
*   **Alternatives considered**:
    *   **SHA1/SHA256**: Rejected as they are cryptographic hashes and unnecessarily slow for this purpose.

### 4. HTTP Client
*   **Decision**: **requests**
*   **Rationale**: A simple, reliable, and industry-standard library for making HTTP requests to download the source files. It is easy to use and robust.
*   **Alternatives considered**:
    *   `urllib3`: Lower-level, more verbose. `requests` provides a simpler, more user-friendly API.
    *   `aiohttp`: Asynchronous, which is not necessary for this batch-oriented download process.
