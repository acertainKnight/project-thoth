"""
Vault-relative path resolution for Obsidian integration.

This module provides utilities for resolving paths relative to the Obsidian vault root,
ensuring consistent path handling across different environments (local development, Docker).
"""

import os
from pathlib import Path
from typing import Optional

from loguru import logger


class VaultPathResolver:
    """Resolves all paths relative to Obsidian vault root.

    The vault structure is:
    - vault_root/           (Obsidian vault directory)
      - .obsidian/          (Obsidian config)
      - .thoth/             (Thoth workspace)
        - settings.json     (Thoth settings with relative paths)
        - data/             (Thoth data directory)
          - pdfs/           (PDF storage)
          - notes/          (Generated notes)
          - knowledge/      (Knowledge base)
        - logs/             (Log files)

    All paths in settings.json are relative to vault_root, e.g.:
    - ".thoth/data/pdfs" → vault_root/.thoth/data/pdfs
    - ".thoth/data/notes" → vault_root/.thoth/data/notes
    """

    def __init__(self, vault_path: str | Path):
        """
        Initialize the vault path resolver.

        Args:
            vault_path: Absolute path to Obsidian vault root

        Raises:
            ValueError: If vault path doesn't exist or is invalid
        """
        self.vault_root = Path(vault_path).expanduser().resolve()
        self._validate_vault()
        logger.debug(f"Initialized VaultPathResolver with vault root: {self.vault_root}")

    def _validate_vault(self) -> None:
        """Ensure vault has required structure.

        Checks:
        1. Vault root exists
        2. .obsidian directory exists (identifies this as an Obsidian vault)
        3. .thoth directory exists or can be created

        Raises:
            ValueError: If validation fails
        """
        if not self.vault_root.exists():
            raise ValueError(f"Vault path does not exist: {self.vault_root}")

        if not self.vault_root.is_dir():
            raise ValueError(f"Vault path is not a directory: {self.vault_root}")

        # Check for .obsidian directory to confirm this is an Obsidian vault
        obsidian_dir = self.vault_root / '.obsidian'
        if not obsidian_dir.exists():
            logger.warning(
                f".obsidian directory not found at {obsidian_dir}. "
                "This may not be a valid Obsidian vault."
            )

        # Ensure .thoth directory exists
        thoth_dir = self.vault_root / '.thoth'
        if not thoth_dir.exists():
            logger.info(f"Creating .thoth directory at {thoth_dir}")
            thoth_dir.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative_path: str | Path) -> Path:
        """Convert vault-relative path to absolute path.

        Args:
            relative_path: Path relative to vault root (e.g., ".thoth/data/pdfs")

        Returns:
            Absolute resolved path

        Examples:
            >>> resolver = VaultPathResolver("/home/user/Documents/MyVault")
            >>> resolver.resolve(".thoth/data/pdfs")
            Path("/home/user/Documents/MyVault/.thoth/data/pdfs")
            >>> resolver.resolve(".thoth/settings.json")
            Path("/home/user/Documents/MyVault/.thoth/settings.json")
        """
        if not relative_path:
            return self.vault_root

        path = Path(relative_path)

        # If already absolute, just return it resolved
        if path.is_absolute():
            return path.resolve()

        # Resolve relative to vault root
        absolute = (self.vault_root / path).resolve()

        logger.debug(f"Resolved '{relative_path}' → '{absolute}'")
        return absolute

    def make_relative(self, absolute_path: str | Path) -> str:
        """Convert absolute path to vault-relative.

        Args:
            absolute_path: Absolute path to convert

        Returns:
            Path relative to vault root (as string with forward slashes)

        Raises:
            ValueError: If path is not within vault root

        Examples:
            >>> resolver = VaultPathResolver("/home/user/Documents/MyVault")
            >>> resolver.make_relative("/home/user/Documents/MyVault/.thoth/data/pdfs")
            ".thoth/data/pdfs"
        """
        path = Path(absolute_path).resolve()

        # Ensure path is within vault
        try:
            relative = path.relative_to(self.vault_root)
            # Use forward slashes for consistency across platforms
            relative_str = str(relative).replace('\\', '/')
            logger.debug(f"Made relative '{absolute_path}' → '{relative_str}'")
            return relative_str
        except ValueError:
            raise ValueError(
                f"Path '{absolute_path}' is not within vault root '{self.vault_root}'"
            )

    def ensure_directory(self, relative_path: str | Path) -> Path:
        """Ensure a directory exists at the given relative path.

        Args:
            relative_path: Path relative to vault root

        Returns:
            Absolute path to the directory
        """
        absolute = self.resolve(relative_path)
        absolute.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {absolute}")
        return absolute

    @property
    def thoth_workspace(self) -> Path:
        """Get the .thoth workspace directory."""
        return self.vault_root / '.thoth'

    @property
    def settings_file(self) -> Path:
        """Get the settings.json file path."""
        return self.thoth_workspace / 'settings.json'

    def is_vault_relative(self, path: str | Path) -> bool:
        """Check if a path is relative to the vault root.

        Args:
            path: Path to check

        Returns:
            True if path is within vault root, False otherwise
        """
        try:
            path_resolved = Path(path).resolve()
            path_resolved.relative_to(self.vault_root)
            return True
        except (ValueError, OSError):
            return False


def detect_vault_path() -> Optional[Path]:
    """Auto-detect Obsidian vault path from environment or current directory.

    Detection priority:
    1. OBSIDIAN_VAULT_PATH environment variable
    2. THOTH_VAULT_PATH environment variable
    3. Current working directory (if it contains .obsidian)
    4. Parent directories (walk up to 5 levels)

    Returns:
        Path to vault root if detected, None otherwise
    """
    # 1. Check OBSIDIAN_VAULT_PATH
    vault_path = os.getenv('OBSIDIAN_VAULT_PATH')
    if vault_path:
        path = Path(vault_path).expanduser().resolve()
        if path.exists() and (path / '.obsidian').exists():
            logger.info(f"Vault detected from OBSIDIAN_VAULT_PATH: {path}")
            return path
        else:
            logger.warning(
                f"OBSIDIAN_VAULT_PATH set to '{vault_path}' but not a valid vault"
            )

    # 2. Check THOTH_VAULT_PATH (alternative name)
    vault_path = os.getenv('THOTH_VAULT_PATH')
    if vault_path:
        path = Path(vault_path).expanduser().resolve()
        if path.exists() and (path / '.obsidian').exists():
            logger.info(f"Vault detected from THOTH_VAULT_PATH: {path}")
            return path
        else:
            logger.warning(
                f"THOTH_VAULT_PATH set to '{vault_path}' but not a valid vault"
            )

    # 3. Check current directory and parents
    current = Path.cwd()
    for _ in range(6):  # Check up to 5 parent levels
        obsidian_dir = current / '.obsidian'
        if obsidian_dir.exists() and obsidian_dir.is_dir():
            logger.info(f"Vault auto-detected at: {current}")
            return current

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    logger.debug("No vault path detected")
    return None


def create_vault_resolver(vault_path: Optional[str | Path] = None) -> VaultPathResolver:
    """Create a VaultPathResolver with auto-detection if path not provided.

    Args:
        vault_path: Optional explicit vault path. If None, will auto-detect.

    Returns:
        Configured VaultPathResolver instance

    Raises:
        ValueError: If vault path cannot be determined or is invalid
    """
    if vault_path:
        return VaultPathResolver(vault_path)

    detected_path = detect_vault_path()
    if detected_path:
        return VaultPathResolver(detected_path)

    raise ValueError(
        "Could not detect Obsidian vault path. Please set OBSIDIAN_VAULT_PATH "
        "environment variable or run from within an Obsidian vault directory."
    )
