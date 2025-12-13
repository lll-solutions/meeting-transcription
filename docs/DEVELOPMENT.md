# Development Guide

## Python Version

This project requires **Python 3.12+**.

## Development Tools

We use modern Python tooling for code quality:

- **ruff** - Fast linter and formatter (replaces black, isort, flake8)
- **mypy** - Static type checker
- **pytest** - Testing framework with coverage

## Code Quality Standards

### Type Hints

All new code **must** include type hints:

```python
# ✅ Good
def create_meeting(
    meeting_url: str,
    bot_name: str,
    user: str
) -> dict[str, Any]:
    ...

# ❌ Bad
def create_meeting(meeting_url, bot_name, user):
    ...
```

Use modern Python 3.12+ syntax:
- `list[str]` instead of `List[str]`
- `dict[str, Any]` instead of `Dict[str, Any]`
- `tuple[bool, str]` instead of `Tuple[bool, str]`
- `str | None` instead of `Optional[str]`

### Class Variables

Use `ClassVar` for class-level constants:

```python
from typing import ClassVar

class ValidationService:
    ALLOWED_DOMAINS: ClassVar[list[str]] = [
        "zoom.us",
        "meet.google.com",
    ]
```

## Workflow Commands

### Before Committing Code

```bash
# 1. Format code
poetry run ruff format .

# 2. Lint and auto-fix issues
poetry run ruff check . --fix

# 3. Type check
poetry run mypy .

# 4. Run tests with coverage
poetry run pytest
```

### Individual Commands

```bash
# Format a single file
poetry run ruff format src/services/validation.py

# Check a single file without fixing
poetry run ruff check src/services/validation.py

# Type check a specific module
poetry run mypy src/services/

# Run specific test file
poetry run pytest tests/services/test_validation.py -v
```

### CI/CD Checks

These commands run in CI and must pass:

```bash
# Verify formatting (no changes)
poetry run ruff format --check .

# Verify linting (no errors)
poetry run ruff check .

# Verify types (no errors)
poetry run mypy .

# Run tests with coverage
poetry run pytest --cov=src --cov=main --cov-report=term-missing
```

## Configuration

All tool configuration is in `pyproject.toml`:

- **Line length**: 100 characters
- **Python version**: 3.12+
- **Type checking**: Strict mode (`disallow_untyped_defs = true`)
- **Test coverage**: Reports to terminal and HTML

## Testing Standards

### Test Structure

```python
def test_function_name_happy_path():
    """Test description of what's being validated."""
    # Arrange
    service = MyService()

    # Act
    result = service.do_something("input")

    # Assert
    assert result == expected_output
```

### Test Coverage

- **Happy path first**: Test the most common, successful use case
- **Then edge cases**: Test error conditions, invalid inputs, boundaries
- **Target coverage**: 90%+ for services, 80%+ for routes

### Running Tests

```bash
# All tests with coverage
poetry run pytest

# Specific test file
poetry run pytest tests/services/test_validation.py

# Specific test function
poetry run pytest tests/services/test_validation.py::test_valid_zoom_url -v

# With verbose output
poetry run pytest -v

# Stop on first failure
poetry run pytest -x

# Show print statements
poetry run pytest -s
```

## IDE Setup

### VS Code

Install extensions:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)

Add to `.vscode/settings.json`:
```json
{
  "python.analysis.typeCheckingMode": "strict",
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "charliermarsh.ruff",
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true
}
```

### PyCharm

1. Settings → Tools → Python Integrated Tools → Default test runner: pytest
2. Settings → Tools → File Watchers → Add ruff formatter
3. Settings → Editor → Inspections → Python → Type Checker: mypy

## Common Issues

### Import Errors

If imports aren't found:

```bash
# Ensure you're in the virtual environment
poetry shell

# Or prefix commands with poetry run
poetry run python main.py
```

### Type Checking Errors

If third-party packages have no type stubs:

```python
# Add to pyproject.toml under [[tool.mypy.overrides]]
module = [
    "problematic_package.*",
]
ignore_missing_imports = true
```

### Ruff Formatting Conflicts

Ruff is configured to ignore line length errors (E501) because the formatter handles it.

If you want to disable a specific rule in one file:

```python
# ruff: noqa: RUF012
SOME_VARIABLE = "value"
```

## Writing Services

All services should follow this pattern:

```python
from typing import Any

class MyService:
    """Service description."""

    def __init__(self, dependency1: Dependency1, dependency2: Dependency2) -> None:
        """Initialize the service with dependencies."""
        self.dependency1 = dependency1
        self.dependency2 = dependency2

    def do_something(self, param: str, optional: str | None = None) -> dict[str, Any]:
        """
        Do something useful.

        Args:
            param: Description of param
            optional: Description of optional param

        Returns:
            Dictionary containing result data

        Raises:
            ValueError: If param is invalid
            APIError: If external API fails
        """
        # Implementation
        pass
```

## Questions?

- Check existing services in `src/services/` for examples
- Review tests in `tests/services/` for testing patterns
- See `docs/REFACTORING_PLAN.md` for architecture decisions
