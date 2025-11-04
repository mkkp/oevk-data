<!--
DOCUMENT METADATA
=================
Title: Utility Scripts Documentation
Type: Guide
Category: Infrastructure
Status: Active
Version: 1.0
Created: 2025-10-29
Last Updated: 2025-10-29
Author: System

Related Documents:
- Dump Loader Fix (DUMP_LOADER_FIX.md)
- Main README (../README.md - Database Setup section)
- PostgreSQL Schema (../docs/POSTGRESQL_FINAL_SCHEMA.md)

Related Code:
- scripts/load_dump_to_docker.py (main dump loader implementation)

Dependencies:
- Docker
- PostgreSQL/PostGIS Docker image (postgis/postgis:15-3.3)
- Python 3.9+

Keywords: scripts, dump-loader, postgresql, docker, utilities, database-setup, automation

Summary:
Complete documentation for utility scripts in the scripts/ directory. Primary focus on load_dump_to_docker.py which provides one-command database setup from PostgreSQL dump files. Includes features, usage examples, command-line options, troubleshooting guide, and performance metrics. Supports auto-detection of latest dumps, Docker container management, and PostgreSQL optimization.

Audience:
DevOps engineers, database administrators, developers setting up local databases for development or testing.
-->

# Utility Scripts

This directory contains standalone utility scripts for managing OEVK data.

## load_dump_to_docker.py

**Purpose**: Load the latest PostgreSQL dump file into a Docker PostGIS container.

**Use Case**: Quick database setup from an existing dump file without running the full ETL pipeline.

### Features

- ✅ Auto-detects latest dump file in `exports/` directory
- ✅ Creates Docker PostGIS container automatically
- ✅ Auto-finds available port if default is in use
- ✅ Creates database with PostGIS and pg_trgm extensions
- ✅ Loads compressed `.sql.gz` dump files
- ✅ Verifies import by checking row counts
- ✅ Displays connection information
- ✅ Reuses existing containers if available

### Quick Start

```bash
# Load latest dump with default settings
python scripts/load_dump_to_docker.py

# This creates:
# - Container: oevk-postgresql
# - Database: oevk
# - Port: 5432 (or auto-detected)
# - User/Password: oevk/oevk
```

### Usage Examples

#### Basic Usage

```bash
# Load latest dump file
python scripts/load_dump_to_docker.py

# Load specific dump file
python scripts/load_dump_to_docker.py --dump-file exports/oevk_db_20251029091200.sql.gz
```

#### Custom Configuration

```bash
# Use custom container name
python scripts/load_dump_to_docker.py --container my-oevk-db

# Use specific port
python scripts/load_dump_to_docker.py --port 5433

# Use custom database name
python scripts/load_dump_to_docker.py --db-name oevk_prod
```

#### Advanced Options

```bash
# Drop and recreate database (fresh start)
python scripts/load_dump_to_docker.py --drop-database

# Only start container without loading dump
python scripts/load_dump_to_docker.py --start-only

# Keep container running even if import fails
python scripts/load_dump_to_docker.py --no-cleanup

# Use different PostGIS version
python scripts/load_dump_to_docker.py --image postgis/postgis:16-3.4
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dump-file` | Path to specific dump file | Latest in exports/ |
| `--exports-dir` | Directory containing dumps | `exports` |
| `--container` | Docker container name | `oevk-postgresql` |
| `--port` | PostgreSQL port | Auto-detect (5432+) |
| `--db-name` | Database name | `oevk` |
| `--drop-database` | Drop existing database | False |
| `--image` | Docker image | `postgis/postgis:15-3.3` |
| `--no-cleanup` | Keep container on failure | False |
| `--start-only` | Only start container | False |

### Output

The script provides colored, step-by-step progress output:

```
=== PostgreSQL Dump Loader ===

=== Step 0/6: Checking Docker ===
✓ Docker is available

=== Step 1/6: Finding dump file ===
✓ Found dump: exports/oevk_db_20251029091200.sql.gz
INFO:   Size: 145.3 MB
INFO:   Modified: 2025-10-29 09:12:00

=== Step 2/6: Setting up Docker container ===
INFO: Creating PostgreSQL container 'oevk-postgresql'...
✓ Container 'oevk-postgresql' created successfully

=== Step 3/6: Waiting for PostgreSQL ===
✓ PostgreSQL ready after 3.2s

=== Step 4/6: Creating database ===
✓ Database 'oevk' created
✓ PostGIS and pg_trgm extensions enabled

=== Step 5/6: Loading dump ===
INFO: Dump file size: 145.3 MB (compressed)
INFO: Importing data (this may take several minutes)...
✓ Dump loaded successfully

=== Step 6/6: Verifying import ===

Table Row Counts:
--------------------------------------------------
✓ county                                    19 rows
✓ settlement                             3,178 rows
✓ oevk                                     106 rows
✓ tevk                                   2,444 rows
✓ postal_code                            3,200 rows
✓ polling_station                        8,547 rows
✓ address                            3,323,113 rows
✓ public_space_name                     25,117 rows
✓ public_space_type                        148 rows
--------------------------------------------------
Total rows:                          3,365,872
✓ Import verification passed

=== Connection Information ===
Container:  oevk-postgresql
Host:       localhost
Port:       5432
Database:   oevk
User:       oevk
Password:   oevk

Connect with psql:
  docker exec -it oevk-postgresql psql -U oevk -d oevk

Connection string:
  postgresql://oevk:oevk@localhost:5432/oevk

✓ Import completed successfully!
```

### Connecting to the Database

After successful import, connect using:

```bash
# Using psql inside container
docker exec -it oevk-postgresql psql -U oevk -d oevk

# Using local psql client
psql -h localhost -p 5432 -U oevk -d oevk

# Connection string for applications
postgresql://oevk:oevk@localhost:5432/oevk
```

### Performance

- **Import time**: 2-5 minutes for 554 MB dump (~3.3M addresses)
- **Disk space**: ~4 GB for full database with indexes
- **Memory**: Optimized settings applied automatically (256MB shared_buffers, 64MB work_mem)
- **Streaming**: Uses shell pipeline to avoid loading entire dump into memory

### Troubleshooting

#### Docker not running
```
ERROR: Docker is not installed or not running
```
**Solution**: Start Docker Desktop or Docker daemon

#### Port already in use
```
ERROR: Port 5432 is already in use
```
**Solution**: The script auto-detects available ports. If it fails, specify a port manually:
```bash
python scripts/load_dump_to_docker.py --port 5433
```

#### Container already exists
The script reuses existing containers automatically. To start fresh:
```bash
# Remove existing container
docker stop oevk-postgresql
docker rm oevk-postgresql

# Run script again
python scripts/load_dump_to_docker.py
```

#### No dump file found
```
ERROR: No dump files found in exports
```
**Solution**: Create a dump file first:
```bash
python -m src.cli db verify
```

### Requirements

- Docker installed and running
- Python 3.9+
- Dump file in `.sql.gz` format (created by `db verify` command)
- ~4 GB free disk space

### Related Commands

```bash
# Create a dump file
python -m src.cli db verify

# Full pipeline with dump creation
python -m src.cli run
python -m src.cli db verify

# Manual dump import (alternative)
gunzip -c exports/oevk_db_20251029091200.sql.gz | \
  docker exec -i oevk-postgresql psql -U oevk -d oevk
```

### See Also

- Main README: `../README.md`
- PostgreSQL Schema: `../docs/POSTGRESQL_FINAL_SCHEMA.md`
- Database Setup: `../README.md#postgresql-export-and-database-setup`
