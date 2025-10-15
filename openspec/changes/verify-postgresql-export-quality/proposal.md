# Proposal: Verify PostgreSQL Export Quality

## Overview

**Change ID**: `verify-postgresql-export-quality`  
**Type**: Verification  
**Status**: Draft  
**Created**: 2025-10-15

## Problem Statement

The PostgreSQL export feature has been implemented with canonical data structure, NULL handling fixes, and enhanced loader capabilities. However, we need to verify that:

1. The data loading completes with **zero skipped records** (previously had 103,253 skipped)
2. All 3.3M canonical addresses load successfully without constraint violations
3. Data integrity is maintained (no NULL values in NOT NULL columns, valid foreign keys)
4. Performance meets expectations for production use
5. Documentation accurately reflects the verified behavior

## Current State

**Implemented Features**:
- ✅ Canonical-only export (13 tables, excludes internal transformation data)
- ✅ OriginalAddressCount column tracks deduplication ratio
- ✅ NULL handling with COALESCE for all NOT NULL columns
- ✅ Topological table ordering to prevent FK violations
- ✅ Enhanced loader with progress tracking, ETA, and error grouping
- ✅ Performance mode (strips ON CONFLICT for fresh loads)

**Last Test Status** (from docs/POSTGRESQL_EXPORT_FIXES.md):
- Schema: ✅ Loaded successfully in 0.02s
- Data: ⏳ Loading in progress (2236.75 MB)
- Performance mode: ✅ Enabled (ON CONFLICT clauses stripped)
- Expected: Zero skipped records if all fixes work

## Proposed Solution

Create comprehensive verification tasks to validate:

1. **Loading Success Verification**
   - Confirm data loading completed without errors
   - Verify zero skipped records in final output
   - Check for error summary (should be empty in performance mode)

2. **Data Integrity Validation**
   - Count total records matches expected ~3,323,113
   - Verify no NULL values in NOT NULL columns
   - Validate all foreign key relationships
   - Test OriginalAddressCount values are populated

3. **Performance Validation**
   - Measure full load time with --drop-database
   - Compare Python loader vs psql performance
   - Verify trigram indexes work for text search
   - Test memory usage with large datasets

4. **Documentation Verification**
   - Confirm all documented features work as described
   - Validate SQL examples in documentation
   - Test standalone loader from release package
   - Verify troubleshooting guides are accurate

5. **Production Readiness**
   - Create repeatable verification script
   - Document known limitations and workarounds
   - Provide clear success/failure criteria
   - Update status in all documentation

## Success Criteria

**Primary Goal**: Confirm zero skipped records when loading with `--drop-database` flag

**Verification Checklist**:
- [ ] Data loads with 0 skipped records (was 103,253 before fixes)
- [ ] All 3.3M addresses present in database
- [ ] No NULL constraint violations
- [ ] No foreign key violations
- [ ] OriginalAddressCount populated for all records
- [ ] Trigram text search indexes functional
- [ ] Loader progress tracking and ETA accurate
- [ ] Error grouping works correctly (no errors in clean load)
- [ ] Performance mode optimization effective
- [ ] Documentation examples verified

## Dependencies

- Requires: PostgreSQL export implementation (completed)
- Requires: Enhanced loader script (completed)
- Requires: Test data exports generated (completed)
- Blocks: Production deployment
- Blocks: Release package finalization

## Risks and Mitigation

**Risk 1**: Data loading may still have skipped records
- **Likelihood**: Low (all known issues fixed)
- **Impact**: High (blocks production use)
- **Mitigation**: Detailed error logging will identify any remaining issues

**Risk 2**: Performance may not meet expectations
- **Likelihood**: Medium (2.2GB is large dataset)
- **Impact**: Medium (can recommend psql for production)
- **Mitigation**: Clear performance guidance already documented

**Risk 3**: Edge cases may reveal new issues
- **Likelihood**: Medium (complex data with many foreign keys)
- **Impact**: Medium (may require additional fixes)
- **Mitigation**: Comprehensive test scenarios cover common cases

## Timeline

**Estimated Effort**: 4-8 hours

**Phase 1: Loading Verification** (1-2 hours)
- Check if background load completed
- Analyze final output and error logs
- Verify record counts

**Phase 2: Data Integrity** (2-3 hours)
- Run SQL validation queries
- Test foreign key constraints
- Validate NULL handling

**Phase 3: Performance Testing** (1-2 hours)
- Time full reload
- Compare with psql
- Test concurrent scenarios

**Phase 4: Documentation** (1 hour)
- Update verification status
- Document any issues found
- Finalize production guidance

## Related Changes

- Related to: `add-postgresql-export` (archived as 2025-10-15-add-postgresql-export)
- Verifies: All requirements in `postgresql-export` spec
- Enables: Production deployment and release

## Open Questions

1. **Q**: Should we automate verification as part of CI/CD?
   **A**: Future enhancement - focus on manual verification first

2. **Q**: What is acceptable load time for 2.2GB dataset?
   **A**: Python loader: <15 min acceptable, psql: <2 min expected

3. **Q**: Should we verify on multiple PostgreSQL versions?
   **A**: PostgreSQL 14+ (current Docker image version is sufficient)

4. **Q**: How do we handle if verification fails?
   **A**: Document issues, create follow-up fixes, do not deploy until passing
