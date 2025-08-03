"""
MCP server CLI commands.

This module provides command-line interface for running MCP servers
with different transport configurations.
"""

import sys

from loguru import logger

from thoth.pipeline import ThothPipeline


def configure_subparser(subparsers):
    """Configure the MCP subparser."""
    parser = subparsers.add_parser(
        'mcp', help='Run MCP (Model Context Protocol) server'
    )

    # Add subcommands for different MCP server modes
    mcp_subparsers = parser.add_subparsers(
        dest='mcp_command', help='MCP server mode', required=True
    )

    # Stdio server (for CLI integration)
    stdio_parser = mcp_subparsers.add_parser(
        'stdio', help='Run MCP server with stdio transport (for CLI integration)'
    )
    stdio_parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level for the server',
    )
    stdio_parser.set_defaults(func=run_stdio_server)

    # HTTP server
    http_parser = mcp_subparsers.add_parser(
        'http', help='Run MCP server with HTTP transport'
    )
    http_parser.add_argument(
        '--host', default='localhost', help='HTTP server host (default: localhost)'
    )
    http_parser.add_argument(
        '--port', type=int, default=8000, help='HTTP server port (default: 8000)'
    )
    http_parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level for the server',
    )
    http_parser.set_defaults(func=run_http_server)

    # Full server (all transports)
    full_parser = mcp_subparsers.add_parser(
        'full', help='Run MCP server with all transports (stdio, HTTP, SSE)'
    )
    full_parser.add_argument(
        '--host', default='localhost', help='Server host (default: localhost)'
    )
    full_parser.add_argument(
        '--http-port', type=int, default=8000, help='HTTP server port (default: 8000)'
    )
    full_parser.add_argument(
        '--sse-port', type=int, default=8001, help='SSE server port (default: 8001)'
    )
    full_parser.add_argument(
        '--disable-file-access',
        action='store_true',
        help='Disable file system resource access',
    )
    full_parser.add_argument(
        '--file-paths',
        nargs='*',
        help='Additional file system paths to expose as resources',
    )
    full_parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level for the server',
    )
    full_parser.set_defaults(func=run_full_server)

    # Legacy compatibility (equivalent to the old mcp-server command)
    legacy_parser = mcp_subparsers.add_parser(
        'server', help='Run MCP server (legacy compatibility - same as http mode)'
    )
    legacy_parser.add_argument(
        '--host', default='localhost', help='HTTP server host (default: localhost)'
    )
    legacy_parser.add_argument(
        '--port', type=int, default=8000, help='HTTP server port (default: 8000)'
    )
    legacy_parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level for the server',
    )
    legacy_parser.set_defaults(func=run_http_server)


def run_stdio_server(args, _pipeline: ThothPipeline):
    """Run MCP server with stdio transport only."""
    from thoth.mcp.launcher import run_stdio_server

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    logger.info('Starting MCP server with stdio transport...')
    run_stdio_server()


def run_http_server(args, _pipeline: ThothPipeline):
    """Run MCP server with HTTP transport only."""
    import sys

    from thoth.mcp.launcher import run_http_server

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    logger.info(f'Starting MCP HTTP server at {args.host}:{args.port}...')
    run_http_server(host=args.host, port=args.port)


def run_full_server(args, _pipeline: ThothPipeline):
    """Run MCP server with all transports."""
    import sys

    from thoth.mcp.launcher import run_full_server

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    enable_file_access = not args.disable_file_access

    logger.info('Starting full MCP server...')
    logger.info(f'  HTTP: {args.host}:{args.http_port}')
    logger.info(f'  SSE: {args.host}:{args.sse_port}')
    logger.info('  Stdio: enabled')
    logger.info(f'  File access: {"enabled" if enable_file_access else "disabled"}')

    if args.file_paths:
        logger.info(f'  Additional file paths: {args.file_paths}')

    run_full_server(
        http_host=args.host,
        http_port=args.http_port,
        sse_port=args.sse_port,
        enable_file_access=enable_file_access,
    )
