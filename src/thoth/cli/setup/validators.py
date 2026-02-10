"""Input validators for setup wizard.

Provides validation functions for API keys, paths, URLs, ports, and other inputs.
"""

from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

import psutil
from loguru import logger


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


class APIKeyValidator:
    """Validates API keys for different providers."""

    # API key patterns for different providers
    PATTERNS: ClassVar[dict[str, str]] = {
        'openai': r'^sk-[A-Za-z0-9_-]{20,}$',  # Updated to allow underscores and hyphens
        'anthropic': r'^sk-ant-[A-Za-z0-9\-_]{95,}$',
        'google': r'^[A-Za-z0-9\-_]{39}$',
        'mistral': r'^[A-Za-z0-9]{32}$',
        'openrouter': r'^sk-or-v1-[A-Za-z0-9]{64}$',
        'semantic_scholar': r'^[A-Za-z0-9]{40}$',
        'cohere': r'^[A-Za-z0-9\-_]{40,}$',  # Cohere keys are typically 40+ chars
    }

    @classmethod
    def validate(cls, provider: str, api_key: str) -> tuple[bool, str | None]:
        """Validate API key format for a provider.

        Args:
            provider: Provider name (openai, anthropic, etc.)
            api_key: API key to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not api_key or not api_key.strip():
            return False, 'API key cannot be empty'

        api_key = api_key.strip()

        # Check if provider has a pattern
        pattern = cls.PATTERNS.get(provider.lower())
        if not pattern:
            # No pattern defined, accept any non-empty key
            logger.warning(f'No validation pattern for provider: {provider}')
            return True, None

        # Validate pattern
        if re.match(pattern, api_key):
            return True, None
        else:
            return False, f'Invalid {provider} API key format'


class PathValidator:
    """Validates file system paths."""

    @staticmethod
    def validate_directory(
        path: str, must_exist: bool = False, must_be_writable: bool = True
    ) -> tuple[bool, str | None]:
        """Validate a directory path.

        Args:
            path: Directory path to validate
            must_exist: Whether directory must already exist
            must_be_writable: Whether directory must be writable

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not path or not path.strip():
            return False, 'Path cannot be empty'

        try:
            path_obj = Path(path).expanduser().resolve()
        except Exception as e:
            return False, f'Invalid path: {e}'

        # Check if exists
        if must_exist and not path_obj.exists():
            return False, f'Directory does not exist: {path}'

        if path_obj.exists():
            # Check if it's a directory
            if not path_obj.is_dir():
                return False, f'Path is not a directory: {path}'

            # Check if writable
            if must_be_writable and not PathValidator.is_writable(path_obj):
                return False, f'Directory is not writable: {path}'

        # Check disk space (warn if <3GB, recommend 5GB+)
        if path_obj.exists() or path_obj.parent.exists():
            free_gb = PathValidator.get_free_space_gb(path_obj)
            if free_gb < 3:
                return (
                    False,
                    f'Insufficient disk space ({free_gb:.1f}GB available). Minimum 3GB required.',
                )
            elif free_gb < 5:
                return (
                    True,
                    f'Warning: Low disk space ({free_gb:.1f}GB available). Recommend 5GB+ for comfortable usage.',
                )

        return True, None

    @staticmethod
    def is_writable(path: Path) -> bool:
        """Check if path is writable."""
        try:
            # Try creating a temp file
            test_file = path / '.write_test'
            test_file.touch()
            test_file.unlink()
            return True
        except (PermissionError, OSError):
            return False

    @staticmethod
    def get_free_space_gb(path: Path) -> float:
        """Get free disk space in GB for path."""
        try:
            # Get parent if path doesn't exist
            check_path = path if path.exists() else path.parent
            stat = psutil.disk_usage(str(check_path))
            gb: float = stat.free / (1024**3)  # Convert to GB
            return gb
        except Exception as e:
            logger.debug(f'Could not determine disk space, assuming enough: {e}')
            return float('inf')  # Can't determine, assume enough


class URLValidator:
    """Validates URLs and connection strings."""

    @staticmethod
    def validate_url(
        url: str, check_reachable: bool = False
    ) -> tuple[bool, str | None]:
        """Validate a URL.

        Args:
            url: URL to validate
            check_reachable: Whether to check if URL is reachable

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not url.strip():
            return False, 'URL cannot be empty'

        url = url.strip()

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f'Invalid URL format: {e}'

        # Check scheme
        if not parsed.scheme or parsed.scheme not in ['http', 'https']:
            return False, 'URL must start with http:// or https://'

        # Check host
        if not parsed.netloc:
            return False, 'URL must include a hostname'

        # Optional reachability check
        if check_reachable:
            try:
                import httpx

                response = httpx.get(url, timeout=5.0, follow_redirects=True)
                if response.status_code >= 400:
                    return False, f'URL returned error: {response.status_code}'
            except httpx.ConnectError:
                return False, 'Could not connect to URL'
            except httpx.TimeoutException:
                return False, 'Connection timeout'
            except Exception as e:
                return False, f'Connection error: {e}'

        return True, None

    @staticmethod
    def validate_database_url(url: str) -> tuple[bool, str | None]:
        """Validate PostgreSQL database URL.

        Args:
            url: Database URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not url.strip():
            return False, 'Database URL cannot be empty'

        url = url.strip()

        # Check format
        if not url.startswith('postgresql://') and not url.startswith('postgres://'):
            return False, 'Database URL must start with postgresql:// or postgres://'

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f'Invalid database URL format: {e}'

        # Check components
        if not parsed.hostname:
            return False, 'Database URL must include hostname'

        if not parsed.path or parsed.path == '/':
            return False, 'Database URL must include database name'

        return True, None


class PortValidator:
    """Validates port numbers and availability."""

    @staticmethod
    def validate_port(port: int) -> tuple[bool, str | None]:
        """Validate port number.

        Args:
            port: Port number to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(port, int):
            return False, 'Port must be an integer'

        if port < 1 or port > 65535:
            return False, 'Port must be between 1 and 65535'

        if port < 1024:
            return True, 'Warning: Port < 1024 may require root privileges'

        return True, None

    @staticmethod
    def is_port_available(port: int, host: str = 'localhost') -> bool:
        """Check if port is available for binding.

        Args:
            port: Port number to check
            host: Hostname to check

        Returns:
            True if port is available
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0  # Port available if connection fails
        except Exception as e:
            logger.debug(f'Error checking port availability: {e}')
            return False

    @staticmethod
    def get_port_status(port: int, host: str = 'localhost') -> tuple[bool, str | None]:
        """Get port availability status with details.

        Args:
            port: Port number to check
            host: Hostname to check

        Returns:
            Tuple of (is_available, status_message)
        """
        # Validate port number first
        valid, msg = PortValidator.validate_port(port)
        if not valid:
            return False, msg

        # Check availability
        if PortValidator.is_port_available(port, host):
            return True, f'Port {port} is available'
        else:
            # Try to find process using port
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        connections = proc.connections()
                        for conn in connections:
                            if conn.laddr.port == port:
                                return (
                                    False,
                                    f'Port {port} in use by {proc.info["name"]} (PID {proc.info["pid"]})',
                                )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as e:
                logger.debug(f'Error checking port status: {e}')

            return False, f'Port {port} is in use'


class EmailValidator:
    """Validates email addresses."""

    # Basic email pattern (not RFC 5322 compliant, but good enough)
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    @classmethod
    def validate(cls, email: str) -> tuple[bool, str | None]:
        """Validate email address format.

        Args:
            email: Email address to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not email or not email.strip():
            return False, 'Email cannot be empty'

        email = email.strip()

        if re.match(cls.EMAIL_PATTERN, email):
            return True, None
        else:
            return False, 'Invalid email format'
