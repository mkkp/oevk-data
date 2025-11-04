#!/usr/bin/env python3
"""
Fast cache migration using DuckDB for processing.

Strategy:
1. Import cache into DuckDB
2. Join with current addresses to recalculate cache keys
3. Export back to SQLite
"""

import sqlite3
import duckdb
import time

print("=== FAST GEOCODING CACHE MIGRATION ===\n")

start_time = time.time()

# Paths
cache_db_path = "data/geocoding_cache/geocoding_cache.db"
duck_db_path = "data/oevk.db"

print("Opening DuckDB connection...")
duck_conn = duckdb.connect(duck_db_path)

try:
    # Step 1: Attach SQLite cache database
    print("Attaching cache database...")
    duck_conn.execute(f"""
        ATTACH DATABASE '{cache_db_path}' AS cache_db (TYPE SQLITE)
    """)

    # Get initial stats
    print("\n=== BEFORE MIGRATION ===")
    result = duck_conn.execute(
        "SELECT COUNT(*) FROM cache_db.geocoding_cache"
    ).fetchone()
    print(f"Total cache entries: {result[0]:,}")

    # Step 2: Create migrated cache in DuckDB (fast!)
    print("\nMigrating cache entries (recalculating cache keys)...")

    duck_conn.execute("""
        CREATE OR REPLACE TEMP TABLE migrated_cache AS
        SELECT
            MD5(ca.SettlementName || '|' || ca.StreetName || '|' || ca.HouseNumber) as cache_key,
            gc.canonical_address_id,
            gc.latitude,
            gc.longitude,
            gc.quality,
            gc.source,
            gc.osm_type,
            gc.osm_id,
            gc.matched_address,
            gc.created_at,
            -- Add metadata for analysis
            ca.SettlementName as settlement,
            ca.StreetName as street,
            ca.HouseNumber as house
        FROM cache_db.geocoding_cache gc
        INNER JOIN CanonicalAddress ca ON gc.canonical_address_id = ca.ID
    """)

    # Get migration stats
    result = duck_conn.execute("SELECT COUNT(*) FROM migrated_cache").fetchone()
    matched_count = result[0]
    print(f"Successfully matched addresses: {matched_count:,}")

    # Step 3: Handle duplicates (keep best quality)
    print("\nResolving duplicates (keeping best quality per cache key)...")

    duck_conn.execute("""
        CREATE OR REPLACE TEMP TABLE migrated_cache_dedup AS
        SELECT DISTINCT ON (cache_key)
            cache_key,
            canonical_address_id,
            latitude,
            longitude,
            quality,
            source,
            osm_type,
            osm_id,
            matched_address,
            created_at
        FROM migrated_cache
        ORDER BY
            cache_key,
            CASE quality
                WHEN 'exact' THEN 0
                WHEN 'street' THEN 1
                WHEN 'settlement' THEN 2
                WHEN 'failed' THEN 3
                ELSE 4
            END
    """)

    result = duck_conn.execute("SELECT COUNT(*) FROM migrated_cache_dedup").fetchone()
    final_count = result[0]
    print(f"After deduplication: {final_count:,} entries")
    print(f"Removed duplicates: {matched_count - final_count:,}")

    # Step 4: Replace old cache with new cache
    print("\nReplacing old cache table...")

    # Drop old table and create new one
    duck_conn.execute("DROP TABLE cache_db.geocoding_cache")

    duck_conn.execute("""
        CREATE TABLE cache_db.geocoding_cache (
            cache_key TEXT PRIMARY KEY,
            canonical_address_id TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            quality TEXT NOT NULL,
            source TEXT NOT NULL,
            osm_type TEXT,
            osm_id INTEGER,
            matched_address TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Insert migrated data
    print("Writing migrated data to cache...")
    duck_conn.execute("""
        INSERT INTO cache_db.geocoding_cache
        SELECT
            cache_key,
            canonical_address_id,
            latitude,
            longitude,
            quality,
            source,
            osm_type,
            osm_id,
            matched_address,
            created_at
        FROM migrated_cache_dedup
    """)

    # Create index using SQLite connection directly
    print("Creating index...")
    import sqlite3

    cache_conn = sqlite3.connect(cache_db_path)
    cache_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quality ON geocoding_cache(quality)"
    )
    cache_conn.commit()
    cache_conn.close()

    # Get final stats
    print("\n=== AFTER MIGRATION ===")
    result = duck_conn.execute(
        "SELECT COUNT(*) FROM cache_db.geocoding_cache"
    ).fetchone()
    print(f"Total cache entries: {result[0]:,}")

    result = duck_conn.execute(
        "SELECT COUNT(*) FROM cache_db.geocoding_cache WHERE quality != 'failed'"
    ).fetchone()
    print(f"Successful geocodes: {result[0]:,}")

    # Detach
    duck_conn.execute("DETACH DATABASE cache_db")

    elapsed = time.time() - start_time
    print(f"\n✓ Migration complete in {elapsed:.1f} seconds!")

except Exception as e:
    print(f"\n✗ Error during migration: {e}")
    import traceback

    traceback.print_exc()

finally:
    duck_conn.close()

print(
    "\nNow you can re-run geocoding with --update-from-cache to apply the migrated cache."
)
