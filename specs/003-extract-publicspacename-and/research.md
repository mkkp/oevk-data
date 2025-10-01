# Research: Public Space Extraction Feature

## Technical Decisions

### Database Schema Design
**Decision**: Use normalized tables with deterministic hash IDs for public space entities
- **Rationale**: Improves data integrity, reduces storage redundancy, enables efficient queries
- **Alternatives considered**: 
  - Keep denormalized text fields (rejected: data redundancy, harder updates)
  - Use integer auto-increment IDs (rejected: not deterministic, harder data migration)

### Hash Function Selection
**Decision**: Use xxhash64 for deterministic entity IDs
- **Rationale**: Fast, deterministic, collision-resistant, already used in existing codebase
- **Alternatives considered**:
  - SHA256 (rejected: slower, overkill for this use case)
  - MD5 (rejected: security concerns, collision risk)

### Data Processing Approach
**Decision**: Use vectorized operations with Polars/DuckDB for 3.3M+ records
- **Rationale**: Maintains performance targets, leverages existing infrastructure
- **Alternatives considered**:
  - Pandas (rejected: higher memory usage)
  - Row-by-row processing (rejected: too slow for large datasets)

### House Number Formatting
**Decision**: Remove leading zeros while preserving non-numeric characters
- **Rationale**: Standardizes display while maintaining data integrity
- **Alternatives considered**:
  - Keep original format (rejected: inconsistent user experience)
  - Strip all non-numeric characters (rejected: loses important address information)

### Public Space Uniqueness
**Decision**: Create single shared entries across all settlements
- **Rationale**: Simplifies data model, enables cross-settlement analysis
- **Alternatives considered**:
  - Settlement-scoped entries (rejected: unnecessary complexity, harder queries)
  - County-scoped entries (rejected: arbitrary boundary, limited benefit)

## Performance Considerations

### Processing Scale
- **Current baseline**: 3.3M+ address records
- **Target**: ≤10% performance degradation
- **Strategy**: Chunked processing (100k-500k rows), vectorized operations

### Memory Usage
- **Constraint**: Must handle large datasets efficiently
- **Strategy**: Use Polars/DuckDB for memory-efficient processing

## Integration Points

### Existing Codebase
- **Hashing functions**: Extend existing xxhash64 implementation
- **Transformation pipeline**: Integrate with current transform_optimized.py
- **Export system**: Add new tables to existing export logic

### Data Migration
- **Strategy**: Schema migration with data preservation
- **Risk**: Existing databases need migration
- **Mitigation**: Provide migration scripts, maintain backward compatibility

## Technology Stack Validation

### Python 3.11+
- **Decision**: Use existing project Python version
- **Rationale**: Maintains consistency, leverages existing dependencies

### Polars/DuckDB
- **Decision**: Continue using current data processing stack
- **Rationale**: Proven performance, existing expertise in codebase

### SQLite/DuckDB
- **Decision**: Maintain current database approach
- **Rationale**: Single-file databases, zero administration, fits project needs