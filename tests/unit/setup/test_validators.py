"""
Unit tests for setup wizard validators.
"""

import socket
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import psutil
import pytest

from thoth.cli.setup.validators import (
    APIKeyValidator,
    EmailValidator,
    PathValidator,
    PortValidator,
    URLValidator,
    ValidationError,
)


class TestAPIKeyValidator:
    """Tests for APIKeyValidator."""

    def test_validate_openai_valid(self):
        """Test valid OpenAI API key."""
        valid, error = APIKeyValidator.validate('openai', 'sk-abc123def456ghi789jkl012')
        assert valid is True
        assert error is None

    def test_validate_openai_invalid(self):
        """Test invalid OpenAI API key."""
        valid, error = APIKeyValidator.validate('openai', 'invalid-key')
        assert valid is False
        assert 'Invalid openai API key format' in error

    def test_validate_anthropic_valid(self):
        """Test valid Anthropic API key."""
        key = 'sk-ant-' + 'a' * 95
        valid, error = APIKeyValidator.validate('anthropic', key)
        assert valid is True
        assert error is None

    def test_validate_anthropic_invalid(self):
        """Test invalid Anthropic API key."""
        valid, error = APIKeyValidator.validate('anthropic', 'sk-ant-tooshort')
        assert valid is False
        assert 'Invalid anthropic API key format' in error

    def test_validate_google_valid(self):
        """Test valid Google API key."""
        key = 'A' * 39
        valid, error = APIKeyValidator.validate('google', key)
        assert valid is True
        assert error is None

    def test_validate_google_invalid(self):
        """Test invalid Google API key."""
        valid, error = APIKeyValidator.validate('google', 'tooshort')
        assert valid is False
        assert 'Invalid google API key format' in error

    def test_validate_empty_key(self):
        """Test empty API key."""
        valid, error = APIKeyValidator.validate('openai', '')
        assert valid is False
        assert 'API key cannot be empty' in error

    def test_validate_whitespace_key(self):
        """Test whitespace-only API key."""
        valid, error = APIKeyValidator.validate('openai', '   ')
        assert valid is False
        assert 'API key cannot be empty' in error

    def test_validate_unknown_provider(self):
        """Test validation for provider without pattern."""
        valid, error = APIKeyValidator.validate('unknown_provider', 'any-key')
        assert valid is True
        assert error is None

    def test_validate_strips_whitespace(self):
        """Test that whitespace is stripped from API key."""
        valid, error = APIKeyValidator.validate(
            'openai', '  sk-abc123def456ghi789jkl012  '
        )
        assert valid is True
        assert error is None


class TestPathValidator:
    """Tests for PathValidator."""

    def test_validate_empty_path(self):
        """Test empty path validation."""
        valid, error = PathValidator.validate_directory('')
        assert valid is False
        assert 'Path cannot be empty' in error

    def test_validate_existing_directory(self, tmp_path):
        """Test validation of existing directory."""
        valid, error = PathValidator.validate_directory(str(tmp_path))
        assert valid is True
        assert error is None

    def test_validate_nonexistent_directory_must_exist(self, tmp_path):
        """Test validation when directory must exist but doesn't."""
        nonexistent = tmp_path / 'does_not_exist'
        valid, error = PathValidator.validate_directory(
            str(nonexistent), must_exist=True
        )
        assert valid is False
        assert 'does not exist' in error.lower()

    def test_validate_nonexistent_directory_optional(self, tmp_path):
        """Test validation when directory doesn't need to exist."""
        nonexistent = tmp_path / 'does_not_exist'
        valid, error = PathValidator.validate_directory(
            str(nonexistent), must_exist=False
        )
        assert valid is True

    def test_validate_file_not_directory(self, tmp_path):
        """Test validation when path is file, not directory."""
        file_path = tmp_path / 'test.txt'
        file_path.touch()
        valid, error = PathValidator.validate_directory(str(file_path))
        assert valid is False
        assert 'not a directory' in error.lower()

    def test_validate_not_writable(self, tmp_path):
        """Test validation when directory is not writable."""
        test_dir = tmp_path / 'readonly'
        test_dir.mkdir()

        with patch.object(PathValidator, 'is_writable', return_value=False):
            valid, error = PathValidator.validate_directory(
                str(test_dir), must_be_writable=True
            )
            assert valid is False
            assert 'not writable' in error.lower()

    def test_validate_low_disk_space(self, tmp_path):
        """Test warning when disk space is low."""
        with patch.object(PathValidator, 'get_free_space_gb', return_value=5.0):
            valid, error = PathValidator.validate_directory(str(tmp_path))
            assert valid is True
            assert error is not None
            assert 'low disk space' in error.lower()

    def test_is_writable_success(self, tmp_path):
        """Test writable check on writable directory."""
        assert PathValidator.is_writable(tmp_path) is True

    def test_is_writable_failure(self, tmp_path):
        """Test writable check on non-writable directory."""
        with patch('pathlib.Path.touch', side_effect=PermissionError):
            result = PathValidator.is_writable(tmp_path)
            assert result is False

    def test_get_free_space_gb(self, tmp_path):
        """Test getting free disk space."""
        space_gb = PathValidator.get_free_space_gb(tmp_path)
        assert space_gb > 0

    def test_get_free_space_gb_error(self, tmp_path):
        """Test getting free space when error occurs."""
        with patch('psutil.disk_usage', side_effect=Exception('Test error')):
            space_gb = PathValidator.get_free_space_gb(tmp_path)
            assert space_gb == float('inf')

    def test_validate_expands_tilde(self, tmp_path):
        """Test that tilde is expanded in path."""
        with patch('pathlib.Path.home', return_value=tmp_path):
            valid, error = PathValidator.validate_directory(
                '~/test', must_exist=False
            )
            assert valid is True


class TestURLValidator:
    """Tests for URLValidator."""

    def test_validate_empty_url(self):
        """Test empty URL validation."""
        valid, error = URLValidator.validate_url('')
        assert valid is False
        assert 'URL cannot be empty' in error

    def test_validate_http_url(self):
        """Test valid HTTP URL."""
        valid, error = URLValidator.validate_url('http://example.com')
        assert valid is True
        assert error is None

    def test_validate_https_url(self):
        """Test valid HTTPS URL."""
        valid, error = URLValidator.validate_url('https://example.com')
        assert valid is True
        assert error is None

    def test_validate_url_no_scheme(self):
        """Test URL without scheme."""
        valid, error = URLValidator.validate_url('example.com')
        assert valid is False
        assert 'http://' in error or 'https://' in error

    def test_validate_url_invalid_scheme(self):
        """Test URL with invalid scheme."""
        valid, error = URLValidator.validate_url('ftp://example.com')
        assert valid is False
        assert 'http://' in error or 'https://' in error

    def test_validate_url_no_host(self):
        """Test URL without hostname."""
        valid, error = URLValidator.validate_url('http://')
        assert valid is False
        assert 'hostname' in error.lower()

    @patch('httpx.get')
    def test_validate_url_reachable_success(self, mock_get):
        """Test reachability check when URL is reachable."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        valid, error = URLValidator.validate_url(
            'http://example.com', check_reachable=True
        )
        assert valid is True
        assert error is None

    @patch('httpx.get')
    def test_validate_url_reachable_error(self, mock_get):
        """Test reachability check when URL returns error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        valid, error = URLValidator.validate_url(
            'http://example.com', check_reachable=True
        )
        assert valid is False
        assert '404' in error

    @patch('httpx.get')
    def test_validate_url_connection_error(self, mock_get):
        """Test reachability check when connection fails."""
        import httpx

        mock_get.side_effect = httpx.ConnectError('Connection refused')

        valid, error = URLValidator.validate_url(
            'http://example.com', check_reachable=True
        )
        assert valid is False
        assert 'connect' in error.lower()

    @patch('httpx.get')
    def test_validate_url_timeout(self, mock_get):
        """Test reachability check when timeout occurs."""
        import httpx

        mock_get.side_effect = httpx.TimeoutException('Timeout')

        valid, error = URLValidator.validate_url(
            'http://example.com', check_reachable=True
        )
        assert valid is False
        assert 'timeout' in error.lower()

    def test_validate_database_url_valid(self):
        """Test valid PostgreSQL database URL."""
        valid, error = URLValidator.validate_database_url(
            'postgresql://user:pass@localhost:5432/dbname'
        )
        assert valid is True
        assert error is None

    def test_validate_database_url_postgres_scheme(self):
        """Test database URL with postgres:// scheme."""
        valid, error = URLValidator.validate_database_url(
            'postgres://user:pass@localhost:5432/dbname'
        )
        assert valid is True
        assert error is None

    def test_validate_database_url_no_scheme(self):
        """Test database URL without proper scheme."""
        valid, error = URLValidator.validate_database_url(
            'user:pass@localhost:5432/dbname'
        )
        assert valid is False
        assert 'postgresql://' in error

    def test_validate_database_url_no_database(self):
        """Test database URL without database name."""
        valid, error = URLValidator.validate_database_url(
            'postgresql://user:pass@localhost:5432/'
        )
        assert valid is False
        assert 'database name' in error.lower()

    def test_validate_database_url_no_host(self):
        """Test database URL without hostname."""
        valid, error = URLValidator.validate_database_url('postgresql:///dbname')
        assert valid is False
        assert 'hostname' in error.lower()


class TestPortValidator:
    """Tests for PortValidator."""

    def test_validate_port_valid(self):
        """Test valid port number."""
        valid, error = PortValidator.validate_port(8080)
        assert valid is True
        assert error is None

    def test_validate_port_too_low(self):
        """Test port number too low."""
        valid, error = PortValidator.validate_port(0)
        assert valid is False
        assert 'between 1 and 65535' in error

    def test_validate_port_too_high(self):
        """Test port number too high."""
        valid, error = PortValidator.validate_port(70000)
        assert valid is False
        assert 'between 1 and 65535' in error

    def test_validate_port_privileged_warning(self):
        """Test warning for privileged port."""
        valid, error = PortValidator.validate_port(80)
        assert valid is True
        assert 'root privileges' in error.lower()

    def test_validate_port_not_integer(self):
        """Test non-integer port."""
        valid, error = PortValidator.validate_port('8080')
        assert valid is False
        assert 'must be an integer' in error

    def test_is_port_available_free(self):
        """Test checking if port is available (free)."""
        with patch('socket.socket') as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 1  # Connection fails = port free
            mock_socket.return_value.__enter__.return_value = mock_sock_instance

            result = PortValidator.is_port_available(9999)
            assert result is True

    def test_is_port_available_in_use(self):
        """Test checking if port is in use."""
        with patch('socket.socket') as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.connect_ex.return_value = 0  # Connection succeeds = port in use
            mock_socket.return_value.__enter__.return_value = mock_sock_instance

            result = PortValidator.is_port_available(9999)
            assert result is False

    def test_is_port_available_error(self):
        """Test port availability check when error occurs."""
        with patch('socket.socket', side_effect=Exception('Test error')):
            result = PortValidator.is_port_available(9999)
            assert result is False

    def test_get_port_status_available(self):
        """Test getting status of available port."""
        with patch.object(PortValidator, 'is_port_available', return_value=True):
            available, message = PortValidator.get_port_status(8080)
            assert available is True
            assert '8080' in message
            assert 'available' in message.lower()

    def test_get_port_status_in_use(self):
        """Test getting status of port in use."""
        with patch.object(PortValidator, 'is_port_available', return_value=False):
            with patch('psutil.process_iter', return_value=[]):
                available, message = PortValidator.get_port_status(8080)
                assert available is False
                assert '8080' in message
                assert 'in use' in message.lower()

    def test_get_port_status_with_process(self):
        """Test getting status when process using port is found."""
        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1234, 'name': 'test_process'}
        mock_connection = MagicMock()
        mock_connection.laddr.port = 8080
        mock_proc.connections.return_value = [mock_connection]

        with patch.object(PortValidator, 'is_port_available', return_value=False):
            with patch('psutil.process_iter', return_value=[mock_proc]):
                available, message = PortValidator.get_port_status(8080)
                assert available is False
                assert 'test_process' in message
                assert '1234' in message

    def test_get_port_status_invalid_port(self):
        """Test getting status of invalid port number."""
        available, message = PortValidator.get_port_status(99999)
        assert available is False
        assert 'between 1 and 65535' in message


class TestEmailValidator:
    """Tests for EmailValidator."""

    def test_validate_email_valid(self):
        """Test valid email address."""
        valid, error = EmailValidator.validate('user@example.com')
        assert valid is True
        assert error is None

    def test_validate_email_with_subdomain(self):
        """Test email with subdomain."""
        valid, error = EmailValidator.validate('user@mail.example.com')
        assert valid is True
        assert error is None

    def test_validate_email_with_plus(self):
        """Test email with plus sign."""
        valid, error = EmailValidator.validate('user+tag@example.com')
        assert valid is True
        assert error is None

    def test_validate_email_with_dots(self):
        """Test email with dots in username."""
        valid, error = EmailValidator.validate('first.last@example.com')
        assert valid is True
        assert error is None

    def test_validate_email_no_at(self):
        """Test invalid email without @ symbol."""
        valid, error = EmailValidator.validate('userexample.com')
        assert valid is False
        assert 'Invalid email format' in error

    def test_validate_email_no_domain(self):
        """Test invalid email without domain."""
        valid, error = EmailValidator.validate('user@')
        assert valid is False
        assert 'Invalid email format' in error

    def test_validate_email_no_tld(self):
        """Test invalid email without TLD."""
        valid, error = EmailValidator.validate('user@example')
        assert valid is False
        assert 'Invalid email format' in error

    def test_validate_email_empty(self):
        """Test empty email."""
        valid, error = EmailValidator.validate('')
        assert valid is False
        assert 'cannot be empty' in error.lower()

    def test_validate_email_whitespace(self):
        """Test whitespace-only email."""
        valid, error = EmailValidator.validate('   ')
        assert valid is False
        assert 'cannot be empty' in error.lower()

    def test_validate_email_strips_whitespace(self):
        """Test that whitespace is stripped from email."""
        valid, error = EmailValidator.validate('  user@example.com  ')
        assert valid is True
        assert error is None
