"""
Tests for MCP service configuration integrity.

Prevents regressions in:
- Service dependency extras (ensuring required packages like cachetools are included)
- Docker configuration consistency (port mappings, health checks, commands)
- CLI argument handling for MCP commands
- Module import chains that MCP depends on
"""

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestMCPDependencies:
    """Verify MCP service has all required dependencies."""

    def test_cachetools_importable(self):
        """Test that cachetools is installed and importable.

        cachetools is required by BaseRepository which is in the MCP import chain.
        This broke when vectordb was removed from service-mcp extras.
        """
        import cachetools

        assert hasattr(cachetools, 'TTLCache')

    def test_base_repository_importable(self):
        """Test that BaseRepository can be imported without errors.

        This catches missing transitive dependencies in the import chain:
        thoth.repositories.base -> cachetools
        """
        from thoth.repositories.base import BaseRepository

        assert BaseRepository is not None

    def test_service_manager_importable(self):
        """Test that ServiceManager can be imported.

        ServiceManager -> DiscoveryOrchestrator -> repositories -> BaseRepository
        This was the import chain that failed with missing cachetools.
        """
        from thoth.services.service_manager import ServiceManager

        assert ServiceManager is not None

    def test_mcp_server_module_importable(self):
        """Test that the MCP server module can be imported."""
        from thoth.mcp.server import create_mcp_server

        assert create_mcp_server is not None

    def test_mcp_tools_module_importable(self):
        """Test that MCP tools can be imported."""
        from thoth.mcp.tools import register_all_mcp_tools

        assert register_all_mcp_tools is not None


class TestMCPServiceExtras:
    """Verify pyproject.toml core dependencies include required packages."""

    @pytest.fixture
    def pyproject_content(self) -> str:
        """Load pyproject.toml content."""
        pyproject_path = Path(__file__).parent.parent.parent.parent / 'pyproject.toml'
        return pyproject_path.read_text()

    def test_cachetools_is_core_dependency(self, pyproject_content: str):
        """Test that cachetools is a core (non-optional) dependency.

        cachetools is required by BaseRepository which is imported by all services.
        It must be in the core dependencies so every service gets it automatically,
        rather than requiring each service extra to include vectordb.
        """
        # Find the core dependencies section (before [project.optional-dependencies])
        core_match = re.search(
            r'dependencies\s*=\s*\[(.*?)\]',
            pyproject_content,
            re.DOTALL,
        )
        assert core_match is not None, 'dependencies not found in pyproject.toml'
        core_deps = core_match.group(1)
        assert 'cachetools' in core_deps, (
            'cachetools must be a core dependency (in [project].dependencies). '
            'It is required by BaseRepository which is in every service import chain.'
        )

    def test_rag_embeddings_are_lazy_loaded(self):
        """Test that RAG module can be imported without heavy embedding dependencies.

        The EmbeddingManager uses lazy imports for HuggingFaceEmbeddings so that
        the RAG service works with API-based embeddings (OpenAI) without requiring
        sentence-transformers / PyTorch.
        """
        # This should succeed without langchain-huggingface installed
        from thoth.rag.embeddings import EmbeddingManager

        assert EmbeddingManager is not None

    def test_rag_service_importable_without_embeddings_extra(self):
        """Test that RAGService imports without the embeddings extra.

        The import chain: thoth.services.rag_service -> thoth.rag.rag_manager
        -> thoth.rag.embeddings must not fail at import time when only
        using API-based embeddings.
        """
        from thoth.services.rag_service import RAGService

        assert RAGService is not None


class TestMCPDockerConfiguration:
    """Verify Docker configuration for MCP service is consistent."""

    @pytest.fixture
    def compose_dev_content(self) -> str:
        """Load docker-compose.dev.yml content."""
        compose_path = (
            Path(__file__).parent.parent.parent.parent / 'docker-compose.dev.yml'
        )
        return compose_path.read_text()

    def _extract_mcp_service_section(self, compose_content: str) -> str:
        """Extract the thoth-mcp service section from docker-compose content."""
        lines = compose_content.split('\n')
        mcp_lines = []
        in_mcp = False
        for line in lines:
            # Service definitions start at 2-space indent
            if re.match(r'^  thoth-mcp:\s*$', line):
                in_mcp = True
            elif in_mcp and re.match(r'^  \S', line):
                # Hit the next top-level service definition
                break
            if in_mcp:
                mcp_lines.append(line)
        return '\n'.join(mcp_lines)

    def test_mcp_service_has_command_override(self, compose_dev_content: str):
        """Test MCP service has explicit command to run MCP server, not API server.

        Without a command override, the default Dockerfile CMD runs the API server
        (uvicorn thoth.server.app:app) instead of the MCP server.
        """
        mcp_section = self._extract_mcp_service_section(compose_dev_content)
        assert mcp_section, 'thoth-mcp service not found in docker-compose.dev.yml'

        # Must have either a command override or use docker/mcp/Dockerfile
        has_command = 'command:' in mcp_section
        has_mcp_dockerfile = 'docker/mcp/Dockerfile' in mcp_section

        assert has_command or has_mcp_dockerfile, (
            'thoth-mcp service must either have an explicit command: override '
            'or use docker/mcp/Dockerfile (which has the correct MCP CMD). '
            'Without this, the container runs the API server instead of MCP.'
        )

    def test_mcp_health_check_port_matches(self, compose_dev_content: str):
        """Test that MCP health check port matches the exposed port."""
        mcp_section = self._extract_mcp_service_section(compose_dev_content)
        assert mcp_section, 'thoth-mcp service not found'

        # Extract health check port
        health_match = re.search(r'localhost:(\d+)/health', mcp_section)
        assert health_match is not None, 'Health check not found for MCP service'
        health_port = health_match.group(1)

        # Extract container-side port from the ports: section
        # Format: "host_port:container_port" under the ports: key
        ports_section = re.search(r'ports:\s*\n((?:\s+-\s+.*\n?)+)', mcp_section)
        assert ports_section is not None, 'ports section not found for MCP service'
        # Find the container port (right side of host:container mapping)
        port_match = re.search(r'"(\d+):(\d+)"', ports_section.group(1))
        assert port_match is not None, 'Port mapping not found for MCP service'
        container_port = port_match.group(2)

        assert health_port == container_port, (
            f'MCP health check port ({health_port}) does not match '
            f'container port ({container_port}). The server and health check '
            f'must use the same port.'
        )


class TestMCPCLILazyLoading:
    """Test MCP CLI commands work with lazy loading."""

    def test_mcp_cli_module_importable(self):
        """Test that thoth.cli.mcp can be imported without heavy dependencies."""
        from thoth.cli import mcp

        assert hasattr(mcp, 'configure_subparser')

    def test_mcp_handler_accepts_no_pipeline(self):
        """Test MCP CLI handlers work without a pipeline argument.

        When using lazy loading in cli/main.py, MCP commands are called with
        only (args) instead of (args, pipeline). The handlers must accept
        pipeline=None.
        """
        import inspect

        from thoth.cli.mcp import run_http_server, run_stdio_server

        # Check that _pipeline parameter has a default value (is optional)
        for func in [run_stdio_server, run_http_server]:
            sig = inspect.signature(func)
            pipeline_param = sig.parameters.get('_pipeline')
            assert pipeline_param is not None, (
                f'{func.__name__} missing _pipeline parameter'
            )
            assert pipeline_param.default is not inspect.Parameter.empty, (
                f'{func.__name__}._pipeline must have a default value (None) '
                f'for lazy loading to work. Without this, calling the MCP '
                f'command without a pipeline raises TypeError.'
            )

    def test_cli_main_checks_raw_command_for_lazy_loading(self):
        """Test that cli/main.py checks sys.argv for lazy loading.

        The CLI must check the raw command from sys.argv before argparse
        parsing so that 'mcp' can be handled without importing heavy
        dependencies.
        """
        import inspect

        from thoth.cli import main as cli_main_module

        source = inspect.getsource(cli_main_module.main)
        assert 'raw_command' in source or 'sys.argv' in source, (
            'cli/main.py must check sys.argv for the command before argparse '
            'to allow lazy loading of MCP and DB subparsers.'
        )

    def test_cli_main_handles_mcp_command_lazily(self):
        """Test that the MCP command is in the lazy-loading command list."""
        import inspect

        from thoth.cli import main as cli_main_module

        source = inspect.getsource(cli_main_module.main)
        # The lazy loading block should include 'mcp' in its command list
        assert "'mcp'" in source or '"mcp"' in source, (
            'cli/main.py must handle "mcp" in the lazy-loading command set '
            'to avoid importing heavy dependencies for MCP server startup.'
        )


class TestPromptsChangeHandler:
    """Test the _PromptsChangeHandler inherits from FileSystemEventHandler."""

    def test_handler_has_dispatch_method(self):
        """Test that _PromptsChangeHandler has the dispatch method.

        watchdog's Observer calls handler.dispatch() internally. Without
        inheriting from FileSystemEventHandler, this method is missing
        and causes AttributeError at runtime.
        """
        try:
            from thoth.server.app import _PromptsChangeHandler
        except ImportError:
            pytest.skip('Server app not importable in this configuration')

        watcher_mock = MagicMock()
        handler = _PromptsChangeHandler(watcher=watcher_mock, prompts_dir=Path('/tmp'))
        assert hasattr(handler, 'dispatch'), (
            '_PromptsChangeHandler must have a dispatch() method. '
            'Inherit from watchdog.events.FileSystemEventHandler.'
        )

    def test_handler_inherits_from_filesystem_event_handler(self):
        """Test proper inheritance from FileSystemEventHandler."""
        try:
            from watchdog.events import FileSystemEventHandler

            from thoth.server.app import _PromptsChangeHandler
        except ImportError:
            pytest.skip('watchdog or server app not available')

        assert issubclass(_PromptsChangeHandler, FileSystemEventHandler), (
            '_PromptsChangeHandler must inherit from '
            'watchdog.events.FileSystemEventHandler'
        )
