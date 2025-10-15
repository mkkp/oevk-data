# Tasks: Verify PostgreSQL Export Quality

## Task List

### Phase 1: Loading Verification

- [ ] **Task 1.1**: Check if background loading process completed
  - Command: `ps aux | grep load_postgresql`
  - Expected: No process running (completed)
  - Deliverable: Process status confirmation

- [ ] **Task 1.2**: Analyze final loader output for skipped records
  - Check for "X executed, 0 skipped" in final output
  - Verify "✓ Loaded successfully" message appears
  - Confirm no "⚠ New error type" messages
  - Deliverable: Zero skipped records confirmed

- [ ] **Task 1.3**: Review error summary if any errors occurred
  - Check error summary section in output
  - Analyze error types and counts
  - Document any unexpected errors
  - Deliverable: Error analysis report (if applicable)

### Phase 2: Data Integrity Validation

- [ ] **Task 2.1**: Validate total record count
  - SQL: `SELECT COUNT(*) FROM Address;`
  - Expected: ~3,323,113 records
  - Tolerance: ±1% (±33,231 records)
  - Deliverable: Record count matches expectation

- [ ] **Task 2.2**: Check for NULL values in NOT NULL columns
  - SQL: `SELECT COUNT(*) FROM Address WHERE PublicSpaceType IS NULL OR PublicSpaceType = '';`
  - Expected: 0 records
  - Test all NOT NULL columns: FullAddress, PublicSpaceName, HouseNumber, foreign keys
  - Deliverable: Zero NULL values in NOT NULL columns

- [ ] **Task 2.3**: Validate foreign key relationships
  - SQL: Check orphaned PostalCode_ID references
    ```sql
    SELECT COUNT(*) FROM Address a
    LEFT JOIN PostalCode p ON a.PostalCode_ID = p.ID
    WHERE p.ID IS NULL;
    ```
  - Expected: 0 orphaned records
  - Test all FK relationships (PollingStation, County, Settlement, etc.)
  - Deliverable: All foreign keys valid

- [ ] **Task 2.4**: Verify OriginalAddressCount column
  - SQL: `SELECT MIN(OriginalAddressCount), MAX(OriginalAddressCount), AVG(OriginalAddressCount) FROM Address;`
  - Expected: MIN ≥ 1, MAX > 1, reasonable AVG
  - SQL: `SELECT COUNT(*) FROM Address WHERE OriginalAddressCount > 1;`
  - Expected: Many records (deduplication occurred)
  - Deliverable: OriginalAddressCount validation report

### Phase 3: Performance Testing

- [ ] **Task 3.1**: Measure full reload time with Python loader
  - Drop database and reload: `python load_postgresql.py --docker --drop-database`
  - Record start time, end time, and throughput
  - Expected: <15 minutes for 2.2GB
  - Deliverable: Performance metrics documented

- [ ] **Task 3.2**: Compare Python loader vs psql performance
  - Test psql direct load: `psql -h localhost -p 15432 -U oevk -d oevk -f data.sql`
  - Record load time
  - Expected: psql 5-10x faster than Python
  - Deliverable: Performance comparison table

- [ ] **Task 3.3**: Verify trigram index performance
  - SQL: `EXPLAIN ANALYZE SELECT * FROM Address WHERE FullAddress ILIKE '%utca%' LIMIT 100;`
  - Check query plan uses GIN index
  - Measure execution time
  - Expected: <1 second with index usage
  - Deliverable: Query performance report

- [ ] **Task 3.4**: Test memory usage during loading
  - Monitor loader process memory: `ps aux | grep load_postgresql`
  - Record peak memory usage
  - Expected: <500MB for Python process
  - Deliverable: Memory usage profile

### Phase 4: Schema Structure Validation

- [ ] **Task 4.1**: Verify table count and names
  - SQL: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;`
  - Expected: Exactly 13 tables
  - Verify: County, Settlement, Address, AddressPollingStations, AddressPIRCodes, etc.
  - Deliverable: Table list matches specification

- [ ] **Task 4.2**: Confirm internal tables are excluded
  - Check AddressMapping does NOT exist
  - Check DeduplicationReport does NOT exist
  - Check Address_new does NOT exist
  - Deliverable: Internal tables confirmed absent

- [ ] **Task 4.3**: Validate Address table structure
  - SQL: `\d Address` (or equivalent)
  - Verify all columns match documented DDL
  - Check OriginalAddressCount column exists
  - Verify all foreign keys defined
  - Deliverable: Schema structure verified

- [ ] **Task 4.4**: Verify indexes exist
  - SQL: `SELECT indexname FROM pg_indexes WHERE tablename = 'address';`
  - Check for trigram index: `idx_address_fulladdress_trgm`
  - Verify all documented indexes present
  - Deliverable: Index verification report

### Phase 5: Documentation Verification

- [ ] **Task 5.1**: Test SQL examples from README.md
  - Execute: `SELECT * FROM Address WHERE FullAddress ILIKE '%Budapest%' LIMIT 10;`
  - Execute: `SELECT * FROM Address WHERE FullAddress ILIKE '%utca%' LIMIT 10;`
  - Execute: OriginalAddressCount query example
  - Expected: All queries execute successfully
  - Deliverable: SQL examples validated

- [ ] **Task 5.2**: Test loader command examples
  - Test: `python load_postgresql.py --docker`
  - Test: `python load_postgresql.py --docker --drop-database`
  - Test: `python load_postgresql.py --docker --clean`
  - Expected: All commands work as documented
  - Deliverable: Loader usage validated

- [ ] **Task 5.3**: Verify schema documentation accuracy
  - Compare documented 13-table structure with actual
  - Verify Address table DDL matches documentation
  - Check that excluded tables are correctly documented
  - Deliverable: Documentation accuracy confirmed

- [ ] **Task 5.4**: Test troubleshooting guides
  - Follow documented troubleshooting steps
  - Verify solutions work for common issues
  - Test documented workarounds
  - Deliverable: Troubleshooting guides validated

### Phase 6: Production Readiness

- [ ] **Task 6.1**: Create verification summary report
  - Compile all verification results
  - Document any issues found
  - Provide pass/fail for each requirement
  - Deliverable: Comprehensive verification report

- [ ] **Task 6.2**: Update documentation with verification status
  - Update docs/POSTGRESQL_EXPORT_FIXES.md with results
  - Mark verification tasks as complete
  - Document any known limitations discovered
  - Deliverable: Documentation updated

- [ ] **Task 6.3**: Create repeatable verification script
  - Script should automate all SQL validation queries
  - Include pass/fail criteria
  - Generate verification report
  - Deliverable: `scripts/verify_postgresql.sh` or `.py`

- [ ] **Task 6.4**: Document production deployment readiness
  - Update project status based on verification
  - Provide go/no-go recommendation
  - List any remaining blockers
  - Deliverable: Production readiness assessment

## Dependencies

**Sequential Dependencies**:
- Phase 1 must complete before Phase 2 (need loaded database)
- Phase 2 must complete before Phase 3 (need valid data)
- Phase 4 can run in parallel with Phase 2-3
- Phase 5 can run in parallel with Phase 2-4
- Phase 6 depends on all previous phases

**Parallel Work**:
- Tasks 2.x, 3.x, 4.x, and 5.x can be executed in parallel once Phase 1 completes
- Multiple SQL validation queries can run concurrently

## Success Criteria

**Must Pass** (Blocks Production):
- ✅ Zero skipped records in fresh load
- ✅ All 3.3M records loaded successfully
- ✅ No NULL constraint violations
- ✅ No foreign key violations
- ✅ All 13 tables present, internal tables absent

**Should Pass** (Document if not):
- ⚠ Load time <15 minutes (can recommend psql if not)
- ⚠ Trigram search <1 second (should work with proper indexes)
- ⚠ Memory usage <500MB (acceptable if higher)

**Nice to Have** (Future improvements):
- 💡 Automated verification script
- 💡 CI/CD integration
- 💡 Multi-version PostgreSQL testing

## Validation

**How to verify this change**:
1. Run all tasks in sequence
2. Document results for each task
3. Compile verification report
4. Update all documentation
5. Provide production readiness recommendation

**Expected outcomes**:
- Verification report shows all critical tests passing
- Documentation updated with actual verified behavior
- Production deployment decision made with confidence
- Any issues found are documented with mitigation plans
