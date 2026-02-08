"""Obsidian installation detection and vault discovery.

Detects Obsidian installation across platforms and finds valid Obsidian vaults.
"""

from __future__ import annotations

import platform
import subprocess  # nosec B404  # Required for platform detection
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from loguru import logger


@dataclass
class ObsidianVault:
    """Obsidian vault information."""

    path: Path
    name: str
    has_thoth_workspace: bool
    config_exists: bool


@dataclass
class ObsidianStatus:
    """Obsidian installation status."""

    installed: bool
    version: str | None
    install_path: Path | None
    vaults: list[ObsidianVault]
    platform: str


class ObsidianDetector:
    """Detects Obsidian installation and vaults."""

    # Platform-specific installation paths
    INSTALL_PATHS: ClassVar[dict[str, list]] = {
        'darwin': ['/Applications/Obsidian.app'],  # macOS
        'linux': [
            '/usr/bin/obsidian',
            '/usr/local/bin/obsidian',
            Path.home() / '.local' / 'share' / 'applications' / 'obsidian.desktop',
            '/opt/Obsidian/obsidian',
            '/snap/bin/obsidian',
            '/var/lib/flatpak/exports/bin/md.obsidian.Obsidian',
        ],
        'windows': [
            Path('C:/Program Files/Obsidian/Obsidian.exe'),
            Path('C:/Program Files (x86)/Obsidian/Obsidian.exe'),
            Path.home() / 'AppData' / 'Local' / 'Obsidian' / 'Obsidian.exe',
        ],
    }

    # Download URLs
    DOWNLOAD_URLS: ClassVar[dict[str, str]] = {
        'darwin': 'https://obsidian.md/download',
        'linux': 'https://obsidian.md/download',
        'windows': 'https://obsidian.md/download',
    }

    @staticmethod
    def get_platform() -> str:
        """Get current platform.

        Returns:
            Platform string: 'linux', 'darwin', or 'windows'
        """
        return platform.system().lower()

    @classmethod
    def check_installed(cls) -> tuple[bool, str | None, Path | None]:
        """Check if Obsidian is installed.

        Returns:
            Tuple of (installed, version, install_path)
        """
        platform_name = cls.get_platform()
        paths = cls.INSTALL_PATHS.get(platform_name, [])

        # Check known installation paths
        for path in paths:
            path_obj = Path(path) if isinstance(path, str) else path
            if path_obj.exists():
                logger.info(f'Obsidian found at {path_obj}')
                version = cls._get_version(path_obj)
                return True, version, path_obj

        # Try which/where command
        command = 'where' if platform_name == 'windows' else 'which'
        try:
            result = subprocess.run(
                [command, 'obsidian'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                path_obj = Path(result.stdout.strip().split('\n')[0])
                logger.info(f'Obsidian found via {command}: {path_obj}')
                version = cls._get_version(path_obj)
                return True, version, path_obj

        except Exception as e:
            logger.debug(f'Error running {command}: {e}')

        logger.warning('Obsidian not found')
        return False, None, None

    @staticmethod
    def _get_version(install_path: Path) -> str | None:
        """Try to get Obsidian version.

        Args:
            install_path: Path to Obsidian installation

        Returns:
            Version string or None
        """
        try:
            # Try running with --version flag (may not work on all platforms)
            result = subprocess.run(
                [str(install_path), '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

        except Exception:
            pass

        return None

    @staticmethod
    def is_valid_vault(path: Path) -> bool:
        """Check if a directory is a valid Obsidian vault.

        A valid vault has a .obsidian directory with app.json

        Args:
            path: Directory path to check

        Returns:
            True if valid Obsidian vault
        """
        if not path.is_dir():
            return False

        obsidian_dir = path / '.obsidian'
        if not obsidian_dir.is_dir():
            return False

        # Check for app.json (indicates valid vault)
        app_json = obsidian_dir / 'app.json'
        return app_json.exists()

    @staticmethod
    def search_vaults(
        search_paths: list[Path] | None = None, max_depth: int = 2, timeout: int = 5
    ) -> list[ObsidianVault]:
        """Search for Obsidian vaults using os.walk for better control.

        Args:
            search_paths: Paths to search (uses defaults if None)
            max_depth: Maximum directory depth to search (default: 2)
            timeout: Maximum time in seconds to search (default: 5)

        Returns:
            List of found vaults
        """
        import os
        import time

        start_time = time.time()

        if search_paths is None:
            # Default search paths (limit to likely locations only)
            search_paths = [
                Path.home() / 'Documents',
                Path.home() / 'Obsidian',
                Path.home() / 'obsidian',
            ]

        vaults: list[ObsidianVault] = []
        dirs_checked = 0
        max_dirs = 1000  # Limit total directories checked

        logger.info(
            f'Starting vault search (timeout: {timeout}s, max_depth: {max_depth})'
        )

        for search_path in search_paths:
            if not search_path.exists():
                logger.debug(f'Skipping non-existent path: {search_path}')
                continue

            logger.info(f'Searching in: {search_path}')

            try:
                # Use os.walk for better control over traversal
                for root, dirs, _files in os.walk(search_path):
                    # Check timeout frequently
                    if time.time() - start_time > timeout:
                        logger.warning(
                            f'Vault search timeout after {timeout}s (checked {dirs_checked} dirs)'
                        )
                        return vaults

                    # Limit total directories checked
                    dirs_checked += 1
                    if dirs_checked > max_dirs:
                        logger.warning(f'Reached max directory limit ({max_dirs})')
                        return vaults

                    # Check depth
                    try:
                        depth = len(Path(root).relative_to(search_path).parts)
                    except ValueError:
                        continue

                    # Skip if too deep
                    if depth > max_depth:
                        dirs.clear()  # Don't descend into subdirectories
                        continue

                    # Skip common large directories that won't have vaults
                    dirs[:] = [
                        d
                        for d in dirs
                        if d
                        not in {
                            'node_modules',
                            '.git',
                            '.cache',
                            'venv',
                            'env',
                            '__pycache__',
                            '.venv',
                            'target',
                            'build',
                            'dist',
                            '.npm',
                            '.nvm',
                            'Library',
                            'Applications',
                        }
                    ]

                    # Check if current directory contains .obsidian
                    if '.obsidian' in dirs:
                        vault_path = Path(root)

                        # Validate vault
                        if ObsidianDetector.is_valid_vault(vault_path):
                            # Check for Thoth workspace (new and legacy locations)
                            thoth_dir = vault_path / 'thoth' / '_thoth'
                            legacy_dir = vault_path / '_thoth'
                            has_thoth = (thoth_dir.exists() and thoth_dir.is_dir()) or (
                                legacy_dir.exists() and legacy_dir.is_dir()
                            )

                            # Check for settings.json (new and legacy locations)
                            settings_file = thoth_dir / 'settings.json'
                            legacy_settings = legacy_dir / 'settings.json'
                            config_exists = (
                                settings_file.exists() or legacy_settings.exists()
                            )

                            vault = ObsidianVault(
                                path=vault_path,
                                name=vault_path.name,
                                has_thoth_workspace=has_thoth,
                                config_exists=config_exists,
                            )

                            vaults.append(vault)
                            logger.info(f'Found vault: {vault_path}')

                            # Don't search inside vault directories
                            dirs.clear()

            except (PermissionError, OSError) as e:
                logger.debug(f'Error searching {search_path}: {e}')
                continue

        logger.info(
            f'Search complete: found {len(vaults)} vault(s) after checking {dirs_checked} directories'
        )
        return vaults

    @classmethod
    def get_status(cls, search_paths: list[Path] | None = None) -> ObsidianStatus:
        """Get comprehensive Obsidian status.

        Args:
            search_paths: Paths to search for vaults

        Returns:
            ObsidianStatus object with detection results
        """
        platform_name = cls.get_platform()
        installed, version, install_path = cls.check_installed()

        # Search for vaults
        vaults = cls.search_vaults(search_paths)

        return ObsidianStatus(
            installed=installed,
            version=version,
            install_path=install_path,
            vaults=vaults,
            platform=platform_name,
        )

    @classmethod
    def get_download_url(cls) -> str:
        """Get download URL for current platform.

        Returns:
            Download URL string
        """
        platform_name = cls.get_platform()
        return cls.DOWNLOAD_URLS.get(platform_name, 'https://obsidian.md/download')

    @staticmethod
    def detect_vault_from_env() -> Path | None:
        """Detect vault path from environment variables.

        Checks OBSIDIAN_VAULT_PATH and THOTH_VAULT_PATH

        Returns:
            Vault path if found, None otherwise
        """
        import os

        vault_path = os.getenv('OBSIDIAN_VAULT_PATH') or os.getenv('THOTH_VAULT_PATH')

        if vault_path:
            path_obj = Path(vault_path).expanduser().resolve()
            if ObsidianDetector.is_valid_vault(path_obj):
                return path_obj

        return None
