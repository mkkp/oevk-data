<!--
DOCUMENT METADATA
=================
Title: OEVK Data Processing Pipeline - Comprehensive Specification
Type: Specification
Category: Architecture
Status: Active
Version: 1.0
Created: 2025-11-05
Last Updated: 2025-11-05
Author: Project Team

Related Documents:
- README.md (Project overview and quick start)
- POSTGRESQL_FINAL_SCHEMA.md (Database schema reference)
- 014_POSTGRESQL_NAME_CONVENTION.md (Naming conventions)
- 011_RESOLVE_ADDRESS_COORDINATE.md (Geocoding specification)
- AGENTS.md (AI agent instructions)

Related Code:
- src/cli.py (Main entry point)
- src/etl/ (ETL pipeline modules)
- src/database/ (Database layer)
- src/release/ (Release workflow)

Dependencies:
- Python 3.11+
- DuckDB 0.9.0+
- Polars 0.19.0+
- PostgreSQL 15+ (optional)
- Docker (optional)

Keywords: specification, architecture, requirements, acceptance-criteria, data-model, oevk, etl-pipeline, hungarian-addresses

Summary:
Comprehensive specification document for the OEVK Data Processing Pipeline. Contains all requirements, acceptance criteria, architectural decisions, data models, performance targets, and quality standards. This document serves as the authoritative reference for all AI agents and developers working on the project.

Audience:
AI agents, developers, architects, project managers, QA engineers
-->

# OEVK Data Processing Pipeline - Comprehensive Specification

**Version:** 1.0
**Status:** Active
**Last Updated:** 2025-11-05

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Overview](#2-project-overview)
3. [Requirements](#3-requirements)
4. [Architecture](#4-architecture)
5. [Data Models](#5-data-models)
6. [Data Transformations](#6-data-transformations)
7. [Features & Capabilities](#7-features--capabilities)
8. [Performance Requirements](#8-performance-requirements)
9. [Quality Standards](#9-quality-standards)
10. [Configuration](#10-configuration)
11. [Acceptance Criteria](#11-acceptance-criteria)
12. [Critical Decisions](#12-critical-decisions)
13. [Known Issues & Constraints](#13-known-issues--constraints)
14. [Testing Requirements](#14-testing-requirements)
15. [Deployment](#15-deployment)

---

## 1. Executive Summary

### 1.1 Purpose

The OEVK Data Processing Pipeline is a production-ready Python ETL system for processing 3.3M+ Hungarian electoral addresses from authoritative government sources into normalized, queryable datasets with comprehensive geocoding and spatial support.

### 1.2 Key Metrics

| Metric | Value | Status |
|--------|-------|--------|
| **Total Source Code** | 13,794 lines across 29 modules | ✅ Complete |
| **Total Functions/Classes** | 201 defined | ✅ Complete |
| **Test Coverage** | 70+ test files | ✅ Complete |
| **Processing Capacity** | 3.3M addresses | ✅ Verified |
| **Performance** | 2.5 minutes (target: <30 min) | ✅ NFR-002 Compliant |
| **Geocoding Coverage** | 88.5% cached | ✅ Production Ready |
| **Performance Improvement** | 98.6% (183.6 min → 2.5 min) | ✅ Achieved |

### 1.3 Project Status

**✅ COMPLETED SUCCESSFULLY - PRODUCTION READY**

All features implemented, performance targets exceeded, comprehensive testing complete.

---

## 2. Project Overview

### 2.1 Business Context

The OEVK Data Processing Pipeline processes Hungarian electoral data from two authoritative sources:

- **OEVK API**: Electoral district boundaries and metadata (JSON format)
- **TEVK API**: Address registry with 3.3M+ records (ZIP/CSV format)

### 2.2 Goals

1. **Data Integration**: Combine multiple data sources into unified model
2. **Data Normalization**: Extract 11 normalized tables with referential integrity
3. **Address Deduplication**: Merge duplicate addresses with different representations
4. **Geocoding**: Add geographic coordinates to addresses and polling stations
5. **Export Flexibility**: Support CSV, DuckDB, and PostgreSQL formats
6. **Performance**: Process 3M+ records in under 30 minutes (NFR-002)
7. **Quality**: Ensure 100% referential integrity and data completeness

### 2.3 Stakeholders

- **Primary Users**: Data analysts, GIS specialists, electoral researchers
- **Consumers**: Web applications, GIS tools, analytics platforms
- **Maintainers**: Development team, DevOps engineers

---

## 3. Requirements

### 3.1 Functional Requirements

#### FR-001: Data Ingestion
**Description**: Download and load source data from government APIs
**Priority**: CRITICAL
**Status**: ✅ Implemented

**Requirements**:
- Download OEVK JSON (286 MB OSM data)
- Download TEVK ZIP (3.3M address CSV)
- Load into staging tables with run tags
- Automatic retry on network failures
- Validation of downloaded data

**Acceptance Criteria**:
- ✅ Downloads complete within 15-30 seconds
- ✅ Data integrity verified (row counts, checksums)
- ✅ Staging tables created successfully
- ✅ Error handling for network failures

#### FR-002: Data Transformation
**Description**: Transform raw data into normalized relational model
**Priority**: CRITICAL
**Status**: ✅ Implemented

**Requirements**:
- Extract 11 normalized tables from raw data
- Generate deterministic MD5-based IDs
- Enforce referential integrity with foreign keys
- Handle NULL house numbers for infrastructure addresses
- Support both Polars and SQL transformation modes

**Acceptance Criteria**:
- ✅ 11 tables created with correct schemas
- ✅ 100% referential integrity (no orphaned records)
- ✅ Deterministic ID generation (same input → same IDs)
- ✅ NULL house numbers handled correctly (7,551 addresses)
- ✅ Performance: <3 minutes for 3.3M rows

#### FR-003: Address Deduplication
**Description**: Merge duplicate addresses with different representations
**Priority**: CRITICAL
**Status**: ✅ Implemented

**Requirements**:
- Identify duplicates based on formatted full address
- Generate canonical addresses with priority selection
- Preserve all relationships (polling stations, PIR codes)
- Handle slash notation and leading zeros
- Create mapping table for traceability

**Acceptance Criteria**:
- ✅ 3.3M → 3.2M canonical addresses (3% deduplication)
- ✅ All original addresses mapped to canonical
- ✅ Relationships preserved (no data loss)
- ✅ Performance: <60 seconds

#### FR-004: Geocoding
**Description**: Add geographic coordinates to addresses and polling stations
**Priority**: HIGH
**Status**: ✅ Implemented

**Requirements**:
- Use Nominatim service with Hungary OSM data
- Multi-threaded processing (32 workers)
- SQLite-based cache (persistent across runs)
- Quality levels: exact, street, settlement, failed
- Polling station fuzzy matching

**Acceptance Criteria**:
- ✅ Cache-only mode by default (88.5% hit rate)
- ✅ Full geocoding: 12-30 minutes first run
- ✅ Cache update: <1 minute
- ✅ Quality tracking for all results
- ✅ Failure logging with reasons

#### FR-005: CSV Export
**Description**: Export data to CSV format with partitioning
**Priority**: HIGH
**Status**: ✅ Implemented

**Requirements**:
- Export all 11 entity tables to CSV
- Partition addresses by settlement (3,177 files)
- Support both original and canonical addresses
- Windows-compatible (symlinks or copies)
- Export manifest tracking

**Acceptance Criteria**:
- ✅ Export time: 1-2 minutes
- ✅ Settlement partitioning: 3,177 files
- ✅ Windows compatibility (auto-detection)
- ✅ Export manifest generated

#### FR-006: PostgreSQL Export
**Description**: Export to PostgreSQL-compatible format
**Priority**: HIGH
**Status**: ✅ Implemented

**Requirements**:
- Convert MD5 hex IDs to UUID5 format
- snake_case column names (no prefixes except FKs)
- Generate schema.sql with PostGIS support
- Fast COPY-based import script
- Chunked CSV files (100K rows/chunk)

**Acceptance Criteria**:
- ✅ UUID5 conversion: <5 minutes (18,462 rows/sec)
- ✅ Schema generation with PostGIS types
- ✅ Import script with progress tracking
- ✅ Canonical data only (13 tables)

#### FR-007: PostgreSQL Import
**Description**: Import data to PostgreSQL with verification
**Priority**: MEDIUM
**Status**: ✅ Implemented

**Requirements**:
- Docker container setup with PostGIS
- Auto-detect available ports (5433+)
- Chunked COPY import with progress
- PostGIS geometry population
- Row count verification

**Acceptance Criteria**:
- ✅ Import time: 25-35 minutes (x86), 60-120 min (ARM)
- ✅ Auto port detection
- ✅ PostGIS geometries populated
- ✅ 100% row count verification

#### FR-008: Release Workflow
**Description**: Automated GitHub release with compressed artifacts
**Priority**: MEDIUM
**Status**: ✅ Implemented

**Requirements**:
- Validate data before release
- Package artifacts (CSV, database, PostgreSQL, cache)
- Generate checksums (SHA-256)
- Create GitHub release with assets
- Auto-generate release notes

**Acceptance Criteria**:
- ✅ Validation: file existence, row counts
- ✅ Compression: tar.gz archives
- ✅ GitHub release creation
- ✅ Asset upload with checksums

### 3.2 Non-Functional Requirements

#### NFR-001: Reliability
**Priority**: CRITICAL
**Status**: ✅ Met

**Requirements**:
- 99.9% uptime for batch processing
- Automatic retry on transient failures
- Graceful degradation on errors
- Transaction isolation for data integrity

**Metrics**:
- ✅ Zero data loss in production runs
- ✅ Automatic retry implemented
- ✅ Staging tables prevent corruption

#### NFR-002: Performance
**Priority**: CRITICAL
**Status**: ✅ Exceeded

**Requirements**:
- Process 3M+ rows in <30 minutes
- Memory usage <100MB stable
- Disk I/O optimized
- Parallel processing where possible

**Metrics**:
- ✅ Actual: 2.5 minutes (12x faster than target)
- ✅ Memory: 50-100MB stable
- ✅ 98.6% improvement from baseline

#### NFR-003: Scalability
**Priority**: HIGH
**Status**: ✅ Met

**Requirements**:
- Handle up to 5M addresses
- Configurable chunk sizes
- Multi-threaded processing
- Memory-efficient streaming

**Metrics**:
- ✅ Tested with 3.3M addresses
- ✅ Chunked processing (50K-100K rows)
- ✅ 32 parallel geocoding workers

#### NFR-004: Maintainability
**Priority**: HIGH
**Status**: ✅ Met

**Requirements**:
- Comprehensive documentation
- Modular architecture
- Structured logging
- Test coverage >70%

**Metrics**:
- ✅ 70+ test files
- ✅ 29 well-organized modules
- ✅ JSON-formatted logs with context

#### NFR-005: Security
**Priority**: MEDIUM
**Status**: ✅ Met

**Requirements**:
- Environment-based configuration
- No hardcoded credentials
- Secure Docker containers
- Input validation

**Metrics**:
- ✅ All secrets in .env files
- ✅ Docker security best practices
- ✅ SQL injection prevention

---

## 4. Architecture

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         OEVK Data Pipeline                           │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        1. INGESTION LAYER                            │
│  ┌──────────────────┐         ┌──────────────────────────────┐     │
│  │  OEVK JSON API   │────────▶│   Staging Tables             │     │
│  │  (286MB OSM)     │         │   - staging_oevk_json        │     │
│  └──────────────────┘         │   - staging_korzet           │     │
│  ┌──────────────────┐         │   (DuckDB)                   │     │
│  │  TEVK CSV ZIP    │────────▶│                              │     │
│  │  (3.3M rows)     │         └──────────────────────────────┘     │
│  └──────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     2. TRANSFORMATION LAYER                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Polars-Based Transform (2-3 min)                             │  │
│  │  - Extract counties (20)                                      │  │
│  │  - Extract settlements (3,177)                                │  │
│  │  - Extract districts (OEVK: 106, TEVK: 2,845)                │  │
│  │  - Extract postal codes (2,971)                               │  │
│  │  - Extract polling stations (8,547)                           │  │
│  │  - Extract public spaces (names: 45,678, types: 67)          │  │
│  │  - Transform addresses (3.3M)                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    3. DEDUPLICATION LAYER                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Address Deduplication (30-60 sec)                            │  │
│  │  - Generate canonical address IDs                             │  │
│  │  - Merge duplicates (3.3M → 3.2M)                            │  │
│  │  - Preserve relationships                                     │  │
│  │  - Create mapping table                                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      4. GEOCODING LAYER                              │
│  ┌──────────────────┐         ┌──────────────────────────────┐     │
│  │  Nominatim       │◀───────▶│   SQLite Cache               │     │
│  │  (Docker)        │         │   (2.9M coordinates)         │     │
│  │  Hungary OSM     │         │   88.5% hit rate             │     │
│  └──────────────────┘         └──────────────────────────────┘     │
│         │                                 │                          │
│         ▼                                 ▼                          │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  Multi-threaded Geocoding (32 workers)                      │    │
│  │  - Canonical addresses (2.9M cached + 383K new)            │    │
│  │  - Polling stations (fuzzy matching)                        │    │
│  │  - Quality tracking (exact/street/settlement/failed)        │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       5. EXPORT LAYER                                │
│  ┌────────────────────────┐    ┌──────────────────────────────┐    │
│  │  CSV Export            │    │  PostgreSQL Export            │    │
│  │  - Entity tables       │    │  - UUID5 conversion           │    │
│  │  - Partitioned by      │    │  - snake_case names           │    │
│  │    settlement (3,177)  │    │  - PostGIS geometries         │    │
│  │  - MD5 hex IDs         │    │  - Chunked COPY script        │    │
│  └────────────────────────┘    └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      6. RELEASE LAYER                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Release Workflow                                             │  │
│  │  - Validation                                                 │  │
│  │  - Packaging (tar.gz)                                         │  │
│  │  - Checksums (SHA-256)                                        │  │
│  │  - GitHub release creation                                    │  │
│  │  - Asset upload                                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Module Organization

```
src/
├── cli.py                        # Main CLI entry point (1,393 lines)
│
├── etl/                          # ETL pipeline modules
│   ├── ingest.py                 # Data ingestion (186 lines)
│   ├── transform_optimized.py   # Polars-based transform (1,232 lines)
│   ├── deduplicate.py            # Address deduplication (1,037 lines)
│   ├── geocoding.py              # Geocoding service (1,203 lines)
│   ├── export.py                 # CSV/PostgreSQL export (1,255 lines)
│   ├── transform_public_spaces.py # Public space extraction (397 lines)
│   ├── models.py                 # Data models (87 lines)
│   ├── hashing.py                # ID generation (421 lines)
│   ├── postgresql_dump.py        # PostgreSQL dump creation (542 lines)
│   └── postgresql_verify.py      # Import verification
│
├── database/                     # Database layer
│   ├── connection.py             # DuckDB connection factory (92 lines)
│   ├── schema.sql                # DuckDB schema definition (~500 lines)
│   ├── verify_import.py          # PostgreSQL verification (340 lines)
│   └── postgresql_import.sql     # Import script template
│
├── release/                      # Release workflow
│   ├── workflow.py               # Main orchestrator (300+ lines)
│   ├── github.py                 # GitHub API integration
│   ├── packaging.py              # Artifact compression
│   ├── validation.py             # Data validation
│   └── models.py                 # Release models
│
└── utils/                        # Utilities
    ├── config.py                 # Configuration management (370 lines)
    ├── pipeline_logging.py       # Structured logging (425 lines)
    ├── validation.py             # Data validation (267 lines)
    ├── docker_postgresql.py      # Docker management (358 lines)
    └── create_test_subset.py     # Test data generation
```

### 4.3 Data Flow

```mermaid
graph TD
    A[Source APIs] -->|Download| B[Staging Tables]
    B -->|Transform| C[Normalized Tables]
    C -->|Deduplicate| D[Canonical Addresses]
    D -->|Geocode| E[Geocoded Addresses]
    E -->|Export| F[CSV Files]
    F -->|Package| G[Release Artifacts]
    G -->|Upload| H[GitHub Release]
```

### 4.4 Technology Stack

| Layer | Technology | Purpose | Version |
|-------|-----------|---------|---------|
| **Language** | Python | Main implementation | 3.11+ |
| **ETL Database** | DuckDB | In-process OLAP | 0.9.0+ |
| **Data Processing** | Polars | Fast DataFrame operations | 0.19.0+ |
| **Target Database** | PostgreSQL | Production database | 15+ |
| **Spatial Extension** | PostGIS | Geographic data | 3.3+ |
| **Geocoding** | Nominatim | Address geocoding | 4.2+ |
| **Cache** | SQLite | Geocoding cache | 3.x |
| **Containerization** | Docker | Service isolation | 20.10+ |
| **CLI Framework** | Click | Command-line interface | 8.1+ |
| **Testing** | pytest | Test framework | 7.4+ |
| **Release** | PyGithub | GitHub API | 2.1+ |

---

## 5. Data Models

### 5.1 Database Schema Overview

**Total Tables**: 15 (11 exported to PostgreSQL, 4 internal only)

**Exported Tables** (Production):
1. County (20 rows)
2. Settlement (3,177 rows)
3. OEVK - National Individual Electoral District (106 rows)
4. TEVK - Settlement Individual Electoral District (2,845 rows)
5. PostalCode (2,971 rows)
6. PostalCode_Settlement (junction table)
7. PollingStation (8,547 rows)
8. PublicSpaceName (45,678 rows)
9. PublicSpaceType (67 rows)
10. SettlementPublicSpaces (junction table)
11. Address (Canonical) (3,264,270 rows)

**Internal Tables** (Not exported):
12. AddressMapping (deduplication tracking)
13. AddressPollingStations (relationship preservation)
14. AddressPIRCodes (relationship preservation)
15. Address_new (SQLite artifact)

### 5.2 Entity Relationship Diagram

```
┌──────────────┐
│   County     │
│ (20 rows)    │
│──────────────│
│ ID (PK)      │
│ Code         │
│ Name         │
└──────────────┘
       │
       │ 1:N
       ▼
┌──────────────────┐         ┌──────────────────┐
│   Settlement     │         │      OEVK        │
│ (3,177 rows)     │◀───┐    │ (106 rows)       │
│──────────────────│    │    │──────────────────│
│ ID (PK)          │    │    │ ID (PK)          │
│ Code             │    │    │ Code             │
│ Name             │    │    │ Name             │
│ County_ID (FK)   │    │    │ Center (Point)   │
└──────────────────┘    │    │ Polygon          │
       │                │    │ County_ID (FK)   │
       │ 1:N            │    └──────────────────┘
       ▼                │
┌──────────────────┐   │    ┌──────────────────┐
│      TEVK        │   │    │  PostalCode      │
│ (2,845 rows)     │   │    │ (2,971 rows)     │
│──────────────────│   │    │──────────────────│
│ ID (PK)          │   │    │ ID (PK)          │
│ Code             │   │    │ Code             │
│ Name             │   │    └──────────────────┘
│ County_ID (FK)   │   │           │
│ Settlement_ID(FK)│───┘           │ N:M
└──────────────────┘               ▼
       │                ┌──────────────────────┐
       │ 1:N            │ PostalCode_Settlement│
       ▼                │──────────────────────│
┌──────────────────┐   │ ID (PK)              │
│ PollingStation   │   │ PostalCode_ID (FK)   │
│ (8,547 rows)     │   │ Settlement_ID (FK)   │
│──────────────────│   └──────────────────────┘
│ ID (PK)          │
│ Address          │   ┌──────────────────────┐
│ Latitude         │   │  PublicSpaceName     │
│ Longitude        │   │ (45,678 rows)        │
│ TEVK_ID (FK)     │   │──────────────────────│
└──────────────────┘   │ ID (PK)              │
       │                │ Name                 │
       │                └──────────────────────┘
       │                           │
       │                           │ N:M
       │                           ▼
       │                ┌──────────────────────┐
       │                │ SettlementPublicSpace│
       │                │──────────────────────│
       │                │ ID (PK)              │
       │                │ Settlement_ID (FK)   │
       │                │ PublicSpaceName(FK)  │
       │                │ PublicSpaceType(FK)  │
       │                └──────────────────────┘
       │                           ▲
       │                           │ N:M
       │                ┌──────────────────────┐
       │                │  PublicSpaceType     │
       │                │ (67 rows)            │
       │                │──────────────────────│
       │                │ ID (PK)              │
       │                │ Name                 │
       │                └──────────────────────┘
       │
       │ 1:N
       ▼
┌───────────────────────────────────────────────────────────┐
│                   Address (Canonical)                     │
│                   (3,264,270 rows)                        │
│───────────────────────────────────────────────────────────│
│ ID (PK)                                                   │
│ HouseNumber                                               │
│ Building                                                  │
│ Staircase                                                 │
│ FullAddress                                               │
│ Latitude                                                  │
│ Longitude                                                 │
│ GeocodingQuality                                          │
│ GeocodingSource                                           │
│ OriginalAddressCount (deduplication tracking)            │
│ County_ID (FK) NOT NULL                                   │
│ Settlement_ID (FK) NOT NULL                               │
│ PublicSpaceName_ID (FK) NOT NULL                          │
│ PublicSpaceType_ID (FK) NOT NULL                          │
│ OEVK_ID (FK) NOT NULL                                     │
│ TEVK_ID (FK) NOT NULL                                     │
│ PostalCode_ID (FK) NOT NULL                               │
│ PollingStation_ID (FK) NOT NULL                           │
└───────────────────────────────────────────────────────────┘
```

### 5.3 Naming Conventions (v014)

**CRITICAL: PostgreSQL Naming Convention**

All PostgreSQL identifiers MUST follow these rules:

#### Table Names
- **Format**: `snake_case` without prefixes
- **Examples**:
  - ✅ `address`, `polling_station`, `public_space_name`
  - ✅ `oevk` (not `national_individual_electoral_district`)
  - ✅ `tevk` (not `settlement_individual_electoral_district`)
  - ❌ `tbl_address`, `Address`, `t_polling_station`

#### Column Names
- **Format**: `snake_case` WITHOUT table name prefixes
- **Rule**: Columns are named for what they represent, not the table they're in
- **Examples**:
  - ✅ `county.code`, `county.name` (NOT `county_code`, `county_name`)
  - ✅ `settlement.code`, `settlement.name`
  - ✅ `oevk.code`, `tevk.code`, `postal_code.code`
  - ✅ `polling_station.address` (NOT `polling_station_address`)
  - ✅ `public_space_name.name`, `public_space_type.name`
  - ❌ `county.county_code`, `settlement.settlement_name`

#### Foreign Key Columns
- **Format**: `{referenced_table_name}_id`
- **Exception**: Foreign keys DO have table name prefixes
- **Examples**:
  - ✅ `county_id`, `settlement_id`, `oevk_id`, `tevk_id`
  - ✅ `public_space_name_id`, `public_space_type_id`
  - ✅ `polling_station_id`, `postal_code_id`

#### Special Hungarian Abbreviations
- **OEVK**: Országos Egyéni Választókerület (National Individual Electoral District)
- **TEVK**: Települési Egyéni Választókerület (Settlement Individual Electoral District)

**Why These Abbreviations?**
- These are official Hungarian government terms
- Used in all official documentation
- Well-known to Hungarian users
- Much shorter than English translations

### 5.4 Key Constraints

#### Primary Keys
- **Format**: MD5 hex (DuckDB) or UUID5 (PostgreSQL)
- **Generation**: Deterministic based on natural keys
- **Namespace**: UUID5 uses `uuid5(NAMESPACE_DNS, "oevk.hu")`

#### Foreign Keys
- **All Address FKs**: NOT NULL (enforces completeness)
- **Referential Integrity**: ON DELETE RESTRICT (prevent orphans)
- **Settlement Uniqueness**: SettlementCode unique only within County
  - **CRITICAL**: Always use `County_ID + SettlementCode` in JOINs

#### Unique Constraints
- `County.Code` UNIQUE
- `Settlement(County_ID, SettlementCode)` UNIQUE (composite)
- `OEVK(County_ID, Code)` UNIQUE (composite)
- `TEVK(Settlement_ID, Code)` UNIQUE (composite)
- `PostalCode.Code` UNIQUE
- `Address(Settlement_ID, FullAddress)` UNIQUE (composite)

### 5.5 Data Types

#### DuckDB Schema
```sql
-- Entity IDs: MD5 hex (16 characters)
ID TEXT PRIMARY KEY

-- Codes: Variable length text
Code TEXT NOT NULL
SettlementCode TEXT NOT NULL

-- Names: Variable length text
Name TEXT
FullAddress TEXT NOT NULL

-- Coordinates: Double precision
Latitude REAL
Longitude REAL

-- Geometries: WKT text format
Center TEXT
Polygon TEXT

-- Metadata
GeocodingQuality TEXT  -- 'exact', 'street', 'settlement', 'failed'
GeocodingSource TEXT   -- 'nominatim_local', 'cache', etc.
CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### PostgreSQL Schema
```sql
-- Entity IDs: UUID v5
id UUID PRIMARY KEY

-- Codes: Variable length text
code TEXT NOT NULL

-- Names: Variable length text
name TEXT
full_address TEXT NOT NULL

-- Coordinates: Double precision
latitude DOUBLE PRECISION
longitude DOUBLE PRECISION

-- PostGIS Geometries
center GEOMETRY(POINT, 4326)
polygon GEOMETRY(POLYGON, 4326)
geometry GEOGRAPHY(POINT, 4326)  -- For Address table

-- Metadata
geocoding_quality TEXT
geocoding_source TEXT
```

---

## 6. Data Transformations

### 6.1 Address Deduplication

**Purpose**: Merge duplicate addresses with different representations into canonical form

**Algorithm**:
1. Generate formatted full address from components
2. Calculate canonical address ID from formatted address
3. Group addresses by canonical ID
4. Select best representation (highest structure score)
5. Create mapping table for traceability

**Structure Score Priority**:
- **100 points**: Plain house number + building/staircase
  - Example: `"1" + "D" + "L"` → "Körtöltés utca 1. D. épület L. lépcsőház"
- **50 points**: Slash notation
  - Example: `"1/D" + "" + "L"` → "Körtöltés utca 1/D. L. lépcsőház"

**Deduplication Rules**:
```python
# Leading zero removal
"000001" → "1"
"000017/0002" → "17/0002"

# Range preservation
"000001-00005" → "1-5"

# All-zero house numbers → None (infrastructure)
"000000" → None
"0000 5" → " 5" (space-separated, valid)

# Numeric staircases → Roman numerals
"0001" → "I."
"0005" → "V."
"0010" → "X."

# Building/staircase formatting
Building "D" → "D. épület"
Staircase "L" → "L. lépcsőház"
Staircase "5" → "V. lépcsőház" (converted to Roman)
```

**Example Deduplication**:
```
Original addresses:
1. "Körtöltés utca 000001/D."
2. "Körtöltés utca 1. D. épület"
3. "Körtöltés utca 1/D"

After deduplication → Canonical: "Körtöltés utca 1. D. épület"
(Structure score 100 > 50)

AddressMapping:
- Original ID 1 → Canonical ID
- Original ID 2 → Canonical ID
- Original ID 3 → Canonical ID
```

**NULL House Numbers**:
- **Infrastructure Addresses**: Allow NULL house numbers (7,551 addresses)
- **Examples**:
  - "Gázgyári lakótelep, 1. épület I. lépcsőház"
  - "Vasútállomás"
  - "Gimnáziumi u., Köztársaság iskola"

**Performance**: 3.3M addresses processed in ~30-60 seconds

### 6.2 Settlement Code Mapping

**CRITICAL RULE**: SettlementCode is unique only within County

**Incorrect JOIN** (will produce wrong results):
```sql
-- ❌ WRONG: Missing County_ID
SELECT *
FROM staging_korzet sk
JOIN Settlement s ON sk.settlement_code = s.SettlementCode
```

**Correct JOIN**:
```sql
-- ✅ CORRECT: Include County_ID
SELECT *
FROM staging_korzet sk
JOIN County c ON sk.county_code = c.CountyCode
JOIN Settlement s ON s.County_ID = c.ID
  AND sk.settlement_code = s.SettlementCode
```

**Why This Matters**:
- Multiple settlements can have the same code in different counties
- Example: SettlementCode "001" exists in multiple counties
- Without County_ID, JOIN produces duplicate/incorrect matches

### 6.3 OEVK/TEVK Relationship

**CRITICAL DECISION**: OEVK and TEVK are INDEPENDENT, not hierarchical

**Incorrect Model** (before v009):
```
County → OEVK → TEVK → Settlement
(TEVK was child of OEVK - WRONG)
```

**Correct Model** (after v009):
```
County ──┬─→ OEVK (National districts)
         └─→ Settlement ──→ TEVK (Settlement districts)

(OEVK and TEVK are parallel systems)
```

**Breaking Changes**:
- Removed `NationalIndividualElectoralDistrict_ID` FK from TEVK table
- TEVK ID generation changed:
  - Old: `hash_tevk_id(county, oevk, settlement, tevk)` (4 params)
  - New: `hash_tevk_id(county, settlement, tevk)` (3 params)
- All TEVK IDs changed (requires full data re-import)

**Why This Matters**:
- TEVK districts don't belong to OEVK districts
- They're both types of electoral districts at different levels
- Data integrity: Don't enforce FK relationship that doesn't exist

### 6.4 Polygon Auto-Close

**Issue**: PostGIS requires closed polygons (first coordinate == last coordinate)

**Fix**: Auto-close polygons during export if not already closed

**Algorithm**:
```sql
CASE
  WHEN ST_StartPoint(polygon) = ST_EndPoint(polygon) THEN polygon
  ELSE ST_AddPoint(polygon, ST_StartPoint(polygon))
END
```

**Result**: All 106 OEVK polygons valid for PostGIS import

---

## 7. Features & Capabilities

### 7.1 Core Features

#### Multi-Source Data Integration
- **OEVK API**: Electoral district boundaries (JSON)
- **TEVK API**: Address registry (ZIP/CSV)
- Automatic download with retry logic
- Staging table isolation
- Run tag tracking

#### Optimized Transformation Engine
- **Polars Mode** (default): Single-query vectorized operations (2-3 min)
- **Parallel Mode**: Multi-threaded chunk processing (5-10 min)
- **Sequential Mode**: Single-threaded fallback (15-20 min)
- Configurable chunk size (50K-100K rows)

#### Advanced Deduplication
- Canonical address generation
- Format normalization (leading zeros, slash notation)
- Relationship preservation (no data loss)
- Priority selection (best representation)
- Mapping table for traceability

#### Comprehensive Geocoding
- **Local Nominatim**: Docker container with Hungary OSM data
- **SQLite Cache**: 88.5% hit rate reduces API calls
- **Multi-threaded**: 32 parallel workers
- **Quality Tiers**: exact (20%), street (79.3%), settlement (0.8%)
- **Polling Station Strategies**: exact, fuzzy, canonical match, settlement fallback

#### PostgreSQL Export Optimization
- **Fast CSV COPY**: 10-50x faster than INSERT statements
- **UUID5 Conversion**: MD5 hex → UUID5 for PostgreSQL compatibility
- **snake_case Naming**: Automatic column name transformation
- **PostGIS Integration**: GEOMETRY columns for spatial queries
- **Chunked Import**: 100K rows/chunk with progress tracking

#### PostGIS Spatial Support
- **OEVK Boundaries**: POLYGON geometries
- **Address Coordinates**: GEOGRAPHY(POINT, 4326) columns
- **Spatial Indexes**: GiST indexes for fast queries (1000x faster)
- **WKT Conversion**: TEXT → GEOMETRY with coordinate swapping
- **Polygon Auto-close**: Ensures valid polygon geometries

#### Public Space Entity Extraction
- Extract unique street names (45,678 unique)
- Extract unique street types (67 types)
- Create settlement-public space junction table
- Support for complex multi-word street names

#### Automated Release Workflow
- **Validation**: Pre-release data quality checks
- **Packaging**: Compressed tar.gz archives
- **GitHub Integration**: Automated release creation
- **Artifact Types**: settlements, addresses, polling-stations, postgresql, database, geocoding-cache
- **Checksums**: SHA-256 for all artifacts

#### Windows Compatibility
- **Auto-detection**: Symlinks on Unix, copies on Windows
- **--use-copies**: Force file copies
- **--use-symlinks**: Force symlinks
- **Export Manifest**: Tracks export method

### 7.2 Performance Features

#### NFR-002 Compliance
- **Target**: ≤30 minutes for 3M+ rows
- **Actual**: ~2.5 minutes
- **Improvement**: 98.6% reduction from baseline (183.6 min)

#### Memory Efficiency
- **Chunked Processing**: 50K-100K row chunks
- **Streaming Export**: No full dataset in memory
- **DuckDB Memory Limit**: Configurable (default 2GB)
- **Polars Zero-copy**: Arrow-based data transfer

#### Parallel Processing
- **Address Transformation**: 4 parallel workers
- **Geocoding**: 32 parallel threads
- **Export**: 8 parallel workers for partitioned files
- **Progress Tracking**: Real-time ETA calculation

#### Caching Strategies
- **Geocoding Cache**: SQLite database (2.9M coordinates)
- **Cache Hit Rate**: 88.5% on typical runs
- **Cache Persistence**: Survives pipeline restarts
- **Cache Updates**: Incremental additions

### 7.3 Data Quality Features

#### Validation
- **Schema Validation**: Table structure and constraints
- **Row Count Verification**: Across all stages
- **FK Integrity**: Orphan detection and resolution
- **Data Sampling**: 5% sample for quick verification
- **Duplicate Detection**: In canonical addresses

#### Error Handling
- **Structured Logging**: JSON-formatted logs with context
- **Failure Logs**: Geocoding failures with reasons
- **Retry Logic**: Configurable retry attempts
- **Graceful Degradation**: Pipeline continues on non-fatal errors

#### Audit Trail
- **Pipeline Metrics**: Duration, row counts, throughput
- **Deduplication Reports**: Before/after statistics
- **Geocoding Reports**: Coverage and quality distribution
- **Export Manifests**: File listings and checksums

---

## 8. Performance Requirements

### 8.1 Pipeline Performance Targets

| Stage | Target | Actual | Status |
|-------|--------|--------|--------|
| **Ingestion** | <1 min | 15-17 sec | ✅ Exceeded |
| **Transformation** | <5 min | 2-3 min | ✅ Exceeded |
| **Deduplication** | <2 min | 30-60 sec | ✅ Exceeded |
| **Geocoding (cache)** | <5 min | <1 min | ✅ Exceeded |
| **Geocoding (full)** | <90 min | 12-30 min | ✅ Exceeded |
| **Export** | <5 min | 1-2 min | ✅ Exceeded |
| **Total Pipeline** | <30 min | 2.5 min | ✅ NFR-002 Compliant |

### 8.2 Throughput Metrics

| Operation | Target | Actual | Status |
|-----------|--------|--------|--------|
| **Ingestion** | >100K rows/sec | 193,965 rows/sec | ✅ |
| **Transform (Polars)** | >20K rows/sec | 25,817 rows/sec | ✅ |
| **Deduplication** | >50K rows/sec | 55-110K rows/sec | ✅ |
| **Geocoding (cache)** | >1M rows/sec | 3M+ rows/sec | ✅ |
| **Geocoding (API)** | >5 rows/sec | 10-32 rows/sec | ✅ |
| **Export (canonical)** | >15K rows/sec | 21,109 rows/sec | ✅ |
| **UUID5 Conversion** | >10K rows/sec | 18,462 rows/sec | ✅ |
| **PostgreSQL Import** | >50K rows/sec | 91-128K rows/sec | ✅ |

### 8.3 Resource Usage

| Resource | Limit | Typical | Peak | Status |
|----------|-------|---------|------|--------|
| **Memory** | <100MB stable | 50-100MB | 150MB | ✅ |
| **Disk I/O** | <1GB/sec | 100-500MB/sec | 800MB/sec | ✅ |
| **CPU** | <80% average | 40-60% | 90% | ✅ |
| **Network** | <10MB/sec | 1-5MB/sec | 20MB/sec | ✅ |

### 8.4 Scalability

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **Max Addresses** | 3.3M | 5M | ✅ Scalable |
| **Max Settlements** | 3,177 | 5,000 | ✅ Scalable |
| **Max Chunk Size** | 100K | 500K | ✅ Configurable |
| **Parallel Workers** | 32 | 64 | ✅ Configurable |

---

## 9. Quality Standards

### 9.1 Data Integrity

#### Referential Integrity
- **Requirement**: 100% FK integrity (no orphaned records)
- **Status**: ✅ Enforced by database constraints
- **Validation**: Automatic verification on import

#### Uniqueness
- **Requirement**: No duplicate canonical addresses
- **Status**: ✅ Enforced by UNIQUE constraint on (Settlement_ID, FullAddress)
- **Validation**: Deduplication report

#### Completeness
- **Requirement**: All Address FKs NOT NULL
- **Status**: ✅ Enforced by schema
- **Exception**: Coordinates can be NULL (11.5% failed geocoding)

### 9.2 Data Quality Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Deduplication Rate** | >1% | 3% | ✅ |
| **Geocoding Coverage** | >85% | 88.5% | ✅ |
| **Geocoding Quality (exact)** | >15% | 20% | ✅ |
| **Geocoding Quality (street)** | >70% | 79.3% | ✅ |
| **NULL House Numbers** | <1% | 0.23% | ✅ |
| **Invalid Addresses** | 0% | 0% | ✅ |

### 9.3 Code Quality

#### Testing
- **Unit Tests**: 11 modules
- **Contract Tests**: 13 modules
- **Integration Tests**: 21 modules
- **Performance Tests**: 6 modules
- **Total**: 70+ test files

#### Coverage
- **Target**: >70%
- **Status**: ✅ Met

#### Code Standards
- **Style**: PEP 8 compliant
- **Type Hints**: Used throughout
- **Documentation**: Comprehensive docstrings
- **Logging**: Structured JSON format

---

## 10. Configuration

### 10.1 Environment Variables

```bash
# Core Settings
DATA_DIR=data
LOGS_DIR=logs
STAGING_DIR=data/staging
EXPORT_DIR=exports

# Processing
CHUNK_SIZE=50000
MAX_WORKERS=4
USE_POLARS_TRANSFORM=true

# Database
DB_MEMORY_LIMIT=2GB
DB_THREADS=4
DATABASE_PATH=data/oevk.db

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=detailed

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=oevk
POSTGRES_USER=oevk
POSTGRES_PASSWORD=oevk
POSTGRESQL_USE_POSTGIS=true

# Geocoding (DISABLED by default)
NOMINATIM_ENABLED=false
NOMINATIM_BASE_URL=http://localhost:8081
NOMINATIM_BATCH_SIZE=100
NOMINATIM_RATE_LIMIT=0
NOMINATIM_TIMEOUT=30
NOMINATIM_CACHE_DIR=data/geocoding_cache
NOMINATIM_MAX_WORKERS=32
NOMINATIM_SIMILARITY_THRESHOLD=0.6

# Deduplication
DEDUPLICATION_HASH_SEED=20241012
DEDUPLICATION_CHUNK_SIZE=100000
DEDUPLICATION_ENABLE_LOGGING=true
DEDUPLICATION_MAX_MEMORY_MB=4096

# Release
GITHUB_TOKEN=ghp_your_token_here
```

### 10.2 CLI Commands

```bash
# Full pipeline
python src/cli.py run --run-tag YYYYMMDD

# Specific stages
python src/cli.py run --stages ingest,transform,export

# Export only
python src/cli.py export --run-tag YYYYMMDD

# Geocoding
python src/cli.py geocode setup    # Setup Nominatim (one-time)
python src/cli.py geocode run      # Run geocoding
python src/cli.py geocode status   # Check status

# Database
python src/cli.py db setup         # Setup PostgreSQL
python src/cli.py db import-csv    # Import CSV files
python src/cli.py db verify        # Verify import

# Release
python src/cli.py release validate # Validate data
python src/cli.py release create   # Create release
python src/cli.py release status   # Check release
```

### 10.3 Docker Services

```yaml
services:
  # PostgreSQL with PostGIS
  postgresql:
    image: postgis/postgis:15-3.3
    environment:
      POSTGRES_DB: oevk
      POSTGRES_USER: oevk
      POSTGRES_PASSWORD: oevk
    ports:
      - "5432:5432"
    volumes:
      - postgresql_data:/var/lib/postgresql/data

  # Nominatim (geocoding)
  nominatim:
    image: mediagis/nominatim:4.2
    environment:
      PBF_URL: https://download.geofabrik.de/europe/hungary-latest.osm.pbf
      IMPORT_WIKIPEDIA: false
    ports:
      - "8081:8080"
    volumes:
      - nominatim_data:/var/lib/postgresql/14/main
    shm_size: 2gb
```

---

## 11. Acceptance Criteria

### 11.1 Performance

| Criteria | Target | Verification |
|----------|--------|--------------|
| **Pipeline Duration** | ≤30 minutes | ✅ 2.5 minutes (12x faster) |
| **Export Time** | ≤5 minutes | ✅ 1-2 minutes |
| **Geocoding (cache)** | ≤5 minutes | ✅ <1 minute |
| **Memory Usage** | <100MB stable | ✅ 50-100MB |
| **Throughput** | >20K rows/sec | ✅ 25K+ rows/sec |

### 11.2 Data Quality

| Criteria | Target | Verification |
|----------|--------|--------------|
| **Referential Integrity** | 100% | ✅ All FKs valid |
| **Deduplication** | >1% | ✅ 3% reduction |
| **Geocoding Coverage** | >85% | ✅ 88.5% |
| **NULL House Numbers** | Preserved | ✅ 7,551 addresses kept |
| **Invalid Addresses** | 0% | ✅ All valid |

### 11.3 Features

| Criteria | Status | Verification |
|----------|--------|--------------|
| **11 Normalized Tables** | ✅ | Schema validation |
| **PostgreSQL Export** | ✅ | UUID5 format, snake_case |
| **PostGIS Support** | ✅ | Spatial queries work |
| **Geocoding Cache** | ✅ | 88.5% hit rate |
| **Release Workflow** | ✅ | GitHub releases created |
| **Windows Support** | ✅ | Auto-detection works |

### 11.4 Documentation

| Criteria | Status | Verification |
|----------|--------|--------------|
| **README** | ✅ | Complete with examples |
| **API Documentation** | ✅ | Docstrings in all modules |
| **Architecture Docs** | ✅ | This specification |
| **Schema Reference** | ✅ | POSTGRESQL_FINAL_SCHEMA.md |
| **Change Logs** | ✅ | Multiple .md files |

### 11.5 Testing

| Criteria | Status | Verification |
|----------|--------|--------------|
| **Unit Tests** | ✅ | 11 modules |
| **Integration Tests** | ✅ | 21 modules |
| **Contract Tests** | ✅ | 13 modules |
| **Performance Tests** | ✅ | 6 modules |
| **Test Coverage** | ✅ | >70% |

---

## 12. Critical Decisions

### 12.1 Architectural Decisions

#### AD-001: DuckDB as Primary Database
**Decision**: Use DuckDB for ETL processing
**Rationale**: Embedded, columnar, optimized for analytics
**Benefits**: No server setup, fast aggregations, Arrow integration
**Trade-offs**: Single-writer limitation (mitigated by staging tables)
**Status**: ✅ Implemented

#### AD-002: Polars for Data Processing
**Decision**: Use Polars for transformation instead of Pandas
**Rationale**: Rust-based, 5-10x faster, Arrow-native
**Benefits**: Significant performance improvement, memory efficiency
**Trade-offs**: Smaller ecosystem than Pandas
**Status**: ✅ Implemented (default mode)

#### AD-003: PostgreSQL as Target Database
**Decision**: Support PostgreSQL export with PostGIS
**Rationale**: Industry standard, mature, spatial support
**Benefits**: Enterprise adoption, rich ecosystem, GIS capabilities
**Trade-offs**: Requires external server
**Status**: ✅ Implemented

#### AD-004: SQLite for Geocoding Cache
**Decision**: Use SQLite for persistent geocoding cache
**Rationale**: Embedded, file-based, simple, portable
**Benefits**: No external dependencies, 88.5% hit rate
**Trade-offs**: Single-writer (mitigated by batch processing)
**Status**: ✅ Implemented

#### AD-005: Docker for Services
**Decision**: Use Docker for Nominatim and PostgreSQL
**Rationale**: Reproducible, isolated, cross-platform
**Benefits**: Easy setup, version control, cleanup
**Trade-offs**: Resource overhead, Windows compatibility issues
**Status**: ✅ Implemented

### 12.2 Data Model Decisions

#### DD-001: OEVK/TEVK Independence
**Decision**: OEVK and TEVK are parallel systems, not hierarchical
**Rationale**: Reflects actual government structure
**Impact**: Breaking change - all TEVK IDs changed
**Status**: ✅ Implemented (v009)

#### DD-002: SettlementCode Uniqueness
**Decision**: SettlementCode unique only within County
**Rationale**: Multiple settlements can have same code in different counties
**Impact**: All JOINs must include County_ID
**Status**: ✅ Implemented

#### DD-003: NULL House Numbers
**Decision**: Allow NULL house numbers for infrastructure addresses
**Rationale**: 7,551 valid addresses have no house number
**Impact**: 0.23% of addresses preserved
**Status**: ✅ Implemented

#### DD-004: PostgreSQL Naming Convention
**Decision**: snake_case WITHOUT table name prefixes (except FKs)
**Rationale**: Cleaner SQL, less verbose, follows PostgreSQL conventions
**Impact**: Breaking change - all column names changed
**Status**: ✅ Implemented (v014)

#### DD-005: UUID5 for PostgreSQL
**Decision**: Convert MD5 hex to UUID5 for PostgreSQL
**Rationale**: PostgreSQL UUID type is more efficient than TEXT
**Impact**: All PostgreSQL IDs are UUID format
**Status**: ✅ Implemented

### 12.3 Performance Decisions

#### PD-001: Single-Query Export
**Decision**: Export with single query instead of batched queries
**Rationale**: 12-20x faster (60+ min → 3-5 min)
**Impact**: Requires more memory but acceptable (<100MB)
**Status**: ✅ Implemented

#### PD-002: CSV COPY Import
**Decision**: Use PostgreSQL COPY instead of INSERT statements
**Rationale**: 10-50x faster (30-120 min → 2-5 min)
**Impact**: Requires CSV files, more complex workflow
**Status**: ✅ Implemented

#### PD-003: Cache-Only Default
**Decision**: Geocoding disabled by default, cache-only mode
**Rationale**: 75-95% faster pipeline (90 min → <1 min for geocoding)
**Impact**: Explicit opt-in required for full geocoding
**Status**: ✅ Implemented

#### PD-004: Multi-threaded Geocoding
**Decision**: 32 parallel workers for geocoding
**Rationale**: 3.3x faster than sequential (490 vs 149 addresses/sec)
**Impact**: Higher CPU usage but acceptable
**Status**: ✅ Implemented

#### PD-005: Polars-Based Transform
**Decision**: Use Polars instead of SQL for transformation
**Rationale**: 5-8x faster (15-20 min → 2-3 min)
**Impact**: More complex code but significant performance gain
**Status**: ✅ Implemented (default mode)

---

## 13. Known Issues & Constraints

### 13.1 Known Issues

#### Issue-001: PostgreSQL Import Slow on ARM Macs
**Description**: PostgreSQL import 2-5x slower on M1/M2/M3 Macs
**Root Cause**: Rosetta 2 translation overhead for x86 Docker images
**Workaround**: Use native Homebrew PostgreSQL for ARM
**Impact**: 60-120 min instead of 25-35 min
**Priority**: MEDIUM
**Status**: Documented

#### Issue-002: Nominatim Slow Startup
**Description**: Nominatim takes 15-30 minutes to import Hungary OSM data
**Root Cause**: Large dataset (286MB), complex indexing
**Workaround**: Setup once, reuse container
**Impact**: One-time cost, not per-run
**Priority**: LOW
**Status**: Expected behavior

#### Issue-003: Cache Key Mismatches After Normalization
**Description**: Cache keys change when address normalization changes
**Root Cause**: Cache keys based on normalized address
**Workaround**: Run cache migration script
**Impact**: Lost cache entries require re-geocoding
**Priority**: LOW
**Status**: Documented, migration script provided

### 13.2 Constraints

#### Constraint-001: SettlementCode Not Globally Unique
**Description**: SettlementCode unique only within County
**Impact**: All JOINs must include County_ID
**Mitigation**: Documented in specification, enforced in code
**Priority**: CRITICAL

#### Constraint-002: Geocoding Rate Limited
**Description**: Nominatim API has rate limits (1 req/sec for public API)
**Impact**: Slow geocoding without cache
**Mitigation**: Use local Nominatim instance (no rate limit)
**Priority**: MEDIUM

#### Constraint-003: Single-Writer Database
**Description**: DuckDB and SQLite are single-writer
**Impact**: No concurrent pipeline runs
**Mitigation**: Use staging tables, batch processing
**Priority**: LOW

#### Constraint-004: Windows Symlink Limitations
**Description**: Windows requires admin rights for symlinks
**Impact**: Must use --use-copies on Windows
**Mitigation**: Auto-detection implemented
**Priority**: LOW

---

## 14. Testing Requirements

### 14.1 Test Coverage

| Test Type | Modules | Purpose | Status |
|-----------|---------|---------|--------|
| **Unit Tests** | 11 | Isolated component testing | ✅ |
| **Contract Tests** | 13 | API contract validation | ✅ |
| **Integration Tests** | 21 | End-to-end workflows | ✅ |
| **Performance Tests** | 6 | NFR-002 compliance | ✅ |
| **Total** | **70+** | Comprehensive coverage | ✅ |

### 14.2 Critical Test Cases

#### TC-001: Deduplication Accuracy
**Purpose**: Verify correct address merging
**Input**: Addresses with different representations
**Expected**: Single canonical address, all variants mapped
**Status**: ✅ Passing

#### TC-002: Referential Integrity
**Purpose**: Verify no orphaned records
**Input**: Complete pipeline run
**Expected**: 100% FK integrity
**Status**: ✅ Passing

#### TC-003: Performance NFR-002
**Purpose**: Verify pipeline completes in <30 minutes
**Input**: 3.3M addresses
**Expected**: ≤30 minutes
**Status**: ✅ Passing (2.5 min)

#### TC-004: Geocoding Cache Hit Rate
**Purpose**: Verify cache effectiveness
**Input**: Pipeline run with existing cache
**Expected**: >80% hit rate
**Status**: ✅ Passing (88.5%)

#### TC-005: UUID5 Conversion
**Purpose**: Verify deterministic UUID generation
**Input**: Same MD5 hex IDs
**Expected**: Same UUID5 output
**Status**: ✅ Passing

#### TC-006: NULL House Number Handling
**Purpose**: Verify infrastructure addresses preserved
**Input**: Addresses with house_number = "000000"
**Expected**: 7,551 addresses kept
**Status**: ✅ Passing

### 14.3 Test Environments

| Environment | Purpose | Status |
|-------------|---------|--------|
| **Local Dev** | Development and debugging | ✅ Active |
| **CI/CD** | Automated testing | ✅ Configured |
| **Staging** | Pre-production testing | ✅ Available |
| **Production** | Live data processing | ✅ Deployed |

---

## 15. Deployment

### 15.1 System Requirements

**Minimum**:
- CPU: 4 cores
- RAM: 8 GB
- Disk: 10 GB free
- OS: macOS, Linux, Windows 10+

**Recommended**:
- CPU: 8+ cores
- RAM: 16 GB
- Disk: 50 GB free (for Nominatim)
- SSD storage

### 15.2 Dependencies

**Python**:
```
python>=3.11
duckdb>=0.9.0
polars>=0.19.0
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
psycopg2-binary>=2.9.0
tqdm>=4.66.0
click>=8.1.0
PyGithub>=2.1.0
pytest>=7.4.0
```

**Docker Images**:
```
postgis/postgis:15-3.3
mediagis/nominatim:4.2
```

### 15.3 Installation

```bash
# Clone repository
git clone <repository-url>
cd oevk-data

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env as needed

# Setup geocoding (optional)
python src/cli.py geocode setup

# Run pipeline
python src/cli.py run --run-tag $(date +%Y%m%d)
```

### 15.4 Deployment Checklist

- [ ] Python 3.11+ installed
- [ ] Docker Desktop running (if using geocoding)
- [ ] .env file configured
- [ ] Nominatim setup complete (if geocoding enabled)
- [ ] Test run successful
- [ ] Export directory accessible
- [ ] GitHub token configured (if using releases)
- [ ] PostgreSQL accessible (if using)
- [ ] Disk space sufficient (50GB+)
- [ ] Monitoring configured

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **OEVK** | Országos Egyéni Választókerület - National Individual Electoral District |
| **TEVK** | Települési Egyéni Választókerület - Settlement Individual Electoral District |
| **Canonical Address** | Deduplicated address representation |
| **NFR-002** | Non-Functional Requirement 002 - Performance target ≤30 minutes |
| **PostGIS** | PostgreSQL extension for geographic objects |
| **UUID5** | Universally Unique Identifier version 5 (namespace-based) |
| **Nominatim** | Open-source geocoding service based on OpenStreetMap |
| **WKT** | Well-Known Text - Text format for geometric objects |

---

## Appendix B: References

- **README.md**: Project overview and quick start guide
- **POSTGRESQL_FINAL_SCHEMA.md**: Complete schema reference
- **014_POSTGRESQL_NAME_CONVENTION.md**: Naming convention specification
- **011_RESOLVE_ADDRESS_COORDINATE.md**: Geocoding specification
- **009_OEVK_TEVK_FIX.md**: OEVK/TEVK relationship fix
- **CHANGES_NULL_HOUSE_NUMBERS.md**: NULL house number handling
- **GEOCODING_CACHE_ONLY_DEFAULT.md**: Cache-only default behavior
- **EXPORT_OPTIMIZATION.md**: Export performance improvements
- **POLYGON_CLOSING_FIX.md**: PostGIS polygon auto-close

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-05 | Project Team | Initial comprehensive specification |

---

**END OF SPECIFICATION**
