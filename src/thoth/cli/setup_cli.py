"""
Setup CLI command.

Provides CLI entry point for the setup wizard.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from loguru import logger


def configure_subparser(subparsers: ArgumentParser) -> None:
    """
    Configure the setup subcommand.

    Args:
        subparsers: ArgumentParser subparsers object
    """
    setup_parser = subparsers.add_parser(
        "setup",
        help="Run interactive setup wizard",
        description="Launch the Thoth setup wizard to configure your installation",
    )

    setup_parser.add_argument(
        "--vault",
        type=str,
        help="Path to Obsidian vault (skips vault selection)",
    )

    setup_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode using environment variables",
    )

    setup_parser.set_defaults(func=run_setup)


def run_setup(args: Namespace) -> None:
    """
    Run the setup wizard.

    Args:
        args: Command line arguments
    """
    logger.info("Starting Thoth setup wizard")

    if args.headless:
        logger.error("Headless setup mode not yet implemented")
        print("Error: Headless setup mode is not yet implemented")
        print("Please run 'thoth setup' without --headless for interactive setup")
        return

    # Launch the interactive TUI wizard
    from .setup.wizard import run_wizard

    try:
        run_wizard()
    except KeyboardInterrupt:
        logger.info("Setup wizard cancelled by user")
        print("\nSetup cancelled")
    except Exception as e:
        logger.error(f"Setup wizard failed: {e}")
        print(f"\nSetup failed: {e}")
        print("Please check the logs for more details")
        raise
