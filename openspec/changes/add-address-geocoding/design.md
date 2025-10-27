# Address Geocoding Design

## Context

The OEVK data processing pipeline currently handles 3.3M+ Hungarian addresses without geographic coordinates. This design adds geocoding capabilities using OpenStreetMap data via Nominatim, with special handling for both canonical addresses and polling station addresses.

**Key Challenges:**
1. Geocoding 3.3M+ addresses efficiently (minimize API calls, cache results)
2. Handling composite institutional addresses for polling stations
3. Providing comprehensive progress logging for long-running operations
4. Supporting optional PostGIS integration for spatial queries
5. Maintaining backward compatibility with existing exports

**Stakeholders:**
- Data analysts requiring geospatial analysis capabilities
- GIS tool users (QGIS, ArcGIS) needing spatial data
- Electoral research requiring distance-based queries
- Pipeline users needing progress visibility

## Goals / Non-Goals

### Goals
- ✅ Geocode canonical addresses with ≥95% success rate
- ✅ Geocode polling stations with ≥90% success rate using fuzzy search
- ✅ Provide real-time progress logging with ETA
- ✅ Support PostGIS GEOGRAPHY columns for spatial queries
- ✅ Maintain idempotent processing (cache results)
- ✅ Optional geocoding stage (disabled by default)
- ✅ Export coordinates in CSV and PostgreSQL formats

### Non-Goals
- ❌ Real-time geocoding API (batch processing only)
- ❌ Address validation or correction
- ❌ Reverse geocoding (coordinates → addresses)
- ❌ Alternative geocoding services (Google Maps, etc.)
- ❌ Custom address normalization beyond existing logic

## Architecture Decisions

### Decision 1: Local Nominatim vs. Public API

**Choice:** Local Nominatim instance in Docker

**Rationale:**
- **No rate limits**: Can process 3.3M addresses without throttling
- **Privacy**: No data leaves local environment
- **Cost**: Free, no API quotas or billing
- **Performance**: Low latency (~10-100ms vs 1000ms+ for remote)
- **Reliability**: No dependency on external service availability

**Trade-offs:**
- **Setup time**: 1-2 hours for Hungary OSM import (one-time)
- **Storage**: ~15-20GB for Hungary data
- **Memory**: Requires 4-8GB RAM

**Alternatives Considered:**
1. **Nominatim Public API**: Rejected due to rate limits (1 req/sec), would take 38+ days
2. **Google Maps Geocoding API**: Rejected due to cost ($5/1000 requests = $16,500 for 3.3M)
3. **Batch geocoding services**: Rejected due to data privacy and cost concerns

### Decision 2: Multi-Strategy Polling Station Geocoding

**Choice:** 4-strategy waterfall approach with fuzzy search

**Rationale:**
- **Composite addresses**: Polling stations often have institution names + street addresses
- **Quality degradation**: Fallback from exact → fuzzy → canonical → settlement
- **High coverage**: Multiple strategies increase success rate
- **Transparent matching**: MatchedAddress column tracks which address was used

**Strategies:**
1. **Exact Nominatim match**: Try full address string first
2. **Fuzzy tokenization**: Remove institution keywords, extract street patterns
3. **Canonical address matching**: Levenshtein similarity against geocoded addresses
4. **Settlement centroid**: Use average of addresses in settlement

**Trade-offs:**
- **Complexity**: More code to maintain vs. single-strategy approach
- **Performance**: Multiple attempts per failed address (mitigated by success rate)
- **Quality variance**: Different strategies have different accuracy levels

**Alternatives Considered:**
1. **Single-strategy only**: Rejected, would have low success rate (~50%)
2. **Machine learning**: Rejected as over-engineering for this use case
3. **Manual correction UI**: Future enhancement, not in scope

### Decision 3: Progress Logging Strategy

**Choice:** Multi-level structured logging with statistics

**Rationale:**
- **Long-running operations**: Geocoding can take 9-90 minutes
- **User feedback**: Progress updates prevent "is it working?" questions
- **Debugging**: Detailed logs help diagnose failures
- **Performance monitoring**: Track cache hit rates, processing rates

**Logging Levels:**
1. **Batch progress** (every 10 batches): Current batch, percentages, statistics
2. **Final statistics**: Comprehensive summary with quality breakdown
3. **Export progress** (every 50K-100K rows): Row counts, percentages
4. **Memory tracking**: Log if usage exceeds 500MB threshold

**Format:**
```
Progress: 10,000 addresses | Cached: 9,000 (90.0%) | Exact: 800 (8.0%) | Failed: 200 (2.0%)
Batch 50/331 (15.1%) | ETA: 45 minutes | Rate: 120 addr/sec
```

**Trade-offs:**
- **Log verbosity**: More frequent logging increases output (mitigated by batch intervals)
- **Performance overhead**: Logging has minimal impact (<1% overhead)

**Alternatives Considered:**
1. **Progress bar library (tqdm)**: Rejected to maintain simple logging infrastructure
2. **Event-driven progress**: Rejected as over-engineering

### Decision 4: Caching Strategy

**Choice:** File-based cache with MD5 keys

**Rationale:**
- **Idempotency**: Same address always produces same result
- **Performance**: 90%+ cache hit rate on subsequent runs
- **Persistence**: Cache survives pipeline restarts
- **Simplicity**: No external dependencies (Redis, etc.)

**Cache Key:** MD5 hash of `settlement_name|street_name|house_number`

**Cache Storage:** JSON files in `data/geocoding_cache/`

**Trade-offs:**
- **Disk usage**: ~50MB for 3.3M cached addresses (acceptable)
- **Cache invalidation**: Manual deletion required if OSM data changes significantly

**Alternatives Considered:**
1. **In-memory cache**: Rejected, doesn't persist between runs
2. **Redis**: Rejected as over-engineering, adds dependency
3. **Database table**: Rejected, want cache separate from pipeline data

### Decision 5: PostGIS Integration

**Choice:** Optional GEOGRAPHY columns alongside REAL columns

**Rationale:**
- **Backward compatibility**: Keep Latitude/Longitude REAL columns
- **GIS tools**: GEOGRAPHY enables QGIS/ArcGIS import
- **Spatial queries**: Enable distance calculations, point-in-polygon
- **Optional**: Can disable with `GEOCODING_USE_POSTGIS=false`

**Schema Design:**
```sql
-- Dual format support
Latitude REAL,              -- Simple numeric format
Longitude REAL,             -- Simple numeric format
Geometry GEOGRAPHY(POINT, 4326)  -- PostGIS format (optional)
```

**Trade-offs:**
- **Storage overhead**: ~50% increase (100MB → 150MB for addresses)
- **Complexity**: Must populate both formats during export

**Alternatives Considered:**
1. **GEOGRAPHY only**: Rejected, breaks compatibility with non-PostGIS consumers
2. **TEXT format**: Rejected, already moving away from TEXT for OEVK polygons
3. **Separate PostGIS table**: Rejected as redundant, adds complexity

### Decision 6: Levenshtein Similarity for Canonical Matching

**Choice:** String similarity with 0.6 threshold

**Rationale:**
- **Fuzzy matching**: Handles typos, variations in polling station addresses
- **Performance**: DuckDB has built-in `levenshtein()` function
- **Threshold tuning**: 0.6 balances precision (false positives) vs recall (false negatives)

**Similarity Calculation:**
```
similarity = 1.0 - (levenshtein_distance / max_length)
```

**Trade-offs:**
- **Performance**: Levenshtein is O(n*m) but scoped to settlement (typically <1000 addresses)
- **False positives**: Threshold too low matches incorrect addresses
- **False negatives**: Threshold too high misses valid matches

**Alternatives Considered:**
1. **Trigram similarity (pg_trgm)**: Rejected, DuckDB doesn't have native support
2. **Exact match only**: Rejected, too restrictive for composite addresses
3. **Jaro-Winkler distance**: Rejected, Levenshtein is sufficient

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  Address Geocoding Pipeline                  │
└─────────────────────────────────────────────────────────────┘

1. CANONICAL ADDRESS GEOCODING
   ┌──────────────────┐
   │ CanonicalAddress │
   │ (3.3M records)   │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Check Cache     │───────► Cache Hit (90%+)
   │  (MD5 key)       │         └─► Use cached coordinates
   └────────┬─────────┘
            │ Cache Miss
            ▼
   ┌──────────────────┐
   │ Nominatim Query  │
   │ (structured)     │
   │ street=...       │
   │ city=...         │
   │ countrycodes=hu  │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ Parse GeoJSON    │
   │ Determine Quality│
   │ (exact/street/   │
   │  settlement)     │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ Save to Cache    │
   │ Update Database  │
   └──────────────────┘

2. POLLING STATION GEOCODING
   ┌──────────────────┐
   │ PollingStation   │
   │ (8,555 records)  │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────────────────────────────────┐
   │        Multi-Strategy Waterfall              │
   ├──────────────────────────────────────────────┤
   │                                              │
   │  Strategy 1: Exact Nominatim Match          │
   │  ├─► Try full address string                │
   │  └─► If success: source="nominatim_local"   │
   │                                              │
   │  Strategy 2: Fuzzy Tokenization (if failed) │
   │  ├─► Remove institution keywords            │
   │  ├─► Extract street pattern (regex)         │
   │  ├─► Try simplified address                 │
   │  └─► If success: source="nominatim_fuzzy"   │
   │                                              │
   │  Strategy 3: Canonical Matching (if failed) │
   │  ├─► Query CanonicalAddress by Settlement   │
   │  ├─► Calculate Levenshtein similarity       │
   │  ├─► Match if similarity ≥ 0.6             │
   │  └─► If success: source="canonical_address" │
   │                                              │
   │  Strategy 4: Settlement Fallback (if failed)│
   │  ├─► Calculate average lat/lon in settlement│
   │  ├─► Quality = SETTLEMENT                   │
   │  └─► source="settlement_centroid"           │
   │                                              │
   │  All Failed: Mark as FAILED                 │
   └──────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────┐
   │ Update Database  │
   │ + MatchedAddress │
   └──────────────────┘

3. EXPORT INTEGRATION
   ┌──────────────────────────────────────────┐
   │                                          │
   │  CSV Export                              │
   │  ├─► Add coordinate columns              │
   │  ├─► Log progress every 100K rows        │
   │  └─► Export: Address_{settlement}.csv    │
   │                                          │
   │  PostgreSQL Export                       │
   │  ├─► Add REAL columns (Lat/Lon)          │
   │  ├─► Add GEOGRAPHY columns (optional)    │
   │  ├─► ST_GeogFromText('POINT(lon lat)')   │
   │  ├─► Create GIST spatial indexes         │
   │  ├─► Log progress every 50K inserts      │
   │  └─► Export: schema.sql + data.sql       │
   │                                          │
   └──────────────────────────────────────────┘
```

## Performance Considerations

### Geocoding Performance

**Canonical Addresses (3.3M):**
- **First run**: 9-90 minutes (depends on batch size, concurrency)
  - Optimistic: 100 req/sec × 3.3M = 9 hours → batched ~9 min
  - Realistic: 10-30 req/sec × 3.3M = 30-90 minutes
- **Incremental run**: <5 minutes (90%+ cache hit rate)

**Polling Stations (8,555):**
- **First run**: 5-15 minutes (multi-strategy overhead)
- **Incremental run**: <1 minute

### Memory Profile

- **DuckDB**: ~34MB baseline (existing)
- **Geocoding**: ~200MB for address batches
- **Cache**: ~50MB for 3.3M JSON files
- **Peak**: ~300MB total (well under 500MB threshold)

### Storage Impact

- **Coordinate columns**: ~50MB (REAL × 2 × 3.3M addresses)
- **PostGIS GEOGRAPHY**: ~75MB (additional overhead)
- **Cache directory**: ~50MB (JSON files)
- **Total**: ~175MB additional storage

### Export Performance

**CSV Export:**
- **Baseline**: ~2 minutes for 3.3M addresses
- **With coordinates**: ~2.4 minutes (+20% acceptable)
- **Progress logging**: Minimal overhead (<1%)

**PostgreSQL Export:**
- **Schema generation**: <1 second
- **Data file generation**: ~3-4 minutes
- **Import to PostgreSQL**: ~5-10 minutes (with indexes)
- **Total**: ~15 minutes (acceptable for batch processing)

## Risks / Trade-offs

### Risk 1: Nominatim Setup Complexity

**Risk:** Users may struggle with Docker setup or Hungary OSM import

**Mitigation:**
- Provide automated `geocode setup` CLI command
- Include health check monitoring with progress logging
- Document troubleshooting steps
- Gracefully skip if Nominatim unavailable (with warning)
- Can be explicitly disabled with NOMINATIM_ENABLED=false

### Risk 2: Low Geocoding Success Rate

**Risk:** May not achieve ≥95% success rate target

**Mitigation:**
- Multi-strategy approach for polling stations
- Quality thresholds (can accept street-level matches)
- Settlement fallback prevents complete failures
- Monitor success rate and adjust strategies

**Acceptance Criterion:** ≥90% combined success (exact + street + settlement)

### Risk 3: Coordinate Accuracy

**Risk:** Nominatim coordinates may be inaccurate for some addresses

**Mitigation:**
- OSM data quality for Hungary is generally high (~80% house-level)
- Store GeocodingQuality to track confidence
- Hungary bounding box validation prevents gross errors
- Manual review possible via MatchedAddress column

### Risk 4: Performance Degradation

**Risk:** Geocoding may slow down pipeline unacceptably

**Mitigation:**
- Geocoding can be disabled (NOMINATIM_ENABLED=false flag)
- Gracefully skips if service unavailable
- Cache ensures subsequent runs are fast (<5 min)
- Batch processing with parallelization potential
- Monitor and log performance metrics

## Migration Plan

### Phase 1: Schema Migration (Non-breaking)

```sql
-- Add columns to existing tables
ALTER TABLE CanonicalAddress ADD COLUMN Latitude REAL;
ALTER TABLE CanonicalAddress ADD COLUMN Longitude REAL;
ALTER TABLE CanonicalAddress ADD COLUMN GeocodingQuality TEXT;
ALTER TABLE CanonicalAddress ADD COLUMN GeocodingSource TEXT;
ALTER TABLE CanonicalAddress ADD COLUMN GeocodedAt TIMESTAMP;

-- Same for PollingStation
-- ...

-- Existing data: NULL coordinates (no data loss)
```

### Phase 2: Geocoding Execution (Enabled by Default)

```bash
# Setup Nominatim service (one-time)
python src/cli.py geocode setup

# Run pipeline with geocoding enabled (default)
python src/cli.py run

# Or geocode explicitly
python src/cli.py geocode run

# Disable geocoding if needed
export NOMINATIM_ENABLED=false
python src/cli.py run
```

### Phase 3: Export Integration (Automatic)

- CSV exports automatically include coordinate columns (NULL if not geocoded)
- PostgreSQL exports include coordinate columns
- PostGIS support optional (GEOCODING_USE_POSTGIS flag)

### Rollback Plan

```bash
# Disable geocoding
export NOMINATIM_ENABLED=false

# Remove coordinate columns (if needed)
ALTER TABLE CanonicalAddress 
  DROP COLUMN Latitude,
  DROP COLUMN Longitude,
  DROP COLUMN GeocodingQuality,
  DROP COLUMN GeocodingSource,
  DROP COLUMN GeocodedAt,
  DROP COLUMN Geometry;
```

## Open Questions

1. **OSM Data Updates**: How often should Hungary OSM data be refreshed?
   - **Answer**: Annually or when significant address changes occur (new developments)

2. **Geocoding Retry Policy**: Should failed addresses be retried in subsequent runs?
   - **Answer**: Yes, always geocode WHERE Latitude IS NULL (incremental)

3. **Quality Threshold**: Should we reject settlement-level matches?
   - **Answer**: No, accept all quality levels, filter on GeocodingQuality in queries

4. **Parallel Processing**: Should we support concurrent Nominatim requests?
   - **Answer**: Future enhancement, start with sequential (no rate limit anyway)

5. **Alternative Data Sources**: Should we support fallback to other geocoders?
   - **Answer**: Not in initial implementation, but design allows future extension

## References

- **Nominatim Documentation**: https://nominatim.org/release-docs/latest/
- **PostGIS Documentation**: https://postgis.net/docs/
- **OpenStreetMap Hungary**: https://download.geofabrik.de/europe/hungary.html
- **SRID 4326 (WGS 84)**: https://epsg.io/4326
- **Levenshtein Distance**: https://en.wikipedia.org/wiki/Levenshtein_distance
- **GeoJSON Format**: https://geojson.org/
- **OGC Simple Features**: https://www.ogc.org/standards/sfa

## Appendix: Configuration Matrix

| Configuration | Default | Purpose |
|--------------|---------|---------|
| `NOMINATIM_ENABLED` | `true` | Enable/disable geocoding stage |
| `NOMINATIM_MODE` | `local` | Local vs API mode |
| `NOMINATIM_BASE_URL` | `http://localhost:8081` | Nominatim endpoint |
| `NOMINATIM_BATCH_SIZE` | `100` | Addresses per batch |
| `NOMINATIM_RATE_LIMIT` | `0` | Requests per second (0 = no limit) |
| `NOMINATIM_TIMEOUT` | `30` | Request timeout (seconds) |
| `NOMINATIM_CACHE_DIR` | `data/geocoding_cache` | Cache storage location |
| `NOMINATIM_RETRY_ATTEMPTS` | `3` | Retry failed requests |
| `NOMINATIM_MIN_QUALITY` | `street` | Minimum acceptable quality |
| `NOMINATIM_SIMILARITY_THRESHOLD` | `0.6` | Fuzzy match threshold |
| `GEOCODING_USE_POSTGIS` | `true` | Enable PostGIS GEOGRAPHY columns |
| `NOMINATIM_CONTAINER_NAME` | `oevk-nominatim` | Docker container name |
| `NOMINATIM_PORT` | `8081` | Nominatim service port |
| `NOMINATIM_PBF_URL` | Geofabrik Hungary | OSM data source |

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-24  
**Status**: Proposed
