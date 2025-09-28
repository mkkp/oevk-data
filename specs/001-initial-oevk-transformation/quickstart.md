# Quickstart: OEVK Transformation App

This guide provides the steps to set up and run the OEVK data transformation pipeline.

## Prerequisites
- Python 3.11+
- Pip for installing dependencies

## 1. Setup

### Clone the Repository
```bash
git clone <repository-url>
cd oevk-data
```

### Install Dependencies
```bash
pip install polars duckdb xxhash requests
```

### Create Directories
The application expects the following directory structure.
```bash
mkdir -p data/staging data/export data/database logs
```

## 2. Running the Pipeline

The entire pipeline can be run via the main CLI script.

### Step 1: Download and Load Staging Data
This command fetches the source data from the web, unzips the address file, and loads both sources into staging tables in the DuckDB database.
```bash
python src/cli.py ingest --run-tag $(date +%Y%m%d)
```

### Step 2: Transform Data
This command reads from the staging tables and populates the 8 normalized target tables using the logic from the functional specification. The transformation supports parallel processing for optimal performance.
```bash
# Standard transformation
python src/cli.py transform --run-tag $(date +%Y%m%d)

# With parallel processing (recommended for large datasets)
python src/cli.py transform --run-tag $(date +%Y%m%d) --parallel

# With custom chunk size and worker threads
python src/cli.py transform --run-tag $(date +%Y%m%d) --parallel --chunk-size 50000 --max-workers 4
```

### Step 3: Export Data
This command exports the final data into CSV files.
```bash
python src/cli.py export --run-tag $(date +%Y%m%d)
```

## 3. Verifying the Output

After the pipeline completes, you can check the `data/export` directory.

### Expected Output Structure
```
data/export/
└── {RUN_TAG}/
    ├── County.csv
    ├── Settlement.csv
    ├── NationalIndividualElectoralDistrict.csv
    ├── SettlementIndividualElectoralDistrict.csv
    ├── PostalCode.csv
    ├── PostalCode_Settlement.csv
    ├── PollingStation.csv
    ├── Address/
    │   ├── Address_{SettlementCode}_{slug}.csv
    │   └── ... (one file per settlement)
    └── (optional) Address.csv
```

### Validation
You can run the integration tests to verify the data integrity and correctness of the pipeline.
```bash
python -m pytest tests/integration/
```
All tests should pass, confirming that foreign key relationships are intact and data quality rules have been enforced.
