# Tasks: Extract Public Space Name and Type

**Input**: Design documents from `/specs/003-extract-publicspacename-and/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 3.1: Setup ✅ COMPLETED
- [x] T001 Create database schema migration for new public space tables in src/database/schema.sql
- [x] T002 Extend existing hashing functions for public space entities in src/etl/hashing.py
- [x] T003 [P] Configure performance monitoring for public space extraction in src/utils/pipeline_logging.py

## Phase 3.2: Tests First (TDD) ✅ COMPLETED
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [x] T004 [P] Contract test for public space transformation in tests/contract/test_transform_public_spaces.py
- [x] T005 [P] Contract test for public space export in tests/contract/test_export_public_spaces.py
- [x] T006 [P] Integration test for complete public space extraction pipeline in tests/integration/test_public_space_extraction.py
- [x] T007 [P] Integration test for data quality and referential integrity in tests/integration/test_public_space_validation.py

## Phase 3.3: Core Implementation (ONLY after tests are failing) ✅ COMPLETED
- [x] T008 [P] PublicSpaceName model and table creation in src/etl/transform_public_spaces.py
- [x] T009 [P] PublicSpaceType model and table creation in src/etl/transform_public_spaces.py
- [x] T010 [P] SettlementPublicSpaces lookup table creation in src/etl/transform_public_spaces.py
- [x] T011 Extract unique public space names from address data in src/etl/transform_public_spaces.py
- [x] T012 Extract unique public space types from address data in src/etl/transform_public_spaces.py
- [x] T013 Generate deterministic hash IDs for public space entities in src/etl/transform_public_spaces.py
- [x] T014 Populate PublicSpaceName table with unique names and hash IDs in src/etl/transform_public_spaces.py
- [x] T015 Populate PublicSpaceType table with unique types and hash IDs in src/etl/transform_public_spaces.py
- [x] T016 Populate SettlementPublicSpaces lookup table in src/etl/transform_public_spaces.py
- [x] T017 Update Address table with foreign key references in src/etl/transform_public_spaces.py
- [x] T018 Format house numbers to remove leading zeros in src/etl/transform_public_spaces.py
- [x] T019 Update FullAddress generation with formatted house numbers in src/etl/transform_public_spaces.py

## Phase 3.4: Integration ✅ COMPLETED
- [x] T020 [P] Export PublicSpaceName table to CSV in src/etl/export.py
- [x] T021 [P] Export PublicSpaceType table to CSV in src/etl/export.py
- [x] T022 [P] Export SettlementPublicSpaces lookup table to CSV in src/etl/export.py
- [x] T023 Export updated Address table with foreign keys in src/etl/export.py
- [x] T024 Update release workflow to include new public space tables in src/release/workflow.py
- [x] T025 Update data validation for public space referential integrity in src/release/validation.py

## Phase 3.5: Polish
- [x] T026 [P] Unit tests for public space hashing functions in tests/unit/test_public_space_hashing.py
- [x] T027 Performance tests for public space extraction in tests/performance/test_public_space_performance.py
- [x] T028 [P] Update documentation with new data model in docs/FUNCTIONAL_REQUIREMENTS.md
- [ ] T029 Remove duplication and optimize public space extraction in src/etl/transform_public_spaces.py
- [ ] T030 Run validation checks and performance benchmarks

## Dependencies
- Tests (T004-T007) before implementation (T008-T019)
- T008-T010 blocks T011-T016
- T011-T016 blocks T017-T019
- T017-T019 blocks T020-T025
- Implementation before polish (T026-T030)

## Parallel Example
```
# Launch T004-T007 together:
Task: "Contract test for public space transformation in tests/contract/test_transform_public_spaces.py"
Task: "Contract test for public space export in tests/contract/test_export_public_spaces.py"
Task: "Integration test for complete public space extraction pipeline in tests/integration/test_public_space_extraction.py"
Task: "Integration test for data quality and referential integrity in tests/integration/test_public_space_validation.py"

# Launch T008-T010 together:
Task: "PublicSpaceName model and table creation in src/etl/transform_public_spaces.py"
Task: "PublicSpaceType model and table creation in src/etl/transform_public_spaces.py"
Task: "SettlementPublicSpaces lookup table creation in src/etl/transform_public_spaces.py"

# Launch T020-T022 together:
Task: "Export PublicSpaceName table to CSV in src/etl/export.py"
Task: "Export PublicSpaceType table to CSV in src/etl/export.py"
Task: "Export SettlementPublicSpaces lookup table to CSV in src/etl/export.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Avoid: vague tasks, same file conflicts

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   - Each contract file → contract test task [P]
   - Each endpoint → implementation task
   
2. **From Data Model**:
   - Each entity → model creation task [P]
   - Relationships → service layer tasks
   
3. **From User Stories**:
   - Each story → integration test [P]
   - Quickstart scenarios → validation tasks

4. **Ordering**:
   - Setup → Tests → Models → Services → Endpoints → Polish
   - Dependencies block parallel execution

## Validation Checklist
*GATE: Checked by main() before returning*

- [x] All contracts have corresponding tests
- [x] All entities have model tasks
- [x] All tests come before implementation
- [x] Parallel tasks truly independent
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task