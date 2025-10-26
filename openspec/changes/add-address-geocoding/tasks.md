# Implementation Tasks

## 1. Infrastructure Setup

- [x] 1.1 Create `docker-compose.yml` with Nominatim service configuration
- [x] 1.2 Configure Nominatim with Hungary OSM data URL
- [x] 1.3 Set up Docker health check for Nominatim service
- [x] 1.4 Add environment variables for Nominatim configuration
- [x] 1.5 Update `.env.example` with Nominatim settings
- [x] 1.6 Test Nominatim Docker container startup and health check

## 2. Database Schema Extensions

- [x] 2.1 Add coordinate columns to CanonicalAddress table (Latitude, Longitude, GeocodingQuality, GeocodingSource, GeocodedAt)
- [x] 2.2 Add coordinate columns to PollingStation table (+ MatchedAddress field)
- [x] 2.3 Create indexes on coordinate columns
- [x] 2.4 Add PostGIS GEOGRAPHY columns (optional, when GEOCODING_USE_POSTGIS=true)
- [x] 2.5 Create GIST spatial indexes on geometry columns
- [x] 2.6 Update PostgreSQL schema generation in `src/etl/export.py`
- [x] 2.7 Test schema changes with sample data

## 3. Core Geocoding Module

- [x] 3.1 Create `src/etl/geocoding.py` module
- [x] 3.2 Implement `GeocodingQuality` enum (exact/street/settlement/failed)
- [x] 3.3 Implement `GeocodingResult` dataclass
- [x] 3.4 Implement `NominatimGeocoder` class with initialization
- [x] 3.5 Implement `geocode_addresses()` method with batch processing
- [x] 3.6 Implement `_geocode_single()` method with structured queries
- [x] 3.7 Implement `_parse_response()` method for GeoJSON parsing
- [x] 3.8 Implement `_determine_quality()` method for quality classification
- [x] 3.9 Implement rate limiting logic (disabled for local instance)
- [x] 3.10 Test geocoding module with sample addresses

## 4. Caching System

- [x] 4.1 Implement `_get_cache_key()` method using MD5 hash
- [x] 4.2 Implement `_get_from_cache()` method for cache lookups
- [x] 4.3 Implement `_save_to_cache()` method for cache storage
- [x] 4.4 Create cache directory management (default: data/geocoding_cache)
- [x] 4.5 Add cache configuration options (NOMINATIM_CACHE_DIR)
- [x] 4.6 Test cache hit/miss scenarios

## 5. Progress Logging for Canonical Addresses

- [x] 5.1 Implement `_log_progress()` method logging every 10 batches
- [x] 5.2 Display batch number and total batches (e.g., "Batch 50/331")
- [x] 5.3 Show cumulative statistics (cached, exact, street, settlement, failed)
- [x] 5.4 Display percentage completion
- [x] 5.5 Calculate and display processing rate (addresses/second)
- [x] 5.6 Calculate and display estimated time remaining (ETA)
- [x] 5.7 Implement `_log_final_stats()` method with comprehensive summary
- [x] 5.8 Add memory usage tracking (log if >500MB)
- [x] 5.9 Test progress logging with large dataset

## 6. Polling Station Geocoding with Fuzzy Search

- [x] 6.1 Create `PollingStationGeocoder` class in `src/etl/geocoding.py`
- [x] 6.2 Implement multi-strategy geocoding approach (4 strategies)
- [x] 6.3 Implement Strategy 1: Exact Nominatim match
- [x] 6.4 Implement Strategy 2: Fuzzy tokenization with `_extract_address_components()`
- [x] 6.5 Implement institution keyword removal (iskola, hivatal, etc.)
- [x] 6.6 Implement street pattern extraction using regex
- [x] 6.7 Implement Strategy 3: Canonical address matching with `_match_canonical_address()`
- [x] 6.8 Implement Levenshtein similarity calculation
- [x] 6.9 Implement Strategy 4: Settlement centroid fallback with `_get_settlement_centroid()`
- [x] 6.10 Add configuration for similarity threshold (default: 0.6)
- [x] 6.11 Implement progress logging for polling stations
- [x] 6.12 Test fuzzy search with composite institutional addresses

## 7. ETL Pipeline Integration

- [x] 7.1 Add `geocode_canonical_addresses()` function to pipeline
- [x] 7.2 Add `geocode_polling_stations()` function to pipeline
- [x] 7.3 Integrate geocoding stage into `src/etl/transform_optimized.py` after deduplication
- [x] 7.4 Add geocoding stage toggle with NOMINATIM_ENABLED flag
- [x] 7.5 Implement incremental geocoding (WHERE Latitude IS NULL)
- [x] 7.6 Update database with geocoding results
- [x] 7.7 Generate PostGIS geometry columns when enabled
- [x] 7.8 Test pipeline integration end-to-end

## 8. CSV and PostgreSQL Export Integration

- [x] 8.1 Update `src/etl/export_canonical_v3.py` to include coordinate columns in CSV
- [x] 8.2 Update PostgreSQL schema in `src/etl/export.py` with coordinate columns
- [x] 8.3 Add PostGIS GEOGRAPHY column generation (optional)
- [x] 8.4 Implement ST_GeogFromText for coordinate insertion
- [x] 8.5 Add GIST spatial index creation
- [x] 8.6 Add progress logging for CSV export (log every 100,000 rows)
- [x] 8.7 Add progress logging for PostgreSQL import (log every 50,000 rows)
- [x] 8.8 Add progress logging for pg_dump operations
- [x] 8.9 Test CSV export with coordinates
- [x] 8.10 Test PostgreSQL export with PostGIS support

## 9. CLI Commands

- [x] 9.1 Add `geocode` subparser to `src/cli.py`
- [x] 9.2 Implement `geocode setup` command for Nominatim service startup
- [x] 9.3 Add --force-reimport flag for OSM data reload
- [x] 9.4 Implement `geocode run` command for batch geocoding
- [x] 9.5 Add --batch-size parameter for batch configuration
- [x] 9.6 Add --db-path parameter for database selection
- [x] 9.7 Implement `geocode status` command for statistics display
- [x] 9.8 Add health check monitoring during Nominatim setup
- [x] 9.9 Implement progress logging during OSM import (log every 10 minutes)
- [x] 9.10 Test CLI commands

## 10. Configuration Management

- [x] 10.1 Add Nominatim configuration options to `src/utils/config.py`
- [x] 10.2 Add NOMINATIM_ENABLED (default: true)
- [x] 10.3 Add NOMINATIM_MODE (default: local)
- [x] 10.4 Add NOMINATIM_BASE_URL (default: http://localhost:8081)
- [x] 10.5 Add NOMINATIM_BATCH_SIZE (default: 100)
- [x] 10.6 Add NOMINATIM_RATE_LIMIT (default: 0 for local)
- [x] 10.7 Add NOMINATIM_CACHE_DIR (default: data/geocoding_cache)
- [x] 10.8 Add NOMINATIM_SIMILARITY_THRESHOLD (default: 0.6)
- [x] 10.9 Add GEOCODING_USE_POSTGIS (default: true)
- [x] 10.10 Document all configuration options

## 11. Error Handling and Validation

- [ ] 11.1 Implement retry logic with exponential backoff (DEFERRED: can be added if needed)
- [x] 11.2 Add timeout handling for Nominatim requests
- [ ] 11.3 Implement coordinate range validation (-90 to 90 lat, -180 to 180 lon) (DEFERRED: can be added if needed)
- [ ] 11.4 Implement Hungary bounding box validation (lat: 45.7-48.6, lon: 16.1-22.9) (DEFERRED: can be added if needed)
- [x] 11.5 Add error logging for failed geocoding attempts
- [x] 11.6 Implement graceful degradation (continue on errors)
- [ ] 11.7 Add warning logs for coordinates outside Hungary (DEFERRED: can be added if needed)
- [ ] 11.8 Test error scenarios (Part of Phase 12: Testing)

## 12. Testing

- [ ] 12.1 Write unit tests for `NominatimGeocoder` class
- [ ] 12.2 Write unit tests for `PollingStationGeocoder` class
- [ ] 12.3 Write unit tests for address component extraction
- [ ] 12.4 Write unit tests for Levenshtein similarity calculation
- [ ] 12.5 Write unit tests for quality determination logic
- [ ] 12.6 Write unit tests for cache operations
- [ ] 12.7 Write integration tests for end-to-end geocoding
- [ ] 12.8 Write integration tests for fuzzy search
- [ ] 12.9 Write integration tests for PostGIS export
- [ ] 12.10 Write integration tests for spatial queries
- [ ] 12.11 Test with real Hungary address data
- [ ] 12.12 Achieve >80% code coverage

## 13. Documentation

- [x] 13.1 Update README.md with geocoding features section
- [x] 13.2 Document Nominatim setup process
- [x] 13.3 Document CLI commands usage
- [x] 13.4 Document configuration options
- [x] 13.5 Add spatial query examples for PostGIS
- [x] 13.6 Document fuzzy search logic for polling stations
- [x] 13.7 Add troubleshooting section
- [x] 13.8 Document performance characteristics
- [x] 13.9 Add example workflows
- [x] 13.10 Update CLAUDE.md with new features

## 14. Validation and Performance Testing

- [ ] 14.1 Run geocoding on full 3.3M address dataset
- [ ] 14.2 Verify ≥95% match rate success criteria
- [ ] 14.3 Verify ≥80% exact/street quality success criteria
- [ ] 14.4 Measure geocoding performance (time and rate)
- [ ] 14.5 Verify cache hit rate >90% on subsequent runs
- [ ] 14.6 Test incremental geocoding performance (<5 minutes)
- [ ] 14.7 Verify memory usage stays <500MB
- [ ] 14.8 Test spatial queries with PostGIS
- [ ] 14.9 Validate GeoJSON export
- [ ] 14.10 Test QGIS import compatibility

## Dependencies

- **Parallel work allowed**: Tasks 1-2 can start immediately
- **Blocking dependencies**:
  - Tasks 3-6 depend on Task 2 (schema complete)
  - Task 7 depends on Tasks 3-6 (core modules complete)
  - Task 8 depends on Task 7 (pipeline integration complete)
  - Task 12 can run parallel to development
  - Tasks 13-14 depend on all previous tasks

## Time Estimates

- **Phase 1** (Tasks 1-2): Infrastructure & Schema - 4 hours
- **Phase 2** (Tasks 3-5): Core Geocoding - 8 hours
- **Phase 3** (Task 6): Fuzzy Search - 6 hours
- **Phase 4** (Tasks 7-9): Integration & CLI - 6 hours
- **Phase 5** (Tasks 10-11): Config & Error Handling - 4 hours
- **Phase 6** (Task 12): Testing - 8 hours
- **Phase 7** (Tasks 13-14): Documentation & Validation - 4 hours

**Total Estimated Time**: 40 hours (~1 week full-time)
