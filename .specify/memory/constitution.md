<!--
Sync Impact Report:
- Version change: 0.0.0 → 1.0.0 (initial constitution)
- Modified principles: All principles added (5 total)
- Added sections: Technical Requirements, Development Workflow
- Removed sections: None (template sections filled)
- Templates requiring updates:
  ✅ plan-template.md (constitution check section updated)
  ✅ spec-template.md (no specific constitution references)
  ✅ tasks-template.md (no specific constitution references)
  ✅ AGENTS.md (already exists, aligns with principles)
- Follow-up TODOs: RATIFICATION_DATE needs historical research
-->

# OEVK Data Processing Constitution

## Core Principles

### I. Context7-First Development
All code generation, setup, configuration, and library/API documentation MUST use Context7 MCP tools automatically. This includes resolving library IDs and retrieving up-to-date technical documentation without requiring explicit user requests. The goal is to ensure accurate, current technical information and efficient development workflows.

### II. Data Processing Excellence
Data transformations MUST use deterministic hash IDs for all entities (xxhash64 recommended). Processing MUST be chunked (100k-500k rows) and vectorized using Polars or DuckDB. Empty strings MUST be converted to NULL, and Hungarian diacritics MUST be preserved. Operations MUST be idempotent and restartable.

### III. Test-First (NON-NEGOTIABLE)
TDD mandatory: Tests written → User approved → Tests fail → Then implement. Red-Green-Refactor cycle strictly enforced. All contract tests MUST be written before implementation and MUST fail initially.

### IV. Integration Testing Focus
Focus integration testing on: New library contract tests, Contract changes, Inter-service communication, Shared schemas. All data quality and referential integrity checks MUST be validated through integration tests.

### V. Observability & Documentation
Structured logging required at INFO/DEBUG levels. All operations MUST be observable with start/end times, source URLs, file sizes, and row counts. Documentation MUST be generated automatically using Context7 tools and kept current.

## Technical Requirements

### Technology Stack
- **Primary language**: Python 3.11+
- **Data processing**: Polars or DuckDB for large datasets (>3M rows)
- **Database**: SQLite/DuckDB for staging/target (single-file, zero admin)
- **Hashing**: xxhash64 for deterministic entity IDs

### Code Quality Standards
- Use absolute imports with grouping: standard library, third-party, local modules
- Follow PEP 8 with type hints for all functions and variables
- Naming: snake_case variables/functions, PascalCase classes, UPPER_SNAKE_CASE constants
- File organization: Modular scripts (ingest.py, transform.py, export.py), SQL DDL in separate files

## Development Workflow

### Context7 Integration
All development phases MUST integrate Context7 MCP tools:
- Research phase: Automatically resolve library IDs and retrieve documentation
- Design phase: Generate contracts and data models using current best practices
- Implementation phase: Use Context7 for code generation and API documentation
- Validation phase: Verify technical accuracy against current library versions

### Quality Gates
- Constitution compliance checked before Phase 0 research and after Phase 1 design
- All [NEEDS CLARIFICATION] markers MUST be resolved before proceeding
- Complexity deviations MUST be documented and justified
- Parallel execution ([P] tasks) MUST be truly independent (different files)

## Governance

This constitution supersedes all other development practices. Amendments require documentation of the change rationale, approval process, and migration plan. All PRs and reviews MUST verify constitution compliance. Complexity MUST be justified with simpler alternatives evaluated. Use AGENTS.md for runtime development guidance.

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): Research original adoption date | **Last Amended**: 2025-09-28