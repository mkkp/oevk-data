Problem Description

### Issue
**Only `NationalIndividualElectoralDistrict` (OEVK)** should have polygon data, but it's currently missing those columns. The `SettlementIndividualElectoralDistrict` (TEVK) table has `Center` and `Polygon` columns defined in the schema, but these should **NOT be there** since the data doesn't exist.

### Current State

**Source Data Available**:

1. **`oevk.json`** - Contains OEVK polygon data:
   ```json
   {
     "maz": "01",      // County code
     "evk": "01",      // OEVK code
     "centrum": "47.490980 19.045150",
     "poligon": "47.5146939015652 19.0436777064605,..."
   }
   ```

2. **Korzet CSV** - Does **NOT** contain polygon data:
   ```
   "Vármegye kód";"Vármegye";"OEVK";"Település kód";"Település";"TEVK";"Szavazókör";"Szavazókör cím";"PIR";"Közterület név";"Közterület jelleg";"Házszám";"Épület";"Lépcsőház";"Kapukód";
   ```
   - No polygon/centrum columns
   - Only has address-level data

**Database Schema Issues**:

1. **`NationalIndividualElectoralDistrict`** (lines 22-29) - **MISSING polygon columns**:
   ```sql
   CREATE TABLE IF NOT EXISTS NationalIndividualElectoralDistrict (
       ID TEXT PRIMARY KEY,
       OEVK TEXT NOT NULL,
       Name TEXT NOT NULL,
       County_ID TEXT NOT NULL,
       -- MISSING: Center TEXT,
       -- MISSING: Polygon TEXT,
       ...
   );
   ```

2. **`SettlementIndividualElectoralDistrict`** (lines 32-45) - **INCORRECTLY has polygon columns**:
   ```sql
   CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
       ID TEXT PRIMARY KEY,
       TEVK TEXT,
       Name TEXT NOT NULL,
       Center TEXT,   -- ❌ SHOULD BE REMOVED - no data source
       Polygon TEXT,  -- ❌ SHOULD BE REMOVED - no data source
       ...
   );
   ```

### Transformation Code Issues

**OEVK transformation** (`src/etl/transform_optimized.py:274-302`):
- Does NOT load `oevk.json` data
- Does NOT include Center/Polygon columns
- Ignores geospatial data completely

**TEVK transformation** - Would try to populate Center/Polygon but has no data source (CSV doesn't have these fields)

---

## Corrected Solution Description

### What Needs to Be Fixed

**1. Add Polygon Columns to NationalIndividualElectoralDistrict**

**`src/database/schema.sql` (lines 22-29)**:
```sql
CREATE TABLE IF NOT EXISTS NationalIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY,
    OEVK TEXT NOT NULL,
    Name TEXT NOT NULL,
    Center TEXT,   -- ADD: Center point for OEVK boundary
    Polygon TEXT,  -- ADD: Polygon for OEVK boundary
    County_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    UNIQUE (County_ID, OEVK)
);
```

**2. Remove Polygon Columns from SettlementIndividualElectoralDistrict**

**`src/database/schema.sql` (lines 32-45)**:
```sql
CREATE TABLE IF NOT EXISTS SettlementIndividualElectoralDistrict (
    ID TEXT PRIMARY KEY,
    TEVK TEXT,
    Name TEXT NOT NULL,
    -- REMOVE: Center TEXT,   -- No data source available
    -- REMOVE: Polygon TEXT,  -- No data source available
    County_ID TEXT NOT NULL,
    Settlement_ID TEXT NOT NULL,
    NationalIndividualElectoralDistrict_ID TEXT NOT NULL,
    FOREIGN KEY (County_ID) REFERENCES County(ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (NationalIndividualElectoralDistrict_ID) REFERENCES NationalIndividualElectoralDistrict(ID),
    UNIQUE (County_ID, Settlement_ID, TEVK, NationalIndividualElectoralDistrict_ID)
);
```

**3. Create OEVK JSON Staging Table**

Add to `src/database/schema.sql`:
```sql
-- Staging table for OEVK geospatial data from JSON
CREATE TABLE IF NOT EXISTS staging_oevk_json (
    maz TEXT NOT NULL,      -- County code (Vármegye azonosító)
    evk TEXT NOT NULL,      -- OEVK code
    centrum TEXT,           -- Center coordinates
    poligon TEXT,           -- Polygon coordinates
    run_tag TEXT,
    PRIMARY KEY (maz, evk)
);
```

**4. Load OEVK JSON Data**

Add function to `src/etl/ingest.py`:
```python
def load_oevk_json(
    conn: duckdb.DuckDBPyConnection,
    json_path: str,
    run_tag: str
) -> None:
    """Load OEVK geospatial data from JSON file."""
    import json

    logger.info(f"Loading OEVK JSON from {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        oevk_data = json.load(f)

    conn.executemany(
        """
        INSERT INTO staging_oevk_json (maz, evk, centrum, poligon, run_tag)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (maz, evk) DO UPDATE SET
            centrum = EXCLUDED.centrum,
            poligon = EXCLUDED.poligon,
            run_tag = EXCLUDED.run_tag
        """,
        [(item['maz'], item['evk'], item.get('centrum'),
          item.get('poligon'), run_tag) for item in oevk_data]
    )

    count = len(oevk_data)
    logger.info(f"Loaded {count} OEVK polygon records")
```

Call it in the ingestion stage:
```python
# In load_staging_data() after loading CSV
load_oevk_json(conn, os.path.join(staging_dir, "oevk.json"), run_tag)
```

**5. Update OEVK Transformation**

**`src/etl/transform_optimized.py` (lines 274-302)**:
```python
def transform_national_individual_electoral_districts(
    db_connection: duckdb.DuckDBPyConnection, run_tag: str
) -> None:
    """Transforms staging data into NationalIndividualElectoralDistrict table."""
    logger.info("Transforming NationalIndividualElectoralDistrict data")

    db_connection.execute(
        """
        INSERT INTO NationalIndividualElectoralDistrict
            (ID, OEVK, Name, Center, Polygon, County_ID)
        SELECT
            lower(substring(md5(sk.county_code || '|' || sk.oevk_code), 1, 16)) as ID,
            sk.oevk_code,
            c.CountyName || ' ' || sk.oevk_code as Name,
            oevk.centrum as Center,    -- From oevk.json
            oevk.poligon as Polygon,   -- From oevk.json
            c.ID as County_ID
        FROM staging_korzet sk
        JOIN County c ON sk.county_code = c.CountyCode
        LEFT JOIN staging_oevk_json oevk
            ON sk.county_code = oevk.maz
            AND sk.oevk_code = oevk.evk
            AND oevk.run_tag = ?
        WHERE sk.run_tag = ?
        GROUP BY sk.county_code, sk.oevk_code, c.ID, c.CountyName,
                 oevk.centrum, oevk.poligon
        ON CONFLICT (County_ID, OEVK) DO NOTHING
    """,
        [run_tag, run_tag],
    )

    row_count = db_connection.execute(
        "SELECT COUNT(*) FROM NationalIndividualElectoralDistrict"
    ).fetchone()[0]

    # Log how many have polygon data
    polygon_count = db_connection.execute(
        "SELECT COUNT(*) FROM NationalIndividualElectoralDistrict WHERE Polygon IS NOT NULL"
    ).fetchone()[0]

    logger.info(f"Transformed {row_count} OEVK districts ({polygon_count} with polygon data)")
```

**6. Update PostgreSQL Export Schema**

**`exports/schema.sql` and `src/etl/export.py`**:
- Add `Center TEXT, Polygon TEXT` to `NationalIndividualElectoralDistrict` table
- Remove `Center TEXT, Polygon TEXT` from `SettlementIndividualElectoralDistrict` table

### Summary

**What's Wrong**:
- OEVK polygons exist in `oevk.json` but are not imported ❌
- TEVK has polygon columns but no data source ❌

**What Should Happen**:
- OEVK table gets Center + Polygon from `oevk.json` ✅
- TEVK table does NOT have Center/Polygon columns ✅

**Data Sources**:
- **OEVK polygons**: `oevk.json` (centrum, poligon fields)
- **TEVK polygons**: None available
- **Address data**: Korzet CSV (no polygon data)
