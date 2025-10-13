---
name: Csv
description: Export data to CSV files for distribution
category: Data Export
tags: [export, csv, data-distribution, performance]
---

Export processed OEVK data to CSV files for distribution and analysis.

**Export Features**
- Parallel processing with configurable worker threads (default: 8)
- Exports canonical (deduplicated) addresses with UUID v3 identifiers
- Exports entity tables (counties, settlements, districts, etc.)
- Optional original address export for debugging
- Selective export (tables-only or addresses-only)
- Partitioned by settlement for easy distribution
- Read-only database operations for safety

**Common Commands**

1. **Standalone export (all data)**:
   ```bash
   python src/cli.py export --db-path data/oevk.db --output-dir exports
   ```

2. **Export with custom worker count** (for performance tuning):
   ```bash
   python src/cli.py export --max-workers 16 --output-dir exports
   ```

3. **Export only entity tables** (skip addresses):
   ```bash
   python src/cli.py export --tables-only --output-dir exports
   ```

4. **Export only addresses** (skip entity tables):
   ```bash
   python src/cli.py export --addresses-only --output-dir exports
   ```

5. **Export with original addresses** (for debugging):
   ```bash
   python src/cli.py export --export-original-addresses --output-dir exports
   ```

6. **Release export** (integrated with release workflow):
   ```bash
   python src/cli.py release export --output-dir data/export --max-workers 8
   ```

7. **Export with custom run tag**:
   ```bash
   python src/cli.py export --run-tag "v1.0.0" --output-dir exports
   ```

**Performance Optimization**

The export process uses parallel processing for optimal performance:
- **Default workers**: 8 (configurable via `--max-workers`)
- **Expected performance**: ~300-400 seconds for full dataset (vs 1800s sequential)
- **Improvement**: 75-80% faster than sequential export
- **Each worker**: Independent read-only database connection
- **Progress logging**: Every 10 settlements

**Output Structure**

Entity tables (single CSV files):
- `County_{run_tag}.csv`
- `Settlement_{run_tag}.csv`
- `NationalIndividualElectoralDistrict_{run_tag}.csv`
- `SettlementIndividualElectoralDistrict_{run_tag}.csv`
- `PollingStation_{run_tag}.csv`
- `PostalCode_{run_tag}.csv`
- `PublicSpaceName_{run_tag}.csv`
- `PublicSpaceType_{run_tag}.csv`

Address files (partitioned by settlement):
- `canonical_addresses_{run_tag}/Address_{settlement_code}_{settlement_name}.csv`
- 194 settlement-specific CSV files with deduplicated addresses
- UUID v3 identifiers for external consumption

**CLI Parameters**

- `--db-path`: Database file path (default: `data/oevk.db`)
- `--output-dir`: Output directory for CSV files (default: `exports`)
- `--run-tag`: Custom timestamp tag (default: auto-generated)
- `--max-workers`: Number of parallel workers (default: 8)
- `--tables-only`: Export only entity tables, skip addresses
- `--addresses-only`: Export only addresses, skip entity tables
- `--export-original-addresses`: Include original non-deduplicated addresses

**Guidelines**
- Use higher `--max-workers` on machines with more CPU cores
- Use `--tables-only` for quick entity table exports
- Use `--addresses-only` when entity tables haven't changed
- Always verify database exists before exporting
- Monitor disk space (exports can be several hundred MB)
- Use `--export-original-addresses` only for debugging (large output)

**Configuration**

Export settings in `src/utils/config.py`:
```python
"export": {
    "include_partitioned_addresses": True,
    "include_consolidated_addresses": True,
    "partition_by_settlement": True,
    "csv_delimiter": ",",
    "csv_header": True,
    "max_workers": 8,  # Default parallel workers
}
```

Override via environment variable:
```bash
export OEVK_EXPORT_MAX_WORKERS=16
python src/cli.py export
```

**Key Files**
- `src/cli.py` - CLI export command implementation
- `src/etl/export.py` - Entity table export functions
- `src/etl/export_canonical_v2.py` - Parallel canonical address export
- `src/utils/config.py` - Export configuration settings

**Troubleshooting**

- **"Database not found"**: Run pipeline first with `python src/cli.py run`
- **Slow performance**: Increase `--max-workers` (try 16 or 32 on powerful machines)
- **Memory issues**: Decrease `--max-workers` (try 4 or 2)
- **Disk space errors**: Check available space, clean old exports
- **Connection errors**: Check database file permissions and path
