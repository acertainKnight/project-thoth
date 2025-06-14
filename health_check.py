#!/usr/bin/env python3
"""
Thoth System Health Check Script

This script validates the entire Thoth system configuration,
dependencies, API connections, and functionality.

Usage:
    python health_check.py
    uv run python health_check.py
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from thoth.pipeline import ThothPipeline
    from thoth.utilities.config import get_config
except ImportError as e:
    print(f'❌ Failed to import Thoth modules: {e}')
    print("Make sure you've installed the package: uv sync")
    sys.exit(1)


class HealthChecker:
    """Comprehensive health checker for Thoth system."""

    def __init__(self):
        """Initialize health checker."""
        self.results: dict[str, list[tuple[str, bool, str]]] = {}
        self.config = None

    def print_header(self, section: str) -> None:
        """Print section header."""
        print(f'\n{"=" * 60}')
        print(f'🔍 {section}')
        print('=' * 60)
        self.results[section] = []

    def print_result(self, check: str, status: bool, message: str = '') -> None:
        """Print check result."""
        icon = '✅' if status else '❌'
        print(f'{icon} {check}')
        if message:
            print(f'   {message}')

        # Store result for summary
        current_section = list(self.results.keys())[-1] if self.results else 'Unknown'
        self.results[current_section].append((check, status, message))

    def run_all_checks(self) -> bool:
        """Run all health checks."""
        print('🦉 Thoth System Health Check')
        print('=' * 60)

        # Core system checks
        self.check_python_version()
        self.check_dependencies()
        self.check_configuration()
        self.check_directories()

        # API and connectivity
        self.check_api_keys()
        self.check_llm_connectivity()

        # System functionality
        self.check_services()
        self.check_rag_system()
        self.check_agent_system()

        # Optional checks
        self.check_docker()
        self.check_obsidian_api()

        # Summary
        self.print_summary()

        return self.overall_health()

    def check_python_version(self) -> None:
        """Check Python version compatibility."""
        self.print_header('Python Environment')

        version = sys.version_info
        required_min = (3, 10)
        recommended_min = (3, 11)

        if version >= required_min:
            if version >= recommended_min:
                self.print_result(
                    'Python Version',
                    True,
                    f'Python {version.major}.{version.minor}.{version.micro} (recommended)',
                )
            else:
                self.print_result(
                    'Python Version',
                    True,
                    f'Python {version.major}.{version.minor}.{version.micro} (compatible, upgrade to 3.11+ recommended)',
                )
        else:
            self.print_result(
                'Python Version',
                False,
                f'Python {version.major}.{version.minor}.{version.micro} (requires 3.10+)',
            )

        # Check virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        self.print_result(
            'Virtual Environment',
            in_venv,
            'Using virtual environment' if in_venv else 'Not in virtual environment',
        )

    def check_dependencies(self) -> None:
        """Check required dependencies."""
        self.print_header('Dependencies')

        required_packages = [
            'langchain',
            'langchain_core',
            'langgraph',
            'chromadb',
            'fastapi',
            'uvicorn',
            'pydantic',
            'requests',
            'loguru',
            'click',
        ]

        for package in required_packages:
            try:
                importlib.import_module(package)
                self.print_result(f'{package}', True)
            except ImportError:
                self.print_result(f'{package}', False, 'Package not installed')

    def check_configuration(self) -> None:
        """Check configuration loading and validity."""
        self.print_header('Configuration')

        try:
            self.config = get_config()
            self.print_result(
                'Configuration Loading', True, 'Config loaded successfully'
            )
        except Exception as e:
            self.print_result('Configuration Loading', False, f'Error: {e}')
            return

        # Check .env file
        env_file = Path('.env')
        self.print_result(
            '.env File',
            env_file.exists(),
            f'Found at {env_file.absolute()}'
            if env_file.exists()
            else 'Missing .env file',
        )

        # Check critical configuration
        critical_configs = [
            ('PDF Directory', self.config.pdf_dir),
            ('Notes Directory', self.config.notes_dir),
            ('Templates Directory', self.config.templates_dir),
        ]

        for name, path in critical_configs:
            if path:
                self.print_result(f'{name}', True, f'Configured: {path}')
            else:
                self.print_result(f'{name}', False, 'Not configured')

    def check_directories(self) -> None:
        """Check required directories exist and are writable."""
        self.print_header('Directories')

        if not self.config:
            self.print_result('Directories', False, 'Configuration not loaded')
            return

        directories = [
            ('PDF Directory', Path(self.config.pdf_dir)),
            ('Notes Directory', Path(self.config.notes_dir)),
            ('Templates Directory', Path(self.config.templates_dir)),
            ('Logs Directory', Path('logs')),
            ('Data Directory', Path('data')),
        ]

        for name, path in directories:
            if path.exists():
                if os.access(path, os.W_OK):
                    self.print_result(f'{name}', True, f'Exists and writable: {path}')
                else:
                    self.print_result(
                        f'{name}', False, f'Exists but not writable: {path}'
                    )
            else:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    self.print_result(f'{name}', True, f'Created: {path}')
                except Exception as e:
                    self.print_result(f'{name}', False, f'Cannot create: {e}')

    def check_api_keys(self) -> None:
        """Check API key configuration."""
        self.print_header('API Keys')

        if not self.config:
            self.print_result('API Keys', False, 'Configuration not loaded')
            return

        api_keys = [
            (
                'OpenRouter',
                self.config.api_keys.openrouter_key,
                'Required for LLM functionality',
            ),
            ('Mistral', self.config.api_keys.mistral_key, 'Optional for remote OCR'),
            ('OpenAI', self.config.api_keys.openai_key, 'Optional for OpenAI models'),
            (
                'Anthropic',
                self.config.api_keys.anthropic_key,
                'Optional for Claude models',
            ),
        ]

        for name, key, description in api_keys:
            if key and key.strip():
                # Mask the key for security
                masked_key = f'{key[:8]}...{key[-4:]}' if len(key) > 12 else '***'
                self.print_result(f'{name} API Key', True, f'Configured: {masked_key}')
            else:
                required = 'Required' in description
                self.print_result(f'{name} API Key', not required, description)

    def check_llm_connectivity(self) -> None:
        """Check LLM API connectivity."""
        self.print_header('LLM Connectivity')

        if not self.config or not self.config.api_keys.openrouter_key:
            self.print_result(
                'LLM Connectivity', False, 'No OpenRouter API key configured'
            )
            return

        try:
            # Simple connectivity test
            self.print_result(
                'LLM Configuration',
                True,
                'API key configured, connectivity test requires actual API call',
            )

        except Exception as e:
            self.print_result('LLM Connectivity', False, f'Connection test failed: {e}')

    def check_services(self) -> None:
        """Check service layer functionality."""
        self.print_header('Service Layer')

        try:
            pipeline = ThothPipeline()
            self.print_result(
                'Pipeline Initialization', True, 'Pipeline created successfully'
            )

            # Check service manager
            if hasattr(pipeline, 'services'):
                self.print_result('Service Manager', True, 'Services accessible')
            else:
                self.print_result('Service Manager', False, 'Services not accessible')

        except Exception as e:
            self.print_result(
                'Service Layer', False, f'Service initialization failed: {e}'
            )

    def check_rag_system(self) -> None:
        """Check RAG system functionality."""
        self.print_header('RAG System')

        try:
            # Check embedding functionality
            from thoth.rag.embeddings import get_embeddings

            get_embeddings()  # Just check if we can get embeddings
            self.print_result('Embeddings', True, 'Embedding model accessible')
        except Exception as e:
            self.print_result('Embeddings', False, f'Embedding error: {e}')

        try:
            # Check vector store
            from thoth.rag.vector_store import get_vector_store

            get_vector_store()  # Just check if we can get vector store
            self.print_result('Vector Store', True, 'Vector store accessible')
        except Exception as e:
            self.print_result('Vector Store', False, f'Vector store error: {e}')

    def check_agent_system(self) -> None:
        """Check agent system functionality."""
        self.print_header('Agent System')

        try:
            from thoth.ingestion.agent_v2.core.agent import ThothAgent

            agent = ThothAgent()
            self.print_result(
                'Agent Initialization', True, 'Agent created successfully'
            )

            # Check tool registry
            if hasattr(agent, 'tool_registry') and agent.tool_registry:
                if hasattr(agent.tool_registry, 'tools'):
                    self.print_result('Tool Registry', True, 'Tool registry accessible')
                else:
                    self.print_result('Tool Registry', False, 'No tools registered')
            else:
                self.print_result('Tool Registry', False, 'Tool registry not available')

        except Exception as e:
            self.print_result(
                'Agent System', False, f'Agent initialization failed: {e}'
            )

    def check_docker(self) -> None:
        """Check Docker functionality."""
        self.print_header('Docker (Optional)')

        try:
            result = subprocess.run(
                ['docker', '--version'], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                self.print_result('Docker', True, f'Available: {version}')

                # Check if Docker daemon is running
                result = subprocess.run(
                    ['docker', 'info'], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    self.print_result('Docker Daemon', True, 'Running')
                else:
                    self.print_result('Docker Daemon', False, 'Not running')
            else:
                self.print_result('Docker', False, 'Not installed')

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.print_result('Docker', False, 'Not available')

    def check_obsidian_api(self) -> None:
        """Check Obsidian API server."""
        self.print_header('Obsidian API (Optional)')

        if not self.config:
            self.print_result('API Configuration', False, 'Configuration not loaded')
            return

        host = self.config.api_server_config.host
        port = self.config.api_server_config.port
        base_url = f'http://{host}:{port}'

        try:
            import requests

            response = requests.get(f'{base_url}/health', timeout=5)
            if response.status_code == 200:
                self.print_result('API Server', True, f'Running on {base_url}')
            else:
                self.print_result(
                    'API Server', False, f'Unhealthy response: {response.status_code}'
                )
        except requests.exceptions.RequestException:
            self.print_result('API Server', False, f'Not running on {base_url}')

    def print_summary(self) -> None:
        """Print health check summary."""
        self.print_header('Health Check Summary')

        # Count results
        total_checks = 0
        passed_checks = 0

        for _section, checks in self.results.items():
            for _check, status, _message in checks:
                total_checks += 1
                if status:
                    passed_checks += 1

        health_percentage = (
            (passed_checks / total_checks * 100) if total_checks > 0 else 0
        )

        print(
            f'📊 Overall Health: {passed_checks}/{total_checks} checks passed ({health_percentage:.1f}%)'
        )

        if health_percentage >= 90:
            print('🎉 System is healthy and ready to use!')
        elif health_percentage >= 70:
            print(
                '⚠️  System is mostly functional with some optional features unavailable.'
            )
        else:
            print('❌ System has significant issues that need to be resolved.')

        print('\n🚀 Quick Start:')
        print('   python -m thoth agent        # Start the research agent')
        print('   python -m thoth api          # Start the API server')
        print('   python -m thoth process --pdf-path paper.pdf  # Process a PDF')

        print('\n📖 For troubleshooting help, see: docs/OBSIDIAN_TROUBLESHOOTING.md')
        print(
            '💬 For support, create an issue: https://github.com/yourusername/project-thoth/issues'
        )

    def overall_health(self) -> bool:
        """Return overall system health status."""
        # Check critical components
        critical_checks = [
            'Python Version',
            'Configuration Loading',
            'OpenRouter API Key',
            'Pipeline Initialization',
        ]

        for _section, checks in self.results.items():
            for check, status, _message in checks:
                if check in critical_checks and not status:
                    return False

        return True


def main():
    """Main health check function."""
    checker = HealthChecker()

    try:
        success = checker.run_all_checks()

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print('\n❌ Health check interrupted by user')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ Health check failed with error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
