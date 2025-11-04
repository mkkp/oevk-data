#!/usr/bin/env python3
import duckdb

duck_conn = duckdb.connect("data/oevk.db", read_only=True)
cache_db_path = "data/geocoding_cache/geocoding_cache.db"

print("=== TESTING CACHE JOIN LOGIC ===\n")

# Sample addresses to test
duck_conn.execute(f"""
    ATTACH DATABASE '{cache_db_path}' AS cache_db (TYPE SQLITE, READ_ONLY)
""")

# Test the exact query from geocoding.py
result = duck_conn.execute("""
    SELECT
        a.ID,
        c.latitude as Latitude,
        c.longitude as Longitude,
        c.quality as GeocodingQuality,
        'cache' as GeocodingSource,
        CURRENT_TIMESTAMP as GeocodedAt,
        a.SettlementName,
        a.StreetName,
        a.HouseNumber,
        c.canonical_address_id as OldCacheID
    FROM CanonicalAddress a
    INNER JOIN cache_db.geocoding_cache c ON c.cache_key = MD5(a.SettlementName || '|' || a.StreetName || '|' || a.HouseNumber)
    WHERE c.quality != 'failed'
    LIMIT 10
""").fetchall()

print(f"Found {len(result)} matches using the JOIN query")
print("\nSample matches:")
for row in result:
    print(f"\nCurrent ID: {row[0]}")
    print(f"  Address: {row[6]} | {row[7]} | {row[8]}")
    print(f"  Lat/Lon: ({row[1]}, {row[2]})")
    print(f"  Quality: {row[3]}, Source: {row[4]}")
    print(f"  Old Cache ID: {row[9]}")
    if str(row[0]) == str(row[9]):
        print(f"  ✓ IDs MATCH")
    else:
        print(f"  ⚠ IDs DIFFERENT (Current: {row[0]}, Cache: {row[9]})")

# Count total potential matches
count = duck_conn.execute("""
    SELECT COUNT(*)
    FROM CanonicalAddress a
    INNER JOIN cache_db.geocoding_cache c ON c.cache_key = MD5(a.SettlementName || '|' || a.StreetName || '|' || a.HouseNumber)
    WHERE c.quality != 'failed'
""").fetchone()[0]

print(f"\n=== TOTAL MATCHES AVAILABLE ===")
print(f"Total addresses that could be geocoded from cache: {count:,}")

duck_conn.execute("DETACH DATABASE cache_db")
duck_conn.close()
