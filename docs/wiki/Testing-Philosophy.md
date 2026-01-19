# Testing Philosophy

Vociferous employs a rigorous, two-tier testing strategy to ensure reliability without sacrificing development velocity.

---

## Overview

The test suite is designed around two principles:

1. **Fast feedback** — Non-UI tests run in < 5 seconds
2. **Comprehensive coverage** — UI tests verify end-to-end behavior

---

## Test Tiers

### Tier 1: Non-UI Tests (Default)

Fast, isolated tests that run without Qt:

```bash
pytest
```

**Characteristics:**
- No `QApplication` instantiation
- Pure Python logic testing
- < 5 second execution
- Run on every commit

**Examples:**
- Configuration parsing
- Database operations
- Prompt composition
- Input handling
- Refinement logic

### Tier 2: UI-Dependent Tests

Full Qt integration tests:

```bash
pytest --run-ui
```

**Characteristics:**
- Require `QApplication`
- Test widget behavior
- Signal/slot verification
- ~30-60 second execution
- Run before releases

---

## Pytest Markers

### Core Markers

| Marker | Purpose |
|--------|---------|
| `@pytest.mark.ui_dependent` | Requires Qt |
| `@pytest.mark.slow` | Long-running test |
| `@pytest.mark.integration` | Cross-component test |

### Usage Examples

```python
@pytest.mark.ui_dependent
def test_main_window_creation(qapp):
    """Requires Qt application."""
    window = MainWindow()
    assert window is not None

@pytest.mark.slow
def test_model_loading():
    """Takes > 30 seconds."""
    model = load_whisper_model("large-v3")
    assert model is not None
```

---

## Fixtures

### conftest.py Fixtures

The test suite provides these fixtures in [tests/conftest.py](tests/conftest.py):

#### Environment Fixtures

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `qapp` | session | Shared QApplication |
| `qtbot` | function | pytest-qt helper |
| `event_loop` | function | Async support |

#### Database Fixtures

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `db_session` | function | Isolated SQLite session |
| `history_manager` | function | Pre-configured manager |
| `sample_transcripts` | function | Test data |

#### Mock Fixtures

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `mock_audio_device` | function | Fake microphone |
| `mock_whisper_model` | function | Fast inference stub |
| `mock_slm_service` | function | Refinement mock |

---

## Lock Prevention

### The Problem

Parallel test runs can cause deadlocks when:
- Multiple tests access the same database
- Qt event loops conflict
- File locks aren't released

### The Solution

```python
@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Create isolated database per test."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()
```

**Key patterns:**
- Unique temp directory per test
- Explicit session cleanup
- Engine disposal after test

---

## Architecture Guardrails

### Enforced Invariants

Tests verify architectural constraints:

```python
# test_architecture_guardrails.py

def test_no_direct_db_access_from_ui():
    """UI code must not import database models."""
    ui_modules = get_all_ui_modules()
    for module in ui_modules:
        assert "database.models" not in module.imports

def test_intent_pattern_compliance():
    """All user actions must use intents."""
    actions = get_all_action_handlers()
    for action in actions:
        assert action.uses_intent_pattern()
```

### Contract Tests

Located in `tests/test_architecture_contracts.py`:

| Contract | Verification |
|----------|--------------|
| Dual-text invariant | raw_text immutability |
| Intent pattern | Signal -> Intent -> Handler |
| Cleanup protocol | All widgets implement cleanup() |
| Style isolation | No inline setStyleSheet() |

---

## Test Organization

### Directory Structure

```
tests/
├── conftest.py              # Shared fixtures
├── __init__.py
├── core/                    # Core module tests
│   └── ...
├── core_runtime/            # Runtime tests
│   └── ...
├── test_*.py                # Feature tests
└── __pycache__/
```

### Naming Conventions

| Pattern | Purpose |
|---------|---------|
| `test_<feature>.py` | Feature-specific tests |
| `test_<view>_*.py` | View-related tests |
| `test_*_integration.py` | Cross-component tests |
| `test_*_invariants.py` | Architectural constraints |

---

## Running Tests

### Common Commands

```bash
# Run all non-UI tests (fast)
pytest

# Run with UI tests
pytest --run-ui

# Run specific file
pytest tests/test_history_manager.py

# Run with coverage
pytest --cov=src

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run marked tests
pytest -m "not slow"
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Fast tests
        run: pytest
      - name: UI tests
        run: |
          sudo apt-get install -y xvfb
          xvfb-run pytest --run-ui
```

---

## Mocking Strategies

### Audio Device Mocking

```python
@pytest.fixture
def mock_audio_device(mocker):
    """Replace audio input with silence generator."""
    device = mocker.MagicMock()
    device.read.return_value = np.zeros(16000, dtype=np.float32)
    return device
```

### Model Mocking

```python
@pytest.fixture
def mock_whisper_model(mocker):
    """Fast transcription stub."""
    model = mocker.MagicMock()
    model.transcribe.return_value = ("Test transcription", {})
    return model
```

### Service Mocking

```python
@pytest.fixture
def mock_slm_service(mocker):
    """Refinement service that returns input unchanged."""
    service = mocker.MagicMock()
    service.refine.return_value = mocker.AsyncMock(return_value="Refined text")
    return service
```

---

## Test Data

### Sample Transcripts Fixture

```python
@pytest.fixture
def sample_transcripts(history_manager):
    """Create standard test transcripts."""
    transcripts = [
        Transcript(raw_text="Hello world", normalized_text="Hello, world."),
        Transcript(raw_text="Test one two", normalized_text="Test 1, 2."),
        Transcript(raw_text="Lorem ipsum", normalized_text="Lorem ipsum."),
    ]
    for t in transcripts:
        history_manager.add(t)
    return transcripts
```

### Factory Functions

```python
def make_transcript(
    raw_text: str = "default",
    normalized_text: str | None = None,
    created_at: datetime | None = None,
) -> Transcript:
    """Create transcript with defaults."""
    return Transcript(
        raw_text=raw_text,
        normalized_text=normalized_text or raw_text,
        created_at=created_at or datetime.now(),
    )
```

---

## Coverage Goals

### Target Coverage

| Component | Target |
|-----------|--------|
| Core | 90%+ |
| Database | 85%+ |
| Services | 80%+ |
| UI | 70%+ |

### Measuring Coverage

```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View report
open htmlcov/index.html
```

---

## Best Practices

### Do

- Use fixtures for setup/teardown
- Test one concept per test
- Use descriptive test names
- Clean up resources explicitly
- Mock external dependencies

### Don't

- Share state between tests
- Depend on test execution order
- Use sleep() for timing
- Access real network/files
- Skip tests without reason

---

## Debugging Tests

### Verbose Output

```bash
pytest -v -s tests/test_specific.py
```

### PDB on Failure

```bash
pytest --pdb
```

### Inspect Fixtures

```bash
pytest --fixtures
```

---

## Related Pages

- [Architecture](Architecture) — Component structure
- [Getting-Started](Getting-Started) — Development setup
- [Data-and-Persistence](Data-and-Persistence) — Database testing
