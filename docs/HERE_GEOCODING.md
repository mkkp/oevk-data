<!--
DOCUMENT METADATA
=================
Title: HERE Geocoding API Integration
Type: Technical Documentation
Category: Geocoding
Status: Active
Version: 1.0
Created: 2025-11-09
Last Updated: 2025-11-09
Author: Project Team

Related Documents:
- GEOCODING_INTERPOLATION.md (Post-processing interpolation)
- 011_RESOLVE_ADDRESS_COORDINATE.md (Address geocoding specification)
- README.md (Project overview)

Related Code:
- src/etl/geocoding.py (HereGeocoder class)
- src/utils/config.py (Configuration management)
- test_here_geocoding.py (Test suite)

Dependencies:
- HERE Geocoding & Search API v8
- requests library
- Polars DataFrame library

Keywords: here-api, geocoding, fallback, api-integration, address-quality, commercial-geocoding

Summary:
HERE Geocoding API integration as a post-processing fallback for addresses that failed or have low-quality results from Nominatim. Provides commercial-grade geocoding to improve coverage and quality, with configurable retry strategies and rate limiting. Free tier: 250,000 queries/month.

Audience:
Developers, system administrators, data engineers
-->

# HERE Geocoding API Integration

## Overview

The HERE Geocoding API integration provides a commercial-grade geocoding fallback for addresses that failed or received low-quality results from Nominatim. HERE offers superior coverage and quality for many addresses, especially in complex urban areas.

### Key Features

- **Post-processing fallback**: Runs after Nominatim and interpolation
- **Quality-based retry**: Configurable minimum quality threshold
- **Smart quality upgrade**: Only replaces Nominatim results if HERE is better
- **Rate limiting**: Respects free tier limits (5 req/sec)
- **Parallel processing**: Multi-threaded API requests
- **Free tier**: 250,000 queries/month included

## API Information

### HERE Geocoding & Search API v8

- **Endpoint**: `https://geocode.search.hereapi.com/v1/geocode`
- **Documentation**: https://www.here.com/docs/bundle/geocoding-and-search-api-developer-guide
- **Authentication**: API key
- **Free Tier**: 250,000 queries/month
- **Pricing**: $1 per 1,000 queries after free tier
- **Rate Limit**: 5 requests/second (free tier)

### Account Setup

1. **Create HERE Account**
   - Visit: https://platform.here.com/sign-up
   - Sign up for free developer account

2. **Create Project**
   - Go to Projects dashboard
   - Click "Create Project"
   - Name your project (e.g., "OEVK Geocoding")

3. **Generate API Key**
   - In your project, go to "Credentials"
   - Click "Generate API Key"
   - Copy the API key (starts with lowercase letters/numbers)
   - **Important**: Save this key securely - it won't be shown again

4. **Enable Geocoding Service**
   - In project settings, enable "Geocoding & Search API"
   - Accept terms of service

## Configuration

### Environment Variables

```bash
# Enable HERE geocoding fallback
export HERE_ENABLED=true

# Set your API key
export HERE_API_KEY='your-api-key-here'

# Optional: Customize settings
export HERE_RATE_LIMIT=5              # Requests per second (default: 5)
export HERE_MAX_WORKERS=4             # Parallel threads (default: 4)
export HERE_TIMEOUT=30                # Request timeout in seconds (default: 30)
export HERE_MIN_QUALITY_TO_RETRY=settlement  # Retry threshold (default: settlement)
```

### Configuration File (.env)

```ini
# HERE Geocoding Configuration
HERE_ENABLED=true
HERE_API_KEY=your-api-key-here
HERE_RATE_LIMIT=5
HERE_MAX_WORKERS=4
HERE_TIMEOUT=30
HERE_MIN_QUALITY_TO_RETRY=settlement
```

### Configuration Options

**`HERE_ENABLED`** (boolean, default: `false`)
- Enable/disable HERE geocoding fallback
- Set to `true` to activate

**`HERE_API_KEY`** (string, required if enabled)
- Your HERE API key
- Get from https://platform.here.com

**`HERE_RATE_LIMIT`** (integer, default: `5`)
- Maximum requests per second
- Free tier limit: 5 req/sec
- Adjust based on your plan

**`HERE_MAX_WORKERS`** (integer, default: `4`)
- Number of parallel worker threads
- Conservative default to respect rate limits
- Formula: `max_workers × rate_limit` = max concurrent req/sec

**`HERE_TIMEOUT`** (integer, default: `30`)
- Request timeout in seconds
- Increase if experiencing timeout errors

**`HERE_MIN_QUALITY_TO_RETRY`** (string, default: `"settlement"`)
- Minimum quality level to retry with HERE
- Options:
  - `"failed"`: Only retry failed addresses
  - `"settlement"`: Retry failed + settlement-level (default)
  - `"street"`: Retry failed + settlement + street-level
  - `"exact"`: Retry all addresses (expensive!)

## Usage

### Integration with Pipeline

HERE geocoding runs automatically as part of the geocoding pipeline:

```bash
# Run full geocoding pipeline with HERE fallback
export HERE_ENABLED=true
export HERE_API_KEY='your-key'
python -m src.cli geocode run
```

### Execution Flow

```
1. Nominatim Geocoding
   ↓ (produces initial results)
2. Post-Processing Interpolation
   ↓ (upgrades street-level to exact)
3. HERE Geocoding Fallback  ← HERE runs here
   ↓ (improves failed/low-quality)
4. Database Update
   ↓
5. Complete
```

### Example Output

```
Applying HERE geocoding fallback (retry_failed=True, retry_settlement=True, retry_street=False)
Retrying 52,341 addresses with HERE geocoding...
HERE Geocoder initialized (rate_limit=5 req/sec)
Geocoding 52,341 addresses with HERE API
HERE Geocoding complete: 52,341 addresses | Success: 48,234 (92.2%) | Exact: 12,345 (23.6%) | Street: 35,889 (68.6%) | Settlement: 0 (0.0%) | Failed: 4,107 (7.8%)
HERE fallback complete: 45,127 addresses improved (86.2% of retried)
```

## How It Works

### Smart Quality Upgrade

HERE only replaces Nominatim results if the quality is better:

| Nominatim Quality | HERE Quality | Action |
|-------------------|--------------|--------|
| Failed | Exact | ✓ Replace |
| Failed | Street | ✓ Replace |
| Failed | Settlement | ✓ Replace |
| Settlement | Exact | ✓ Replace |
| Settlement | Street | ✓ Replace |
| Street | Exact | ✓ Replace |
| Street | Street | ✗ Keep Nominatim |
| Exact | Any | ✗ Keep Nominatim |

### Quality Determination

HERE API returns `resultType` which maps to quality levels:

| HERE resultType | OEVK Quality | Description |
|-----------------|--------------|-------------|
| `houseNumber` | Exact | House-level precision |
| `street` | Street | Street-level precision |
| `locality`, `place` | Settlement | Settlement-level |
| No results | Failed | No match found |

### Example Request

```http
GET https://geocode.search.hereapi.com/v1/geocode?q=Andrássy+út+1,+Budapest,+Hungary&apiKey=YOUR_KEY&limit=1&lang=hu
```

Response:
```json
{
  "items": [
    {
      "title": "Andrássy út 1, 1061 Budapest, Hungary",
      "resultType": "houseNumber",
      "position": {
        "lat": 47.50299,
        "lng": 19.05399
      },
      "address": {
        "label": "Andrássy út 1, 1061 Budapest, Hungary",
        "countryCode": "HUN",
        "city": "Budapest",
        "street": "Andrássy út",
        "houseNumber": "1"
      }
    }
  ]
}
```

## Performance

### Rate Limiting

With default settings:
- Rate limit: 5 req/sec
- Workers: 4 threads
- Effective throughput: ~4.5 req/sec (accounting for network latency)

### Timing Estimates

| Addresses to Retry | Time (5 req/sec) | Time (10 req/sec*) |
|--------------------|------------------|---------------------|
| 1,000 | ~3.5 minutes | ~2 minutes |
| 10,000 | ~35 minutes | ~17 minutes |
| 50,000 | ~3 hours | ~1.5 hours |
| 100,000 | ~5.5 hours | ~2.8 hours |

\* Requires paid plan

### Cost Estimates

Free tier: 250,000 queries/month

| Scenario | Queries | Free Tier | Cost (if over) |
|----------|---------|-----------|----------------|
| Failed only (~1,329) | 1,329 | ✓ Free | - |
| Failed + Settlement (~47,851) | 47,851 | ✓ Free | - |
| Failed + Settlement + Street (~534,837) | 534,837 | First 250K free | $284.84/run |

**Recommendation**: Use `min_quality_to_retry=settlement` to stay within free tier.

## Testing

### Run Test Suite

```bash
# Basic test (no API key needed)
python test_here_geocoding.py

# Test with real API
export HERE_API_KEY='your-key'
python test_here_geocoding.py
```

### Test Output

```
HERE Geocoding Integration Test Suite
================================================================================

✓ PASS: Configuration
✓ PASS: Mock Initialization
✓ PASS: Real API

Total: 3/3 tests passed
```

### Manual API Test

```bash
# Test a single address
curl "https://geocode.search.hereapi.com/v1/geocode?q=Andrássy+út+1,+Budapest,+Hungary&apiKey=YOUR_KEY&limit=1"
```

## Monitoring

### Check Coverage Improvement

Before HERE fallback:
```sql
SELECT 
    GeocodingQuality,
    COUNT(*) as Count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as Percentage
FROM CanonicalAddress
GROUP BY GeocodingQuality
ORDER BY Count DESC;
```

After HERE fallback (source will show `here_api`):
```sql
SELECT 
    GeocodingQuality,
    GeocodingSource,
    COUNT(*) as Count
FROM CanonicalAddress
WHERE GeocodingSource = 'here_api'
GROUP BY GeocodingQuality, GeocodingSource;
```

### Log Analysis

```bash
# Check HERE statistics
grep "HERE" logs/oevk_transform_*.log | grep -E "(fallback|complete|improved)"

# Example output:
# Applying HERE geocoding fallback (retry_failed=True, retry_settlement=True, retry_street=False)
# Retrying 52,341 addresses with HERE geocoding...
# HERE Geocoding complete: 52,341 addresses | Success: 48,234 (92.2%)
# HERE fallback complete: 45,127 addresses improved (86.2% of retried)
```

## Troubleshooting

### Error: "HERE API key not configured"

**Solution**: Set `HERE_API_KEY` environment variable
```bash
export HERE_API_KEY='your-key-here'
```

### Error: 401 Unauthorized

**Cause**: Invalid or expired API key

**Solution**: 
1. Verify API key in HERE platform
2. Generate new API key if needed
3. Check that Geocoding & Search API is enabled

### Error: 429 Too Many Requests

**Cause**: Rate limit exceeded

**Solution**: 
1. Reduce `HERE_MAX_WORKERS`
2. Reduce `HERE_RATE_LIMIT`
3. Upgrade to paid plan for higher limits

### Slow Performance

**Cause**: Rate limiting or network latency

**Solution**:
1. Increase `HERE_MAX_WORKERS` (if rate limit allows)
2. Check network connectivity
3. Upgrade to paid plan for higher rate limits

### Low Improvement Rate

**Cause**: Nominatim already has good coverage

**Solution**: This is expected! HERE is a fallback, not a replacement.
- Typical improvement: 70-90% of retried addresses
- If < 50%, check address quality in Nominatim

## Best Practices

### Cost Optimization

1. **Use settlement threshold** (default)
   - `HERE_MIN_QUALITY_TO_RETRY=settlement`
   - Stays within free tier
   - Covers most problematic cases

2. **Run incrementally**
   - Geocode failed addresses first
   - Then settlement if needed
   - Avoid retrying street-level unless necessary

3. **Monitor usage**
   - Check HERE platform dashboard
   - Track queries per month
   - Set up billing alerts

### Quality Optimization

1. **Run after interpolation**
   - Let interpolation improve street-level first
   - HERE then focuses on genuinely difficult cases

2. **Check results**
   - Validate HERE results match expected locations
   - Compare against Nominatim for quality

3. **Use caching**
   - HERE results are cached automatically
   - Subsequent runs use cache (free)

## Limitations

### API Constraints

- **Rate limits**: Free tier = 5 req/sec
- **Monthly quota**: 250,000 queries/month free
- **No bulk endpoint**: Each address = 1 API call

### Data Coverage

- **Hungary coverage**: Excellent (HERE has strong European coverage)
- **Rural areas**: May still have gaps
- **New developments**: May not be in HERE database yet

### Quality Considerations

- HERE may return different coordinates than Nominatim
- Results should be validated for critical applications
- Settlement-level fallback may not always improve precision

## Future Enhancements

Potential improvements:

1. **Structured queries**: Use HERE's structured address format for better matching
2. **Batch API**: Use HERE batch endpoint when available
3. **Reverse geocoding**: Validate coordinates by reverse lookup
4. **Quality scoring**: Compare HERE vs Nominatim quality scores
5. **Hybrid strategy**: Combine multiple sources for consensus

## References

- HERE Platform: https://platform.here.com
- HERE Geocoding API Docs: https://www.here.com/docs/bundle/geocoding-and-search-api-developer-guide
- Pricing: https://www.here.com/get-started/pricing
- Support: https://developer.here.com/help

## Changelog

### 2025-11-09 - v1.0
- Initial implementation of HERE geocoding fallback
- Configuration management with environment variables
- Smart quality-based upgrade logic
- Rate limiting and parallel processing
- Test suite with mock and real API tests
- Integration into geocoding pipeline
