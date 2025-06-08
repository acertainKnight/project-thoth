import argparse

from . import agent, discovery, notes, rag, system


def main():
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
    notes.configure_subparser(subparsers)
    rag.configure_subparser(subparsers)
    system.configure_subparser(subparsers)

    args = parser.parse_args()

    if hasattr(args, 'func'):
        args.func(args)
    else:
        # This part should ideally not be reached if 'required=True' is set on
        # subparsers
        parser.print_help()


if __name__ == '__main__':
    main()
