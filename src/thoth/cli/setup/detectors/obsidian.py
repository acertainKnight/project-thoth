"""
Obsidian installation detection and vault discovery.

Detects Obsidian installation across platforms and finds valid Obsidian vaults.
"""

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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
    version: Optional[str]
    install_path: Optional[Path]
    vaults: List[ObsidianVault]
    platform: str


class ObsidianDetector:
    """Detects Obsidian installation and vaults."""

    # Platform-specific installation paths
    INSTALL_PATHS = {
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
    DOWNLOAD_URLS = {
        'darwin': 'https://obsidian.md/download',
        'linux': 'https://obsidian.md/download',
        'windows': 'https://obsidian.md/download',
    }

    @staticmethod
    def get_platform() -> str:
        """
        Get current platform.

        Returns:
            Platform string: 'linux', 'darwin', or 'windows'
        """
        return platform.system().lower()

    @classmethod
    def check_installed(cls) -> tuple[bool, Optional[str], Optional[Path]]:
        """
        Check if Obsidian is installed.

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
    def _get_version(install_path: Path) -> Optional[str]:
        """
        Try to get Obsidian version.

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
        """
        Check if a directory is a valid Obsidian vault.

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
        search_paths: Optional[List[Path]] = None, max_depth: int = 3
    ) -> List[ObsidianVault]:
        """
        Search for Obsidian vaults.

        Args:
            search_paths: Paths to search (uses defaults if None)
            max_depth: Maximum directory depth to search

        Returns:
            List of found vaults
        """
        if search_paths is None:
            # Default search paths
            search_paths = [
                Path.home() / 'Documents',
                Path.home() / 'Obsidian',
                Path.home() / 'obsidian',
                Path.home(),
            ]

        vaults = []

        for search_path in search_paths:
            if not search_path.exists():
                continue

            try:
                # Look for .obsidian directories
                for obsidian_dir in search_path.rglob('.obsidian'):
                    # Check depth
                    depth = len(obsidian_dir.relative_to(search_path).parts)
                    if depth > max_depth:
                        continue

                    vault_path = obsidian_dir.parent

                    # Validate vault
                    if not ObsidianDetector.is_valid_vault(vault_path):
                        continue

                    # Check for Thoth workspace
                    thoth_dir = vault_path / '_thoth'
                    has_thoth = thoth_dir.exists() and thoth_dir.is_dir()

                    # Check for settings.json
                    settings_file = thoth_dir / 'settings.json'
                    config_exists = settings_file.exists()

                    vault = ObsidianVault(
                        path=vault_path,
                        name=vault_path.name,
                        has_thoth_workspace=has_thoth,
                        config_exists=config_exists,
                    )

                    vaults.append(vault)
                    logger.info(f'Found vault: {vault_path}')

            except (PermissionError, OSError) as e:
                logger.debug(f'Error searching {search_path}: {e}')
                continue

        return vaults

    @classmethod
    def get_status(cls, search_paths: Optional[List[Path]] = None) -> ObsidianStatus:
        """
        Get comprehensive Obsidian status.

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
        """
        Get download URL for current platform.

        Returns:
            Download URL string
        """
        platform_name = cls.get_platform()
        return cls.DOWNLOAD_URLS.get(platform_name, 'https://obsidian.md/download')

    @staticmethod
    def detect_vault_from_env() -> Optional[Path]:
        """
        Detect vault path from environment variables.

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
