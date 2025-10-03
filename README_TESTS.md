# Testing Guide

## Setup

### Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage report
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_database.py
```

### Run specific test
```bash
pytest tests/test_database.py::TestDatabase::test_save_activity
```

### Run only unit tests
```bash
pytest -m unit
```

### Run verbose mode
```bash
pytest -v
```

## Type Checking

### Run pyright
```bash
pyright src/
```

## Code Quality

### Run ruff linter
```bash
ruff check src/
```

### Run ruff formatter
```bash
ruff format src/
```

### Auto-fix issues
```bash
ruff check --fix src/
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and mock database
├── test_database.py         # Database tests
├── test_tracker.py          # Activity tracker tests
├── test_mock_database.py    # Mock database tests
└── test_config.py           # Configuration tests
```

## Writing Tests

### Using the Mock Database

```python
def test_example(mock_db):
    # mock_db is a fully functional in-memory database
    project_id = mock_db.create_project("Test Project")
    activity_id = mock_db.save_activity(
        "Code.exe",
        "main.py",
        datetime(2024, 1, 15, 10, 0),
        datetime(2024, 1, 15, 11, 0)
    )
    assert activity_id > 0
```

### Using Sample Data

```python
def test_with_samples(sample_activities):
    # sample_activities provides a mock_db with 3 activities
    activities = sample_activities.get_activities()
    assert len(activities) == 3
```

## Continuous Integration

Tests run automatically on GitHub Actions for every push and pull request.

## Coverage

After running tests with coverage, open `htmlcov/index.html` to view detailed coverage report.

Target: Maintain >80% code coverage
