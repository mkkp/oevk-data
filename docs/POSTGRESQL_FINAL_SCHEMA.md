<!--
DOCUMENT METADATA
=================
Title: PostgreSQL Final Schema Structure
Type: Reference
Category: Schema
Status: Active
Version: 1.1
Created: 2025-10-28
Last Updated: 2025-10-29
Author: System

Related Documents:
- PostgreSQL Naming Convention (014_POSTGRESQL_NAME_CONVENTION.md)
- README.md (Database Schema section)

Related Code:
- src/etl/export.py (lines 580-650: schema generation)
- src/database/postgresql_import.sql (import script)

Dependencies:
- PostgreSQL 15+
- PostGIS 3.3+
- pg_trgm extension

Keywords: postgresql, schema, database, postgis, final-structure, reference, v014, snake_case

Summary:
Complete reference documentation for the final PostgreSQL database schema after all import steps (schema creation, CSV import, PostGIS geometry population, FK constraints). Describes 14 tables with 3.3M+ addresses, including table structures, indexes, relationships, and query examples. Represents production-ready database state with snake_case naming convention (v014).

Audience:
Database administrators, backend developers, data analysts working with the production PostgreSQL database.
-->

# PostgreSQL Final Schema Structure

**Document Purpose**: This document describes the **final** PostgreSQL database schema **after** all import steps are complete, including:
1. Initial schema creation (schema.sql)
2. CSV data import (import_postgresql.sql)
3. PostGIS geometry population from lat/lon coordinates
4. Foreign key constraint re-creation

This represents the actual production-ready database structure.

---

## Complete Table Listing

The database contains **14 tables** after import:

1. `county` - Counties (20 rows)
2. `settlement` - Settlements (3,177 rows)
3. `oevk` - National Electoral Districts (106 rows)
4. `tevk` - Settlement Electoral Districts (2,444 rows)
5. `postal_code` - Postal codes (~3,200 rows)
6. `postal_code_settlement` - Postal code to settlement mapping
7. `polling_station` - Polling stations (8,547 rows)
8. `public_space_name` - Street names (25,117 unique names)
9. `public_space_type` - Street types (148 types)
10. `settlement_public_spaces` - Settlement public space combinations
11. `address` - **Canonical addresses (3.3M+ rows)** - Main table
12. `address_mapping` - Deduplication tracking (optional export)
13. `address_polling_stations` - Address-to-polling station relationships (optional export)
14. `address_pir_codes` - Address-to-PIR code relationships (optional export)

---

## Detailed Table Structures

### 1. County Table

```sql
CREATE TABLE county (
    id UUID PRIMARY KEY,                -- uuid5(md5(code))
    code TEXT UNIQUE NOT NULL,          -- County code (e.g., "01")
    name TEXT NOT NULL                  -- County name (e.g., "Budapest")
);

CREATE INDEX idx_county_code ON county(code);
```

**Column Details:**
- `code`: 2-digit county code
- `name`: Full county name in Hungarian

**Important**: Columns are NOT prefixed with table name (`code`, not `county_code`)

---

### 2. Settlement Table

```sql
CREATE TABLE settlement (
    id UUID PRIMARY KEY,                -- uuid5(md5(county_code|code))
    code TEXT NOT NULL,                 -- Settlement code within county
    name TEXT NOT NULL,                 -- Settlement name
    county_id UUID NOT NULL,
    FOREIGN KEY (county_id) REFERENCES county(id),
    UNIQUE (county_id, code)
);

CREATE INDEX idx_settlement_county_id ON settlement(county_id);
CREATE INDEX idx_settlement_county_id_code ON settlement(county_id, code);
```

**Column Details:**
- `code`: Settlement code (unique within county, not globally)
- `name`: Full settlement name in Hungarian
- `county_id`: Parent county reference

**Important**: Columns are NOT prefixed (`code`, `name`, not `settlement_code`, `settlement_name`)

---

### 3. OEVK Table (National Electoral Districts)

```sql
CREATE TABLE oevk (
    id UUID PRIMARY KEY,                -- uuid5(md5(county_code|code))
    code TEXT NOT NULL,                 -- District code (e.g., "01")
    name TEXT NOT NULL,                 -- District name
    center GEOMETRY(POINT, 4326),       -- Center point (PostGIS)
    polygon GEOMETRY(POLYGON, 4326),    -- Boundary polygon (PostGIS)
    county_id UUID NOT NULL,
    FOREIGN KEY (county_id) REFERENCES county(id),
    UNIQUE (county_id, code)
);

CREATE INDEX idx_oevk_county_id ON oevk(county_id);
CREATE INDEX idx_oevk_center_gist ON oevk USING GIST(center);
CREATE INDEX idx_oevk_polygon_gist ON oevk USING GIST(polygon);
```

**Column Details:**
- `code`: National electoral district code (abbreviated from original `oevk` column name)
- `name`: Full district name
- `center`: Geographic center as PostGIS POINT
- `polygon`: Boundary as PostGIS POLYGON
- `county_id`: Parent county reference

**Geometry Population:**
- `center` and `polygon` are populated during import from WKT (Well-Known Text) format
- Invalid geometries are skipped with warning
- Spatial indexes (GIST) enable efficient spatial queries

**Important**: Table name is `oevk` (not `national_individual_electoral_district`), column is `code` (not `oevk_code`)

---

### 4. TEVK Table (Settlement Electoral Districts)

```sql
CREATE TABLE tevk (
    id UUID PRIMARY KEY,                -- uuid5(md5(county_code|settlement_code|code))
    code TEXT,                          -- District code (can be NULL for some settlements)
    name TEXT NOT NULL,                 -- District name
    county_id UUID NOT NULL,
    settlement_id UUID NOT NULL,
    FOREIGN KEY (county_id) REFERENCES county(id),
    FOREIGN KEY (settlement_id) REFERENCES settlement(id),
    UNIQUE (county_id, settlement_id, code)
);

CREATE INDEX idx_tevk_county_id ON tevk(county_id);
CREATE INDEX idx_tevk_settlement_id ON tevk(settlement_id);
```

**Column Details:**
- `code`: Settlement electoral district code (can be NULL for settlements without districts)
- `name`: Full district name
- `county_id`: Parent county reference
- `settlement_id`: Parent settlement reference

**Relationship**: TEVK and OEVK are **independent parallel systems**, not hierarchical

**Important**: Table name is `tevk` (not `settlement_individual_electoral_district`), column is `code` (not `tevk_code`)

---

### 5. Postal Code Table

```sql
CREATE TABLE postal_code (
    id UUID PRIMARY KEY,                -- uuid5(md5(code))
    code TEXT UNIQUE NOT NULL           -- Postal code (e.g., "1011")
);
```

**Column Details:**
- `code`: 4-digit postal code

**Important**: Column is `code` (not `postal_code`)

---

### 6. Postal Code Settlement Junction Table

```sql
CREATE TABLE postal_code_settlement (
    id UUID PRIMARY KEY,                -- uuid5(md5(postal_code_id|settlement_id))
    postal_code_id UUID NOT NULL,
    settlement_id UUID NOT NULL,
    FOREIGN KEY (postal_code_id) REFERENCES postal_code(id),
    FOREIGN KEY (settlement_id) REFERENCES settlement(id),
    UNIQUE (postal_code_id, settlement_id)
);

CREATE INDEX idx_postal_code_settlement_postal_code_id ON postal_code_settlement(postal_code_id);
CREATE INDEX idx_postal_code_settlement_settlement_id ON postal_code_settlement(settlement_id);
```

**Purpose**: Many-to-many relationship (postal codes can span multiple settlements)

---

### 7. Polling Station Table

```sql
CREATE TABLE polling_station (
    id UUID PRIMARY KEY,                -- uuid5(md5(...))
    address TEXT NOT NULL,              -- Polling station address
    latitude REAL,                      -- Geocoded latitude
    longitude REAL,                     -- Geocoded longitude
    geometry GEOGRAPHY(POINT, 4326),    -- PostGIS GEOGRAPHY for spatial queries
    geocoding_quality TEXT,             -- Quality: 'high', 'medium', 'low', 'failed'
    geocoding_source TEXT,              -- Source: 'exact', 'fuzzy', 'canonical', 'settlement'
    matched_address TEXT,               -- Matched canonical address (if applicable)
    tevk_id UUID NOT NULL,
    county_id UUID NOT NULL,
    settlement_id UUID NOT NULL,
    oevk_id UUID NOT NULL,
    FOREIGN KEY (tevk_id) REFERENCES tevk(id),
    FOREIGN KEY (county_id) REFERENCES county(id),
    FOREIGN KEY (settlement_id) REFERENCES settlement(id),
    FOREIGN KEY (oevk_id) REFERENCES oevk(id),
    UNIQUE (county_id, settlement_id, oevk_id, tevk_id, address)
);

CREATE INDEX idx_polling_station_coordinates ON polling_station(latitude, longitude);
CREATE INDEX idx_polling_station_quality ON polling_station(geocoding_quality);
CREATE INDEX idx_polling_station_geometry ON polling_station USING GIST(geometry);
CREATE INDEX idx_polling_station_county_id ON polling_station(county_id);
CREATE INDEX idx_polling_station_settlement_id ON polling_station(settlement_id);
```

**Column Details:**
- `address`: Polling station address (NOT prefixed - not `polling_station_address`)
- `geometry`: Populated during import from `latitude`/`longitude` using `ST_MakePoint`
- All geocoding metadata columns present

**Geometry Population:**
```sql
UPDATE polling_station
SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
```

**Important**: Column is `address` (not `polling_station_address`)

---

### 8. Public Space Name Table

```sql
CREATE TABLE public_space_name (
    id UUID PRIMARY KEY,                -- uuid5(md5(name))
    name TEXT UNIQUE NOT NULL           -- Street name (e.g., "Kossuth Lajos")
);
```

**Column Details:**
- `name`: Street/public space name without type (NOT prefixed - not `public_space_name`)

**Important**: Column is `name` (not `public_space_name`)

---

### 9. Public Space Type Table

```sql
CREATE TABLE public_space_type (
    id UUID PRIMARY KEY,                -- uuid5(md5(name))
    name TEXT UNIQUE NOT NULL           -- Street type (e.g., "utca", "út", "tér")
);
```

**Column Details:**
- `name`: Street type in Hungarian (NOT prefixed - not `public_space_type`)

**Important**: Column is `name` (not `public_space_type`)

---

### 10. Settlement Public Spaces Junction Table

```sql
CREATE TABLE settlement_public_spaces (
    id UUID PRIMARY KEY,                -- uuid5(md5(settlement_id|public_space_name_id|public_space_type_id))
    settlement_id UUID NOT NULL,
    public_space_name_id UUID NOT NULL,
    public_space_type_id UUID NOT NULL,
    FOREIGN KEY (settlement_id) REFERENCES settlement(id),
    FOREIGN KEY (public_space_name_id) REFERENCES public_space_name(id),
    FOREIGN KEY (public_space_type_id) REFERENCES public_space_type(id),
    UNIQUE (settlement_id, public_space_name_id, public_space_type_id)
);

CREATE INDEX idx_settlement_public_spaces_settlement_id ON settlement_public_spaces(settlement_id);
CREATE INDEX idx_settlement_public_spaces_public_space_name_id ON settlement_public_spaces(public_space_name_id);
CREATE INDEX idx_settlement_public_spaces_public_space_type_id ON settlement_public_spaces(public_space_type_id);
```

**Purpose**: Tracks which public space combinations exist in each settlement

---

### 11. Address Table (MAIN TABLE - Canonical Addresses)

```sql
CREATE TABLE address (
    id UUID PRIMARY KEY,                -- uuid5(md5(...))
    
    -- Address components
    house_number TEXT,                  -- House number (e.g., "42"); can be NULL for infrastructure/area addresses
    building TEXT,                      -- Building (e.g., "A")
    staircase TEXT,                     -- Staircase/entrance (e.g., "2")
    full_address TEXT NOT NULL,         -- Complete formatted address
    
    -- Geocoding data (populated, not NULL for most addresses)
    latitude REAL,                      -- Geocoded latitude (WGS 84)
    longitude REAL,                     -- Geocoded longitude (WGS 84)
    geometry GEOGRAPHY(POINT, 4326),    -- PostGIS GEOGRAPHY for spatial queries
    geocoding_quality TEXT,             -- Quality: 'high', 'medium', 'low', 'failed'
    geocoding_source TEXT,              -- Source: 'nominatim', 'cache'
    
    -- Foreign keys (ALL NOT NULL - enforced data quality)
    county_id UUID NOT NULL,
    settlement_id UUID NOT NULL,
    public_space_name_id UUID NOT NULL,
    public_space_type_id UUID NOT NULL,
    oevk_id UUID NOT NULL,
    tevk_id UUID NOT NULL,
    postal_code_id UUID NOT NULL,
    polling_station_id UUID NOT NULL,
    
    FOREIGN KEY (county_id) REFERENCES county(id),
    FOREIGN KEY (settlement_id) REFERENCES settlement(id),
    FOREIGN KEY (public_space_name_id) REFERENCES public_space_name(id),
    FOREIGN KEY (public_space_type_id) REFERENCES public_space_type(id),
    FOREIGN KEY (oevk_id) REFERENCES oevk(id),
    FOREIGN KEY (tevk_id) REFERENCES tevk(id),
    FOREIGN KEY (postal_code_id) REFERENCES postal_code(id),
    FOREIGN KEY (polling_station_id) REFERENCES polling_station(id),
    
    UNIQUE (full_address, settlement_id)
);

-- Performance indexes
CREATE INDEX idx_address_coordinates ON address(latitude, longitude);
CREATE INDEX idx_address_quality ON address(geocoding_quality);
CREATE INDEX idx_address_geometry ON address USING GIST(geometry);

-- Foreign key indexes
CREATE INDEX idx_address_county_id ON address(county_id);
CREATE INDEX idx_address_settlement_id ON address(settlement_id);
CREATE INDEX idx_address_public_space_name_id ON address(public_space_name_id);
CREATE INDEX idx_address_public_space_type_id ON address(public_space_type_id);
CREATE INDEX idx_address_oevk_id ON address(oevk_id);
CREATE INDEX idx_address_tevk_id ON address(tevk_id);
CREATE INDEX idx_address_postal_code_id ON address(postal_code_id);
CREATE INDEX idx_address_polling_station_id ON address(polling_station_id);

-- Full-text search index (trigram for LIKE/ILIKE queries)
CREATE INDEX idx_address_full_address_trgm ON address USING GIN(full_address gin_trgm_ops);
```

**Column Details:**
- **Nullable `house_number`**: Can be NULL or empty for infrastructure addresses (railway stations, landmarks) or complex buildings identified by building/staircase only (~7,551 addresses, 0.23% of dataset)
  - Examples: `"Vasútállomás"` (railway station), `"Gázgyári lakótelep, 1. épület I. lépcsőház"` (building with no house number)
- **No redundant text columns**: Street name, county code, settlement name accessed via FKs
- **No timestamp columns**: `created_at`, `geocoded_at` removed (not user-facing)
- **8 NOT NULL foreign keys**: Enforces data quality, every address must have complete information
- **Geometry populated during import**: From `latitude`/`longitude` using chunked updates

**Geometry Population (Chunked for Performance):**
```sql
DO $$
DECLARE
    batch_size INT := 100000;
    total_updated BIGINT := 0;
    rows_updated INT;
BEGIN
    LOOP
        UPDATE address
        SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
        WHERE id IN (
            SELECT id FROM address 
            WHERE latitude IS NOT NULL 
              AND longitude IS NOT NULL 
              AND geometry IS NULL
            LIMIT batch_size
        );
        
        GET DIAGNOSTICS rows_updated = ROW_COUNT;
        EXIT WHEN rows_updated = 0;
        
        total_updated := total_updated + rows_updated;
        RAISE NOTICE 'Updated % addresses (total: %)', rows_updated, total_updated;
    END LOOP;
END $$;
```

**Foreign Key Constraints:**
- Dropped before data import for performance
- Re-created after data import
- All constraints use snake_case naming: `address_county_id_fkey`, `address_oevk_id_fkey`, etc.

**Data Quality:**
- Export query filters addresses lacking required FKs
- Import will fail if data violates NOT NULL constraints
- ~3.3M addresses with complete foreign key relationships

---

### 12. Address Mapping Table (Optional Export)

```sql
CREATE TABLE address_mapping (
    id UUID PRIMARY KEY,                -- uuid5(md5(original_address_id|address_id))
    original_address_id UUID NOT NULL,  -- Original (pre-deduplication) address ID
    address_id UUID NOT NULL,           -- Canonical address ID
    mapping_type TEXT DEFAULT 'deduplication',
    FOREIGN KEY (address_id) REFERENCES address(id),
    UNIQUE (original_address_id, address_id)
);
```

**Purpose**: Tracks which original addresses were merged into each canonical address

**Note**: This table is for internal tracking and may not be exported by default

---

### 13. Address Polling Stations Junction Table (Optional Export)

```sql
CREATE TABLE address_polling_stations (
    id UUID PRIMARY KEY,                -- uuid5(md5(address_id|polling_station_id))
    address_id UUID NOT NULL,
    polling_station_id UUID NOT NULL,
    FOREIGN KEY (address_id) REFERENCES address(id),
    FOREIGN KEY (polling_station_id) REFERENCES polling_station(id),
    UNIQUE (address_id, polling_station_id)
);
```

**Purpose**: Preserves multiple polling station assignments for addresses (advanced use case)

**Note**: This table is optional and may not be exported by default

---

### 14. Address PIR Codes Junction Table (Optional Export)

```sql
CREATE TABLE address_pir_codes (
    id UUID PRIMARY KEY,                -- uuid5(md5(address_id|pir_code))
    address_id UUID NOT NULL,
    pir_code TEXT NOT NULL,
    FOREIGN KEY (address_id) REFERENCES address(id),
    UNIQUE (address_id, pir_code)
);
```

**Purpose**: Preserves PIR code relationships for addresses (advanced use case)

**Note**: This table is optional and may not be exported by default

---

## Import Process Summary

### Step 1: Schema Creation
```bash
psql -d oevk_data -f schema.sql
```
- Creates all 14 tables with correct structure
- Adds `geometry` columns (GEOGRAPHY type) to `address`, `polling_station`, `oevk`
- Creates initial indexes
- **Does NOT create foreign key constraints yet** (added in Step 4)

### Step 2: Data Import (CSV COPY)
```bash
psql -d oevk_data -f import_postgresql.sql
```
- Imports CSV data using fast COPY commands
- Processes in chunks (100K rows per chunk for large tables like `address`)
- Foreign key constraints are **dropped** before import for performance
- Import order respects dependencies (county → settlement → address)

### Step 3: Geometry Population
- `address.geometry`: Populated from `latitude`/`longitude` in 100K row chunks
- `polling_station.geometry`: Populated from `latitude`/`longitude` in single batch
- `oevk.center` and `oevk.polygon`: Populated from WKT format during import
- Invalid geometries are skipped with warnings

### Step 4: Foreign Key Constraint Re-creation
- All foreign key constraints re-created after data import
- Ensures referential integrity
- Naming convention: `{table}_{column}_fkey` (e.g., `address_county_id_fkey`)

### Step 5: Extension Activation
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```
- PostGIS: Enables spatial data types and functions
- pg_trgm: Enables trigram indexes for fast text search

---

## Final Database State

**After all import steps complete, you have:**

✅ **14 tables** with complete data
✅ **3.3M+ addresses** with 8 NOT NULL foreign keys each
✅ **PostGIS geometry columns** populated for spatial queries
✅ **All foreign key constraints** enforced
✅ **Performance indexes** on all key columns
✅ **Trigram index** for fast full-text search on addresses
✅ **100% referential integrity** across all relationships

**Database size:** ~3-4 GB with indexes and geometry data

---

## Query Examples

### 1. Find addresses in a specific county and settlement

```sql
SELECT 
    a.full_address,
    c.name as county_name,
    s.name as settlement_name,
    psn.name as street_name,
    pst.name as street_type,
    a.house_number,
    pc.code as postal_code
FROM address a
JOIN county c ON a.county_id = c.id
JOIN settlement s ON a.settlement_id = s.id
JOIN public_space_name psn ON a.public_space_name_id = psn.id
JOIN public_space_type pst ON a.public_space_type_id = pst.id
JOIN postal_code pc ON a.postal_code_id = pc.id
WHERE c.code = '01' AND s.name LIKE 'Budapest%'
LIMIT 100;
```

### 2. Spatial query - Find addresses within 1km of a point

```sql
SELECT 
    a.full_address,
    ST_Distance(a.geometry, ST_MakePoint(19.0402, 47.4979)::geography) as distance_meters
FROM address a
WHERE ST_DWithin(
    a.geometry, 
    ST_MakePoint(19.0402, 47.4979)::geography,
    1000  -- 1km radius
)
ORDER BY distance_meters
LIMIT 50;
```

### 3. Find all addresses in a specific electoral district

```sql
SELECT 
    a.full_address,
    oevk.code as oevk_code,
    oevk.name as oevk_name,
    tevk.code as tevk_code,
    tevk.name as tevk_name,
    ps.address as polling_station
FROM address a
JOIN oevk ON a.oevk_id = oevk.id
JOIN tevk ON a.tevk_id = tevk.id
JOIN polling_station ps ON a.polling_station_id = ps.id
WHERE oevk.code = '01' AND tevk.code = '03';
```

### 4. Full-text search on addresses (using trigram index)

```sql
SELECT 
    a.full_address,
    s.name as settlement_name,
    psn.name || ' ' || pst.name as street
FROM address a
JOIN settlement s ON a.settlement_id = s.id
JOIN public_space_name psn ON a.public_space_name_id = psn.id
JOIN public_space_type pst ON a.public_space_type_id = pst.id
WHERE a.full_address ILIKE '%Kossuth%utca%'
LIMIT 100;
```

---

## Key Differences from Initial Schema (schema.sql)

| Aspect | Initial Schema | Final State |
|--------|---------------|-------------|
| **Foreign Keys** | Not present | All created and enforced |
| **Geometry Columns** | Empty (declared only) | Fully populated from coordinates |
| **OEVK Geometry** | Empty | Populated from WKT |
| **Data** | Empty tables | 3.3M+ addresses, all reference data |
| **Indexes** | Basic indexes only | Full index set including GIST spatial indexes |
| **Extensions** | Declared | Activated and functional |

---

## Maintenance Notes

### Geometry Updates

If addresses are geocoded after initial import:

```sql
-- Update geometry for newly geocoded addresses
UPDATE address
SET geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
WHERE latitude IS NOT NULL 
  AND longitude IS NOT NULL 
  AND geometry IS NULL;
```

### Constraint Validation

Check for referential integrity issues:

```sql
-- Check for orphaned address records (shouldn't happen with NOT NULL + FKs)
SELECT COUNT(*) FROM address a
WHERE NOT EXISTS (SELECT 1 FROM county c WHERE c.id = a.county_id);
```

### Index Maintenance

Periodically rebuild indexes for optimal performance:

```sql
REINDEX TABLE address;
VACUUM ANALYZE address;
```

---

**Document Version**: 1.1  
**Last Updated**: 2025-10-29  
**Schema Version**: v014 (PostgreSQL naming convention with no-prefix rule)

**Changelog**:
- v1.1 (2025-10-29): Updated `address.house_number` to nullable; added support for infrastructure addresses and complex buildings without house numbers
