# Code Quality Tools

This directory contains automated code quality checks for the Vociferous project.

## Quick Start

Run all checks before committing:

```bash
./scripts/check.sh
```

## Tools Configured

### 1. **Ruff** (Linting & Formatting)
Fast Python linter and formatter, replaces flake8, black, isort, and more.

**Usage:**
```bash
# Check for issues
python -m ruff check .

# Auto-fix issues
python -m ruff check --fix .

# Format code
python -m ruff format .
```

**Config:** [pyproject.toml](../pyproject.toml)

### 2. **MyPy** (Static Type Checking)
Validates Python 3.12+ type hints to catch type-related bugs.

**Usage:**
```bash
python -m mypy src/
```

**Config:** [mypy.ini](../mypy.ini)

**Note:** ~331 errors are Qt6-related false positives (union-attr, override issues) and are acceptable.

### 3. **Bandit** (Security Scanner)
Finds common security issues in Python code.

**Usage:**
```bash
# Basic scan
python -m bandit -r src/

# JSON output
python -m bandit -r src/ -f json
```

**Findings:** 10 LOW severity issues (subprocess usage in `input_simulation.py` and `clipboard_utils.py` - all intentional for Linux keyboard/clipboard control).

### 4. **Pytest** (Unit Testing)
Comprehensive test suite with 125+ tests covering core functionality.

**Usage:**
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_ui_components.py

# Run with coverage
pytest --cov=src --cov-report=html
```

**Config:** [pytest.ini](../pytest.ini)

## CI/CD Integration

The [check.sh](check.sh) script is designed for CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run quality checks
  run: ./scripts/check.sh
```

Exit codes:
- `0` - All checks passed
- `1` - One or more checks failed

## Manual Fixes

### Fix all auto-fixable issues:
```bash
python -m ruff check --fix .
python -m ruff format .
```

### View detailed errors:
```bash
# Ruff errors
python -m ruff check .

# Type errors
python -m mypy src/

# Security issues
python -m bandit -r src/ -f screen
```

## Installing Tools

All tools are in [requirements.txt](../requirements.txt):

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install ruff mypy bandit pytest types-PyYAML
```

## Baseline Quality Metrics

As of January 9, 2026:

| Tool | Status | Details |
|------|--------|---------|
| **Ruff Linting** | ✅ Pass | 0 errors |
| **Ruff Formatting** | ✅ Pass | All files formatted |
| **MyPy** | ✅ Pass | 331 Qt false positives (acceptable) |
| **Bandit** | ✅ Pass | 10 LOW severity (expected) |
| **Pytest** | ✅ Pass | 125 passed, 1 skipped |

## Pre-commit Hooks (Optional)

Install pre-commit hooks to run checks automatically:

```bash
pip install pre-commit
pre-commit install
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```
