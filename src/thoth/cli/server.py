"""
Unified server management for Thoth services.

This module provides commands for starting and managing multiple Thoth services
simultaneously, including discovery, API, and MCP servers.
"""

import signal
import sys
import threading
import time
from multiprocessing import Process

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.services.discovery_server import DiscoveryServer


def start_discovery_server(config):  # noqa: ARG001
    """Start the discovery server in a separate process."""
    try:
        # Set up logging for subprocess
        logger.info('Starting discovery server process...')

        # Create pipeline and discovery server
        pipeline = ThothPipeline()
        server = DiscoveryServer(
            config=pipeline.config, discovery_service=pipeline.services.discovery
        )
        server.initialize()

        # Run server
        server.run_server_blocking()

    except KeyboardInterrupt:
        logger.info('Discovery server shutting down...')
    except Exception as e:
        logger.error(f'Discovery server error: {e}')


def start_api_server(host='127.0.0.1', port=8000, base_url='/', reload=False):
    """Start the API server in a separate process."""
    try:
        logger.info(f'Starting API server process on {host}:{port}...')

        # Import here to avoid circular dependencies
        from pathlib import Path  # noqa: I001

        from thoth.server.app import start_obsidian_server
        from thoth.config import config

        # Get configuration
        # config imported globally from thoth.config

        # Run API server
        start_obsidian_server(
            host=host,
            port=port,
            pdf_directory=Path(config.pdf_dir),
            notes_directory=Path(config.notes_dir),
            base_url=base_url,
            reload=reload,
        )

    except KeyboardInterrupt:
        logger.info('API server shutting down...')
    except Exception as e:
        logger.error(f'API server error: {e}')


def start_mcp_server(mode='http', host='127.0.0.1', port=3000):
    """Start the MCP server in a separate process."""
    try:
        logger.info(f'Starting MCP server process in {mode} mode...')

        # Import here to avoid circular dependencies
        if mode == 'http':
            from thoth.mcp.launcher import run_http_server

            run_http_server(host=host, port=port)
        elif mode == 'stdio':
            from thoth.mcp.launcher import run_stdio_server

            run_stdio_server()
        elif mode == 'full':
            from thoth.mcp.launcher import run_full_server

            run_full_server()
        else:
            raise ValueError(f'Unknown MCP mode: {mode}')

    except KeyboardInterrupt:
        logger.info('MCP server shutting down...')
    except Exception as e:
        logger.error(f'MCP server error: {e}')


class UnifiedServerManager:
    """Manager for running multiple Thoth services simultaneously."""

    def __init__(self):
        """Initialize the server manager."""
        self.processes = {}
        self.running = False
        self.shutdown_event = threading.Event()

    def start_all_servers(
        self,
        include_discovery=True,
        include_api=True,
        include_mcp=True,
        api_host='127.0.0.1',
        api_port=8000,
        api_base_url='/',
        api_reload=False,
        mcp_mode='http',
        mcp_host='127.0.0.1',
        mcp_port=3000,
    ):
        """
        Start all requested servers.

        Args:
            include_discovery: Whether to start discovery server
            include_api: Whether to start API server
            include_mcp: Whether to start MCP server
            api_host: API server host
            api_port: API server port
            api_base_url: API server base URL
            api_reload: Enable API server auto-reload
            mcp_mode: MCP server mode (http, stdio, full)
            mcp_host: MCP server host
            mcp_port: MCP server port
        """
        try:
            logger.info('Starting Thoth unified server...')
            self.running = True

            # Set up signal handlers
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

            # Start discovery server
            if include_discovery:
                logger.info('Starting discovery server...')
                config = None  # Will be created in subprocess
                discovery_process = Process(
                    target=start_discovery_server,
                    args=(config,),
                    name='discovery-server',
                )
                discovery_process.start()
                self.processes['discovery'] = discovery_process

            # Start API server
            if include_api:
                logger.info(f'Starting API server on {api_host}:{api_port}...')
                api_process = Process(
                    target=start_api_server,
                    args=(api_host, api_port, api_base_url, api_reload),
                    name='api-server',
                )
                api_process.start()
                self.processes['api'] = api_process

            # Start MCP server
            if include_mcp:
                logger.info(f'Starting MCP server in {mcp_mode} mode...')
                mcp_process = Process(
                    target=start_mcp_server,
                    args=(mcp_mode, mcp_host, mcp_port),
                    name='mcp-server',
                )
                mcp_process.start()
                self.processes['mcp'] = mcp_process

            # Log startup summary
            services = []
            if include_discovery:
                services.append('Discovery Server')
            if include_api:
                services.append(f'API Server ({api_host}:{api_port})')
            if include_mcp:
                services.append(f'MCP Server ({mcp_mode} mode)')

            logger.info(f'All services started successfully: {", ".join(services)}')
            logger.info('Press Ctrl+C to stop all servers')

            # Monitor processes
            self._monitor_processes()

        except Exception as e:
            logger.error(f'Error starting servers: {e}')
            self.stop_all_servers()
            raise

    def stop_all_servers(self):
        """Stop all running servers gracefully."""
        if not self.running:
            return

        logger.info('Stopping all servers...')
        self.running = False
        self.shutdown_event.set()

        # Terminate all processes gracefully
        for service_name, process in self.processes.items():
            if process.is_alive():
                logger.info(f'Stopping {service_name} server...')
                process.terminate()

        # Wait for processes to stop
        for service_name, process in self.processes.items():
            if process.is_alive():
                logger.info(f'Waiting for {service_name} to stop...')
                process.join(timeout=10)

                # Force kill if still alive
                if process.is_alive():
                    logger.warning(f'Force killing {service_name} server...')
                    process.kill()
                    process.join()

        self.processes.clear()
        logger.info('All servers stopped')

    def get_status(self):
        """Get status of all services."""
        status = {}
        for service_name, process in self.processes.items():
            status[service_name] = {
                'running': process.is_alive(),
                'pid': process.pid if process.is_alive() else None,
                'name': process.name,
            }
        return status

    def _signal_handler(self, signum, frame):  # noqa: ARG002
        """Handle shutdown signals."""
        logger.info(f'Received signal {signum}, shutting down all servers...')
        self.stop_all_servers()
        sys.exit(0)

    def _monitor_processes(self):
        """Monitor all processes and handle failures."""
        while self.running:
            try:
                # Check if any process has died
                dead_processes = []
                for service_name, process in self.processes.items():
                    if not process.is_alive():
                        dead_processes.append(service_name)

                # Report dead processes
                for service_name in dead_processes:
                    process = self.processes[service_name]
                    exit_code = process.exitcode
                    logger.error(
                        f'{service_name} server died with exit code {exit_code}'
                    )

                # Wait before next check
                if self.shutdown_event.wait(timeout=5):
                    break

            except KeyboardInterrupt:
                logger.info('Shutdown requested by user')
                break
            except Exception as e:
                logger.error(f'Error monitoring processes: {e}')
                time.sleep(5)

        self.stop_all_servers()


def run_unified_server(args, pipeline: ThothPipeline):  # noqa: ARG001
    """Run unified server with all services."""
    try:
        # Parse arguments with defaults for when called without subcommand
        include_discovery = not getattr(args, 'no_discovery', False)
        include_api = not getattr(args, 'no_api', False)
        include_mcp = not getattr(args, 'no_mcp', False)

        # Validate at least one service is enabled
        if not (include_discovery or include_api or include_mcp):
            logger.error('At least one service must be enabled')
            return 1

        # Get arguments with defaults
        api_host = getattr(args, 'api_host', '127.0.0.1')
        api_port = getattr(args, 'api_port', 8000)
        api_base_url = getattr(args, 'api_base_url', '/')
        api_reload = getattr(args, 'api_reload', False)
        mcp_mode = getattr(args, 'mcp_mode', 'http')
        mcp_host = getattr(args, 'mcp_host', '127.0.0.1')
        mcp_port = getattr(args, 'mcp_port', 3000)

        # Create and start server manager
        manager = UnifiedServerManager()
        manager.start_all_servers(
            include_discovery=include_discovery,
            include_api=include_api,
            include_mcp=include_mcp,
            api_host=api_host,
            api_port=api_port,
            api_base_url=api_base_url,
            api_reload=api_reload,
            mcp_mode=mcp_mode,
            mcp_host=mcp_host,
            mcp_port=mcp_port,
        )

        return 0

    except KeyboardInterrupt:
        logger.info('Unified server stopped by user')
        return 0
    except Exception as e:
        logger.error(f'Error running unified server: {e}')
        return 1


def run_server_status(args, pipeline: ThothPipeline):  # noqa: ARG001
    """Show status of running services."""
    try:
        logger.info('Checking server status...')

        # This is a simplified status check
        # In a production system, you might want to check actual process status
        # or health endpoints

        logger.info('Server Status:')
        logger.info('  Note: This shows configuration, not actual running status')
        logger.info('  Discovery Server: Configured')
        logger.info('  API Server: Configured')
        logger.info('  MCP Server: Configured')
        logger.info('')
        logger.info('To check actual running processes, use: ps aux | grep thoth')

        return 0
    except Exception as e:
        logger.error(f'Error checking server status: {e}')
        return 1


def configure_subparser(subparsers):
    """Configure the subparser for the server command."""
    parser = subparsers.add_parser(
        'server', help='Unified server management (discovery, API, MCP)'
    )
    subparsers = parser.add_subparsers(
        dest='server_command', help='Server command to run', required=False
    )

    # Start command (default)
    start_parser = subparsers.add_parser('start', help='Start all servers (default)')

    # Service selection options
    start_parser.add_argument(
        '--no-discovery', action='store_true', help='Disable discovery server'
    )
    start_parser.add_argument(
        '--no-api', action='store_true', help='Disable API server'
    )
    start_parser.add_argument(
        '--no-mcp', action='store_true', help='Disable MCP server'
    )

    # API server options
    start_parser.add_argument(
        '--api-host', default='127.0.0.1', help='API server host (default: 127.0.0.1)'
    )
    start_parser.add_argument(
        '--api-port', type=int, default=8000, help='API server port (default: 8000)'
    )
    start_parser.add_argument(
        '--api-base-url', default='/', help='API server base URL (default: /)'
    )
    start_parser.add_argument(
        '--api-reload', action='store_true', help='Enable API server auto-reload'
    )

    # MCP server options
    start_parser.add_argument(
        '--mcp-mode',
        choices=['http', 'stdio', 'full'],
        default='http',
        help='MCP server mode (default: http)',
    )
    start_parser.add_argument(
        '--mcp-host', default='127.0.0.1', help='MCP server host (default: 127.0.0.1)'
    )
    start_parser.add_argument(
        '--mcp-port', type=int, default=3000, help='MCP server port (default: 3000)'
    )

    start_parser.set_defaults(func=run_unified_server)

    # Status command
    status_parser = subparsers.add_parser('status', help='Show server status')
    status_parser.set_defaults(func=run_server_status)

    # Default to start command when no subcommand is provided
    parser.set_defaults(func=run_unified_server)
