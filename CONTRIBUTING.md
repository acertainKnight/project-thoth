# Contributing to Thoth Research Assistant

Thank you for your interest in contributing to Thoth! This document provides comprehensive guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)
- [Architecture Principles](#architecture-principles)
- [Getting Help](#getting-help)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of experience level, background, or identity.

### Expected Behavior

- Be respectful and considerate in all interactions
- Welcome newcomers and help them get started
- Provide constructive feedback
- Focus on what is best for the project and community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or derogatory comments
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct that could reasonably be considered inappropriate

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.10-3.12** (3.12 recommended, NOT 3.13)
- **Git** for version control
- **Docker & Docker Compose** for containerized development
- **Obsidian** for testing the plugin integration
- **UV** package manager (recommended) or pip

### Quick Setup

```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/project-thoth.git
cd project-thoth

# Add upstream remote
git remote add upstream https://github.com/acertainKnight/project-thoth.git

# Install dependencies
uv venv && uv sync

# Set up environment
export OBSIDIAN_VAULT_PATH="/path/to/test/vault"
cp .env.example .env
# Edit .env with your API keys

# Start development environment
make dev

# Verify everything works
make health
pytest tests/
```

## Development Setup

### Environment Setup

1. **Create a test vault** for development (don't use your main research vault):
   ```bash
   mkdir -p ~/thoth-test-vault/_thoth
   export OBSIDIAN_VAULT_PATH="$HOME/thoth-test-vault"
   ```

2. **Install Python dependencies**:
   ```bash
   # With UV (recommended - faster)
   uv venv
   uv sync
   
   # Or with pip
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev,test]"
   ```

3. **Install Playwright** (for browser-based discovery):
   ```bash
   source .venv/bin/activate
   python -m playwright install chromium
   ```

4. **Install pre-commit hooks** (optional but recommended):
   ```bash
   pre-commit install
   ```

### IDE Configuration

**VS Code** (recommended settings):
```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "editor.formatOnSave": true,
  "editor.rulers": [88],
  "python.analysis.typeCheckingMode": "basic"
}
```

**PyCharm**:
- Enable Ruff for formatting and linting
- Set line length to 88 characters
- Enable type checking

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

1. **Bug Reports**: Found a bug? Open an issue with detailed reproduction steps
2. **Feature Requests**: Have an idea? Discuss it in an issue first
3. **Code Contributions**: Bug fixes, new features, optimizations
4. **Documentation**: Improve docs, add examples, fix typos
5. **Testing**: Write tests, improve test coverage
6. **Reviews**: Review pull requests and provide feedback

### Finding Work

- **Good First Issues**: Look for issues labeled `good-first-issue`
- **Help Wanted**: Issues labeled `help-wanted` need contributors
- **Documentation**: Check for `documentation` labeled issues
- **Ask**: Not sure where to start? Ask in discussions!

### Contribution Workflow

1. **Check for existing issues**: Search to avoid duplicate work
2. **Open an issue**: Discuss your idea before starting major work
3. **Fork and branch**: Create a feature branch from `main`
4. **Develop**: Write code following our standards
5. **Test**: Ensure all tests pass
6. **Commit**: Use conventional commit messages
7. **Push**: Push to your fork
8. **PR**: Open a pull request with detailed description

## Coding Standards

### Python Code Style

We use **Ruff** for linting and formatting:

```bash
# Check code style
uv run ruff check .

# Auto-format code
uv run ruff format .

# Auto-fix issues
uv run ruff check --fix .
```

**Key Standards:**
- **Line Length**: 88 characters (Black compatible)
- **Quotes**: Single quotes `'example'` for strings
- **Imports**: Sorted and organized (isort-compatible)
- **Type Hints**: Use type annotations for all public functions
- **Docstrings**: NumPy-style docstrings for all public APIs

**Example:**
```python
from pathlib import Path
from typing import Optional

def process_document(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    *,
    generate_tags: bool = True,
) -> dict[str, any]:
    """Process a PDF document through the pipeline.
    
    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file to process
    output_dir : Optional[Path]
        Output directory for generated notes
    generate_tags : bool, default=True
        Whether to generate AI tags
        
    Returns
    -------
    dict[str, any]
        Processing results with note path and metadata
        
    Raises
    ------
    FileNotFoundError
        If the PDF file doesn't exist
    ProcessingError
        If document processing fails
    """
    # Implementation
    pass
```

### TypeScript Code Style

For the Obsidian plugin:

**Standards:**
- **Line Length**: 100 characters
- **Quotes**: Single quotes
- **Semicolons**: Required
- **Async/Await**: Prefer over callbacks/promises
- **Type Annotations**: Use TypeScript types everywhere

**Example:**
```typescript
interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
}

async function sendMessage(message: string): Promise<ChatMessage> {
    const response = await fetch(`${endpoint}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
    });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return response.json();
}
```

### File Organization

**DO:**
- Keep files under 500 lines (split if larger)
- Use descriptive, meaningful names
- Group related functionality together
- Place files in appropriate directories

**DON'T:**
- Save files to the root folder (use `src/`, `tests/`, `docs/`)
- Create "utility" or "helper" dumping grounds
- Mix concerns in a single file

**Directory Rules:**
```
✅ CORRECT:
src/thoth/services/llm_service.py      # Services in services/
tests/unit/services/test_llm.py        # Tests mirror src structure
docs/architecture.md                   # Docs in docs/

❌ WRONG:
llm_service.py                         # Don't save to root!
src/thoth/utils/everything.py          # Don't create dumping grounds
test_stuff.py                          # Tests must be in tests/
```

## Testing Guidelines

### Writing Tests

We use **pytest** with 998 tests across multiple categories:

```bash
# Run all tests
pytest tests/

# Run specific categories
pytest tests/unit/              # Unit tests
pytest tests/integration/       # Integration tests
pytest tests/e2e/              # End-to-end tests
pytest tests/benchmarks/       # Performance tests

# Run with coverage
pytest --cov=src/thoth --cov-report=html tests/

# Run specific test file
pytest tests/unit/services/test_llm_service.py

# Run tests matching pattern
pytest -k "citation"
```

### Test Structure

**Unit Tests** (`tests/unit/`):
```python
import pytest
from thoth.services.llm_service import LLMService

@pytest.fixture
def llm_service(mock_config):
    """Create LLMService instance for testing."""
    return LLMService(config=mock_config)

def test_llm_service_initialization(llm_service):
    """Test that LLMService initializes correctly."""
    assert llm_service.config is not None
    assert llm_service.default_model is not None

@pytest.mark.asyncio
async def test_llm_service_generate(llm_service, mock_response):
    """Test LLM generation with mocked response."""
    result = await llm_service.generate("test prompt")
    assert result is not None
    assert len(result) > 0
```

**Integration Tests** (`tests/integration/`):
```python
import pytest
from thoth.services.service_manager import ServiceManager

@pytest.mark.integration
async def test_full_document_pipeline(test_pdf, test_vault):
    """Test complete document processing pipeline."""
    manager = ServiceManager()
    manager.initialize()
    
    result = await manager.processing.process_pdf(test_pdf)
    
    assert result['note_path'].exists()
    assert len(result['citations']) > 0
    assert 'metadata' in result
```

### Test Coverage

- **Minimum**: 70% coverage for new code
- **Target**: 80%+ coverage
- **Critical paths**: 100% coverage (config loading, service initialization)

### Property-Based Testing

We use **Hypothesis** for property-based testing:

```python
from hypothesis import given, strategies as st

@given(
    title=st.text(min_size=1, max_size=200),
    authors=st.lists(st.text(min_size=1), min_size=1, max_size=10),
    year=st.integers(min_value=1900, max_value=2030),
)
def test_citation_parsing(title, authors, year):
    """Test citation parsing with generated test cases."""
    citation = format_citation(title, authors, year)
    parsed = parse_citation(citation)
    
    assert parsed['title'] == title
    assert parsed['authors'] == authors
    assert parsed['year'] == year
```

## Commit Message Guidelines

We follow **Conventional Commits** specification:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **chore**: Maintenance tasks
- **docs**: Documentation changes
- **test**: Adding or updating tests
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **ci**: CI/CD changes
- **build**: Build system changes
- **security**: Security fixes

### Examples

```bash
# Simple commit
git commit -m "feat(mcp): add citation network analysis tool"

# With body
git commit -m "fix(pipeline): handle malformed PDF files

The pipeline now gracefully handles PDFs with corrupted metadata
by using fallback extraction methods. Added comprehensive error
handling and logging for debugging."

# With metrics
git commit -m "test(citations): add tests for fuzzy matching (+15 tests passing)"

# Breaking change
git commit -m "feat(config)!: migrate to vault-centric configuration

BREAKING CHANGE: Configuration now requires OBSIDIAN_VAULT_PATH
environment variable. The old THOTH_WORKSPACE_DIR is no longer supported.
See migration guide in docs/migration.md."
```

### Guidelines

- **Subject**: Use imperative mood ("add" not "added")
- **Length**: Subject <50 chars, body wrapped at 72 chars
- **Scope**: Use relevant scope (mcp, pipeline, config, etc.)
- **Body**: Explain WHY, not WHAT (code shows what)
- **Metrics**: Include test counts or metrics when relevant

## Pull Request Process

### Before Opening a PR

1. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests**:
   ```bash
   pytest tests/
   uv run ruff check .
   uv run ruff format .
   ```

3. **Update documentation** if needed

4. **Add tests** for new features

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] All tests pass (`pytest tests/`)
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages follow conventions
- [ ] PR description is clear and detailed
- [ ] No merge conflicts with `main`
- [ ] Branch is up-to-date with upstream

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
Describe the tests you added or how you tested your changes.

## Screenshots (if applicable)
Add screenshots for UI changes.

## Related Issues
Closes #123
Relates to #456

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

### Review Process

1. **Automated Checks**: CI must pass (tests, linting, security)
2. **Code Review**: At least one maintainer approval required
3. **Discussion**: Address feedback and questions
4. **Updates**: Make requested changes
5. **Approval**: Maintainer approves PR
6. **Merge**: Squash and merge to main

### After Your PR is Merged

1. **Delete your branch**:
   ```bash
   git branch -d feature/amazing-feature
   git push origin --delete feature/amazing-feature
   ```

2. **Update your fork**:
   ```bash
   git checkout main
   git fetch upstream
   git merge upstream/main
   git push origin main
   ```

## Project Structure

### Key Directories

```
src/thoth/
├── config.py              # Configuration system (1425 lines)
├── services/              # 32 microservices
│   └── service_manager.py # Central orchestrator
├── mcp/                   # MCP server + 54 tools
├── pipelines/             # Document processing
├── analyze/citations/     # Citation system (20 modules)
├── discovery/             # Multi-source discovery
├── rag/                   # RAG system
├── knowledge/             # Citation graph
├── server/                # FastAPI server
└── repositories/          # Data access (17 repos)

tests/
├── unit/                  # Unit tests
├── integration/           # Integration tests
├── e2e/                   # End-to-end tests
└── benchmarks/            # Performance tests

obsidian-plugin/
└── thoth-obsidian/
    ├── main.ts           # Plugin entry (95K)
    └── src/
        ├── modals/       # Chat UI (66K multi-chat)
        ├── services/     # 7 services
        ├── ui/          # 12 UI components
        └── utils/       # API utilities
```

### Adding New Features

**Backend Service**:
1. Create service in `src/thoth/services/`
2. Add to ServiceManager initialization
3. Write unit tests in `tests/unit/services/`
4. Update type hints and docstrings
5. Add to relevant documentation

**MCP Tool**:
1. Add tool in `src/thoth/mcp/tools/`
2. Register in tool registry
3. Write tests in `tests/unit/mcp/`
4. Document tool parameters
5. Update tool count in README

**API Endpoint**:
1. Create router in `src/thoth/server/routers/`
2. Add to app initialization
3. Write integration tests
4. Document endpoint in OpenAPI schema
5. Update API documentation

## Architecture Principles

### Design Principles

1. **Microservices**: Services should be independent and focused
2. **Dependency Injection**: Use ServiceManager for service coordination
3. **Configuration**: Single source of truth (`vault/_thoth/settings.json`)
4. **Hot-Reload**: Configuration changes should apply without restart (dev mode)
5. **Error Handling**: Graceful degradation, comprehensive logging
6. **Testing**: Write tests first (TDD approach)
7. **Type Safety**: Use type hints throughout
8. **Documentation**: Code should be self-documenting with good naming

### Code Organization

- **Services**: Business logic and orchestration
- **Repositories**: Data access and persistence
- **Pipelines**: Multi-stage data processing
- **Utilities**: Reusable helper functions
- **Models**: Pydantic schemas for data validation

### Performance Considerations

- **Async/Await**: Use for I/O-bound operations
- **Caching**: Cache expensive operations (5 min TTL default)
- **Queue Management**: Limit concurrent operations (max 3 default)
- **Batch Processing**: Process multiple items together
- **Lazy Loading**: Load resources only when needed

## Getting Help

### Resources

- **Documentation**: [docs/](docs/) directory
- **Architecture**: [docs/architecture.md](docs/architecture.md)
- **Setup Guide**: [docs/setup.md](docs/setup.md)
- **Usage Guide**: [docs/usage.md](docs/usage.md)

### Communication

- **GitHub Issues**: For bugs, features, and questions
- **GitHub Discussions**: For general questions and ideas
- **Pull Request Comments**: For code-specific discussions

### Questions?

- Check existing issues and discussions first
- Search documentation
- Ask in a new discussion or issue
- Be specific and provide context

## Recognition

Contributors will be recognized in:
- GitHub contributors page
- Release notes for significant contributions
- Project documentation for major features

Thank you for contributing to Thoth Research Assistant! 🚀

---

**Note**: This is a living document. If you find ways to improve these guidelines, please submit a PR!
