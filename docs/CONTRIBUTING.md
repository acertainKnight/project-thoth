# Contributing to Thoth

Thank you for your interest in contributing to Thoth! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10, 3.11, or 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- Git
- PostgreSQL (for integration tests)

### Getting Started

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/project-thoth.git
   cd project-thoth
   ```

2. **Install Dependencies**
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Install all dependencies including dev tools
   uv sync --all-extras
   ```

3. **Set Up Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

4. **Run Tests**
   ```bash
   uv run python -m pytest tests/unit/ -v
   ```

## Development Workflow

### Branch Naming Convention

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions/modifications

### Code Style

We use several tools to maintain code quality:

- **Ruff** - Fast Python linter and formatter
- **MyPy** - Static type checking
- **Bandit** - Security linting
- **Pre-commit** - Automated checks before commits

Run checks manually:
```bash
# Format and lint
ruff format src/ tests/
ruff check src/ tests/ --fix

# Type checking
mypy src/

# Security scan
bandit -r src/
```

### Testing

We maintain high test coverage (99.6%+). Please add tests for new features.

```bash
# Run all unit tests
uv run python -m pytest tests/unit/ -v

# Run with coverage
uv run python -m pytest tests/unit/ --cov=src/thoth --cov-report=term --cov-report=html

# Run specific test file
uv run python -m pytest tests/unit/citations/test_matching.py -v

# Run property-based tests
uv run python -m pytest tests/unit/properties/ -v
```

### Writing Tests

- **Unit tests** go in `tests/unit/`
- **Integration tests** go in `tests/integration/`
- **E2E tests** go in `tests/e2e/`
- Use `pytest` fixtures from `tests/conftest.py`
- Aim for >95% coverage for new code

Example test:
```python
import pytest
from thoth.analyze.citations.fuzzy_matcher import match_title

def test_match_title_exact():
    """Test exact title matching."""
    score = match_title("Deep Learning", "Deep Learning")
    assert score == 1.0

@pytest.mark.asyncio
async def test_async_function(mock_postgres):
    """Test async function with mock."""
    result = await some_async_function(mock_postgres)
    assert result is not None
```

## Pull Request Process

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write clean, documented code
   - Add tests for new functionality
   - Update documentation as needed

3. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation only
   - `style:` - Code style changes (formatting)
   - `refactor:` - Code refactoring
   - `test:` - Adding or updating tests
   - `chore:` - Maintenance tasks

4. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Open a Pull Request**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template
   - Link any related issues

### PR Checklist

- [ ] Tests pass locally (`pytest tests/unit/`)
- [ ] Code follows style guidelines (pre-commit passes)
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventional commits
- [ ] PR description explains the changes
- [ ] Tests added for new functionality

## CI/CD Pipeline

All PRs trigger automated checks:

- ✅ Unit tests across Python 3.10, 3.11, 3.12
- ✅ Integration tests with PostgreSQL
- ✅ Linting (Ruff)
- ✅ Type checking (MyPy)
- ✅ Security scanning (Bandit, CodeQL)
- ✅ Code coverage reporting

PRs must pass all checks before merging.

## Code Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, a maintainer will merge your PR

## Getting Help

- 📖 [Documentation](../README.md)
- 💬 [GitHub Discussions](https://github.com/YOUR_ORG/project-thoth/discussions)
- 🐛 [Issue Tracker](https://github.com/YOUR_ORG/project-thoth/issues)

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## License

By contributing, you agree that your contributions will be licensed under the project's license.

---

Thank you for contributing to Thoth! 🚀
