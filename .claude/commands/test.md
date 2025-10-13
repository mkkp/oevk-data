---
name: Test
description: Run tests for OEVK data processing project
category: Testing
tags: [test, pytest, quality]
---

Run the appropriate test suite based on context:

**Steps**
1. Identify which tests to run based on the current work:
   - All tests: `python -m pytest tests/ -v`
   - Deduplication tests: `python -m pytest tests/contract/test_deduplication.py tests/integration/test_deduplication_*.py tests/unit/test_deduplication_*.py -v`
   - Contract tests only: `python -m pytest tests/contract/ -v`
   - Integration tests only: `python -m pytest tests/integration/ -v`
   - Unit tests only: `python -m pytest tests/unit/ -v`
   - Specific test file: `python -m pytest tests/path/to/test_file.py -v`
   - Specific test function: `python -m pytest tests/path/to/test_file.py::test_function -v`

2. If tests fail, analyze the failures and fix them

3. Run tests again to confirm fixes

**Guidelines**
- Always run relevant tests after making code changes
- Include `-v` flag for verbose output
- Use `-k` flag to run tests matching a pattern: `python -m pytest tests/ -k "dedup" -v`
- Use `-x` flag to stop on first failure: `python -m pytest tests/ -x -v`
- Check test coverage if needed: `python -m pytest tests/ --cov=src --cov-report=term-missing`
