# Contributing

Thanks for your interest in contributing to Thoth.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/project-thoth.git
cd project-thoth
git remote add upstream https://github.com/acertainKnight/project-thoth.git

uv venv && uv sync
cp .env.example .env   # fill in your API keys
export OBSIDIAN_VAULT_PATH="/path/to/test/vault"

make dev
pytest tests/
```

Use a test vault for development, not your real research vault.

## Workflow

1. Check for existing issues before starting work
2. For anything non-trivial, open an issue to discuss the approach first
3. Fork, branch from `main`, make your changes
4. Run `pytest tests/` and `uv run ruff check .` before pushing
5. Open a PR with a clear description of what changed and why

## Code Style

- **Formatting**: Ruff (PEP 8, 88 char line length, single quotes)
- **Type hints**: Required for public functions (Python 3.12+ syntax)
- **Docstrings**: Google-style for public APIs
- **File size**: Keep files under 500 lines; split if they get bigger
- **Tests**: Add tests for new features; put them in `tests/` mirroring the `src/` structure

```bash
uv run ruff check .       # lint
uv run ruff format .      # auto-format
uv run ruff check --fix . # auto-fix
```

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(mcp): add citation network analysis tool
fix(pipeline): handle malformed PDF metadata gracefully
test(citations): add fuzzy matching edge cases
docs(setup): update Docker instructions for ARM
```

## Project Layout

- `src/thoth/services/` — business logic
- `src/thoth/mcp/tools/` — MCP tool implementations
- `src/thoth/server/routers/` — FastAPI endpoints
- `src/thoth/discovery/plugins/` — source plugins
- `tests/unit/` — unit tests
- `tests/integration/` — integration tests

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
