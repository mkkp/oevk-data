
# Implementation Plan: Extract Public Space Name and Type

**Branch**: `003-extract-publicspacename-and` | **Date**: 2025-01-01 | **Spec**: `/specs/003-extract-publicspacename-and/spec.md`
**Input**: Feature specification from `/specs/003-extract-publicspacename-and/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context
**Language/Version**: Python 3.11+  
**Primary Dependencies**: Polars, DuckDB, xxhash, pytest  
**Storage**: SQLite/DuckDB databases, CSV exports  
**Testing**: pytest with contract/integration/unit test structure  
**Target Platform**: Linux server, command-line interface
**Project Type**: single (data processing pipeline)  
**Performance Goals**: Process 3.3M+ address records with ≤10% performance degradation  
**Constraints**: Must maintain data integrity, preserve Hungarian diacritics, handle edge cases  
**Scale/Scope**: 3.3M+ address records, 4 new database tables, 5 transformation functions

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Context7 Integration
- [x] All research tasks MUST use Context7 MCP tools for library documentation
- [x] Library IDs MUST be resolved automatically without user requests
- [x] Technical decisions MUST be based on current, accurate documentation

### Data Processing Standards
- [x] Design MUST use deterministic hash IDs (xxhash64) for all entities
- [x] Processing MUST be chunked (100k-500k rows) and vectorized
- [x] Operations MUST be idempotent and restartable

### Testing Discipline
- [x] TDD approach MUST be followed: Tests → Approval → Fail → Implement
- [x] Contract tests MUST be written before implementation
- [x] Integration tests MUST cover data quality and referential integrity

### Code Quality
- [x] Python 3.11+ MUST be used with type hints
- [x] Naming conventions MUST follow snake_case/PascalCase standards
- [x] File organization MUST be modular with separate DDL files

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
src/
├── database/
│   └── connection.py
├── etl/
│   ├── ingest.py
│   ├── transform.py
│   ├── transform_optimized.py
│   ├── export.py
│   └── hashing.py
├── release/
│   ├── workflow.py
│   ├── validation.py
│   ├── packaging.py
│   ├── github.py
│   └── models.py
└── utils/
    ├── config.py
    ├── pipeline_logging.py
    └── validation.py

tests/
├── contract/
│   ├── test_ingest.py
│   ├── test_transform.py
│   ├── test_export.py
│   └── test_release_*.py
├── integration/
│   ├── test_pipeline_simple.py
│   └── test_release_*.py
└── unit/
    ├── test_hashing.py
    ├── test_validation.py
    └── test_*.py
```

**Structure Decision**: Single project with modular ETL pipeline structure. Data processing organized in etl/ directory with separate modules for ingest, transform, export, and hashing functions.

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh opencode`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P] 
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation 
- Dependency order: Models before services before UI
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*
