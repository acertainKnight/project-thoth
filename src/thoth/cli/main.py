import argparse
import asyncio
import inspect
import os


# Configure environment variables early to prevent segmentation faults
# with sentence-transformers and ChromaDB
def _configure_safe_environment() -> None:
    """Configure environment variables to prevent segmentation faults."""
    # Prevent threading issues that can cause segfaults
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
    os.environ['NUMEXPR_NUM_THREADS'] = '1'
    os.environ['TORCH_NUM_THREADS'] = '1'

    # Configure ChromaDB to be safer
    os.environ['CHROMA_MAX_BATCH_SIZE'] = '100'
    os.environ['CHROMA_SUBMIT_BATCH_SIZE'] = '100'
    os.environ['SQLITE_ENABLE_PREUPDATE_HOOK'] = '0'
    os.environ['SQLITE_ENABLE_FTS5'] = '0'


# Configure environment variables before importing any ML libraries
_configure_safe_environment()

from loguru import logger  # noqa: E402

logger.info('===== main.py: About to import CLI submodules =====')
from . import (  # noqa: E402
    database,
    discovery,
    letta,
    mcp,
    notes,
    pdf,
    performance,
    rag,
    research,
    schema,
    server,
    service,
    setup_cli,
    system,
)

logger.info('===== main.py: CLI submodules imported successfully =====')


def main() -> None:
    """Main entry point for the Thoth CLI."""
    logger.info('===== main(): Function called, parsing arguments =====')
    parser = argparse.ArgumentParser(
        description='Thoth - Academic PDF processing system'
    )
    subparsers = parser.add_subparsers(
        dest='command', help='Command to run', required=True
    )

    # Register sub-commands from modules
    # agent.configure_subparser(subparsers)  # DEPRECATED: Use Letta REST API (port 8283)  # noqa: W505
    database.configure_subparser(subparsers)
    discovery.configure_subparser(subparsers)
    letta.configure_subparser(subparsers)
    mcp.configure_subparser(subparsers)
    # memory.configure_subparser(subparsers)  # DEPRECATED: Use Letta REST API (port 8283)  # noqa: W505
    notes.configure_subparser(subparsers)
    pdf.configure_subparser(subparsers)
    performance.configure_subparser(subparsers)
    rag.configure_subparser(subparsers)
    research.configure_subparser(subparsers)
    schema.configure_subparser(subparsers)
    server.configure_subparser(subparsers)
    service.configure_subparser(subparsers)
    setup_cli.configure_subparser(subparsers)
    system.configure_subparser(subparsers)

    args = parser.parse_args()

    # Skip initialization for setup and db commands (they don't need full Thoth initialization)
    if args.command in ['setup', 'db']:
        if hasattr(args, 'func'):
            if inspect.iscoroutinefunction(args.func):
                asyncio.run(args.func(args))
            else:
                args.func(args)
        return

    # Initialize Thoth using the new factory function
    # Lazy import to avoid premature config loading
    # Replaces ThothPipeline() and provides cleaner access to components
    logger.info('===== main(): About to import initialize_thoth =====')
    from thoth.initialization import initialize_thoth
    logger.info('===== main(): initialize_thoth imported successfully =====')

    _services, _document_pipeline, _citation_tracker = initialize_thoth()

    # Create ThothPipeline wrapper for backward compatibility with CLI commands
    # that still expect it (will be removed once all commands are updated)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from thoth.pipeline import ThothPipeline  # Lazy import
        pipeline = ThothPipeline()

    if hasattr(args, 'func'):
        # Check if the function is async and handle accordingly
        if inspect.iscoroutinefunction(args.func):
            asyncio.run(args.func(args, pipeline))
        else:
            args.func(args, pipeline)
    else:
        # This part should ideally not be reached if 'required=True' is set on
        # subparsers
        parser.print_help()


if __name__ == '__main__':
    main()
