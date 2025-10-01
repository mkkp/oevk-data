# Quickstart: Public Space Extraction Feature

## Overview
Extract and normalize public space names and types from address data into separate tables with deterministic hash IDs, improving data integrity and query performance.

## Prerequisites
- Python 3.11+ with dependencies installed
- Existing OEVK data pipeline with 3.3M+ address records
- Staging database with Address table containing PublicSpaceName and PublicSpaceType columns

## Implementation Steps

### 1. Database Schema Migration
```sql
-- Create new normalized tables
CREATE TABLE PublicSpaceName (
    ID TEXT PRIMARY KEY,
    PublicSpaceName TEXT UNIQUE NOT NULL
);

CREATE TABLE PublicSpaceType (
    ID TEXT PRIMARY KEY,
    PublicSpaceType TEXT UNIQUE NOT NULL
);

CREATE TABLE SettlementPublicSpaces (
    Settlement_ID TEXT NOT NULL,
    PublicSpaceName_ID TEXT NOT NULL,
    PublicSpaceType_ID TEXT NOT NULL,
    PRIMARY KEY (Settlement_ID, PublicSpaceName_ID, PublicSpaceType_ID),
    FOREIGN KEY (Settlement_ID) REFERENCES Settlement(ID),
    FOREIGN KEY (PublicSpaceName_ID) REFERENCES PublicSpaceName(ID),
    FOREIGN KEY (PublicSpaceType_ID) REFERENCES PublicSpaceType(ID)
);

-- Modify Address table
ALTER TABLE Address ADD COLUMN PublicSpaceName_ID TEXT;
ALTER TABLE Address ADD COLUMN PublicSpaceType_ID TEXT;
```

### 2. Data Transformation
```python
# Extract unique public space names and types
unique_names = df.select("PublicSpaceName").unique().filter(pl.col("PublicSpaceName").is_not_null())
unique_types = df.select("PublicSpaceType").unique().filter(pl.col("PublicSpaceType").is_not_null())

# Generate deterministic hash IDs
unique_names = unique_names.with_columns([
    pl.col("PublicSpaceName").hash().cast(pl.Utf8).alias("ID")
])
unique_types = unique_types.with_columns([
    pl.col("PublicSpaceType").hash().cast(pl.Utf8).alias("ID")
])

# Populate lookup tables
# ... implementation details
```

### 3. Update Address Records
```python
# Update addresses with foreign key references
addresses = addresses.with_columns([
    pl.col("PublicSpaceName").hash().cast(pl.Utf8).alias("PublicSpaceName_ID"),
    pl.col("PublicSpaceType").hash().cast(pl.Utf8).alias("PublicSpaceType_ID"),
    pl.col("HouseNumber").str.replace(r"^0+(?=[0-9])", "").alias("HouseNumber")
])
```

### 4. Export Updated Data
```python
# Export new tables
public_space_names.to_csv("exports/PublicSpaceName.csv")
public_space_types.to_csv("exports/PublicSpaceType.csv") 
settlement_public_spaces.to_csv("exports/SettlementPublicSpaces.csv")

# Export updated addresses
addresses.select(["ID", "Settlement_ID", "PublicSpaceName_ID", "PublicSpaceType_ID", 
                  "HouseNumber", "Building", "Staircase", "Floor", "Door", 
                  "PostalCode_ID", "PollingStation_ID"]).to_csv("exports/addresses.csv")
```

## Testing

### Contract Tests
```bash
# Run transformation contract tests
python -m pytest tests/contract/test_transform_public_spaces.py -v

# Run export contract tests  
python -m pytest tests/contract/test_export_public_spaces.py -v
```

### Integration Tests
```bash
# Test complete pipeline
python -m pytest tests/integration/test_public_space_extraction.py -v
```

### Performance Tests
```bash
# Verify performance targets
python -m pytest tests/performance/test_public_space_performance.py -v
```

## Validation

### Data Quality Checks
1. **Referential Integrity**: All foreign keys must reference existing entities
2. **Uniqueness**: PublicSpaceName and PublicSpaceType entries must be unique
3. **Completeness**: No data loss during transformation
4. **House Number Formatting**: Leading zeros removed while preserving non-numeric characters

### Performance Validation
- Processing time: ≤10% increase over baseline
- Memory usage: ≤4GB peak
- Export time: ≤5 minutes for all files

## Expected Results

### New Tables
- **PublicSpaceName**: ~50,000-100,000 unique names with deterministic hash IDs
- **PublicSpaceType**: ~100-200 unique types with deterministic hash IDs  
- **SettlementPublicSpaces**: ~100,000-200,000 settlement-public space relationships

### Modified Files
- **addresses.csv**: Updated with foreign key references and formatted house numbers
- **FullAddress**: Generated using formatted house numbers

### Benefits
- Improved data integrity through normalization
- Reduced storage redundancy
- Better query performance for public space analysis
- Consistent house number formatting

## Troubleshooting

### Common Issues
1. **Missing foreign keys**: Ensure all public space names/types are extracted before updating addresses
2. **Performance degradation**: Verify chunk sizes (100k-500k rows) and use vectorized operations
3. **Data loss**: Run validation checks before and after transformation

### Debug Mode
```bash
# Enable verbose logging
export LOG_LEVEL="DEBUG"
python -m src.cli transform --verbose
```

## Next Steps
After successful implementation:
1. Update release workflow to include new tables
2. Update documentation with new data model
3. Run full pipeline validation
4. Create migration scripts for existing databases