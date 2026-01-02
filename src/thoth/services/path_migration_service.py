"""
Path Migration Service for Thoth.

Automatically normalizes file paths in tracker and graph files when the app starts
on a different machine. This allows seamless migration between Windows/WSL/Linux.
"""

import json
import re
from pathlib import Path
from typing import Any

from loguru import logger


class PathMigrationService:
    """
    Service to automatically normalize file paths across different machines.

    This service ensures that when Thoth data is synced between machines
    (via Obsidian Sync or manual transfer), all file paths are automatically
    updated to match the current machine's configuration.
    """

    def __init__(self, config):
        """
        Initialize the path migration service.

        Args:
            config: Thoth configuration object
        """
        self.config = config
        self.vault_path = Path(config.pdf_dir).parent.parent  # Get vault root
        self.data_path = Path(config.workspace_dir)
        self.pdf_dir = Path(config.pdf_dir)
        self.notes_dir = Path(config.notes_dir)
        self.markdown_dir = Path(config.markdown_dir)

        logger.debug(f'PathMigrationService initialized')  # noqa: F541
        logger.debug(f'  Vault path: {self.vault_path}')
        logger.debug(f'  Data path: {self.data_path}')

    def detect_path_format(self, path_str: str) -> str:
        """
        Detect if a path is from a different machine/OS.

        Args:
            path_str: Path string to check

        Returns:
            str: 'windows', 'wsl', 'linux', or 'docker'
        """
        if not path_str:
            return 'unknown'

        normalized = path_str.replace('\\', '/')

        if normalized.startswith('C:/') or normalized.startswith('D:/'):
            return 'windows'
        elif normalized.startswith('/mnt/c/') or normalized.startswith('/mnt/d/'):
            return 'wsl'
        elif normalized.startswith('/workspace/'):
            return 'docker'
        else:
            return 'linux'

    def needs_migration(self, path_str: str) -> bool:
        """
        Check if a path needs to be migrated to current machine format.

        Args:
            path_str: Path string to check

        Returns:
            bool: True if path needs migration
        """
        if not path_str:
            return False

        path_format = self.detect_path_format(path_str)

        # Check if path exists as-is
        if Path(path_str).exists():
            return False

        # If it doesn't exist and is from a different format, needs migration
        return path_format in ['windows', 'wsl', 'docker']

    def normalize_path(self, old_path: str) -> str:
        """
        Normalize a path to current machine's configuration.

        Args:
            old_path: Original path from any machine

        Returns:
            str: Normalized path for current machine
        """
        if not old_path:
            return old_path

        # If path already exists and is valid, return as-is
        if Path(old_path).exists():
            return old_path

        # Normalize separators
        normalized = old_path.replace('\\', '/')

        # Extract meaningful path components
        # Pattern 1: Vault paths (notes, PDFs)
        if '/thoth/notes/' in normalized:
            filename = Path(normalized).name
            return str(self.notes_dir / filename)

        if '/thoth/papers/pdfs/' in normalized or '/papers/pdfs/' in normalized:
            filename = Path(normalized).name
            return str(self.pdf_dir / filename)

        # Pattern 2: Data paths (markdown, outputs)
        if '/data/markdown/' in normalized or '\\data\\markdown\\' in old_path:
            filename = Path(normalized).name
            return str(self.markdown_dir / filename)

        if '/data/output/' in normalized or '\\data\\output\\' in old_path:
            # Extract the relative path from data/output/
            match = re.search(r'data/output/(.+)', normalized)
            if match:
                return str(self.data_path / 'data' / 'output' / match.group(1))

        if '/data/notes/' in normalized or '\\data\\notes\\' in old_path:
            filename = Path(normalized).name
            return str(self.data_path / 'data' / 'notes' / filename)

        # Pattern 3: Docker workspace paths
        if '/workspace/' in normalized:
            match = re.search(r'workspace/(.+)', normalized)
            if match:
                return str(self.data_path / match.group(1))

        if '/vault/' in normalized:
            # Extract vault-relative path
            match = re.search(r'vault/(.+)', normalized)
            if match:
                return str(self.vault_path / match.group(1))

        # Pattern 4: Just a filename - guess location based on extension
        filename = Path(normalized).name

        if filename.endswith('.pdf'):
            return str(self.pdf_dir / filename)
        elif filename.endswith('.md'):
            if '_markdown' in filename or '_no_images' in filename:
                return str(self.markdown_dir / filename)
            else:
                return str(self.notes_dir / filename)

        # Fallback: return original
        logger.warning(f'Could not normalize path: {old_path}')
        return old_path

    def migrate_tracker_file(self) -> dict[str, Any]:
        """
        Migrate processed_pdfs.json to current machine paths.

        Returns:
            dict: Migration statistics
        """
        tracker_file = self.data_path / 'data' / 'output' / 'processed_pdfs.json'

        if not tracker_file.exists():
            logger.info('No tracker file found, skipping migration')
            return {'migrated': False, 'reason': 'file_not_found'}

        try:
            # Load tracker
            with open(tracker_file) as f:
                data = json.load(f)

            stats = {
                'migrated': False,
                'total_entries': len(data),
                'paths_updated': 0,
                'paths_unchanged': 0,
            }

            # Check if any paths need migration
            needs_update = False
            for pdf_path in data.keys():
                if self.needs_migration(pdf_path):
                    needs_update = True
                    break

            if not needs_update:
                logger.info('Tracker file paths already normalized for this machine')
                stats['paths_unchanged'] = len(data)
                return stats

            # Create backup
            backup_file = tracker_file.with_suffix('.json.backup')
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Migrate paths
            new_data = {}
            for old_pdf_path, entry in data.items():
                # Normalize the PDF path (key)
                new_pdf_path = self.normalize_path(old_pdf_path)

                # Normalize paths in entry
                new_entry = entry.copy()
                if 'note_path' in new_entry:
                    new_entry['note_path'] = self.normalize_path(new_entry['note_path'])
                if 'new_pdf_path' in new_entry:
                    new_entry['new_pdf_path'] = self.normalize_path(
                        new_entry['new_pdf_path']
                    )
                if 'new_markdown_path' in new_entry:
                    new_entry['new_markdown_path'] = self.normalize_path(
                        new_entry['new_markdown_path']
                    )

                new_data[new_pdf_path] = new_entry

                if new_pdf_path != old_pdf_path:
                    stats['paths_updated'] += 1
                else:
                    stats['paths_unchanged'] += 1

            # Save migrated tracker
            with open(tracker_file, 'w') as f:
                json.dump(new_data, f, indent=2)

            stats['migrated'] = True
            logger.info(
                f'Migrated tracker file: {stats["paths_updated"]} paths updated, '
                f'{stats["paths_unchanged"]} unchanged'
            )

            return stats

        except Exception as e:
            logger.error(f'Error migrating tracker file: {e}')
            return {'migrated': False, 'error': str(e)}

    def migrate_citation_graph(self) -> dict[str, Any]:
        """
        Migrate citations.graphml to current machine paths.

        Note: The citation graph stores paths as filenames only (not full paths),
        so migration is minimal - mainly just validation.

        Returns:
            dict: Migration statistics
        """
        graph_file = self.data_path / 'data' / 'graph' / 'citations.graphml'

        if not graph_file.exists():
            logger.info('No citation graph found, skipping migration')
            return {'migrated': False, 'reason': 'file_not_found'}

        try:
            # Load graph
            with open(graph_file) as f:
                data = json.load(f)

            stats = {
                'migrated': False,
                'total_nodes': len(data.get('nodes', [])),
                'paths_updated': 0,
            }

            # Check if any nodes need path updates
            needs_update = False
            for node in data.get('nodes', []):
                # Check if paths are full paths (need normalization)
                if 'pdf_path' in node and node['pdf_path']:  # noqa: RUF019
                    if '/' in node['pdf_path'] or '\\' in node['pdf_path']:
                        needs_update = True
                        break

            if not needs_update:
                logger.info('Citation graph paths already normalized')
                return stats

            # Create backup
            backup_file = graph_file.with_suffix('.graphml.backup')
            with open(backup_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Normalize paths in nodes
            for node in data.get('nodes', []):
                # Graph stores paths as filenames only, so just extract filename
                if 'pdf_path' in node and node['pdf_path']:  # noqa: RUF019
                    if '/' in node['pdf_path'] or '\\' in node['pdf_path']:
                        node['pdf_path'] = Path(node['pdf_path']).name
                        stats['paths_updated'] += 1

                if 'markdown_path' in node and node['markdown_path']:  # noqa: RUF019
                    if '/' in node['markdown_path'] or '\\' in node['markdown_path']:
                        node['markdown_path'] = Path(node['markdown_path']).name
                        stats['paths_updated'] += 1

                if 'obsidian_path' in node and node['obsidian_path']:  # noqa: RUF019
                    if '/' in node['obsidian_path'] or '\\' in node['obsidian_path']:
                        node['obsidian_path'] = Path(node['obsidian_path']).name
                        stats['paths_updated'] += 1

            # Save migrated graph
            with open(graph_file, 'w') as f:
                json.dump(data, f, indent=2)

            stats['migrated'] = True
            logger.info(
                f'Migrated citation graph: {stats["paths_updated"]} paths normalized'
            )

            return stats

        except Exception as e:
            logger.error(f'Error migrating citation graph: {e}')
            return {'migrated': False, 'error': str(e)}

    def migrate_all(self) -> dict[str, Any]:
        """
        Migrate all data files to current machine paths.

        This is called automatically on app startup.

        Returns:
            dict: Combined migration statistics
        """
        logger.info('Starting automatic path migration for current machine')

        results = {
            'tracker': self.migrate_tracker_file(),
            'graph': self.migrate_citation_graph(),
        }

        # Log summary
        total_updated = 0
        if results['tracker'].get('migrated'):
            total_updated += results['tracker'].get('paths_updated', 0)
        if results['graph'].get('migrated'):
            total_updated += results['graph'].get('paths_updated', 0)

        if total_updated > 0:
            logger.info(
                f'Path migration complete: {total_updated} paths normalized '
                f'for current machine'
            )
        else:
            logger.debug('No path migration needed - files already normalized')

        return results
