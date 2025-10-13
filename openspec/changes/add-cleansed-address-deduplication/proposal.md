# Add Cleansed Full Address Deduplication

## Why

The current address deduplication implementation generates formatted addresses but does not properly handle all the cleansing rules specified in `docs/004_REMOVE_DUPLICATED_ADDRESSES.md`. Specifically, the system needs to apply comprehensive address cleansing (leading zero removal, Roman numeral conversion for numeric staircases, proper handling of slash notation) before comparing addresses for duplicates to ensure accurate deduplication results.

## What Changes

- **ADDED**: Comprehensive address cleansing capability that handles all Hungarian address formatting rules
- **ADDED**: Cleansed full address generation prior to deduplication hash computation
- **ADDED**: Settlement-partitioned export of both canonical and original addresses
- **ADDED**: UUID v3 conversion for all entity IDs in exports using 'oevk.hu' DNS namespace
- **MODIFIED**: Deduplication logic to use cleansed full address as the primary duplicate detection key

## Impact

- **Affected specs**: `address-deduplication` (new capability)
- **Affected code**: 
  - `src/etl/deduplicate.py:440-530` (_format_full_address, _clean_house_number, _to_roman_numeral)
  - `src/etl/export.py` (export logic needs UUID v3 conversion)
  - Database schema already supports deduplication tables (no schema changes needed)
- **Breaking changes**: None (additive functionality)
- **Data quality impact**: Higher deduplication accuracy through standardized address cleansing

## Success Criteria

1. All addresses are cleansed according to Hungarian formatting rules before deduplication
2. Duplicate detection rate matches expected values from sample data (e.g., Körtöltés utca examples)
3. Export files are correctly partitioned by settlement with UUID v3 identifiers
4. Both canonical and original address exports are generated
5. All existing tests pass and new contract tests validate cleansing rules
