"""
CLI commands for managing analysis schemas.

Provides command-line interface for schema validation, listing presets, and switching schemas.
"""

import json

from rich.console import Console
from rich.table import Table

from thoth.config import config
from thoth.services.analysis_schema_service import AnalysisSchemaService

console = Console()


def configure_subparser(subparsers):
    """Configure the schema management subparser."""
    parser = subparsers.add_parser(
        'schema',
        help='Manage analysis schemas',
        description='Validate, list, and switch analysis schema presets',
    )

    schema_subparsers = parser.add_subparsers(
        dest='schema_command', help='Schema command'
    )

    # Validate schema command
    validate_parser = schema_subparsers.add_parser(
        'validate', help='Validate the schema configuration file'
    )
    validate_parser.set_defaults(func=validate_command)

    # List presets command
    list_parser = schema_subparsers.add_parser(
        'list', help='List all available schema presets'
    )
    list_parser.set_defaults(func=list_command)

    # Show current info command
    info_parser = schema_subparsers.add_parser(
        'info', help='Show current schema information'
    )
    info_parser.set_defaults(func=info_command)

    # Set preset command
    set_parser = schema_subparsers.add_parser(
        'set', help='Switch to a different preset'
    )
    set_parser.add_argument(
        'preset',
        help='Name of the preset to activate (standard, detailed, minimal, custom)',
    )
    set_parser.set_defaults(func=set_command)

    # Show preset details command
    details_parser = schema_subparsers.add_parser(
        'details', help='Show detailed information about a preset'
    )
    details_parser.add_argument('preset', help='Name of the preset to show details for')
    details_parser.set_defaults(func=details_command)

    return parser


def validate_command(args):
    """Validate the schema configuration file."""
    try:
        schema_service = AnalysisSchemaService(config=config)
        schema_path = schema_service.schema_path

        # Check file exists
        if not schema_path.exists():
            console.print(f'[red]✗[/red] Schema file not found: {schema_path}')
            console.print(
                '[yellow]Tip:[/yellow] The schema file will be auto-created on first PDF processing'
            )
            return 1

        # Try to load and validate
        try:
            with open(schema_path, encoding='utf-8') as f:
                schema_config = json.load(f)

            # Validate structure
            schema_service._validate_schema_config(schema_config)

            # Get validation details
            version = schema_config.get('version', 'unknown')
            active_preset = schema_config.get('active_preset', 'unknown')
            preset_count = len(schema_config.get('presets', {}))

            console.print('[green]✓[/green] Schema file is valid')
            console.print(f'  [dim]Path:[/dim] {schema_path}')
            console.print(f'  [dim]Version:[/dim] {version}')
            console.print(f'  [dim]Active Preset:[/dim] {active_preset}')
            console.print(f'  [dim]Available Presets:[/dim] {preset_count}')

            return 0

        except json.JSONDecodeError as e:
            console.print('[red]✗[/red] Invalid JSON in schema file')
            console.print(f'  [dim]Error:[/dim] {e}')
            console.print(f'  [dim]Path:[/dim] {schema_path}')
            return 1

        except Exception as e:
            console.print('[red]✗[/red] Schema validation failed')
            console.print(f'  [dim]Error:[/dim] {e}')
            console.print(f'  [dim]Path:[/dim] {schema_path}')
            return 1

    except Exception as e:
        console.print(f'[red]Error:[/red] {e}')
        return 1


def list_command(args):
    """List all available schema presets."""
    try:
        schema_service = AnalysisSchemaService(config=config)
        schema_service.initialize()

        presets = schema_service.list_available_presets()
        active_preset = schema_service.get_active_preset_name()

        # Create table
        table = Table(title='Available Analysis Schema Presets')
        table.add_column('Preset', style='cyan')
        table.add_column('Name', style='white')
        table.add_column('Description', style='dim')
        table.add_column('Active', justify='center')

        for preset in presets:
            is_active = '✓' if preset['id'] == active_preset else ''
            table.add_row(
                preset['id'], preset['name'], preset['description'], is_active
            )

        console.print(table)
        console.print("\n[dim]Use 'thoth schema set <preset>' to switch presets[/dim]")

        return 0

    except Exception as e:
        console.print(f'[red]Error:[/red] {e}')
        return 1


def info_command(args):
    """Show current schema information."""
    try:
        schema_service = AnalysisSchemaService(config=config)
        schema_service.initialize()

        preset_name = schema_service.get_active_preset_name()
        version = schema_service.get_schema_version()
        instructions = schema_service.get_preset_instructions()

        model = schema_service.get_active_model()
        fields = list(model.model_fields.keys())

        console.print('[bold]Current Analysis Schema[/bold]\n')
        console.print(f'  [cyan]Preset:[/cyan] {preset_name}')
        console.print(f'  [cyan]Version:[/cyan] {version}')
        console.print(f'  [cyan]Fields:[/cyan] {len(fields)}')
        console.print(f'  [cyan]Schema Path:[/cyan] {schema_service.schema_path}\n')

        if instructions:
            console.print('  [cyan]Instructions:[/cyan]')
            console.print(f'  [dim]{instructions}[/dim]\n')

        console.print('  [cyan]Field List:[/cyan]')
        for i, field in enumerate(fields, 1):
            console.print(f'    {i}. {field}')

        console.print(
            f"\n[dim]Use 'thoth schema details {preset_name}' for full field specifications[/dim]"
        )

        return 0

    except Exception as e:
        console.print(f'[red]Error:[/red] {e}')
        return 1


def set_command(args):
    """Switch to a different preset."""
    try:
        schema_service = AnalysisSchemaService(config=config)
        schema_service.initialize()

        # Load current schema
        schema_config = schema_service.load_schema()

        # Check if preset exists
        if args.preset not in schema_config['presets']:
            available = list(schema_config['presets'].keys())
            console.print(f"[red]✗[/red] Preset '{args.preset}' not found")
            console.print(
                f'  [yellow]Available presets:[/yellow] {", ".join(available)}'
            )
            return 1

        # Update active preset
        schema_config['active_preset'] = args.preset

        # Save back to file
        schema_path = schema_service.schema_path
        with open(schema_path, 'w', encoding='utf-8') as f:
            json.dump(schema_config, f, indent=2, ensure_ascii=False)

        # Reload schema
        schema_service.load_schema(force_reload=True)

        # Get new preset info
        new_model = schema_service.get_active_model()
        field_count = len(new_model.model_fields)

        console.print(f"[green]✓[/green] Switched to '{args.preset}' preset")
        console.print(f'  [dim]Fields:[/dim] {field_count}')
        console.print('\n[dim]All subsequent PDF processing will use this schema[/dim]')

        return 0

    except Exception as e:
        console.print(f'[red]Error:[/red] {e}')
        return 1


def details_command(args):
    """Show detailed information about a preset."""
    try:
        schema_service = AnalysisSchemaService(config=config)
        schema_service.initialize()

        # Load schema
        schema_config = schema_service.load_schema()

        # Check if preset exists
        if args.preset not in schema_config['presets']:
            available = list(schema_config['presets'].keys())
            console.print(f"[red]✗[/red] Preset '{args.preset}' not found")
            console.print(
                f'  [yellow]Available presets:[/yellow] {", ".join(available)}'
            )
            return 1

        preset_config = schema_config['presets'][args.preset]

        console.print(f'[bold]{preset_config.get("name", args.preset)}[/bold]\n')
        console.print(f'  [dim]{preset_config.get("description", "")}[/dim]\n')

        if preset_config.get('instructions'):
            console.print('  [cyan]Instructions:[/cyan]')
            console.print(f'  [dim]{preset_config["instructions"]}[/dim]\n')

        # Create fields table
        table = Table(title=f"Fields in '{args.preset}' preset")
        table.add_column('Field', style='cyan')
        table.add_column('Type', style='yellow')
        table.add_column('Required', justify='center')
        table.add_column('Description', style='dim')

        for field_name, field_spec in preset_config['fields'].items():
            field_type = field_spec.get('type', 'string')
            if field_type == 'array':
                items = field_spec.get('items', 'string')
                field_type = f'array[{items}]'

            required = '✓' if field_spec.get('required', False) else ''
            description = field_spec.get('description', '')

            table.add_row(field_name, field_type, required, description)

        console.print(table)
        console.print(f'\n[dim]Total: {len(preset_config["fields"])} fields[/dim]')

        return 0

    except Exception as e:
        console.print(f'[red]Error:[/red] {e}')
        return 1
