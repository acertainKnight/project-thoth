# GitHub Actions Workflows

This directory contains CI/CD workflows for automated testing, building, and deployment.

## Workflows

### 🔧 CI Workflow (`ci.yml`)

**Triggers:** Push to main/develop/feature branches, Pull Requests

Comprehensive continuous integration pipeline that runs on every push and PR:

**Jobs:**
- **Pre-commit Checks** - Fast initial validation of code quality
- **Lint & Type Check** - Code quality enforcement with Ruff and MyPy
- **Test Matrix** - Unit tests across:
  - Python versions: 3.10, 3.11, 3.12
  - Operating systems: Ubuntu, Windows, macOS
  - Coverage reporting to Codecov
- **Integration Tests** - Full integration tests with PostgreSQL
- **Security Scan** - Safety check and Bandit security linting
- **Build Validation** - Package build verification

**Requirements:**
- All tests must pass
- Coverage reports uploaded to Codecov
- Security vulnerabilities flagged

### 🚀 Release Workflow (`release.yml`)

**Triggers:** Version tags (`v*.*.*`), Manual workflow dispatch

Automated release process for publishing new versions:

**Jobs:**
- **Create Release** - GitHub release with changelog
- **Build & Publish** - PyPI package publication
- **Docker Build** - Multi-arch container images

**Manual Release:**
```bash
# Via GitHub UI: Actions → Release → Run workflow → Enter version
```

**Automated Release:**
```bash
git tag v1.0.0
git push origin v1.0.0
```

**Requirements:**
- `PYPI_API_TOKEN` secret for PyPI publishing
- Version must follow semver (e.g., 1.2.3)

### 🐳 Docker Workflow (`docker.yml`)

**Triggers:** Push to main/develop, Changes to Docker files

Builds and publishes Docker images to GitHub Container Registry:

**Jobs:**
- **Build & Push** - Multi-stage optimized build
- **Test Docker** - Smoke test of built images

**Image Tags:**
- `main` → `latest`
- `develop` → `develop`
- Pull requests → `pr-#`
- Commits → `branch-sha`

**Pull Images:**
```bash
docker pull ghcr.io/YOUR_ORG/project-thoth:latest
```

### 🔒 CodeQL Workflow (`codeql.yml`)

**Triggers:** Push, Pull Requests, Weekly schedule

GitHub's security scanning for vulnerability detection:

**Features:**
- Static analysis for security issues
- Automated security advisories
- Weekly scheduled scans
- Security alerts in GitHub Security tab

## Status Checks

All workflows report status via GitHub checks:
- ✅ Green check = All tests passed
- ❌ Red X = Failed checks
- 🟡 Yellow dot = In progress

## Secrets Configuration

Required secrets (configure in Settings → Secrets):

```yaml
PYPI_API_TOKEN: # For PyPI package publishing
CODECOV_TOKEN:  # For coverage reporting (optional)
```

## Local Testing

Run CI checks locally before pushing:

```bash
# Run all tests
uv run python -m pytest tests/unit/ -v

# Run linting
ruff check src/ tests/
ruff format --check src/ tests/

# Run type checking
mypy src/

# Run security scan
bandit -r src/

# Run pre-commit hooks
pre-commit run --all-files
```

## Workflow Customization

### Modify Test Matrix

Edit `.github/workflows/ci.yml`:

```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12", "3.13"]  # Add Python 3.13
    os: [ubuntu-latest, macos-latest]  # Remove Windows
```

### Skip CI for Commits

Add to commit message:
```bash
git commit -m "docs: update README [skip ci]"
```

### Manual Workflow Trigger

Go to Actions → Select workflow → Run workflow

## Performance Optimization

### Caching

All workflows use caching to speed up builds:
- uv dependencies cached by `pyproject.toml` hash
- Docker layers cached with BuildKit

### Parallelization

Tests run in parallel across:
- 3 Python versions
- 3 Operating systems
- = 9 concurrent test jobs

**Average CI run time:** ~5-8 minutes

## Monitoring

View workflow runs:
- **Actions tab** - All workflow history
- **Pull Request checks** - PR-specific checks
- **Branch protection** - Required status checks

## Troubleshooting

### Workflow Failed

1. Check the specific job that failed
2. Review logs for error messages
3. Run locally: `uv run python -m pytest tests/unit/ -v`
4. Fix issues and push again

### Cache Issues

Clear workflow caches:
1. Go to Actions → Caches
2. Delete relevant caches
3. Re-run workflow

### Integration Test Failures

Integration tests require PostgreSQL:
```bash
# Start local PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16

# Set environment variable
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thoth_test

# Run tests
uv run python -m pytest tests/integration/ -v
```

## Contributing

See [CONTRIBUTING.md](../../docs/CONTRIBUTING.md) for development guidelines.
