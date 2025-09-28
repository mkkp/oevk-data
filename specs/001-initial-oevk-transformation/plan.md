# Implementation Plan: Initial OEVK Transformation App

**Branch**: `001-initial-oevk-transformation` | **Date**: 2025-09-28 | **Spec**: `/specs/001-initial-oevk-transformation/spec.md`
**Input**: Feature specification from `/specs/001-initial-oevk-transformation/spec.md`

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

**IMPORTANT**: The /plan command STOPS at step 8. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
This project will create a transformer program to download Hungarian electoral address data from two specified URLs, load it into a staging database, transform it into a normalized 8-entity target model using deterministic `xxhash64` IDs, and export the results. The final output will be one CSV file per target table, with the `Address` table additionally being partitioned into separate CSV files for each settlement. The process will be idempotent and handle over 3 million address records efficiently.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**: Polars, xxhash, requests, DuckDB
**Storage**: DuckDB (single-file database for staging and target)
**Testing**: pytest
**Target Platform**: Linux/macOS command-line application
**Project Type**: single (data processing application)
**Performance Goals**: Process >3M rows in under 30 minutes (NFR-002 target).
**Constraints**: Must preserve Hungarian diacritics. Operations must be idempotent.
**Scale/Scope**: ~3.34M rows from CSV, ~108 records from JSON, 8 target entities. Achieved performance: ~2.5 minutes with parallel processing.
**Source URLs**:
-   `https://static.valasztas.hu/dyn/oevk_data/oevk.json`
-   `https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip`

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
specs/001-initial-oevk-transformation/
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
├── etl/
│   ├── ingest.py          # Data download and staging
│   ├── transform.py       # Data transformation logic
│   ├── export.py          # CSV export functionality
│   └── hashing.py         # Deterministic ID generation
├── database/
│   ├── schema.sql         # SQL DDL for staging and target tables
│   └── connection.py      # Database connection management
├── utils/
│   ├── config.py          # Configuration management
│   └── logging.py         # Structured logging
└── cli.py                 # Command-line interface

tests/
├── contract/
│   ├── test_ingest.py
│   ├── test_transform.py
│   └── test_export.py
├── integration/
│   └── test_pipeline.py   # End-to-end data quality & referential integrity
└── unit/
    └── test_hashing.py

data/
├── staging/               # Temporary downloaded files
├── export/                # Generated CSV exports
└── database/              # DuckDB database file

logs/                      # Application logs
```

**Structure Decision**: A single project structure is chosen, organized by function (ETL, database, utils) which is standard for data processing applications. This aligns with the layout suggested in the functional specification.

## Phase 0: Outline & Research
1.  **Consolidate findings** in `research.md` to confirm technology choices:
    *   **Decision**: Polars for data processing. **Rationale**: Performance with large CSVs, expressive API for transformations.
    *   **Decision**: DuckDB for storage. **Rationale**: Fast, file-based, excellent for analytical queries needed during transformation.
    *   **Decision**: `xxhash` for hashing. **Rationale**: Fast, non-cryptographic hash function suitable for generating unique IDs, as recommended by the constitution.
    *   **Decision**: `requests` for downloading. **Rationale**: Standard and simple library for HTTP requests.

**Output**: `research.md` with decisions and rationale.

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1.  **Create `data-model.md`**: Document the 8 target entities, their fields, and relationships as defined in `docs/FUNCTIONAL_SPECIFICATION.md`. IDs will be `TEXT` fields storing hex-encoded `xxhash64` values.
2.  **Generate API contracts** in `/contracts/`:
    *   `ingest-contract.json`: Define functions for `download_sources` and `load_staging_data`.
    *   `transform-contract.json`: Define functions for each of the 8 entity transformation steps (e.g., `transform_counties`, `transform_settlements`).
    *   `export-contract.json`: Define functions for `export_tables_to_csv` and `export_addresses_partitioned`.
3.  **Create `quickstart.md`**: Document the end-to-end process for a user: setup, running the pipeline (download, transform, export), and validating the output files.
4.  **Update agent file**: Run `.specify/scripts/bash/update-agent-context.sh opencode` to update `AGENTS.md` with the selected technologies.

**Output**: `data-model.md`, `/contracts/*.json`, `quickstart.md`, `AGENTS.md`.

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
-   Generate tasks based on the contracts from Phase 1.
-   Create failing contract tests for each function defined in the contracts.
-   Create implementation tasks to make the contract tests pass.
-   Create integration test tasks to verify the full pipeline and data integrity.
-   Tasks will be ordered according to TDD and dependencies (ingest -> transform -> export).

**Estimated Output**: ~30 tasks in `tasks.md`.

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (`/tasks` command creates `tasks.md`)
**Phase 4**: Implementation (execute `tasks.md`)
**Phase 5**: Validation (run tests, execute `quickstart.md`)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *None*    | N/A        | N/A                                 |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [ ] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [ ] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented

---
*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
