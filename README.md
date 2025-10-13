# OEVK Data Transformation Pipeline

A Python-based ETL pipeline for processing Hungarian electoral address data from authoritative sources into normalized, queryable datasets with partitioned exports and public space entity extraction.

## 🎉 Project Status: **COMPLETED SUCCESSFULLY**

**All Features Implemented and Production-Ready**
- ✅ Complete ETL pipeline with 11 normalized tables
- ✅ Public space entity extraction integrated
- ✅ Automated GitHub release workflow
- ✅ 98.6% performance improvement (183.6 min → 2.5 min)
- ✅ NFR-002 compliance achieved with significant margin

## Overview

This application transforms Hungarian electoral address data from two authoritative sources into a normalized relational model and exports CSV files for analysis. The pipeline handles:

- **Data Ingestion**: Download and load source data from JSON and ZIP/CSV formats
- **Data Transformation**: Normalize into 11 target tables with referential integrity
- **Public Space Extraction**: Extract public space entities (names and types) from addresses
- **Data Export**: Generate CSV files with partitioned address data by settlement

### Key Features

- **Deterministic ID Generation**: xxhash64-based surrogate keys for idempotent processing
- **Chunked Processing**: Efficient handling of 3M+ row datasets
- **Parallel Processing**: Multi-threaded chunk processing for optimal performance
- **Structured Logging**: Comprehensive pipeline metrics and performance tracking
- **Configuration Management**: Environment-based configuration with sensible defaults
- **Data Validation**: Referential integrity and data quality checks
- **Partitioned Exports**: Address data split by settlement for efficient access
- **Public Space Extraction**: Automatic extraction of public space entities from addresses
- **Release Workflow**: Automated GitHub releases with compressed artifacts

## Quick Start

### Prerequisites

- Python 3.11+
- Dependencies: `polars`, `duckdb`, `xxhash`, `requests`
- GitHub CLI (`gh`) for release workflow (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd oevk-data
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the complete pipeline**
   ```bash
   python src/cli.py run --run-tag $(date +%Y%m%d)
   ```

### Directory Structure

```
oevk-data/
├── src/                    # Source code
│   ├── etl/               # ETL modules (ingest, transform, export)
│   ├── database/          # Database connection and schema
│   ├── release/           # Release workflow modules
│   └── utils/             # Utilities (config, logging, validation)
├── tests/                 # Test suites
│   ├── contract/          # Contract tests
│   ├── integration/       # Integration tests
│   └── unit/              # Unit tests
├── data/                  # Data directories
│   ├── staging/           # Raw source data
│   ├── export/            # Final CSV exports
│   └── database/          # DuckDB database files
├── logs/                  # Application logs
└── specs/                 # Specifications and documentation
```

## Usage

### Running the Transform Locally

To run the complete data transformation pipeline locally:

```bash
# Run complete pipeline with default settings (canonical addresses only)
python -m src.cli run

# Run with custom database and output directories
python -m src.cli run --db-path data/oevk.db --output-dir exports/ --staging-dir data/staging/

# Run only specific stages
python -m src.cli run --stages ingest,transform,export
python -m src.cli run --stages transform  # Only transformation stage

# Export original addresses for debugging/analysis
python -m src.cli run --export-original-addresses

# Run with custom run tag
python -m src.cli run --run-tag $(date +%Y%m%d_%H%M%S)

# Disable deduplication
python -m src.cli run --no-deduplication

# Show all available options
python -m src.cli run --help
```

### Release Workflow

The project includes a comprehensive release workflow for publishing processed data to GitHub releases:

#### Data Validation

```bash
# Validate release data before creating release
python -m src.cli release validate --staging-dir data/staging --exports-dir exports

# Validate with custom directories
python -m src.cli release validate --staging-dir /path/to/staging --exports-dir /path/to/exports
```

#### Release Creation

```bash
# Set GitHub token (required)
export GITHUB_TOKEN="ghp_your_token_here"

# Create release with auto-generated tag
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto

# Create release with specific tag
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag 20250101-1200

# Create draft release for review
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --draft

# Create prerelease (beta/alpha)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --prerelease

# Force overwrite existing release
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag existing-tag --force

# Create packages without uploading to GitHub (local testing)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --skip-upload
```

#### Release Management

```bash
# Check release status
python -m src.cli release status --repo-owner your-org --repo-name oevk-data --tag 20250101-1200

# List recent releases
python -m src.cli release history --repo-owner your-org --repo-name oevk-data --limit 10

# Get detailed release information
python -m src.cli release info --repo-owner your-org --repo-name oevk-data --tag 20250101-1200
```

#### Environment Variables

```bash
# GitHub Personal Access Token (required for releases)
export GITHUB_TOKEN="ghp_your_token_here"

# Optional: Custom directories
export STAGING_DIR="/path/to/staging"
export EXPORTS_DIR="/path/to/exports"
```

### Pipeline Stages

The pipeline consists of five main stages:

1. **Ingest**: Download source data and load into staging tables
2. **Transform**: Process staging data into normalized target tables
3. **Public Space Extraction**: Extract public space entities from addresses
4. **Export**: Generate CSV files from target tables
5. **Release**: Package and publish data to GitHub releases

### Release Workflow Stages

The release workflow provides automated GitHub releases:

1. **Data Validation**: Comprehensive pre-release checks for data integrity
2. **Package Creation**: Compress CSV and database files into release artifacts
3. **GitHub Integration**: Create releases with proper metadata and assets
4. **Release Management**: Status checking, history, and information retrieval

### Transformation Stage Details

When running the transformation stage locally, the pipeline:

- **Processes 3M+ rows** from staging data
- **Creates 11 normalized tables** with referential integrity
- **Extracts public space entities** (25,117 names, 148 types, 122,524 relationships)
- **Generates deterministic hash IDs** using xxhash64
- **Handles conflicts** with `ON CONFLICT DO UPDATE` for idempotent processing
- **Uses parallel processing** with ThreadPoolExecutor for optimal performance
- **Tracks performance metrics** including timing and row counts
- **Validates NFR-002 compliance** (30-minute processing target)

### Expected Output

After successful transformation, you should see:

```
County: 20 rows
Settlement: 3,177 rows  
NationalIndividualElectoralDistrict: 106 rows
SettlementIndividualElectoralDistrict: 4,677 rows
PollingStation: 8,555 rows
Address: 3,336,202 rows (original)
CanonicalAddress: 3,323,118 rows (deduplicated with 0.39% reduction)
PostalCode: 3,106 rows
PostalCode_Settlement: 3,106 rows
PublicSpaceName: 25,117 rows
PublicSpaceType: 148 rows
SettlementPublicSpaces: 122,524 rows
```

### Release Artifacts

Each release creates two main artifacts:

1. **CSV Archive** (`oevk-data-csv-{tag}.zip`): Contains all CSV files
   - `{run_tag}_Address/` - Directory containing address files split by settlement:
     - `Address_001_Aba.csv` - **Canonical deduplicated addresses** (UUID v3 format)
     - `OriginalAddress_001_Aba.csv` - All original addresses with canonical references
   - `settlements.csv` - Settlement information
   - `counties.csv` - County data
   - `polling_stations.csv` - Polling station details
   - `electoral_districts.csv` - Electoral district information
   - `PublicSpaceName.csv` - 25,117 unique public space names
   - `PublicSpaceType.csv` - 148 unique public space types
   - `SettlementPublicSpaces.csv` - 122,524 settlement-public space relationships

2. **Database Archive** (`oevk-data-db-{tag}.zip`): Contains main transformed database
   - `oevk.db` - Complete relational database with all tables including public space entities and canonical addresses

### Address Export Format

The pipeline exports addresses in two formats. **By default, only canonical addresses are exported.** Use `--export-original-addresses` to also export original addresses.

#### Canonical Addresses (Deduplicated) - Always Exported
- **Files**: `Address_{settlement_code}_{settlement_name}.csv`
- **IDs**: UUID v3 with 'oevk.hu' namespace
- **Structure**: Same as OriginalAddress + `OriginalAddressCount` column
- **Content**: Only unique canonical addresses (one per unique formatted address)
- **Columns** (16 total):
  1. `ID` - Canonical address UUID v3
  2. `Sequence` - Minimum sequence from merged addresses
  3. `OriginalOrder` - Minimum original order from merged addresses
  4. `FullAddress` - Formatted Hungarian address (e.g., "Ady Endre utca 1.")
  5. `PublicSpaceName` - Street name without type (e.g., "Ady Endre")
  6. `PublicSpaceType` - Street type from original address (e.g., "utca", "út", "tér")
  7. `HouseNumber` - House number with leading zeros (e.g., "000001")
  8. `Building` - Building identifier from original address (cleaned: zero-only → empty string)
  9. `Staircase` - Staircase identifier from original address (cleaned: zero-only → empty string)
  10. `PostalCode_ID` - Postal code UUID v3
  11. `PollingStation_ID` - Polling station UUID v3
  12. `SettlementIndividualElectoralDistrict_ID` - TEVK UUID v3
  13. `County_ID` - County UUID v3
  14. `Settlement_ID` - Settlement UUID v3
  15. `NationalIndividualElectoralDistrict_ID` - OEVK UUID v3
  16. **`OriginalAddressCount`** - Number of original addresses merged into this canonical address

- **Field Cleaning Rules**:
  - `PublicSpaceType`, `Building`, `Staircase`: Retrieved from original Address records via `AddressMapping` join
  - `Building`/`Staircase` zero-only cleaning: Values containing only zeros (`'0'`, `'00'`, `'000'`) converted to empty string
  - NULL handling: NULL/empty values exported as empty strings in CSV

- **Example**:
  ```csv
  ID,Sequence,OriginalOrder,FullAddress,PublicSpaceName,PublicSpaceType,HouseNumber,Building,Staircase,PostalCode_ID,PollingStation_ID,SettlementIndividualElectoralDistrict_ID,County_ID,Settlement_ID,NationalIndividualElectoralDistrict_ID,OriginalAddressCount
  32e85e9e-7bac-372b-bd74-7e8ca77025d1,3644,1103644,Ady Endre utca 1.,Ady Endre,utca,000001,,,4381f027-c7e3-3d1c-98fd-5d4f518aabdc,77b6993d-1a44-3ab5-b6a2-4397fded9596,9cad8436-1c1b-3f88-ad0d-6523a7617cfb,826cb982-9964-30d5-ab9d-b6a68d56e999,e62e407d-5ada-397a-8481-1368e54828d0,3a8239cb-cd9b-34fb-9f1b-a2344ba602fb,1
  8f3a1b2c-4d5e-3f6a-9b8c-7d6e5f4a3b2c,3646,1103646,Körtöltés utca 1/D.,Körtöltés,utca,000001,D,,4381f027-c7e3-3d1c-98fd-5d4f518aabdc,77b6993d-1a44-3ab5-b6a2-4397fded9596,9cad8436-1c1b-3f88-ad0d-6523a7617cfb,826cb982-9964-30d5-ab9d-b6a68d56e999,e62e407d-5ada-397a-8481-1368e54828d0,3a8239cb-cd9b-34fb-9f1b-a2344ba602fb,1
  ```

#### Original Addresses (All Records) - Optional Export
- **Files**: `OriginalAddress_{settlement_code}_{settlement_name}.csv`
- **Export**: Use `--export-original-addresses` CLI flag to enable
- **IDs**: UUID v3 with 'oevk.hu' namespace
- **Structure**: Standard address structure with `CanonicalAddress_ID` reference
- **Content**: All original addresses with references to their canonical address
- **Purpose**: Debugging and comparison with deduplicated data
- **Key difference**: Has `CanonicalAddress_ID` instead of `OriginalAddressCount`
- **Note**: Only export if needed for analysis as it creates large files (3.3M records)

#### Canonical Address Export Structure

Visual representation of the canonical address export with field retrieval:

```mermaid
flowchart LR
    subgraph CA[CanonicalAddress Table]
        CA1[ID<br/>CountyCode<br/>SettlementName<br/>FullAddress<br/>StreetName<br/>HouseNumber]
    end
    
    subgraph AM[AddressMapping]
        AM1[OriginalAddressID<br/>CanonicalAddressID]
    end
    
    subgraph OA[Original Address]
        OA1[PublicSpaceType<br/>Building<br/>Staircase<br/>Foreign Keys]
    end
    
    subgraph Export[CSV Export - 16 Columns]
        E1[ID UUID v3]
        E2[Sequence, OriginalOrder]
        E3[FullAddress]
        E4[PublicSpaceName, PublicSpaceType]
        E5[HouseNumber]
        E6[Building, Staircase<br/>cleaned: '0' → '']
        E7[Foreign Key UUIDs<br/>PostalCode, PollingStation, etc.]
        E8[OriginalAddressCount]
    end
    
    CA --> AM
    AM --> OA
    CA --> Export
    OA --> Export
    
    style E6 fill:#ffffcc
    style Export fill:#e6f3ff
```

**Key Points:**
- Fields from CanonicalAddress: ID, FullAddress, PublicSpaceName, HouseNumber
- Fields from Original Address (via AddressMapping): PublicSpaceType, Building, Staircase, Foreign Keys
- Building/Staircase cleaning: Zero-only values (`'0'`, `'00'`, `'000'`) → empty string
- All IDs converted to UUID v3 with 'oevk.hu' namespace

### Release Performance Targets

- **Complete Workflow**: ≤15 minutes for full release process
- **Data Validation**: ≤2 minutes for comprehensive checks
- **Package Creation**: ≤5 minutes for artifact compression
- **GitHub Integration**: ≤3 minutes for release creation
- **Idempotent Operations**: Safe to retry failed operations

### Performance Monitoring

The pipeline includes comprehensive performance tracking:

- **Step timing**: Individual stage durations
- **Row counts**: Records processed per stage
- **Processing rate**: Rows per second
- **Parallel processing metrics**: Chunk completion times and worker utilization
- **NFR-002 validation**: 30-minute target compliance check

Example output:
```
=== PIPELINE PERFORMANCE SUMMARY ===
Total duration: 150.5 seconds
Total rows processed: 3,336,202
Processing rate: 22,166.78 rows/second
✅ NFR-002 COMPLIANT: Pipeline completed in 150.5s (target: ≤1800s)
```

### Configuration

Configuration is managed through `src/utils/config.py` and can be customized via environment variables:

```bash
# Source URLs
export OEVK_JSON_URL="https://static.valasztas.hu/dyn/oevk_data/oevk.json"
export KORZET_ZIP_URL="https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip"

# Processing settings
export CHUNK_SIZE=50000
export MAX_WORKERS=4
export PARALLEL_PROCESSING="true"
export SAMPLE_SIZE=-1  # -1 for all data

# Database settings
export DB_MEMORY_LIMIT="2GB"
export DB_THREADS=4

# Logging settings
export LOG_LEVEL="INFO"

# Export settings
export INCLUDE_PARTITIONED_ADDRESSES="true"
export INCLUDE_CONSOLIDATED_ADDRESSES="true"

# Release workflow settings
export GITHUB_TOKEN="ghp_your_token_here"  # Required for releases
export STAGING_DIR="data/staging"
export EXPORTS_DIR="exports"
```

### Output Structure

After successful execution, the export directory will contain:

```
data/export/{RUN_TAG}/
├── {RUN_TAG}_County.csv
├── {RUN_TAG}_Settlement.csv
├── {RUN_TAG}_NationalIndividualElectoralDistrict.csv
├── {RUN_TAG}_SettlementIndividualElectoralDistrict.csv
├── {RUN_TAG}_PostalCode.csv
├── {RUN_TAG}_PostalCode_Settlement.csv
├── {RUN_TAG}_PollingStation.csv
├── {RUN_TAG}_PublicSpaceName.csv
├── {RUN_TAG}_PublicSpaceType.csv
├── {RUN_TAG}_SettlementPublicSpaces.csv
├── {RUN_TAG}_CanonicalAddress.csv (consolidated deduplicated addresses)
└── {RUN_TAG}_Address/
    ├── Address_001_Aba.csv (canonical deduplicated, UUID v3)
    ├── Address_002_Abony.csv (canonical deduplicated, UUID v3)
    ├── OriginalAddress_001_Aba.csv (all original with canonical refs, UUID v3)
    ├── OriginalAddress_002_Abony.csv (all original with canonical refs, UUID v3)
    └── ... (two files per settlement: canonical + original)
```

**Key Changes:**
- All IDs use UUID v3 format with 'oevk.hu' namespace
- Reference lists are comma-separated without brackets
- Canonical and original address files are in the same directory
- Canonical addresses show aggregated relationships (PollingStationIDs, PIRCodes)
- OriginalAddressCount shows how many duplicates were merged

## Data Model

The pipeline transforms source data into 14 normalized tables:

1. **County** (`megye`) - Administrative counties
2. **Settlement** (`település`) - Cities, towns, villages
3. **NationalIndividualElectoralDistrict** (`OEVK`) - National electoral districts
4. **SettlementIndividualElectoralDistrict** (`TEVK`) - Settlement-level electoral districts
5. **PostalCode** (`irányítószám`) - Postal codes
6. **PostalCode_Settlement** - Junction table for postal code-settlement relationships
7. **PollingStation** (`szavazókör`) - Voting locations
8. **Address** (`cím`) - Individual addresses with electoral assignments (original)
9. **CanonicalAddress** - Deduplicated unique addresses with Hungarian formatting
10. **AddressMapping** - Mapping between original and canonical addresses
11. **AddressPollingStations** - Canonical address to polling station relationships
12. **AddressPIRCodes** - Canonical address to PIR code relationships
13. **PublicSpaceName** - Unique public space names extracted from addresses
14. **PublicSpaceType** - Unique public space types (utca, tér, etc.)
15. **SettlementPublicSpaces** - Many-to-many relationships between settlements and public spaces

### Data Structure Diagram

```mermaid
erDiagram
    County ||--o{ Settlement : contains
    County ||--o{ NationalIndividualElectoralDistrict : contains
    Settlement ||--o{ SettlementIndividualElectoralDistrict : contains
    NationalIndividualElectoralDistrict ||--o{ SettlementIndividualElectoralDistrict : contains
    SettlementIndividualElectoralDistrict ||--o{ PollingStation : contains
    PollingStation ||--o{ Address : contains
    PostalCode ||--o{ PostalCode_Settlement : has
    Settlement ||--o{ PostalCode_Settlement : has
    PostalCode ||--o{ Address : assigned
    Settlement ||--o{ SettlementPublicSpaces : has
    PublicSpaceName ||--o{ SettlementPublicSpaces : has
    PublicSpaceType ||--o{ SettlementPublicSpaces : has
    Address ||--|| AddressMapping : "maps to"
    CanonicalAddress ||--o{ AddressMapping : "has many"
    CanonicalAddress ||--o{ AddressPollingStations : "has"
    CanonicalAddress ||--o{ AddressPIRCodes : "has"
    
    County {
        string ID PK "xxhash64(CountyCode)"
        string CountyCode UK
        string CountyName
    }
    Settlement {
        string ID PK "xxhash64(CountyCode|SettlementCode)"
        string SettlementCode
        string SettlementName
        string County_ID FK
    }
    NationalIndividualElectoralDistrict {
        string ID PK "xxhash64(CountyCode|OEVK)"
        string OEVK
        string Name
        string Center
        string Polygon
        string County_ID FK
    }
    SettlementIndividualElectoralDistrict {
        string ID PK "xxhash64(CountyCode|SettlementCode|TEVK|OEVK)"
        string TEVK
        string Name
        string County_ID FK
        string Settlement_ID FK
        string NationalIndividualElectoralDistrict_ID FK
    }
    PostalCode {
        string ID PK "xxhash64(PostalCode)"
        string PostalCode UK
    }
    PostalCode_Settlement {
        string ID PK "xxhash64(PostalCode_ID|Settlement_ID)"
        string PostalCode_ID FK
        string Settlement_ID FK
    }
    PollingStation {
        string ID PK "xxhash64(CountyCode|SettlementCode|OEVK|TEVK|PollingStationAddress)"
        string PollingStationAddress
        string SettlementIndividualElectoralDistrict_ID FK
        string County_ID FK
        string Settlement_ID FK
        string NationalIndividualElectoralDistrict_ID FK
    }
    Address {
        string ID PK "xxhash64(address components)"
        integer Sequence
        integer OriginalOrder
        string FullAddress
        string PublicSpaceName
        string PublicSpaceType
        string HouseNumber
        string Building
        string Staircase
        string PostalCode_ID FK
        string PollingStation_ID FK
        string SettlementIndividualElectoralDistrict_ID FK
        string County_ID FK
        string Settlement_ID FK
        string NationalIndividualElectoralDistrict_ID FK
    }
    PublicSpaceName {
        string ID PK "xxhash64(PublicSpaceName)"
        string PublicSpaceName UK
    }
    PublicSpaceType {
        string ID PK "xxhash64(PublicSpaceType)"
        string PublicSpaceType UK
    }
    SettlementPublicSpaces {
        string ID PK "xxhash64(Settlement_ID|PublicSpaceName_ID|PublicSpaceType_ID)"
        string Settlement_ID FK
        string PublicSpaceName_ID FK
        string PublicSpaceType_ID FK
    }
    CanonicalAddress {
        string ID PK "xxhash64(CountyCode|SettlementName|FullAddress)"
        string CountyCode
        string SettlementName
        string StreetName
        string HouseNumber
        string FullAddress "Formatted Hungarian address"
        string AccessibilityFlag
        timestamp CreatedAt
    }
    AddressMapping {
        string ID PK "xxhash64(OriginalAddressID|CanonicalAddressID)"
        string OriginalAddressID FK
        string CanonicalAddressID FK
    }
    AddressPollingStations {
        string ID PK "xxhash64(CanonicalAddressID|PollingStationID)"
        string CanonicalAddressID FK
        string PollingStationID FK
    }
    AddressPIRCodes {
        string ID PK "xxhash64(CanonicalAddressID|PIRCode)"
        string CanonicalAddressID FK
        string PIRCode FK
    }
```

### Transformation Flow

```mermaid
flowchart TD
    A[Source Data] --> B[Ingestion]
    B --> C[Staging Tables]
    C --> D[Transformation]
    D --> E[Public Space Extraction]
    E --> F[Address Deduplication]
    F --> G[Normalized Tables]
    G --> H[Export]
    H --> I[CSV Files]
    
    subgraph A [Source Data]
        A1[oevk.json<br/>OEVK boundaries]
        A2[Korzet_allomany_orszagos.zip<br/>Address data]
    end
    
    subgraph B [Ingestion]
        B1[Download Sources]
        B2[Extract & Load]
        B3[Create Staging Tables]
    end
    
    subgraph C [Staging Tables]
        C1[staging_korzet<br/>Raw address data]
        C2[staging_oevk<br/>OEVK boundaries]
    end
    
    subgraph D [Transformation]
        D1[County & Settlement]
        D2[OEVK & TEVK]
        D3[Postal Codes]
        D4[Polling Stations]
        D5[Addresses]
        D6[Relationships]
    end
    
    subgraph E [Public Space Extraction]
        E1[Extract Public Space Names]
        E2[Extract Public Space Types]
        E3[Create Settlement Relationships]
    end
    
    subgraph F [Address Deduplication]
        F1[Format Addresses<br/>Hungarian conventions]
        F2[Generate Canonical IDs<br/>xxhash64]
        F3[Create Canonical Addresses<br/>0.39% reduction]
        F4[Preserve Relationships<br/>Polling Stations, PIR Codes]
    end
    
    subgraph G [Normalized Tables]
        G1[County]
        G2[Settlement]
        G3[NationalIndividualElectoralDistrict]
        G4[SettlementIndividualElectoralDistrict]
        G5[PostalCode]
        G6[PostalCode_Settlement]
        G7[PollingStation]
        G8[Address Original]
        G9[CanonicalAddress]
        G10[AddressMapping]
        G11[AddressPollingStations]
        G12[AddressPIRCodes]
        G13[PublicSpaceName]
        G14[PublicSpaceType]
        G15[SettlementPublicSpaces]
    end
    
    subgraph H [Export]
        H1[Consolidated CSVs]
        H2[Canonical Addresses<br/>UUID v3]
        H3[Original Addresses<br/>UUID v3]
    end
    
    subgraph I [CSV Files]
        I1[Entity CSVs<br/>County, Settlement, etc.]
        I2[Address_{code}_{name}.csv<br/>Canonical deduplicated]
        I3[OriginalAddress_{code}_{name}.csv<br/>With canonical refs]
        I4[Public Space CSVs<br/>Names, Types, Relationships]
    end
    
    D1 --> G1
    D1 --> G2
    D2 --> G3
    D2 --> G4
    D3 --> G5
    D6 --> G6
    D4 --> G7
    D5 --> G8
    
    E1 --> G13
    E2 --> G14
    E3 --> G15
    
    F1 --> F2
    F2 --> F3
    F3 --> F4
    F4 --> G9
    F4 --> G10
    F4 --> G11
    F4 --> G12
    
    G1 --> H1
    G2 --> H1
    G3 --> H1
    G4 --> H1
    G5 --> H1
    G6 --> H1
    G7 --> H1
    G9 --> H2
    G8 --> H3
    G13 --> H1
    G14 --> H1
    G15 --> H1
    
    H1 --> I1
    H2 --> I2
    H3 --> I3
    H1 --> I4
```

### Key Relationships

- Each address belongs to exactly one polling station
- Each polling station belongs to exactly one TEVK
- Each TEVK belongs to exactly one OEVK
- Each settlement belongs to exactly one county
- Postal codes can span multiple settlements
- Public spaces are extracted from addresses and linked to settlements
- Each public space has a name and type (utca, tér, etc.)
- Settlements can have multiple public spaces, and public spaces can appear in multiple settlements

### Deduplication Relationships

- Each original **Address** maps to exactly one **CanonicalAddress** through **AddressMapping**
- Each **CanonicalAddress** can have many original addresses (13,084 duplicates merged)
- **AddressPollingStations** preserves all polling station assignments for canonical addresses
- **AddressPIRCodes** preserves all PIR codes for canonical addresses
- Canonical IDs are deterministic: same formatted address → same canonical ID
- Export uses UUID v3 with 'oevk.hu' namespace for global uniqueness

### Field Descriptions

- **Sequence**: Logical ordering of addresses within their polling station
- **OriginalOrder**: Preserves the original loading order from source CSV for data lineage

## Development

### Testing

Run the complete test suite:

```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/contract/
python -m pytest tests/performance/

# Run public space specific tests
python -m pytest tests/contract/test_transform_public_spaces.py tests/contract/test_export_public_spaces.py

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy .

# Formatting
ruff format .
```

### Public Space Extraction

The pipeline automatically extracts public space entities from addresses:

- **Entity Recognition**: Extracts public space names and types from address strings
- **Relationship Mapping**: Creates many-to-many relationships between settlements and public spaces
- **Hash-based IDs**: Deterministic xxhash64 identifiers for all entities
- **Data Integrity**: Full validation and referential integrity
- **Export Support**: CSV export for all public space entities

#### Public Space Data Extracted:
- **PublicSpaceName**: 25,117 unique public space names (713KB)
- **PublicSpaceType**: 148 unique public space types (3.8KB)
- **SettlementPublicSpaces**: 122,524 relationships (8.3MB)

### Adding New Features

1. Follow the existing patterns in the codebase
2. Add appropriate tests
3. Update documentation
4. Run linting and type checking

## Performance

### ETL Pipeline Performance

- **Target Performance**: Process 3M+ rows in under 30 minutes (NFR-002)
- **Achieved Performance**: ~2.5 minutes for 3.34M records with parallel processing
- **Performance Improvement**: 98.6% reduction from baseline (183.6 minutes → 2.5 minutes)
- **Memory Usage**: Stable at ~34 MB throughout processing
- **Parallel Processing**: 4 worker threads with ThreadPoolExecutor
- **Chunked Processing**: Process data in 50K record chunks
- **Public Space Extraction**: Integrated into main pipeline without performance impact

### Release Workflow Performance

- **Complete Workflow**: ≤15 minutes for full release process
- **Data Validation**: ≤2 minutes for comprehensive checks
- **Package Creation**: ≤5 minutes for artifact compression
- **GitHub Integration**: ≤3 minutes for release creation
- **Idempotent Operations**: Safe to retry failed operations

### Performance Benchmarks

- **Baseline Processing**: 3 hours 3 minutes (sequential processing)
- **Optimized Processing**: ~2.5 minutes (parallel processing)
- **Processing Rate**: ~22,000 rows/second
- **Memory Usage**: ~34 MB (stable throughout processing)
- **NFR-002 Compliance**: ✅ Achieved with significant margin
- **Public Space Data**: 25,117 names, 148 types, 122,524 relationships extracted

See [PERFORMANCE_BENCHMARKS.md](PERFORMANCE_BENCHMARKS.md) for detailed performance analysis.

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Ensure all packages in `requirements.txt` are installed
2. **Network Issues**: Check internet connectivity for source data downloads
3. **Disk Space**: Ensure sufficient space for data processing (several GB)
4. **Memory Limits**: Adjust `DB_MEMORY_LIMIT` if encountering memory issues
5. **Database Locks**: Kill processes holding database locks using `lsof oevk.db` and `kill <PID>`
6. **Parallel Processing Timeouts**: Increase timeout settings for large datasets

### Release Workflow Issues

#### GitHub Token Requirements

To use the release workflow, you need a GitHub Personal Access Token with the following permissions:

- **repo** (full repository access)
- **workflow** (if using GitHub Actions)
- **read:org** (if accessing organization repositories)

**IMPORTANT**: For organization repositories, use **classic personal access tokens** instead of fine-grained tokens. Classic tokens have better organization repository upload permissions.

#### GitHub Authentication
```bash
# Verify GitHub CLI authentication
gh auth status

# Login if needed
gh auth login

# Set token explicitly
gh auth login --with-token <<< "$GITHUB_TOKEN"

# For organization repositories, use classic tokens instead of fine-grained tokens:
# 1. Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
# 2. Create a new classic token with "repo" scope
# 3. Use the classic token (starts with "gho_") instead of fine-grained tokens (start with "github_pat_")
```

#### Release Creation Failures
```bash
# Check if release already exists
gh release view 20250101-1200 --repo your-org/oevk-data

# Delete existing release if needed
gh release delete 20250101-1200 --repo your-org/oevk-data --yes

# Force recreate release
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --tag 20250101-1200 --force

# For organization repository upload issues, use classic tokens:
# 1. Regenerate token as classic token (starts with "gho_")
# 2. Update GITHUB_TOKEN environment variable
# 3. Test upload: gh release upload 20250101-1200 test_file.txt --repo your-org/oevk-data
```

#### Data Validation Issues
```bash
# Run validation with verbose output
python -m src.cli release validate --staging-dir data/staging --exports-dir exports --verbose

# Check file permissions
ls -la data/staging/
ls -la exports/

# Verify file contents
head -n 5 data/staging/addresses.csv
head -n 5 exports/addresses/Address_001_Budapest.csv
```

#### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto

# Dry run (validate without creating release)
python -m src.cli release create --repo-owner your-org --repo-name oevk-data --auto --dry-run
```

### Logs

Detailed logs are written to `logs/oevk_transform_{timestamp}.log` and include:

- Pipeline start/end times
- Step-by-step progress
- Row counts per transformation
- Performance metrics
- Error details with stack traces

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with appropriate tests
4. Ensure all tests pass
5. Submit a pull request

## License

[Add appropriate license information]

## Support

For issues and questions:
- Check the logs in `logs/` directory
- Review the documentation in `specs/`
- Open an issue in the project repository