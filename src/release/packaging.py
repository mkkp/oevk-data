"""
File packaging service.

Handles compression and packaging of release artifacts.
"""

import os
import zipfile
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.utils.pipeline_logging import PipelineLogger
from src.release.common import ReleaseUtils


class FilePackager:
    """Handles compression and packaging of release artifacts."""

    def __init__(self, output_dir: str):
        """Initialize packager with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = ReleaseUtils.create_logger("packaging")

    def package_csv_files(
        self, data_dir: str, release_tag: str, force: bool = False
    ) -> Dict[str, Any]:
        """Package CSV files into a compressed archive.

        Args:
            data_dir: Directory containing CSV files to package
            release_tag: Release tag for naming
            force: If True, recreate even if archive exists
        """
        data_path = Path(data_dir)

        archive_name = ReleaseUtils.generate_archive_name("csv_archive", release_tag)
        archive_path = self.output_dir / archive_name

        # Check if archive already exists
        if archive_path.exists() and not force:
            file_size = archive_path.stat().st_size
            checksum = self._calculate_checksum(archive_path)
            self.logger.logger.info(
                f"CSV archive already exists, skipping creation: {archive_name} ({file_size} bytes)"
            )
            return {
                "artifact_type": "csv_archive",
                "file_path": str(archive_path),
                "file_size": file_size,
                "checksum": checksum,
                "created_at": datetime.now(),
                "skipped": True,
            }

        # Get all CSV files to include
        csv_files_to_package = self._get_all_csv_files(data_path)

        # Create ZIP archive
        self.logger.logger.info(f"Creating CSV archive: {archive_name}")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for csv_file, source_path in csv_files_to_package.items():
                if source_path.exists():
                    zipf.write(source_path, csv_file)

        # Calculate file size and checksum
        file_size = archive_path.stat().st_size
        checksum = self._calculate_checksum(archive_path)

        return {
            "artifact_type": "csv_archive",
            "file_path": str(archive_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
        }

    def _get_all_csv_files(self, data_path: Path) -> Dict[str, Path]:
        """Get all CSV files to include in the package.

        Returns a dictionary mapping target filename to source file path.
        """
        csv_files = {}

        # First, add files from symlinks (these are the latest versions)
        symlink_files = ["Settlements.csv", "Counties.csv"]
        for symlink_file in symlink_files:
            symlink_path = data_path / symlink_file
            if symlink_path.exists() and symlink_path.is_symlink():
                # Use the symlink target as the source
                target_path = symlink_path.resolve()
                csv_files[symlink_file] = target_path

        # Add split address files instead of consolidated addresses.csv
        self._add_split_address_files(data_path, csv_files)

        # Add other important CSV files (find latest versions)
        additional_tables = [
            "NationalIndividualElectoralDistrict",
            "PollingStation",
            "PostalCode",
            "PostalCode_Settlement",
            "SettlementIndividualElectoralDistrict",
        ]

        for table in additional_tables:
            latest_file = self._find_latest_csv_file(data_path, table)
            if latest_file:
                csv_files[f"{table}.csv"] = latest_file

        return csv_files

    def _add_split_address_files(
        self, data_path: Path, csv_files: Dict[str, Path]
    ) -> None:
        """Add split address files to the package instead of consolidated addresses.csv.

        Looks for directories matching *_Address pattern and includes all CSV files
        from those directories.
        """
        # Find all address directories (e.g., 20250929-2101_Address)
        address_dirs = list(data_path.glob("*_Address"))

        if not address_dirs:
            # Fallback to consolidated addresses.csv if no split files found
            symlink_path = data_path / "addresses.csv"
            if symlink_path.exists() and symlink_path.is_symlink():
                target_path = symlink_path.resolve()
                csv_files["addresses.csv"] = target_path
            return

        # Use the latest address directory (by modification time)
        latest_address_dir = max(address_dirs, key=lambda p: p.stat().st_mtime)

        # Add all CSV files from the address directory
        for address_file in latest_address_dir.glob("*.csv"):
            if address_file.is_file():
                # Keep the original filename for the split files
                csv_files[f"addresses/{address_file.name}"] = address_file

    def _find_latest_csv_file(self, data_path: Path, table_name: str) -> Optional[Path]:
        """Find the latest version of a CSV file for a given table."""
        pattern = f"*_{table_name}.csv"
        matching_files = []

        for file_path in data_path.glob(pattern):
            if file_path.is_file():
                matching_files.append(file_path)

        if not matching_files:
            return None

        # Return the file with the latest modification time
        return max(matching_files, key=lambda p: p.stat().st_mtime)

    def package_database(
        self, data_dir: str, release_tag: str, force: bool = False
    ) -> Dict[str, Any]:
        """Package database file into a compressed archive.

        Args:
            data_dir: Directory containing database file
            release_tag: Release tag for naming
            force: If True, recreate even if archive exists
        """
        data_path = Path(data_dir)

        archive_name = ReleaseUtils.generate_archive_name(
            "database_archive", release_tag
        )
        archive_path = self.output_dir / archive_name

        # Check if archive already exists
        if archive_path.exists() and not force:
            file_size = archive_path.stat().st_size
            checksum = self._calculate_checksum(archive_path)
            self.logger.logger.info(
                f"Database archive already exists, skipping creation: {archive_name} ({file_size} bytes)"
            )
            return {
                "artifact_type": "database_archive",
                "file_path": str(archive_path),
                "file_size": file_size,
                "checksum": checksum,
                "created_at": datetime.now(),
                "skipped": True,
            }

        # Try multiple database file locations in order of preference
        # Prioritize the main data/oevk.db file first
        db_files_to_try = [
            "../data/oevk.db",  # Main database in data directory (highest priority)
            "database.duckdb",  # Primary database file
            "oevk.db",  # Main transformed database
            "oevk_data.duckdb",  # Staging database
        ]

        # Find and package the first available database file
        db_file_used = None
        self.logger.logger.info(f"Creating database archive: {archive_name}")

        # First try files in the current data directory
        for db_file in db_files_to_try:
            db_path = data_path / db_file
            if db_path.exists():
                db_file_used = db_file
                # Use consistent name in archive - always name it oevk.db
                archive_db_name = "oevk.db"
                # Create ZIP archive containing the database
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(db_path, archive_db_name)
                self.logger.logger.info(
                    f"Packaged database file: {db_file} as {archive_db_name} ({db_path.stat().st_size} bytes)"
                )
                break

        if not db_file_used:
            raise FileNotFoundError(
                f"No database file found. Tried: {', '.join(db_files_to_try)}"
            )

        # Calculate file size and checksum
        file_size = archive_path.stat().st_size
        checksum = self._calculate_checksum(archive_path)

        return {
            "artifact_type": "database_archive",
            "file_path": str(archive_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
            "database_file": db_file_used,  # Track which database file was used
        }

    def package_postgresql_files(
        self, data_dir: str, release_tag: str, force: bool = False
    ) -> Dict[str, Any]:
        """Package PostgreSQL CSV files and import script into a compressed archive.

        Args:
            data_dir: Directory containing postgresql/ subdirectory with CSV files
            release_tag: Release tag for naming
            force: If True, recreate even if archive exists

        Returns:
            Dictionary containing artifact metadata
        """
        data_path = Path(data_dir)
        postgresql_dir = data_path / "postgresql"

        archive_name = ReleaseUtils.generate_archive_name("postgresql", release_tag)
        archive_path = self.output_dir / archive_name

        # Check if archive already exists
        if archive_path.exists() and not force:
            file_size = archive_path.stat().st_size
            checksum = self._calculate_checksum(archive_path)
            self.logger.logger.info(
                f"PostgreSQL archive already exists, skipping creation: {archive_name} ({file_size} bytes)"
            )
            return {
                "artifact_type": "postgresql",
                "file_path": str(archive_path),
                "file_size": file_size,
                "checksum": checksum,
                "created_at": datetime.now(),
                "skipped": True,
            }

        # Check for PostgreSQL CSV files directory
        if not postgresql_dir.exists():
            raise FileNotFoundError(f"PostgreSQL directory not found: {postgresql_dir}")

        # Find schema.sql and import script
        schema_path = data_path / "schema.sql"
        import_script_path = data_path / "import_postgresql.sql"

        if not schema_path.exists():
            raise FileNotFoundError(f"PostgreSQL schema.sql not found in {data_dir}")

        if not import_script_path.exists():
            raise FileNotFoundError(
                f"PostgreSQL import_postgresql.sql not found in {data_dir}"
            )

        # Get all CSV files from postgresql directory
        csv_files = list(postgresql_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {postgresql_dir}")

        # Exclude large Address.csv file since chunked versions exist
        # This keeps the archive under GitHub's 2GB limit
        csv_files_filtered = [f for f in csv_files if f.name != "Address.csv"]

        excluded_count = len(csv_files) - len(csv_files_filtered)
        if excluded_count > 0:
            self.logger.logger.info(
                f"  Excluding {excluded_count} large file(s) (Address.csv) - using chunked versions instead"
            )

        # Create ZIP archive with STORED method (no compression) for large CSV files
        # CSV files are already text and don't compress well, this makes packaging much faster
        self.logger.logger.info(f"Creating PostgreSQL archive: {archive_name}")
        self.logger.logger.info(
            f"  Including {len(csv_files_filtered)} CSV files (stored without compression)"
        )

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_STORED) as zipf:
            # Add schema and import script
            zipf.write(schema_path, "schema.sql")
            zipf.write(import_script_path, "import_postgresql.sql")

            # Add filtered CSV files in postgresql/ subdirectory
            for csv_file in csv_files_filtered:
                zipf.write(csv_file, f"postgresql/{csv_file.name}")

            # Add README with instructions
            readme_content = """# OEVK PostgreSQL Database

This archive contains PostgreSQL-compatible CSV files and schema for the OEVK database.

## Contents

- `schema.sql`: Database schema (DDL) with foreign keys and indexes
- `import_postgresql.sql`: Optimized COPY-based import script
- `postgresql/`: Directory containing CSV files for all tables
- `README.md`: This file

## Quick Start

### Option 1: Automated Import (Recommended)

```bash
# Extract the archive
unzip oevk-postgresql-YYYYMMDD_HHMMSS.zip

# Create database and enable PostGIS
createdb oevk
psql -d oevk -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Import schema and data (2-5 minutes)
psql -d oevk -f schema.sql
psql -d oevk -f import_postgresql.sql
```

### Option 2: Docker PostgreSQL

```bash
# Extract the archive
unzip oevk-postgresql-YYYYMMDD_HHMMSS.zip

# Start PostgreSQL with PostGIS
docker run --name oevk-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgis/postgis:16-3.4

# Wait for PostgreSQL to start
sleep 5

# Create database
docker exec oevk-postgres psql -U postgres -c "CREATE DATABASE oevk;"

# Import schema
docker exec -i oevk-postgres psql -U postgres -d oevk < schema.sql

# Copy CSV files to container
docker cp postgresql oevk-postgres:/tmp/

# Import data (update paths in import_postgresql.sql to /tmp/postgresql/)
sed 's|/Users/[^/]*/Project/oevk-data/exports/postgresql/|/tmp/postgresql/|g' import_postgresql.sql > import_docker.sql
docker exec -i oevk-postgres psql -U postgres -d oevk < import_docker.sql
```

## What's Included

### CSV Files (15 tables, ~1.6GB total)

All CSV files use standard PostgreSQL COPY format:
- Header row with column names
- Comma-separated values
- Double-quoted strings
- NULL represented as empty string

**Reference Tables:**
- `County.csv` - 20 counties
- `Settlement.csv` - 3,177 settlements
- `NationalIndividualElectoralDistrict.csv` - 106 districts
- `SettlementIndividualElectoralDistrict.csv` - 4,597 districts
- `PostalCode.csv` - 3,106 postal codes
- `PostalCode_Settlement.csv` - 3,684 postal code mappings
- `PublicSpaceName.csv` - 25,117 street names
- `PublicSpaceType.csv` - 148 street types
- `SettlementPublicSpaces.csv` - 122,524 street mappings
- `PollingStation.csv` - 8,547 polling stations

**Address Tables (3.3M addresses):**
- `Address_chunk*.csv` - 3.3M deduplicated canonical addresses (split into chunks for GitHub size limits)
- `AddressPollingStations.csv` - 3.3M address-polling station mappings
- `AddressPIRCodes.csv` - 3.3M address-postal code mappings

**Note:** The full `Address.csv` file is excluded from this archive to keep the size under GitHub's 2GB limit.
Use the `Address_chunk*.csv` files instead, which contain the same data split into manageable chunks.

**Utility Tables:**
- `AddressMapping.csv` - Maps original addresses to canonical addresses
- `CanonicalAddress.csv` - Canonical address reference

## Import Performance

The optimized COPY-based import is **10-50x faster** than INSERT statements:

- **COPY method** (import_postgresql.sql): 2-5 minutes
- **INSERT method** (legacy data.sql): 30-120 minutes

## Database Features

### PostGIS Geography Columns

address and polling_station tables include PostGIS GEOGRAPHY columns for geospatial queries:

```sql
-- Find addresses within 1km of a point
SELECT * FROM address
WHERE ST_DWithin(
    geometry,
    ST_GeogFromText('POINT(19.0402 47.4979)'),
    1000
);

-- Find nearest polling station
SELECT * FROM polling_station
ORDER BY geometry <-> ST_GeogFromText('POINT(19.0402 47.4979)')
LIMIT 1;
```

### Foreign Key Relationships

All tables are properly normalized with foreign key constraints:
- `address.county_id` → `county.id`
- `address.settlement_id` → `settlement.id`
- `address.oevk_id` → `oevk.id`
- `address.tevk_id` → `tevk.id`

### Indexes

Optimized indexes for common queries:
- Primary keys on all ID columns
- Foreign key indexes for fast joins
- Spatial indexes on Geography columns (PostGIS)

## Data Quality

- **Deduplication**: Address table contains 3.3M deduplicated canonical addresses
- **Geocoding**: ~88% of addresses include latitude/longitude coordinates
- **Validation**: All foreign keys validated during export
- **Consistency**: Junction tables use correct AddressID references

## Notes

- CSV files use absolute paths in import_postgresql.sql - update paths if needed
- PostGIS extension required for Geography columns
- Import script includes placeholder records for missing foreign keys
- All ID columns use PostgreSQL TEXT type (xxhash64 hex values)
- Expected database size: ~2.5GB after import
"""
            zipf.writestr("README.md", readme_content)

        # Calculate file size and checksum
        file_size = archive_path.stat().st_size
        checksum = self._calculate_checksum(archive_path)

        self.logger.logger.info(
            f"PostgreSQL archive created: {archive_name} ({file_size} bytes, {len(csv_files)} CSV files)"
        )

        return {
            "artifact_type": "postgresql",
            "file_path": str(archive_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
            "csv_files_count": len(csv_files),
        }

    def package_geocoding_cache(
        self, cache_file: str, release_tag: str, force: bool = False
    ) -> Dict[str, Any]:
        """Package geocoding cache database into a compressed archive.

        Args:
            cache_file: Path to geocoding_cache.db file
            release_tag: Release tag for naming
            force: If True, recreate even if archive exists

        Returns:
            Dictionary containing artifact metadata
        """
        cache_path = Path(cache_file)

        archive_name = ReleaseUtils.generate_archive_name(
            "geocoding_cache", release_tag
        )
        archive_path = self.output_dir / archive_name

        # Check if archive already exists
        if archive_path.exists() and not force:
            file_size = archive_path.stat().st_size
            checksum = self._calculate_checksum(archive_path)
            self.logger.logger.info(
                f"Geocoding cache archive already exists, skipping creation: {archive_name} ({file_size} bytes)"
            )
            return {
                "artifact_type": "geocoding_cache",
                "file_path": str(archive_path),
                "file_size": file_size,
                "checksum": checksum,
                "created_at": datetime.now(),
                "skipped": True,
            }

        if not cache_path.exists():
            raise FileNotFoundError(f"Geocoding cache file not found: {cache_file}")

        # Create ZIP archive
        self.logger.logger.info(f"Creating geocoding cache archive: {archive_name}")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(cache_path, "geocoding_cache.db")

            # Add README with instructions
            readme_content = """# OEVK Geocoding Cache

This archive contains a pre-built geocoding cache for Hungarian addresses using Nominatim.

## Contents

- `geocoding_cache.db`: SQLite database with ~2.9M cached geocoding results
- `README.md`: This file

## What is this?

The geocoding cache contains latitude/longitude coordinates for Hungarian addresses
that have been successfully geocoded using a local Nominatim server with OpenStreetMap data.

## Usage

Place the `geocoding_cache.db` file in your `data/` directory before running geocoding:

```bash
# Extract the cache
unzip oevk-geocoding-cache-YYYYMMDD_HHMMSS.zip

# Move to data directory
mv geocoding_cache.db data/

# Run geocoding (will use cache for ~88% of addresses)
python src/cli.py geocode run
```

## Benefits

Using this cache will:
- Speed up geocoding by ~5x for cached addresses
- Reduce load on your Nominatim server
- Provide consistent coordinates across runs
- Skip ~88% of addresses that are already geocoded

## Cache Statistics

- **Cached addresses**: ~2,900,000 (88.5%)
- **Success rate**: ~88.5%
  - Exact matches: ~17.6%
  - Street-level matches: ~70.1%
  - Settlement-level matches: ~0.7%
- **Source**: Local Nominatim with Hungary OSM data
- **Cache format**: SQLite database
- **Cache key**: MD5(SettlementName|StreetName|HouseNumber)

## Cache Structure

The cache database has the following schema:

```sql
CREATE TABLE geocoding_cache (
    cache_key TEXT PRIMARY KEY,
    canonical_address_id TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    quality TEXT NOT NULL,  -- 'exact', 'street', 'settlement', 'failed'
    source TEXT NOT NULL,
    osm_type TEXT,
    osm_id INTEGER,
    matched_address TEXT,
    created_at TEXT NOT NULL
);
```

## Notes

- Failed geocoding attempts are NOT cached (will be retried)
- Cache is compatible with the multi-threaded geocoder (32 workers)
- Cache lookups are very fast (indexed by cache_key)
- To rebuild the cache from scratch, simply delete the file and re-run geocoding
"""
            zipf.writestr("README.md", readme_content)

        # Calculate file size and checksum
        file_size = archive_path.stat().st_size
        checksum = self._calculate_checksum(archive_path)

        self.logger.logger.info(
            f"Geocoding cache archive created: {archive_name} ({file_size} bytes)"
        )

        return {
            "artifact_type": "geocoding_cache",
            "file_path": str(archive_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
        }

    def package_postgresql_dump(
        self, data_dir: str, release_tag: str, force: bool = False
    ) -> Dict[str, Any]:
        """Package PostgreSQL dump file (.sql.gz) as a release artifact.

        Args:
            data_dir: Directory containing the PostgreSQL dump file
            release_tag: Release tag for naming
            force: If True, recreate even if archive exists

        Returns:
            Dictionary containing artifact metadata
        """
        data_path = Path(data_dir)

        # Find the most recent PostgreSQL dump file
        dump_files = list(data_path.glob("oevk_db_*.sql.gz"))

        if not dump_files:
            raise FileNotFoundError(
                f"No PostgreSQL dump file (oevk_db_*.sql.gz) found in {data_dir}"
            )

        # Use the most recent dump file
        dump_file = max(dump_files, key=lambda p: p.stat().st_mtime)

        self.logger.logger.info(f"Found PostgreSQL dump: {dump_file.name}")

        # The dump file is already compressed, so we'll just copy it to output
        # and include it as-is in the release (no additional packaging needed)
        output_name = f"oevk-postgresql-dump-{release_tag}.sql.gz"
        output_path = self.output_dir / output_name

        # Check if output already exists
        if output_path.exists() and not force:
            file_size = output_path.stat().st_size
            checksum = self._calculate_checksum(output_path)
            self.logger.logger.info(
                f"PostgreSQL dump artifact already exists, skipping: {output_name} ({file_size} bytes)"
            )
            return {
                "artifact_type": "postgresql_dump",
                "file_path": str(output_path),
                "file_size": file_size,
                "checksum": checksum,
                "created_at": datetime.now(),
                "skipped": True,
            }

        # Copy dump file to output directory
        self.logger.logger.info(f"Creating PostgreSQL dump artifact: {output_name}")

        import shutil

        shutil.copy2(dump_file, output_path)

        # Calculate file size and checksum
        file_size = output_path.stat().st_size
        checksum = self._calculate_checksum(output_path)

        self.logger.logger.info(
            f"PostgreSQL dump artifact created: {output_name} ({file_size:,} bytes)"
        )

        return {
            "artifact_type": "postgresql_dump",
            "file_path": str(output_path),
            "file_size": file_size,
            "checksum": checksum,
            "created_at": datetime.now(),
            "source_file": dump_file.name,
        }

    def package_all(self, data_dir: str, release_tag: str) -> List[Dict[str, Any]]:
        """Package all data files into compressed archives."""
        artifacts = []

        # Package CSV files
        csv_artifact = self.package_csv_files(data_dir, release_tag)
        artifacts.append(csv_artifact)

        # Package database
        db_artifact = self.package_database(data_dir, release_tag)
        artifacts.append(db_artifact)

        return artifacts

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def cleanup_artifacts(self, release_tag: str) -> None:
        """Remove packaged artifacts for a specific release."""
        pattern = f"*{release_tag}*"

        for file_path in self.output_dir.glob(pattern):
            try:
                file_path.unlink()
            except Exception as e:
                print(f"Warning: Could not delete {file_path}: {e}")

    def get_artifact_info(self, release_tag: str) -> List[Dict[str, Any]]:
        """Get information about existing artifacts for a release."""
        artifacts = []
        pattern = f"*{release_tag}*"

        for file_path in self.output_dir.glob(pattern):
            if file_path.is_file():
                artifact_type = (
                    "csv_archive" if "csv" in file_path.name else "database_archive"
                )

                artifacts.append(
                    {
                        "artifact_type": artifact_type,
                        "file_path": str(file_path),
                        "file_size": file_path.stat().st_size,
                        "checksum": self._calculate_checksum(file_path),
                        "created_at": datetime.fromtimestamp(file_path.stat().st_mtime),
                    }
                )

        return artifacts
