---
name: Deduplicate
description: Run address deduplication and generate reports
category: Deduplication
tags: [deduplication, addresses, data-quality]
---

Run address deduplication workflow for OEVK data processing.

**Deduplication Features**
- Identifies duplicate addresses using deterministic hash IDs
- Creates canonical address records
- Preserves all relationships (polling stations, PIR codes)
- Generates comprehensive reports with statistics
- Exports reports to JSON format
- Supports large datasets with chunking

**Common Commands**

1. **Run deduplication tests**:
   ```bash
   python -m pytest tests/contract/test_deduplication.py tests/integration/test_deduplication_*.py tests/unit/test_deduplication_*.py -v
   ```

2. **Run specific deduplication test suites**:
   - Contract tests: `python -m pytest tests/contract/test_deduplication.py -v`
   - Integration tests: `python -m pytest tests/integration/test_deduplication_*.py -v`
   - Unit tests: `python -m pytest tests/unit/test_deduplication_*.py -v`

3. **Run deduplication in Python**:
   ```python
   from src.etl.deduplicate import AddressDeduplicator
   
   dedup = AddressDeduplicator()
   result = dedup.deduplicate_addresses(addresses_df)
   ```

4. **Generate deduplication report**:
   ```python
   from src.etl.deduplicate import AddressDeduplicator
   
   dedup = AddressDeduplicator()
   report = dedup.generate_deduplication_report(addresses_df, result, processing_time_ms)
   json_report = dedup.export_report_to_json(report)
   ```

5. **Process large datasets**:
   ```python
   from src.etl.deduplicate import deduplicate_large_dataset
   
   result = deduplicate_large_dataset(addresses_df, chunk_size=100000)
   ```

**Guidelines**
- Always run tests after modifying deduplication logic
- Review deduplication reports for data quality insights
- Use chunking for datasets larger than 100k rows
- Ensure canonical addresses maintain referential integrity
- Check that all polling station and PIR code relationships are preserved

**Key Files**
- `src/etl/deduplicate.py` - Main deduplication logic
- `src/etl/models.py` - Data models for deduplication
- `tests/contract/test_deduplication.py` - Contract tests
- `tests/integration/test_deduplication_*.py` - Integration tests
- `tests/unit/test_deduplication_*.py` - Unit tests
