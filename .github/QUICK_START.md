# CI/CD Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Clone and Setup

```bash
# Clone repository
git clone https://github.com/YOUR_ORG/project-thoth.git
cd project-thoth

# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Step 2: Make Changes

```bash
# Create feature branch
git checkout -b feature/my-amazing-feature

# Make your changes
# Edit files...

# Run tests locally
uv run python -m pytest tests/unit/ -v
```

### Step 3: Commit and Push

```bash
# Add and commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: add amazing feature"

# Push to GitHub
git push origin feature/my-amazing-feature
```

### Step 4: Create Pull Request

1. Go to GitHub repository
2. Click "Pull requests" → "New pull request"
3. Select your branch
4. Fill out PR template
5. Click "Create pull request"

### Step 5: Wait for CI

CI will automatically:
- ✅ Run 840 unit tests
- ✅ Check code quality (Ruff)
- ✅ Type check (MyPy)
- ✅ Security scan (Bandit)
- ✅ Build package

**All checks must pass before merge!**

---

## 📋 Common Commands

### Testing
```bash
# Run all unit tests
uv run python -m pytest tests/unit/ -v

# Run with coverage
uv run python -m pytest tests/unit/ --cov=src/thoth --cov-report=term

# Run specific test
uv run python -m pytest tests/unit/citations/test_matching.py::test_exact_match -v
```

### Code Quality
```bash
# Format code
ruff format src/ tests/

# Lint and fix
ruff check src/ tests/ --fix

# Type check
mypy src/
```

### Pre-commit
```bash
# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files

# Skip hooks (not recommended)
git commit -m "message" --no-verify
```

### Docker
```bash
# Build image
docker build -t thoth:local .

# Run container
docker run -p 8000:8000 thoth:local

# Run with database
docker-compose up
```

---

## 🔧 Troubleshooting

### "Tests failed locally"
```bash
# Check what failed
uv run python -m pytest tests/unit/ -v --tb=short

# Run specific failing test
uv run python -m pytest tests/unit/path/to/test.py::test_name -vv
```

### "Pre-commit failed"
```bash
# See what failed
pre-commit run --all-files

# Auto-fix formatting
ruff format src/ tests/

# Auto-fix linting
ruff check src/ tests/ --fix
```

### "CI passed but my changes don't work"
```bash
# Make sure you're testing the right code
pip show thoth  # Check installed version

# Reinstall in development mode
uv sync --all-extras
```

---

## 📝 Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Formatting
- `refactor:` Code restructuring
- `test:` Adding tests
- `chore:` Maintenance

**Examples:**
```bash
git commit -m "feat(citations): add fuzzy matching"
git commit -m "fix(api): handle missing DOI gracefully"
git commit -m "docs: update README with examples"
git commit -m "test: add property tests for matching"
```

---

## 🏷️ Release Process

### Semantic Versioning

- `v1.0.0` - Major release (breaking changes)
- `v1.1.0` - Minor release (new features)
- `v1.1.1` - Patch release (bug fixes)

### Create Release

```bash
# Update version
# Edit pyproject.toml: version = '1.0.0'

# Commit and tag
git add pyproject.toml
git commit -m "chore: bump version to 1.0.0"
git tag v1.0.0
git push origin main v1.0.0

# CI will automatically:
# - Build package
# - Publish to PyPI
# - Build Docker image
# - Create GitHub release
```

---

## 🆘 Get Help

- 📖 [Full CI/CD Documentation](workflows/README.md)
- 💬 [Contributing Guide](../../docs/CONTRIBUTING.md)
- 🐛 [Report Issues](https://github.com/YOUR_ORG/project-thoth/issues)

---

**Need help?** Open an issue or ask in Discussions!
