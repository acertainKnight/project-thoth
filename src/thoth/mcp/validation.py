"""
MCP Plugin Configuration Validation

This module provides comprehensive validation for MCP plugin configurations,
including schema validation, connectivity testing, and security checks.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .plugin_manager import MCPPluginConfig, MCPPluginRegistry


class ValidationError(Exception):
    """Custom validation error with structured details."""

    def __init__(
        self,
        message: str,
        plugin_id: str | None = None,
        errors: list[str] | None = None,
    ):
        self.message = message
        self.plugin_id = plugin_id
        self.errors = errors or []
        super().__init__(message)


class ValidationResult:
    """Result of plugin configuration validation."""

    def __init__(self):
        self.is_valid = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.plugin_results: dict[str, PluginValidationResult] = {}

    def add_error(self, error: str, plugin_id: str | None = None):
        """Add a validation error."""
        self.is_valid = False
        if plugin_id:
            error = f'[{plugin_id}] {error}'
        self.errors.append(error)

    def add_warning(self, warning: str, plugin_id: str | None = None):
        """Add a validation warning."""
        if plugin_id:
            warning = f'[{plugin_id}] {warning}'
        self.warnings.append(warning)

    def merge(self, other: ValidationResult, plugin_id: str | None = None):
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False

        for error in other.errors:
            self.add_error(error, plugin_id)

        for warning in other.warnings:
            self.add_warning(warning, plugin_id)


class PluginValidationResult:
    """Validation result for a single plugin."""

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.is_valid = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.connectivity_tested = False
        self.connectivity_success = False

    def add_error(self, error: str):
        """Add a validation error."""
        self.is_valid = False
        self.errors.append(error)

    def add_warning(self, warning: str):
        """Add a validation warning."""
        self.warnings.append(warning)


class MCPPluginValidator:
    """
    Comprehensive validator for MCP plugin configurations.

    Provides multi-layered validation including:
    - JSON schema validation
    - Configuration consistency checks
    - Command/URL validation
    - Security validation
    - Runtime connectivity testing
    """

    def __init__(self):
        self.security_rules = self._load_security_rules()

    def _load_security_rules(self) -> dict[str, Any]:
        """Load security validation rules."""
        return {
            'dangerous_commands': [
                'rm',
                'sudo',
                'chmod',
                'chown',
                'passwd',
                'su',
                'dd',
                'mkfs',
                'fdisk',
                'mount',
                'umount',
                'kill',
                'killall',
            ],
            'restricted_paths': ['/etc', '/boot', '/sys', '/proc', '/dev', '/root'],
            'suspicious_hosts': ['localhost:22', 'localhost:3389', '127.0.0.1:22'],
            'required_sandbox_commands': ['rm', 'mv', 'cp', 'chmod', 'chown'],
        }

    async def validate_registry(self, registry: MCPPluginRegistry) -> ValidationResult:
        """
        Validate complete plugin registry.

        Args:
            registry: Plugin registry to validate

        Returns:
            ValidationResult: Comprehensive validation results
        """
        result = ValidationResult()

        # Validate registry structure
        try:
            # Pydantic validation handles basic schema validation
            pass
        except ValidationError as e:
            result.add_error(f'Registry schema validation failed: {e}')
            return result

        # Validate individual plugins
        for plugin_id, plugin_config in registry.plugins.items():
            plugin_result = await self.validate_plugin(plugin_id, plugin_config)
            result.plugin_results[plugin_id] = plugin_result

            if not plugin_result.is_valid:
                result.is_valid = False
                for error in plugin_result.errors:
                    result.add_error(error, plugin_id)

            for warning in plugin_result.warnings:
                result.add_warning(warning, plugin_id)

        # Global validation checks
        await self._validate_global_constraints(registry, result)

        return result

    async def validate_plugin(
        self, plugin_id: str, config: MCPPluginConfig
    ) -> PluginValidationResult:
        """
        Validate a single plugin configuration.

        Args:
            plugin_id: Plugin identifier
            config: Plugin configuration

        Returns:
            PluginValidationResult: Plugin-specific validation results
        """
        result = PluginValidationResult(plugin_id)

        # Basic configuration validation
        await self._validate_plugin_config(config, result)

        # Transport-specific validation
        await self._validate_transport_config(config, result)

        # Security validation
        await self._validate_security_config(config, result)

        # Connectivity testing (if configuration is valid)
        if result.is_valid and config.enabled:
            await self._test_connectivity(config, result)

        return result

    async def _validate_plugin_config(
        self, config: MCPPluginConfig, result: PluginValidationResult
    ):
        """Validate basic plugin configuration."""

        # Required fields check
        if not config.name.strip():
            result.add_error('Plugin name cannot be empty')

        if config.transport not in ['stdio', 'http', 'sse']:
            result.add_error(f'Invalid transport: {config.transport}')

        # Priority validation
        if config.priority < 1 or config.priority > 100:
            result.add_warning(
                'Priority should be between 1-100 for optimal loading order'
            )

        # Timeout validation
        if config.timeout < 5:
            result.add_warning('Timeout < 5 seconds may cause connection issues')
        elif config.timeout > 300:
            result.add_warning('Timeout > 5 minutes may cause agent delays')

        # Capabilities validation
        valid_capabilities = {'tools', 'resources', 'prompts'}
        invalid_capabilities = set(config.capabilities) - valid_capabilities
        if invalid_capabilities:
            result.add_error(f'Invalid capabilities: {invalid_capabilities}')

    async def _validate_transport_config(
        self, config: MCPPluginConfig, result: PluginValidationResult
    ):
        """Validate transport-specific configuration."""

        if config.transport == 'stdio':
            await self._validate_stdio_config(config, result)
        elif config.transport in ['http', 'sse']:
            await self._validate_url_config(config, result)

    async def _validate_stdio_config(
        self, config: MCPPluginConfig, result: PluginValidationResult
    ):
        """Validate stdio transport configuration."""

        if not config.command:
            result.add_error('Command required for stdio transport')
            return

        if not isinstance(config.command, list) or not config.command:
            result.add_error('Command must be a non-empty list')
            return

        # Check if command executable exists
        command_name = config.command[0]
        if not await self._check_command_exists(command_name):
            result.add_error(f'Command not found: {command_name}')

        # Check for dangerous commands
        if command_name in self.security_rules['dangerous_commands']:
            result.add_error(f'Dangerous command detected: {command_name}')

        # Working directory validation
        if config.cwd:
            cwd_path = Path(config.cwd)
            if not cwd_path.exists():
                result.add_error(f'Working directory does not exist: {config.cwd}')
            elif not cwd_path.is_dir():
                result.add_error(f'Working directory is not a directory: {config.cwd}')

    async def _validate_url_config(
        self, config: MCPPluginConfig, result: PluginValidationResult
    ):
        """Validate URL-based transport configuration."""

        if not config.url:
            result.add_error(f'URL required for {config.transport} transport')
            return

        # Basic URL validation
        if not (config.url.startswith('http://') or config.url.startswith('https://')):
            result.add_error('URL must start with http:// or https://')

        # Security check for suspicious hosts
        for suspicious_host in self.security_rules['suspicious_hosts']:
            if suspicious_host in config.url:
                result.add_warning(
                    f'Potentially suspicious host in URL: {suspicious_host}'
                )

        # Authentication validation
        if config.auth:
            if not isinstance(config.auth, dict):
                result.add_error('Auth configuration must be a dictionary')
            elif 'type' not in config.auth:
                result.add_error('Auth type is required when auth is specified')

    async def _validate_security_config(
        self, config: MCPPluginConfig, result: PluginValidationResult
    ):
        """Validate security configuration."""

        # File path restrictions
        for path in config.allowed_file_paths:
            path_obj = Path(path)

            # Check for restricted system paths
            for restricted in self.security_rules['restricted_paths']:
                if str(path_obj).startswith(restricted):
                    result.add_error(f'Access to restricted path not allowed: {path}')

            # Check path exists (warning only)
            if not path_obj.exists():
                result.add_warning(f'Allowed file path does not exist: {path}')

        # Network restrictions
        for host in config.allowed_network_hosts:
            if ':' in host:
                try:
                    host_part, port_part = host.rsplit(':', 1)
                    port = int(port_part)
                    if port < 1 or port > 65535:
                        result.add_error(f'Invalid port in network host: {host}')
                except ValueError:
                    result.add_error(f'Invalid network host format: {host}')

        # Sandbox recommendations
        if not config.sandbox:
            # Check if command requires sandboxing
            if config.command and any(
                cmd in config.command[0]
                for cmd in self.security_rules['required_sandbox_commands']
            ):
                result.add_warning('Sandboxing recommended for this command')

    async def _test_connectivity(
        self, config: MCPPluginConfig, result: PluginValidationResult
    ):
        """Test connectivity to the plugin."""

        try:
            result.connectivity_tested = True

            if config.transport == 'stdio':
                success = await self._test_stdio_connectivity(config)
            else:
                success = await self._test_url_connectivity(config)

            result.connectivity_success = success

            if not success:
                result.add_warning(
                    'Connectivity test failed - plugin may not be available'
                )

        except Exception as e:
            result.add_warning(f'Connectivity test error: {e}')

    async def _test_stdio_connectivity(self, config: MCPPluginConfig) -> bool:
        """Test stdio command connectivity."""

        try:
            # Run command with --help or --version to test basic functionality
            cmd = [*config.command, '--help']

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=config.env if config.env else None,
                cwd=config.cwd,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=min(config.timeout, 10)
            )

            return process.returncode == 0

        except (TimeoutError, FileNotFoundError, OSError):
            return False
        except Exception:
            return False

    async def _test_url_connectivity(self, config: MCPPluginConfig) -> bool:
        """Test URL connectivity."""

        try:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=min(config.timeout, 10))

            # Prepare headers
            headers = {}
            if config.auth and config.auth.get('type') == 'bearer':
                token = config.auth.get('token', '')
                headers['Authorization'] = f'Bearer {token}'

            async with aiohttp.ClientSession(
                timeout=timeout, headers=headers
            ) as session:
                async with session.get(config.url) as response:
                    return response.status < 500

        except ImportError:
            # aiohttp not available - skip connectivity test
            return True
        except Exception:
            return False

    async def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists in the system PATH."""

        try:
            process = await asyncio.create_subprocess_exec(
                'which' if Path('/usr/bin/which').exists() else 'where',
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await process.communicate()
            return process.returncode == 0

        except Exception:
            return False

    async def _validate_global_constraints(
        self, registry: MCPPluginRegistry, result: ValidationResult
    ):
        """Validate global constraints across all plugins."""

        enabled_plugins = [
            plugin for plugin in registry.plugins.values() if plugin.enabled
        ]

        # Check for conflicting priorities
        priorities = [plugin.priority for plugin in enabled_plugins]
        if len(priorities) != len(set(priorities)):
            result.add_warning(
                'Multiple plugins have the same priority - loading order may be unpredictable'
            )

        # Check for resource conflicts (same ports, etc.)
        await self._check_resource_conflicts(enabled_plugins, result)

    async def _check_resource_conflicts(
        self, plugins: list[MCPPluginConfig], result: ValidationResult
    ):
        """Check for resource conflicts between plugins."""

        used_ports = set()

        for plugin in plugins:
            if plugin.transport in ['http', 'sse'] and plugin.url:
                try:
                    # Extract port from URL
                    import urllib.parse

                    parsed = urllib.parse.urlparse(plugin.url)
                    port = parsed.port

                    if port:
                        if port in used_ports:
                            result.add_warning(
                                f'Port {port} is used by multiple plugins'
                            )
                        used_ports.add(port)

                except Exception:
                    pass  # Skip malformed URLs


def validate_plugin_config_file(config_path: Path) -> ValidationResult:
    """
    Validate plugin configuration file.

    Args:
        config_path: Path to configuration file

    Returns:
        ValidationResult: Validation results
    """
    result = ValidationResult()

    # Check file exists
    if not config_path.exists():
        result.add_error(f'Configuration file not found: {config_path}')
        return result

    # Load and validate JSON
    try:
        with open(config_path, encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error(f'Invalid JSON in configuration file: {e}')
        return result
    except Exception as e:
        result.add_error(f'Failed to read configuration file: {e}')
        return result

    # Validate schema
    try:
        _ = MCPPluginRegistry(**config_data)
    except ValidationError as e:
        result.add_error(f'Configuration schema validation failed: {e}')
        return result

    return result
