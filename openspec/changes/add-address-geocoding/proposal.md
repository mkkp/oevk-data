# Address Geocoding Integration Proposal

## Why

The OEVK data currently contains 3.3M+ Hungarian addresses without geographic coordinates, limiting geospatial analysis, mapping capabilities, and distance-based queries. Adding latitude/longitude coordinates via OpenStreetMap and Nominatim will enable:

- Geographic visualization of electoral districts and polling stations
- Distance-based queries (nearest polling station, radius searches)
- PostGIS spatial analysis and queries
- Integration with mapping applications

This change addresses a critical gap in the data quality and unlocks new use cases for electoral analysis, urban planning research, and voter accessibility studies.

## What Changes

- **NEW CAPABILITY**: `geocoding` - Address geocoding using Nominatim and OpenStreetMap data
- Add geographic coordinates (latitude/longitude) to `CanonicalAddress` table
- Add geographic coordinates (latitude/longitude) to `PollingStation` table with fuzzy search
- Implement batch geocoding with Nominatim service running locally in Docker
- Implement multi-strategy fuzzy search for polling station addresses (4 strategies: exact, fuzzy tokenization, canonical matching, settlement fallback)
- Add comprehensive progress logging throughout geocoding, SQL import, and export stages
- Implement persistent caching to avoid re-geocoding addresses
- Support both CSV and PostgreSQL exports with coordinate data
- Optional PostGIS GEOGRAPHY columns for advanced spatial queries and GIS tool integration
- Add CLI commands for geocoding management (`geocode setup`, `geocode run`, `geocode status`)
- Integrate geocoding stage into main ETL pipeline after deduplication

### Progress Logging Enhancements

- Real-time batch progress with percentage completion, ETA, and processing rate
- Cache hit/miss statistics to track efficiency
- Quality distribution tracking (exact/street/settlement/failed matches)
- Database operation progress for large SQL imports and exports
- Streaming progress indicators for PostgreSQL dump operations
- Memory and performance metrics during geocoding

## Impact

### Affected Specs
- **NEW**: `specs/geocoding/spec.md` - New capability for address geocoding
- **MODIFIED**: Database schema (CanonicalAddress table extensions)
- **MODIFIED**: Export formats (CSV and PostgreSQL) to include coordinate columns
- **MODIFIED**: ETL pipeline to add geocoding stage

### Affected Code
- `src/etl/geocoding.py` - NEW: Core geocoding module with NominatimGeocoder and PollingStationGeocoder classes
- `src/etl/transform_optimized.py` - MODIFIED: Add geocoding stage integration for both canonical addresses and polling stations
- `src/etl/export.py` - MODIFIED: Include coordinates in PostgreSQL schema for both tables
- `src/etl/export_canonical_v3.py` - MODIFIED: Include coordinates in CSV exports
- `src/cli.py` - MODIFIED: Add geocoding subcommands (setup, run, status)
- `src/utils/config.py` - MODIFIED: Add Nominatim configuration parameters
- `docker-compose.yml` - NEW: Nominatim service configuration
- `src/database/schema.sql` - MODIFIED: Add coordinate columns to CanonicalAddress and PollingStation tables

### Database Schema Changes
```sql
-- CanonicalAddress table extensions
ALTER TABLE CanonicalAddress ADD COLUMN Latitude REAL;
ALTER TABLE CanonicalAddress ADD COLUMN Longitude REAL;
ALTER TABLE CanonicalAddress ADD COLUMN GeocodingQuality TEXT;
ALTER TABLE CanonicalAddress ADD COLUMN GeocodingSource TEXT;
ALTER TABLE CanonicalAddress ADD COLUMN GeocodedAt TIMESTAMP;

-- Optional PostGIS GEOGRAPHY column (PostgreSQL only, SRID 4326 WGS 84)
ALTER TABLE CanonicalAddress ADD COLUMN Geometry GEOGRAPHY(POINT, 4326);
CREATE INDEX idx_CanonicalAddress_Geometry ON CanonicalAddress USING GIST(Geometry);

-- PollingStation table extensions
ALTER TABLE PollingStation ADD COLUMN Latitude REAL;
ALTER TABLE PollingStation ADD COLUMN Longitude REAL;
ALTER TABLE PollingStation ADD COLUMN GeocodingQuality TEXT;
ALTER TABLE PollingStation ADD COLUMN GeocodingSource TEXT;
ALTER TABLE PollingStation ADD COLUMN GeocodedAt TIMESTAMP;
ALTER TABLE PollingStation ADD COLUMN MatchedAddress TEXT;

-- Optional PostGIS GEOGRAPHY column for polling stations
ALTER TABLE PollingStation ADD COLUMN Geometry GEOGRAPHY(POINT, 4326);
CREATE INDEX idx_PollingStation_Geometry ON PollingStation USING GIST(Geometry);
```

**Note:** This builds on the existing PostGIS support added in Issue #010 for OEVK polygons and extends it to address data.

### Performance Impact
- **First run**: 9-90 minutes for 3.3M addresses (depends on batch size and concurrency)
- **Subsequent runs**: <5 minutes (90%+ cache hit rate for unchanged addresses)
- **Nominatim setup**: 1-2 hours one-time import of Hungary OSM data
- **Storage overhead**: ~200MB for coordinate columns and indexes

### Breaking Changes
None. Geocoding is enabled by default but can be disabled via `NOMINATIM_ENABLED=false`. If Nominatim service is not available, the pipeline will skip geocoding with a warning and continue.

### Dependencies
- Docker (for Nominatim service)
- OpenStreetMap Hungary data (~286 MB)
- Nominatim 5.1 Docker image (`mediagis/nominatim:5.1`)
- PostgreSQL with PostGIS 3.0+ (optional, for GEOGRAPHY columns)
- PostGIS Docker image (`postgis/postgis:15-3.3`) recommended
- Python packages: `requests` (already in requirements)

### Success Criteria
- ≥95% geocoding match rate for canonical addresses
- ≥90% successful geocoding for polling stations (all strategies combined)
- Coordinate accuracy within 10 meters for house-level addresses
- Export time increase ≤20% compared to baseline (mitigated by optional flag)
- Comprehensive progress logging with real-time updates every 10 batches
- SQL import/export progress logged for operations >10,000 rows
- Fuzzy search successfully handles composite institutional addresses
- PostGIS spatial queries functional (point-in-polygon, distance calculations)
