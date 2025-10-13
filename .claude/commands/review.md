---
name: Review
description: Review code changes and ensure quality standards
category: Code Quality
tags: [review, lint, type-check, quality]
---

Review code changes and run quality checks for OEVK data processing project.

**Quality Checks**

1. **Lint code with ruff**:
   ```bash
   ruff check .
   ```
   Fix issues automatically:
   ```bash
   ruff check . --fix
   ```

2. **Type check with mypy**:
   ```bash
   mypy .
   ```
   Check specific file:
   ```bash
   mypy src/etl/deduplicate.py
   ```

3. **Run all tests**:
   ```bash
   python -m pytest tests/ -v
   ```

4. **Format code** (if formatter is configured):
   ```bash
   ruff format .
   ```

**Code Review Checklist**

When reviewing code changes, ensure:

- [ ] **Code Style**: Follows PEP 8 and project conventions
  - Variables: snake_case
  - Functions: snake_case
  - Classes: PascalCase
  - Constants: UPPER_SNAKE_CASE

- [ ] **Type Hints**: All functions have type hints
  - Parameters annotated
  - Return types specified
  - Complex types use proper typing imports

- [ ] **Documentation**: Functions and classes have docstrings
  - Describe purpose and behavior
  - Document parameters and return values
  - Include usage examples for complex functions

- [ ] **Data Processing Patterns**:
  - Uses vectorized operations (no Python row loops)
  - Deterministic hash IDs (xxhash64)
  - Trims whitespace, converts empty strings to NULL
  - Processes data in chunks for large datasets

- [ ] **Error Handling**:
  - Structured logging with appropriate levels
  - Data validation with integrity checks
  - Invalid rows staged with error codes
  - Operations are idempotent and restartable

- [ ] **Testing**:
  - Unit tests for business logic
  - Integration tests for workflows
  - Contract tests for critical behaviors
  - All tests pass

- [ ] **Performance**:
  - Efficient use of Polars/DuckDB for large datasets
  - Appropriate chunk sizes (100k-500k rows)
  - No unnecessary data copies or conversions

**Guidelines**
- Run all quality checks before committing changes
- Fix linting and type errors before submitting
- Ensure all tests pass
- Follow project code style guidelines from AGENTS.md
- Document complex logic and algorithms
