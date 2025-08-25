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

from thoth.pipeline import ThothPipeline  # noqa: E402

from . import (  # noqa: E402
    agent,
    discovery,
    mcp,
    memory,
    notes,
    pdf,
    performance,
    rag,
    server,
    system,
)


def main() -> None:
    """Main entry point for the Thoth CLI."""
    parser = argparse.ArgumentParser(
        description='Thoth - Academic PDF processing system'
    )
    subparsers = parser.add_subparsers(
        dest='command', help='Command to run', required=True
    )

    # Register sub-commands from modules
    agent.configure_subparser(subparsers)
    discovery.configure_subparser(subparsers)
    mcp.configure_subparser(subparsers)
    memory.configure_subparser(subparsers)
    notes.configure_subparser(subparsers)
    pdf.configure_subparser(subparsers)
    performance.configure_subparser(subparsers)
    rag.configure_subparser(subparsers)
    server.configure_subparser(subparsers)
    system.configure_subparser(subparsers)

    args = parser.parse_args()

    # Create a single pipeline instance to be used by all commands
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
