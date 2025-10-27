#!/usr/bin/env python3
"""Migrate file-based geocoding cache to SQLite database."""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

def migrate_cache():
    """Migrate JSON cache files to SQLite database."""
    cache_dir = Path("data/geocoding_cache")
    cache_db = Path("data/geocoding_cache.db")
    
    if not cache_dir.exists():
        print("No cache directory found.")
        return
    
    # Initialize database
    conn = sqlite3.connect(str(cache_db))
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS geocoding_cache (
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
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_quality 
        ON geocoding_cache(quality)
    """)
    
    # Migrate files
    cache_files = list(cache_dir.glob("*.json"))
    total = len(cache_files)
    print(f"Found {total} cache files to migrate...")
    
    migrated = 0
    errors = 0
    
    for i, cache_file in enumerate(cache_files, 1):
        try:
            cache_key = cache_file.stem
            
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Only migrate non-failed results
            if data.get("quality") != "failed":
                cursor.execute("""
                    INSERT OR REPLACE INTO geocoding_cache 
                    (cache_key, canonical_address_id, latitude, longitude, quality,
                     source, osm_type, osm_id, matched_address, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_key,
                    data["canonical_address_id"],
                    data.get("latitude"),
                    data.get("longitude"),
                    data["quality"],
                    data.get("source", "nominatim_local"),
                    data.get("osm_type"),
                    data.get("osm_id"),
                    data.get("matched_address"),
                    datetime.now().isoformat()
                ))
                migrated += 1
            
            if i % 1000 == 0:
                conn.commit()
                print(f"Progress: {i}/{total} ({100*i/total:.1f}%)")
        
        except Exception as e:
            errors += 1
            print(f"Error migrating {cache_file}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\nMigration complete:")
    print(f"  Migrated: {migrated}")
    print(f"  Errors: {errors}")
    print(f"  Database: {cache_db}")

if __name__ == "__main__":
    migrate_cache()
