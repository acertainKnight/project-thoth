"""
Interactive prompts for CLI commands.

Provides helper functions for interactive user input in command-line tools.
"""


def prompt_choice(question: str, options: list[tuple[str, str]]) -> str:
    """
    Prompt user to choose from a list of options.

    Args:
        question: Question to ask the user
        options: List of (value, description) tuples

    Returns:
        Selected value

    Example:
        mode = prompt_choice(
            "Choose mode:",
            [
                ("cloud", "Letta Cloud (hosted)"),
                ("self-hosted", "Self-hosted (local)")
            ]
        )
    """
    print(question)
    print()

    for i, (value, description) in enumerate(options, 1):
        print(f'  {i}. {description}')

    print()

    while True:
        try:
            choice = input(f'Enter choice (1-{len(options)}): ').strip()
            idx = int(choice) - 1

            if 0 <= idx < len(options):
                selected = options[idx][0]
                print()
                return selected
            else:
                print(f'Please enter a number between 1 and {len(options)}')

        except (ValueError, KeyboardInterrupt):
            print('Please enter a valid number')


def prompt_text(question: str, default: str = '') -> str:
    """
    Prompt user for text input.

    Args:
        question: Question to ask the user
        default: Default value if user presses enter

    Returns:
        User input string

    Example:
        api_key = prompt_text("Enter your API key:")
    """
    if default:
        prompt = f'{question} (default: {default}): '
    else:
        prompt = f'{question}: '

    response = input(prompt).strip()

    if not response and default:
        return default

    return response


def confirm(question: str, default: bool = False) -> bool:
    """
    Ask user for yes/no confirmation.

    Args:
        question: Question to ask the user
        default: Default value if user presses enter

    Returns:
        True if yes, False if no

    Example:
        if confirm("Continue?"):
            # Do something
    """
    if default:
        prompt = f'{question} (Y/n): '
    else:
        prompt = f'{question} (y/N): '

    while True:
        response = input(prompt).strip().lower()

        if not response:
            return default

        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' or 'n'")
