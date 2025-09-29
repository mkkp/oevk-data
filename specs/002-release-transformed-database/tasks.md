# Tasks: Release Transformed Database

**Input**: Design documents from `/specs/002-release-transformed-database/`
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
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 3.1: Setup
- [ ] T001 Create release module structure in src/release/
- [ ] T002 Add GitHub CLI dependency and configure authentication
- [ ] T003 [P] Configure release-specific linting rules in .ruff.toml

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T004 [P] Contract test POST /release/create in tests/contract/test_release_create.py
- [ ] T005 [P] Contract test POST /release/validate in tests/contract/test_release_validate.py
- [ ] T006 [P] Contract test POST /release/cleanup in tests/contract/test_release_cleanup.py
- [ ] T007 [P] Integration test data validation in tests/integration/test_release_validation.py
- [ ] T008 [P] Integration test release creation in tests/integration/test_release_creation.py
- [ ] T009 [P] Integration test release cleanup in tests/integration/test_release_cleanup.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [ ] T010 [P] ReleasePackage model in src/release/models.py
- [ ] T011 [P] ReleaseArtifact model in src/release/models.py
- [ ] T012 [P] ReleaseMetadata model in src/release/models.py
- [ ] T013 [P] Data validation service in src/release/validation.py
- [ ] T014 [P] File packaging service in src/release/packaging.py
- [ ] T015 [P] GitHub integration service in src/release/github.py
- [ ] T016 [P] Release workflow orchestrator in src/release/workflow.py
- [ ] T017 CLI release validate command in src/cli.py
- [ ] T018 CLI release create command in src/cli.py
- [ ] T019 CLI release status command in src/cli.py
- [ ] T020 CLI release history command in src/cli.py

## Phase 3.4: Integration
- [ ] T021 Connect release workflow to existing ETL pipeline
- [ ] T022 Implement deterministic hash generation with xxhash64
- [ ] T023 Add structured logging for release operations
- [ ] T024 Implement idempotent release operations
- [ ] T025 Add performance monitoring for 15-minute completion target

## Phase 3.5: Polish
- [ ] T026 [P] Unit tests for validation service in tests/unit/test_validation.py
- [ ] T027 [P] Unit tests for packaging service in tests/unit/test_packaging.py
- [ ] T028 [P] Unit tests for GitHub service in tests/unit/test_github.py
- [ ] T029 [P] Unit tests for workflow orchestrator in tests/unit/test_workflow.py
- [ ] T030 Performance tests for release process completion within 15 minutes
- [ ] T031 [P] Update AGENTS.md with release workflow commands
- [ ] T032 Remove duplication and refactor common patterns
- [ ] T033 Run quickstart.md validation scenarios

## Dependencies
- Tests (T004-T009) before implementation (T010-T020)
- Models (T010-T012) before services (T013-T016)
- Services (T013-T016) before CLI commands (T017-T020)
- CLI commands (T017-T020) before integration (T021-T025)
- Implementation before polish (T026-T033)

## Parallel Example
```
# Launch T004-T009 together (all different files):
Task: "Contract test POST /release/create in tests/contract/test_release_create.py"
Task: "Contract test POST /release/validate in tests/contract/test_release_validate.py"
Task: "Contract test POST /release/cleanup in tests/contract/test_release_cleanup.py"
Task: "Integration test data validation in tests/integration/test_release_validation.py"
Task: "Integration test release creation in tests/integration/test_release_creation.py"
Task: "Integration test release cleanup in tests/integration/test_release_cleanup.py"

# Launch T010-T016 together (all different files):
Task: "ReleasePackage model in src/release/models.py"
Task: "ReleaseArtifact model in src/release/models.py"
Task: "ReleaseMetadata model in src/release/models.py"
Task: "Data validation service in src/release/validation.py"
Task: "File packaging service in src/release/packaging.py"
Task: "GitHub integration service in src/release/github.py"
Task: "Release workflow orchestrator in src/release/workflow.py"

# Launch T026-T029 together (all different files):
Task: "Unit tests for validation service in tests/unit/test_validation.py"
Task: "Unit tests for packaging service in tests/unit/test_packaging.py"
Task: "Unit tests for GitHub service in tests/unit/test_github.py"
Task: "Unit tests for workflow orchestrator in tests/unit/test_workflow.py"
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