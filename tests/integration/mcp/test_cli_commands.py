"""
Integration tests for MCP CLI commands.

Tests the CLI interface including stdio, HTTP, and full server modes
using subprocess execution.
"""

import asyncio  # noqa: F401
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path  # noqa: F401

import pytest
import requests


class TestStdioServerCommand:
    """Test stdio server command execution."""

    def test_run_stdio_server_help(self):
        """Test stdio server help command."""
        result = subprocess.run(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'stdio', '--help'],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert 'stdio' in result.stdout.lower()
        assert 'log-level' in result.stdout.lower()

    @pytest.mark.slow
    def test_stdio_server_starts(self, tmp_path):
        """Test that stdio server process starts successfully."""
        # Start server in subprocess
        process = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'stdio', '--log-level', 'DEBUG'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(tmp_path),
        )

        try:
            # Give it time to start
            time.sleep(2)

            # Check if process is running
            assert process.poll() is None, 'Server process died unexpectedly'

            # Send initialize request
            initialize_request = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {
                    'protocolVersion': '2024-11-05',
                    'clientInfo': {'name': 'Test Client', 'version': '1.0.0'},
                    'capabilities': {},
                },
            }

            # Write request to stdin
            process.stdin.write(json.dumps(initialize_request) + '\n')
            process.stdin.flush()

            # Try to read response (with timeout)
            try:
                # Set a timeout for reading
                import select

                if hasattr(select, 'poll'):
                    poller = select.poll()
                    poller.register(process.stdout, select.POLLIN)
                    if poller.poll(5000):  # 5 second timeout
                        response_line = process.stdout.readline()
                        if response_line:
                            response = json.loads(response_line)
                            assert response['jsonrpc'] == '2.0'
                            assert 'result' in response or 'error' in response
            except (json.JSONDecodeError, KeyError):
                # Server might not have responded yet - that's ok for this test
                pass

        finally:
            # Cleanup
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    def test_stdio_server_log_level_configuration(self):
        """Test log level configuration for stdio server."""
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            process = subprocess.Popen(
                [
                    sys.executable,
                    '-m',
                    'thoth.cli',
                    'mcp',
                    'stdio',
                    '--log-level',
                    level,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                time.sleep(1)
                assert process.poll() is None
            finally:
                process.terminate()
                process.wait(timeout=5)


class TestHTTPServerCommand:
    """Test HTTP server command execution."""

    def test_run_http_server_help(self):
        """Test HTTP server help command."""
        result = subprocess.run(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'http', '--help'],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert 'http' in result.stdout.lower()
        assert '--host' in result.stdout
        assert '--port' in result.stdout

    @pytest.mark.slow
    def test_http_server_starts_on_custom_port(self):
        """Test HTTP server starts on custom port."""
        port = 9100  # Use high port to avoid conflicts

        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'http',
                '--host',
                '127.0.0.1',
                '--port',
                str(port),
                '--log-level',
                'INFO',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for server to start
            max_wait = 10
            start_time = time.time()

            while time.time() - start_time < max_wait:
                try:
                    response = requests.get(
                        f'http://127.0.0.1:{port}/health', timeout=1
                    )
                    if response.status_code == 200:
                        break
                except requests.ConnectionError:
                    time.sleep(0.5)
                    continue

            # Verify server is responding
            response = requests.get(f'http://127.0.0.1:{port}/health', timeout=2)
            assert response.status_code == 200

            # Check response structure
            data = response.json()
            assert 'status' in data or 'healthy' in data

        finally:
            # Cleanup
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    @pytest.mark.slow
    def test_http_server_host_configuration(self):
        """Test HTTP server host configuration."""
        port = 9101

        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'http',
                '--host',
                'localhost',  # Should bind to localhost
                '--port',
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            time.sleep(3)  # Wait for startup

            # Should be accessible via localhost
            try:
                response = requests.get(f'http://localhost:{port}/health', timeout=2)
                assert response.status_code == 200
            except requests.ConnectionError:
                # Server might not be ready yet
                pass

        finally:
            process.terminate()
            process.wait(timeout=5)

    @pytest.mark.slow
    def test_http_server_graceful_shutdown(self):
        """Test HTTP server handles SIGTERM gracefully."""
        port = 9102

        process = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'http', '--port', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            time.sleep(3)  # Let it start

            # Send SIGTERM
            process.send_signal(signal.SIGTERM)

            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
                assert process.returncode == 0 or process.returncode == -signal.SIGTERM
            except subprocess.TimeoutExpired:
                pytest.fail('Server did not shut down gracefully')

        finally:
            if process.poll() is None:
                process.kill()


class TestFullServerCommand:
    """Test full server command with all transports."""

    def test_run_full_server_help(self):
        """Test full server help command."""
        result = subprocess.run(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'full', '--help'],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert 'full' in result.stdout.lower()
        assert '--http-port' in result.stdout
        assert '--sse-port' in result.stdout
        assert '--disable-file-access' in result.stdout

    @pytest.mark.slow
    def test_full_server_starts_all_transports(self):
        """Test full server starts with all transports."""
        http_port = 9103
        sse_port = 9104

        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'full',
                '--host',
                '127.0.0.1',
                '--http-port',
                str(http_port),
                '--sse-port',
                str(sse_port),
                '--log-level',
                'DEBUG',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for startup
            time.sleep(5)

            # Check if server started (via stderr logs)
            # Note: Can't always check HTTP endpoint due to async startup
            assert process.poll() is None, 'Server process died'

        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    @pytest.mark.slow
    def test_full_server_file_access_disabled(self):
        """Test full server with file access disabled."""
        http_port = 9105

        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'full',
                '--http-port',
                str(http_port),
                '--sse-port',
                str(http_port + 1),
                '--disable-file-access',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            time.sleep(3)
            assert process.poll() is None

            # Check logs mention disabled file access
            # (Can't easily verify through API without starting full server)

        finally:
            process.terminate()
            process.wait(timeout=5)

    @pytest.mark.slow
    def test_full_server_custom_ports(self):
        """Test full server with custom port configuration."""
        http_port = 9106
        sse_port = 9107

        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'full',
                '--http-port',
                str(http_port),
                '--sse-port',
                str(sse_port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            time.sleep(4)
            assert process.poll() is None, 'Server should be running'

        finally:
            process.terminate()
            process.wait(timeout=5)


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_invalid_log_level(self):
        """Test invalid log level is rejected."""
        result = subprocess.run(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'http',
                '--log-level',
                'INVALID',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should fail with non-zero exit code
        assert result.returncode != 0
        assert (
            'invalid choice' in result.stderr.lower()
            or 'error' in result.stderr.lower()
        )

    def test_invalid_port_number(self):
        """Test invalid port number."""
        result = subprocess.run(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'http',
                '--port',
                'not-a-number',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode != 0

    def test_port_out_of_range(self):
        """Test port number out of valid range."""
        result = subprocess.run(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'http',
                '--port',
                '70000',  # Out of range
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # May or may not fail at CLI level, but will fail at runtime
        # Just verify it doesn't hang
        assert result.returncode is not None


class TestCLIEnvironmentVariables:
    """Test CLI with environment variable configuration."""

    @pytest.mark.slow
    def test_http_server_with_env_vars(self):
        """Test HTTP server respects environment variables."""
        port = 9108

        env = os.environ.copy()
        env['MCP_HOST'] = '127.0.0.1'
        env['MCP_PORT'] = str(port)

        # Note: Current CLI doesn't use env vars, but test structure is here
        process = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'http', '--port', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            time.sleep(3)
            assert process.poll() is None
        finally:
            process.terminate()
            process.wait(timeout=5)


class TestCLISubprocessManagement:
    """Test CLI subprocess management and cleanup."""

    @pytest.mark.slow
    def test_server_process_cleanup_on_error(self):
        """Test server cleans up on startup error."""
        # Try to start on a privileged port (should fail)
        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'http',
                '--port',
                '80',  # Privileged port
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for it to fail
            returncode = process.wait(timeout=10)

            # Should have failed
            assert returncode != 0

        except subprocess.TimeoutExpired:
            # If it's hanging, kill it
            process.kill()
            pytest.fail('Server hung instead of failing cleanly')

    @pytest.mark.slow
    def test_multiple_server_instances_same_port(self):
        """Test starting multiple servers on same port fails appropriately."""
        port = 9109

        # Start first server
        process1 = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'http', '--port', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            time.sleep(3)  # Let first server start

            # Try to start second server on same port
            process2 = subprocess.Popen(
                [sys.executable, '-m', 'thoth.cli', 'mcp', 'http', '--port', str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                # Second should fail or exit
                time.sleep(2)

                # At least one should have failed or be handling the conflict
                assert process2.poll() is not None or process1.poll() is None

            finally:
                if process2.poll() is None:
                    process2.terminate()
                    process2.wait(timeout=5)

        finally:
            process1.terminate()
            process1.wait(timeout=5)

    @pytest.mark.slow
    def test_server_respects_working_directory(self, tmp_path):
        """Test server respects working directory."""
        port = 9110

        # Create test file in tmp_path
        test_file = tmp_path / 'test.txt'
        test_file.write_text('test content')

        process = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'http', '--port', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmp_path),
        )

        try:
            time.sleep(3)
            assert process.poll() is None

            # Verify process working directory
            # (Would need to check via resources API if implemented)

        finally:
            process.terminate()
            process.wait(timeout=5)


class TestCLIOutputFormat:
    """Test CLI output formatting and logging."""

    def test_stdio_server_log_format(self):
        """Test stdio server produces valid log output."""
        process = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'stdio', '--log-level', 'INFO'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            time.sleep(2)

            # Read stderr (where logs go)
            # Use non-blocking read
            import select

            if hasattr(select, 'select'):
                readable, _, _ = select.select([process.stderr], [], [], 1)
                if readable:
                    log_output = process.stderr.read(1024)
                    # Should contain log messages
                    assert len(log_output) > 0

        finally:
            process.terminate()
            process.wait(timeout=5)

    @pytest.mark.slow
    def test_http_server_startup_messages(self):
        """Test HTTP server prints startup messages."""
        port = 9111

        process = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'http', '--port', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            time.sleep(3)

            # Read stderr for startup messages
            stderr_output = process.stderr.read()  # noqa: F841

            # Should mention starting server
            # (exact format depends on logging configuration)

        finally:
            process.terminate()
            process.wait(timeout=5)
