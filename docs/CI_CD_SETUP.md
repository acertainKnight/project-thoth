# CI/CD Pipeline Documentation

## 🚀 Overview

This document describes the comprehensive CI/CD pipeline for Thoth, implementing industry best practices for automated testing, security, and deployment.

## 📊 Pipeline Summary

| Component | Tool | Status |
|-----------|------|--------|
| **CI/CD Platform** | GitHub Actions | ✅ Configured |
| **Testing** | pytest + coverage | ✅ 99.6% coverage |
| **Linting** | Ruff | ✅ Configured |
| **Type Checking** | MyPy | ✅ Configured |
| **Security** | Bandit + CodeQL | ✅ Configured |
| **Containerization** | Docker | ✅ Multi-stage build |
| **Pre-commit** | Hooks | ✅ Automated |
| **Release** | Automated | ✅ With changelog |

## 🔧 Workflows

### 1. CI Workflow (`.github/workflows/ci.yml`)

**Purpose:** Continuous integration for every push and PR

**Test Matrix:**
- Python versions: 3.10, 3.11, 3.12
- Operating systems: Ubuntu, Windows, macOS
- Total: 9 concurrent test jobs

**Stages:**
1. **Pre-commit Checks** (~30s)
   - Fast fail for style violations
   - Runs all pre-commit hooks

2. **Lint & Type Check** (~1-2 min)
   - Ruff linting and formatting
   - MyPy type checking
   - Code quality enforcement

3. **Unit Tests** (~3-5 min)
   - 840 unit tests across matrix
   - Coverage reporting to Codecov
   - Cached dependencies for speed

4. **Integration Tests** (~2-3 min)
   - PostgreSQL service container
   - Full database integration tests
   - API endpoint testing

5. **Security Scan** (~1-2 min)
   - Safety vulnerability check
   - Bandit security linting
   - Dependency scanning

6. **Build Validation** (~1 min)
   - Package build verification
   - Twine package validation

**Total Duration:** ~5-8 minutes (parallel execution)

### 2. Release Workflow (`.github/workflows/release.yml`)

**Purpose:** Automated releases to PyPI and Docker

**Triggers:**
- Git tags: `v*.*.*` (e.g., `v1.0.0`)
- Manual workflow dispatch

**Process:**
1. **Create Release**
   - Generate changelog from commits
   - Create GitHub release
   - Tag versions (latest, major.minor, major)

2. **Build & Publish**
   - Update version in `pyproject.toml`
   - Build Python package
   - Publish to PyPI (if token configured)

3. **Docker Build**
   - Multi-arch images (amd64, arm64)
   - Push to GitHub Container Registry
   - Tag: `latest`, `v1.0.0`, `v1.0`, `v1`

**Release Example:**
```bash
# Automated
git tag v1.0.0
git push origin v1.0.0

# Manual (via GitHub UI)
Actions → Release → Run workflow → Enter version
```

### 3. Docker Workflow (`.github/workflows/docker.yml`)

**Purpose:** Container image building and publishing

**Features:**
- Multi-stage build (optimized size)
- BuildKit caching (fast rebuilds)
- Non-root user (security)
- Health checks included

**Image Tags:**
- `main` branch → `latest`
- `develop` branch → `develop`
- PRs → `pr-123`
- Commits → `main-abc1234`

**Pull Images:**
```bash
docker pull ghcr.io/YOUR_ORG/project-thoth:latest
docker run -p 8000:8000 ghcr.io/YOUR_ORG/project-thoth:latest
```

### 4. CodeQL Workflow (`.github/workflows/codeql.yml`)

**Purpose:** Security vulnerability scanning

**Features:**
- Static analysis for Python
- Security advisories
- Weekly scheduled scans
- Automatic PR comments

**Scan Types:**
- SQL injection detection
- Code injection vulnerabilities
- Hardcoded credentials
- Insecure cryptography

## 🔒 Security Configuration

### Required Secrets

Configure in: **Settings → Secrets and variables → Actions**

| Secret | Purpose | Required |
|--------|---------|----------|
| `PYPI_API_TOKEN` | PyPI publishing | Release only |
| `CODECOV_TOKEN` | Coverage reporting | Optional |

### Security Features

1. **Bandit** - Python security linter
   - Scans for common vulnerabilities
   - Configured in `pyproject.toml`
   - Runs on every commit

2. **CodeQL** - Advanced security analysis
   - Deep semantic analysis
   - Automatic security advisories
   - GitHub Security tab integration

3. **Safety** - Dependency vulnerability check
   - Known CVE scanning
   - Outdated package detection

4. **Pre-commit Hooks**
   - Private key detection
   - Large file blocking
   - Secret scanning

## 🎯 Quality Gates

All PRs must pass:
- ✅ All unit tests (840 tests)
- ✅ Code coverage ≥ 99%
- ✅ No linting errors
- ✅ No type errors
- ✅ No security vulnerabilities
- ✅ Successful build

## 📦 Artifact Management

### Build Artifacts
- Python packages (`.tar.gz`, `.whl`)
- Coverage reports (XML, HTML)
- Security scan results (JSON)
- Docker images (GHCR)

### Retention
- Test artifacts: 30 days
- Release artifacts: Permanent
- Docker images: Latest + versioned

## 🚀 Deployment

### PyPI Deployment
```bash
# Automated on tag push
git tag v1.0.0
git push origin v1.0.0

# Manual installation
pip install thoth==1.0.0
```

### Docker Deployment
```bash
# Pull and run
docker pull ghcr.io/YOUR_ORG/project-thoth:latest
docker run -p 8000:8000 \
  -v $(pwd)/data:/data \
  -e DATABASE_URL=postgresql://... \
  ghcr.io/YOUR_ORG/project-thoth:latest
```

### Docker Compose
```yaml
version: '3.8'
services:
  thoth:
    image: ghcr.io/YOUR_ORG/project-thoth:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/thoth
    volumes:
      - ./data:/data

  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: postgres
```

## 🔄 Development Workflow

### 1. Local Development
```bash
# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
pre-commit install

# Run tests
uv run python -m pytest tests/unit/ -v

# Run linting
ruff check src/ tests/ --fix
ruff format src/ tests/
```

### 2. Create Feature Branch
```bash
git checkout -b feature/my-feature
```

### 3. Make Changes
- Write code
- Add tests
- Update docs

### 4. Pre-commit Validation
```bash
# Automatic on commit
git add .
git commit -m "feat: add new feature"

# Manual run
pre-commit run --all-files
```

### 5. Push and Create PR
```bash
git push origin feature/my-feature
# Open PR on GitHub
```

### 6. CI Validation
- Automatic checks run
- All tests must pass
- Review and merge

## 📈 Performance Optimization

### Caching Strategy
```yaml
# Python dependencies
- uses: actions/cache@v4
  with:
    path: ~/.cache/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('pyproject.toml') }}

# Docker layers
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### Parallelization
- 9 concurrent test jobs (3 Python × 3 OS)
- Parallel Docker builds
- Concurrent linting and type checking

**Speed Improvements:**
- Without caching: ~15 minutes
- With caching: ~5-8 minutes
- Cache hit rate: ~85%

## 🐛 Troubleshooting

### CI Failures

**Test Failures**
```bash
# Run locally
uv run python -m pytest tests/unit/ -v --tb=short

# Run specific test
uv run python -m pytest tests/unit/citations/test_matching.py::test_exact_match -v
```

**Linting Errors**
```bash
# Fix automatically
ruff check src/ tests/ --fix
ruff format src/ tests/

# Check manually
ruff check src/ tests/
```

**Type Errors**
```bash
# Run type check
mypy src/

# Ignore specific error
# type: ignore[error-code]
```

**Integration Test Failures**
```bash
# Start PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16

# Set environment
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thoth_test

# Run integration tests
uv run python -m pytest tests/integration/ -v
```

### Docker Build Issues

**Build Failures**
```bash
# Build locally
docker build -t thoth:test .

# Debug with no cache
docker build --no-cache -t thoth:test .

# Check logs
docker logs <container-id>
```

**Size Optimization**
```bash
# Check image size
docker images thoth

# Analyze layers
docker history thoth:test

# Multi-stage build already optimized
# Current size: ~500MB (includes Python + dependencies)
```

### Cache Issues

**Clear GitHub Actions Cache**
1. Go to: Actions → Caches
2. Delete relevant caches
3. Re-run workflow

**Clear Local Cache**
```bash
# Clear uv cache
uv cache clean

# Clear Docker cache
docker builder prune -a
```

## 📊 Monitoring

### CI/CD Metrics
- **Success Rate:** Target 95%+
- **Average Duration:** 5-8 minutes
- **Cache Hit Rate:** 85%+
- **Test Coverage:** 99.6%

### GitHub Insights
- Actions tab: Workflow history
- Insights → Actions: Usage analytics
- Security tab: Vulnerability alerts

## 🎓 Best Practices

1. **Fast Feedback**
   - Pre-commit hooks catch issues early
   - Fast jobs run first (lint before tests)
   - Fail fast on critical errors

2. **Security First**
   - No secrets in code
   - Dependency scanning
   - Regular security audits

3. **Reproducibility**
   - Pinned dependency versions
   - Locked Python versions
   - Docker for consistency

4. **Documentation**
   - Clear workflow docs
   - PR templates
   - Contributing guidelines

## 🔗 References

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [pytest Documentation](https://docs.pytest.org/)
- [CONTRIBUTING.md](./CONTRIBUTING.md)

---

**Last Updated:** 2026-01-01
**Pipeline Version:** 1.0.0
**Maintainer:** DevOps Team
