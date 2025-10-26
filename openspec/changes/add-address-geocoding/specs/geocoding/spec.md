# Geocoding Capability Specification

## ADDED Requirements

### Requirement: Nominatim Service Integration

The system SHALL provide a Nominatim geocoding service running locally in Docker using OpenStreetMap data for Hungary.

#### Scenario: Docker service startup

- **WHEN** user runs `python src/cli.py geocode setup`
- **THEN** the system SHALL pull the `mediagis/nominatim:5.1` Docker image
- **AND** download Hungary OSM data from Geofabrik
- **AND** import the data into a PostgreSQL 16 database with PostGIS
- **AND** expose the Nominatim API on port 8081
- **AND** verify service health before completing

#### Scenario: Service configuration

- **WHEN** Nominatim service is configured
- **THEN** the system SHALL use Hungary-only OSM data (~286 MB)
- **AND** optimize for address-level data with NOMINATIM_IMPORT_STYLE=address
- **AND** allocate 2GB shared memory for PostgreSQL
- **AND** require 4-8GB RAM and 15-20GB disk space
- **AND** complete first-time import within 1-2 hours

#### Scenario: Health check monitoring

- **WHEN** Nominatim is starting up
- **THEN** the system SHALL poll the health check endpoint every 30 seconds
- **AND** log progress every 10 minutes during import
- **AND** timeout after 2 hours if service doesn't become healthy
- **AND** provide clear error messages on failure

### Requirement: Batch Address Geocoding

The system SHALL geocode canonical addresses in batches using the Nominatim API with progress tracking and caching.

#### Scenario: Batch geocoding execution

- **WHEN** user runs `python src/cli.py geocode run`
- **THEN** the system SHALL fetch all canonical addresses without coordinates
- **AND** process addresses in configurable batches (default 100)
- **AND** use structured queries with street, city, and country code
- **AND** parse GeoJSON responses to extract coordinates
- **AND** determine quality level (exact/street/settlement/failed)
- **AND** update CanonicalAddress table with results

#### Scenario: Geocoding progress logging

- **WHEN** batch geocoding is running
- **THEN** the system SHALL log progress every 10 batches
- **AND** display current batch number and total batches (e.g., "Batch 50/331")
- **AND** show cumulative statistics (cached, exact, street, settlement, failed)
- **AND** display percentage completion and processing rate
- **AND** calculate and display estimated time remaining (ETA)
- **AND** show memory usage if it exceeds 500MB

#### Scenario: Final geocoding statistics

- **WHEN** geocoding completes
- **THEN** the system SHALL log comprehensive final statistics
- **AND** display total addresses processed
- **AND** show cache hit count and percentage
- **AND** show newly geocoded count and percentage
- **AND** break down quality distribution (exact/street/settlement/failed) with counts and percentages
- **AND** display total processing time

#### Scenario: No rate limiting for local instance

- **WHEN** Nominatim is running locally
- **THEN** the system SHALL set NOMINATIM_RATE_LIMIT=0
- **AND** process requests as fast as the local service can handle
- **AND** NOT apply artificial rate limiting delays between requests

### Requirement: Geocoding Result Quality Classification

The system SHALL classify geocoding results into quality tiers based on OSM match type.

#### Scenario: House-level match classification

- **WHEN** Nominatim returns osm_value="house" or geocoding type="house"
- **THEN** the system SHALL classify result as GeocodingQuality.EXACT
- **AND** expect coordinate accuracy within 10 meters

#### Scenario: Street-level match classification

- **WHEN** Nominatim returns osm_value containing "street" or "road"
- **THEN** the system SHALL classify result as GeocodingQuality.STREET
- **AND** store street-level centroid coordinates

#### Scenario: Settlement-level match classification

- **WHEN** Nominatim returns osm_value containing "city", "town", "village", or "place"
- **THEN** the system SHALL classify result as GeocodingQuality.SETTLEMENT
- **AND** store settlement centroid coordinates

#### Scenario: Failed match handling

- **WHEN** Nominatim returns no results or request times out
- **THEN** the system SHALL classify result as GeocodingQuality.FAILED
- **AND** store NULL for latitude and longitude
- **AND** log warning with address details
- **AND** continue processing remaining addresses

### Requirement: Persistent Geocoding Cache

The system SHALL cache geocoding results to avoid redundant API calls and improve performance.

#### Scenario: Cache key generation

- **WHEN** geocoding an address
- **THEN** the system SHALL generate MD5 hash cache key from settlement name, street name, and house number
- **AND** use cache key for file-based lookup

#### Scenario: Cache hit on existing address

- **WHEN** address has been geocoded before
- **THEN** the system SHALL retrieve result from cache file
- **AND** increment cached_count statistic
- **AND** skip API call to Nominatim
- **AND** log cache usage in progress statistics

#### Scenario: Cache miss on new address

- **WHEN** address has not been geocoded before
- **THEN** the system SHALL call Nominatim API
- **AND** store result in cache file as JSON
- **AND** increment geocoded_count statistic

#### Scenario: Cache directory management

- **WHEN** geocoding starts
- **THEN** the system SHALL create cache directory if it doesn't exist (default: data/geocoding_cache)
- **AND** use configurable cache path via NOMINATIM_CACHE_DIR
- **AND** persist cache files between pipeline runs

### Requirement: Database Schema Extension

The system SHALL extend the CanonicalAddress table with coordinate columns and spatial indexes.

#### Scenario: Coordinate column addition

- **WHEN** database schema is created or migrated
- **THEN** the system SHALL add Latitude REAL column
- **AND** add Longitude REAL column
- **AND** add GeocodingQuality TEXT column with CHECK constraint (exact/street/settlement/failed)
- **AND** add GeocodingSource TEXT column
- **AND** add GeocodedAt TIMESTAMP column

#### Scenario: PostGIS geometry column (optional)

- **WHEN** GEOCODING_USE_POSTGIS=true
- **THEN** the system SHALL add Geometry GEOGRAPHY(POINT, 4326) column
- **AND** populate from Latitude/Longitude using ST_GeogFromText
- **AND** create GIST spatial index on Geometry column

#### Scenario: Coordinate indexes

- **WHEN** coordinate columns are added
- **THEN** the system SHALL create composite index on (Latitude, Longitude)
- **AND** create index on GeocodingQuality for filtering
- **AND** skip NULL coordinate values in indexes

### Requirement: CSV Export with Coordinates

The system SHALL include coordinate data in CSV exports for canonical addresses.

#### Scenario: CSV column additions

- **WHEN** exporting canonical addresses to CSV
- **THEN** the system SHALL include Latitude column
- **AND** include Longitude column
- **AND** include GeocodingQuality column
- **AND** include GeocodingSource column
- **AND** include GeocodedAt timestamp column
- **AND** preserve existing column order with coordinates appended

#### Scenario: CSV export progress logging

- **WHEN** exporting large CSV files (>10,000 rows)
- **THEN** the system SHALL log progress every 100,000 rows
- **AND** display row count and percentage completion
- **AND** show processing rate (rows per second)
- **AND** display file size during write operations

### Requirement: PostgreSQL Export with Coordinates

The system SHALL include coordinate columns in PostgreSQL schema and data exports.

#### Scenario: PostgreSQL schema generation

- **WHEN** generating PostgreSQL DDL
- **THEN** the system SHALL include Latitude DOUBLE PRECISION column
- **AND** include Longitude DOUBLE PRECISION column
- **AND** include GeocodingQuality TEXT column with CHECK constraint
- **AND** include GeocodingSource TEXT column
- **AND** include GeocodedAt TIMESTAMP column
- **AND** create indexes on coordinates and quality

#### Scenario: PostgreSQL data export with coordinates

- **WHEN** generating PostgreSQL INSERT statements
- **THEN** the system SHALL include coordinate values in INSERT statements
- **AND** handle NULL coordinates correctly
- **AND** convert GeocodingQuality enum to text representation

#### Scenario: PostgreSQL import progress logging

- **WHEN** importing large SQL files to PostgreSQL (>10,000 rows)
- **THEN** the system SHALL log progress every 50,000 INSERT statements
- **AND** display row count imported and total rows
- **AND** show percentage completion
- **AND** display elapsed time and estimated time remaining
- **AND** log streaming progress for pg_dump operations

#### Scenario: PostGIS geography column export

- **WHEN** GEOCODING_USE_POSTGIS=true and exporting to PostgreSQL
- **THEN** the system SHALL include Geometry GEOGRAPHY(POINT, 4326) column in DDL
- **AND** generate UPDATE statements to populate Geometry from coordinates
- **AND** create GIST spatial index on Geometry column
- **AND** validate coordinate ranges before POINT creation

### Requirement: ETL Pipeline Integration

The system SHALL integrate geocoding as an optional stage in the main ETL pipeline.

#### Scenario: Geocoding stage execution

- **WHEN** NOMINATIM_ENABLED=true and pipeline runs
- **THEN** the system SHALL execute geocoding after deduplication stage
- **AND** geocode only addresses with NULL coordinates (incremental)
- **AND** log geocoding statistics to pipeline metrics
- **AND** continue pipeline on geocoding errors (non-blocking)

#### Scenario: Geocoding enabled by default

- **WHEN** NOMINATIM_ENABLED is not set or true
- **THEN** the system SHALL attempt to execute geocoding stage
- **AND** check if Nominatim service is available
- **AND** skip with warning if service unavailable
- **AND** proceed with export stage using existing coordinate data

#### Scenario: Geocoding explicitly disabled

- **WHEN** NOMINATIM_ENABLED is false
- **THEN** the system SHALL skip geocoding stage
- **AND** log "Geocoding disabled in configuration, skipping"
- **AND** proceed with export stage using existing coordinate data

#### Scenario: Incremental geocoding

- **WHEN** pipeline runs with existing geocoded addresses
- **THEN** the system SHALL query for addresses WHERE Latitude IS NULL
- **AND** geocode only new or failed addresses
- **AND** preserve existing geocoding results
- **AND** log count of addresses to geocode

### Requirement: CLI Geocoding Commands

The system SHALL provide command-line interface for geocoding operations.

#### Scenario: Geocode setup command

- **WHEN** user runs `python src/cli.py geocode setup`
- **THEN** the system SHALL start Nominatim Docker container
- **AND** wait for service to become healthy
- **AND** log progress during OSM data import
- **AND** support --force-reimport flag to rebuild from scratch

#### Scenario: Geocode run command

- **WHEN** user runs `python src/cli.py geocode run`
- **THEN** the system SHALL connect to database specified by --db-path
- **AND** execute batch geocoding with --batch-size parameter
- **AND** log final statistics on completion
- **AND** exit with non-zero code on critical errors

#### Scenario: Geocode status command

- **WHEN** user runs `python src/cli.py geocode status`
- **THEN** the system SHALL display total addresses count
- **AND** show geocoded count and percentage
- **AND** show pending count and percentage
- **AND** break down quality distribution (exact/street/settlement/failed)
- **AND** connect to database in read-only mode

### Requirement: Configuration Management

The system SHALL support environment-based configuration for all geocoding parameters.

#### Scenario: Nominatim service configuration

- **WHEN** system reads configuration
- **THEN** the system SHALL support NOMINATIM_ENABLED (default: true)
- **AND** support NOMINATIM_MODE (local/api, default: local)
- **AND** support NOMINATIM_BASE_URL (default: http://localhost:8081)
- **AND** support NOMINATIM_RATE_LIMIT (default: 0 for local)
- **AND** support NOMINATIM_TIMEOUT (default: 30 seconds)

#### Scenario: Batch processing configuration

- **WHEN** system configures batch processing
- **THEN** the system SHALL support NOMINATIM_BATCH_SIZE (default: 100)
- **AND** support NOMINATIM_CACHE_DIR (default: data/geocoding_cache)
- **AND** support NOMINATIM_RETRY_ATTEMPTS (default: 3)
- **AND** support NOMINATIM_MIN_QUALITY (default: street)

#### Scenario: Docker configuration

- **WHEN** system configures Nominatim Docker container
- **THEN** the system SHALL support NOMINATIM_CONTAINER_NAME (default: oevk-nominatim)
- **AND** support NOMINATIM_PORT (default: 8081)
- **AND** support NOMINATIM_PBF_URL (default: Hungary Geofabrik URL)
- **AND** support NOMINATIM_POSTGRES_PASSWORD

### Requirement: Error Handling and Retry Logic

The system SHALL handle geocoding errors gracefully with retry logic and comprehensive logging.

#### Scenario: Network timeout handling

- **WHEN** Nominatim request times out
- **THEN** the system SHALL retry up to NOMINATIM_RETRY_ATTEMPTS times
- **AND** use exponential backoff between retries (1s, 2s, 4s)
- **AND** log each retry attempt with timeout duration
- **AND** mark address as FAILED after exhausting retries

#### Scenario: Service unavailable handling

- **WHEN** Nominatim service returns 5xx error
- **THEN** the system SHALL log error with status code and response
- **AND** retry with exponential backoff
- **AND** continue processing remaining addresses
- **AND** include failed count in final statistics

#### Scenario: Invalid response handling

- **WHEN** Nominatim returns malformed JSON or unexpected format
- **THEN** the system SHALL log error with response content
- **AND** mark address as FAILED
- **AND** continue processing without crashing

#### Scenario: Coordinate validation

- **WHEN** parsing geocoding response
- **THEN** the system SHALL validate latitude is between -90 and 90
- **AND** validate longitude is between -180 and 180
- **AND** log warning for out-of-range coordinates
- **AND** mark address as FAILED if coordinates invalid

### Requirement: Data Quality Validation

The system SHALL validate geocoding results to ensure data quality.

#### Scenario: Hungary bounding box validation

- **WHEN** address is geocoded successfully
- **THEN** the system SHALL validate latitude between 45.7 and 48.6
- **AND** validate longitude between 16.1 and 22.9
- **AND** log warning for coordinates outside Hungary
- **AND** still store result but mark for manual review

#### Scenario: Duplicate coordinate detection

- **WHEN** multiple addresses have identical coordinates
- **THEN** the system SHALL allow duplicates (same building)
- **AND** log info when >10 addresses share coordinates
- **AND** support queries to find high-density coordinate clusters

#### Scenario: Geocoding success rate validation

- **WHEN** geocoding batch completes
- **THEN** the system SHALL calculate success rate (non-failed / total)
- **AND** log warning if success rate <95%
- **AND** identify patterns in failed addresses (missing streets, unusual formats)

### Requirement: Performance Optimization

The system SHALL optimize geocoding performance for 3.3M+ address dataset.

#### Scenario: Parallel batch processing

- **WHEN** NOMINATIM_PARALLEL_WORKERS > 1
- **THEN** the system SHALL process multiple batches concurrently
- **AND** respect NOMINATIM_RATE_LIMIT per worker
- **AND** aggregate statistics across workers
- **AND** avoid database write conflicts with locking

#### Scenario: Memory-efficient streaming

- **WHEN** processing large address datasets
- **THEN** the system SHALL use batch iteration (not load all in memory)
- **AND** keep memory usage under 500MB during geocoding
- **AND** release database connections between batches
- **AND** monitor memory with psutil and log if exceeding threshold

#### Scenario: Cache hit optimization

- **WHEN** running geocoding on previously processed data
- **THEN** the system SHALL achieve >90% cache hit rate
- **AND** skip Nominatim calls for cached addresses
- **AND** complete incremental runs in <5 minutes

### Requirement: Polling Station Geocoding with Fuzzy Search

The system SHALL geocode polling station addresses using multi-strategy approach with fuzzy search capabilities.

#### Scenario: Polling station schema extension

- **WHEN** database schema is extended for polling stations
- **THEN** the system SHALL add Latitude REAL column to PollingStation table
- **AND** add Longitude REAL column
- **AND** add GeocodingQuality TEXT column
- **AND** add GeocodingSource TEXT column (nominatim_local/nominatim_fuzzy/canonical_address/settlement_centroid)
- **AND** add GeocodedAt TIMESTAMP column
- **AND** add MatchedAddress TEXT column to store the matched address string
- **AND** create indexes on coordinates and quality

#### Scenario: Multi-strategy geocoding approach

- **WHEN** geocoding a polling station address
- **THEN** the system SHALL attempt Strategy 1: Exact Nominatim match
- **AND** if failed, attempt Strategy 2: Fuzzy tokenization and simplified address
- **AND** if failed, attempt Strategy 3: Canonical address matching with similarity
- **AND** if failed, attempt Strategy 4: Settlement centroid fallback
- **AND** log which strategy succeeded for each station

#### Scenario: Exact Nominatim match for polling stations

- **WHEN** attempting Strategy 1 (exact match)
- **THEN** the system SHALL send full PollingStationAddress to Nominatim
- **AND** combine with settlement name for context
- **AND** mark as GeocodingSource="nominatim_local" if successful
- **AND** proceed to Strategy 2 if no match found

#### Scenario: Fuzzy tokenization of composite addresses

- **WHEN** attempting Strategy 2 (fuzzy tokenization)
- **THEN** the system SHALL extract address components from polling station address
- **AND** remove institution keywords (iskola, hivatal, művelődési ház, etc.)
- **AND** extract street patterns using regex (name + type + number)
- **AND** send simplified address to Nominatim
- **AND** mark as GeocodingSource="nominatim_fuzzy" if successful

#### Scenario: Institution keyword removal

- **WHEN** performing fuzzy tokenization
- **THEN** the system SHALL remove "általános iskola" from address
- **AND** remove "gimnázium", "szakközépiskola"
- **AND** remove "művelődési ház", "közösségi ház", "kultúrház"
- **AND** remove "polgármesteri hivatal", "önkormányzat"
- **AND** remove "óvoda", "könyvtár", "sportcsarnok"
- **AND** preserve street name, type, and number

#### Scenario: Street pattern extraction

- **WHEN** extracting address components
- **THEN** the system SHALL match pattern [Name] [Type] [Number]
- **AND** recognize Hungarian street types (utca, út, tér, köz, körút, sétány, park, sor)
- **AND** extract house numbers with suffixes (10/A, 5-7, etc.)
- **AND** return simplified address like "Petőfi utca 10"

#### Scenario: Canonical address matching with similarity

- **WHEN** attempting Strategy 3 (canonical matching)
- **THEN** the system SHALL query CanonicalAddress table filtered by Settlement_ID
- **AND** calculate Levenshtein similarity ratio between addresses
- **AND** use similarity threshold ≥0.6 for match acceptance
- **AND** order results by similarity descending
- **AND** use coordinates from best matching canonical address
- **AND** mark as GeocodingSource="canonical_address" with MatchedAddress

#### Scenario: Levenshtein similarity calculation

- **WHEN** calculating address similarity
- **THEN** the system SHALL normalize both addresses to lowercase
- **AND** compute Levenshtein distance
- **AND** calculate similarity as 1.0 - (distance / max_length)
- **AND** only consider addresses with GeocodingQuality='exact' or 'street'
- **AND** require Latitude IS NOT NULL for candidate addresses

#### Scenario: Settlement centroid fallback

- **WHEN** attempting Strategy 4 (settlement fallback)
- **THEN** the system SHALL calculate average latitude of geocoded addresses in settlement
- **AND** calculate average longitude of geocoded addresses in settlement
- **AND** only use addresses with quality='exact' or 'street'
- **AND** mark result as GeocodingQuality.SETTLEMENT
- **AND** mark as GeocodingSource="settlement_centroid"
- **AND** store settlement name in MatchedAddress

#### Scenario: All strategies failed

- **WHEN** all four strategies fail to geocode polling station
- **THEN** the system SHALL mark as GeocodingQuality.FAILED
- **AND** store NULL for latitude and longitude
- **AND** mark as GeocodingSource="all_strategies_failed"
- **AND** store NULL for MatchedAddress
- **AND** log warning with station details
- **AND** continue processing remaining stations

#### Scenario: Polling station progress logging

- **WHEN** batch geocoding polling stations
- **THEN** the system SHALL log progress every 10 batches
- **AND** display statistics for each strategy (exact/fuzzy/canonical/settlement/failed)
- **AND** show percentage for each strategy type
- **AND** log batch number and total batches

#### Scenario: Polling station final statistics

- **WHEN** polling station geocoding completes
- **THEN** the system SHALL log comprehensive final statistics
- **AND** display total stations processed
- **AND** show exact match count and percentage (Strategy 1)
- **AND** show fuzzy match count and percentage (Strategy 2)
- **AND** show canonical match count and percentage (Strategy 3)
- **AND** show settlement fallback count and percentage (Strategy 4)
- **AND** show failed count and percentage

#### Scenario: Polling station PostGIS geometry

- **WHEN** GEOCODING_USE_POSTGIS=true for polling stations
- **THEN** the system SHALL add Geometry GEOGRAPHY(POINT, 4326) column
- **AND** populate from Latitude/Longitude using ST_GeogFromText
- **AND** create GIST spatial index on Geometry column
- **AND** enable spatial queries like nearest polling station

### Requirement: PostGIS Spatial Data Support

The system SHALL support PostGIS GEOGRAPHY columns for advanced spatial queries and GIS tool integration.

#### Scenario: PostGIS extension requirement

- **WHEN** PostGIS support is enabled
- **THEN** the system SHALL require PostgreSQL 12+ with PostGIS 3.0+
- **AND** recommend `postgis/postgis:15-3.3` Docker image
- **AND** create PostGIS extension if not exists
- **AND** use SRID 4326 (WGS 84) coordinate system

#### Scenario: GEOGRAPHY column creation

- **WHEN** GEOCODING_USE_POSTGIS=true
- **THEN** the system SHALL add Geometry GEOGRAPHY(POINT, 4326) column to CanonicalAddress
- **AND** add Geometry GEOGRAPHY(POINT, 4326) column to PollingStation
- **AND** populate using ST_GeogFromText('POINT(lon lat)')
- **AND** create GIST spatial indexes on geometry columns

#### Scenario: Coordinate system transformation

- **WHEN** inserting coordinates into GEOGRAPHY columns
- **THEN** the system SHALL use SRID 4326 (WGS 84) coordinate system
- **AND** store coordinates in longitude, latitude order
- **AND** validate latitude range -90 to 90
- **AND** validate longitude range -180 to 180
- **AND** specifically validate Hungary bounding box (lat: 45.7-48.6, lon: 16.1-22.9)

#### Scenario: GIST spatial index creation

- **WHEN** creating spatial indexes
- **THEN** the system SHALL use GIST index type for GEOGRAPHY columns
- **AND** create idx_CanonicalAddress_Geometry index
- **AND** create idx_PollingStation_Geometry index
- **AND** enable efficient spatial queries (point-in-polygon, distance)

#### Scenario: Spatial query support

- **WHEN** PostGIS is enabled
- **THEN** the system SHALL support ST_Contains for point-in-polygon queries
- **AND** support ST_Distance for distance calculations
- **AND** support ST_DWithin for radius searches
- **AND** support ST_Transform for coordinate system transformation
- **AND** enable export to GeoJSON format

#### Scenario: GIS tool integration

- **WHEN** data is exported with PostGIS support
- **THEN** the system SHALL be compatible with QGIS import
- **AND** be compatible with ArcGIS import
- **AND** support OGC Simple Features specification
- **AND** provide standard WKT (Well-Known Text) format

#### Scenario: Backward compatibility with TEXT columns

- **WHEN** PostGIS support is optional
- **THEN** the system SHALL keep existing Latitude/Longitude REAL columns
- **AND** populate both REAL and GEOGRAPHY columns
- **AND** allow applications to choose which format to use
- **AND** support disabling PostGIS with GEOCODING_USE_POSTGIS=false

### Requirement: Fuzzy Search Performance

The system SHALL optimize fuzzy search operations for polling station geocoding.

#### Scenario: Settlement-scoped matching

- **WHEN** matching against CanonicalAddress
- **THEN** the system SHALL filter by Settlement_ID before similarity calculation
- **AND** reduce search space to addresses in same settlement
- **AND** improve performance by avoiding full table scan

#### Scenario: Index utilization

- **WHEN** performing canonical address lookups
- **THEN** the system SHALL use Settlement_ID index for initial filtering
- **AND** use GeocodingQuality index to filter for exact/street matches
- **AND** use Latitude index to filter out NULL coordinates

#### Scenario: Similarity threshold tuning

- **WHEN** configuring fuzzy matching
- **THEN** the system SHALL support NOMINATIM_SIMILARITY_THRESHOLD (default: 0.6)
- **AND** allow adjustment between 0.0 (match anything) and 1.0 (exact match)
- **AND** recommend 0.6 for balanced precision/recall
- **AND** log similarity score for matched addresses in debug mode
