"""Tests for vault detection functionality.

Tests all vault detection mechanisms:
- OBSIDIAN_VAULT_PATH environment variable
- THOTH_VAULT_PATH legacy support
- Auto-detection by walking up directories
- Known location fallback
- ValueError when vault cannot be detected
- Path resolution and expansion
"""

import os
from pathlib import Path

import pytest

from thoth.config import get_vault_root


class TestVaultDetectionFromEnvironment:
    """Test vault detection from environment variables."""

    def test_obsidian_vault_path_valid(self, tmp_path: Path, monkeypatch):
        """Test OBSIDIAN_VAULT_PATH with valid path."""
        vault = tmp_path / "my_vault"
        vault.mkdir()

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

        result = get_vault_root()
        assert result == vault.resolve()

    def test_obsidian_vault_path_with_tilde(self, tmp_path: Path, monkeypatch):
        """Test OBSIDIAN_VAULT_PATH with ~ expansion."""
        # Create a test directory in home
        home_vault = Path.home() / "test_vault_detection"
        home_vault.mkdir(exist_ok=True)

        try:
            monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "~/test_vault_detection")

            result = get_vault_root()
            assert result == home_vault.resolve()
        finally:
            # Cleanup
            if home_vault.exists():
                home_vault.rmdir()

    def test_obsidian_vault_path_nonexistent(self, monkeypatch, caplog):
        """Test OBSIDIAN_VAULT_PATH with nonexistent path falls through."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/nonexistent/vault")
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)

        # Should fall through to other methods and eventually raise
        with pytest.raises(ValueError, match="Could not detect vault"):
            get_vault_root()

        assert "doesn't exist" in caplog.text

    def test_thoth_vault_path_legacy(self, tmp_path: Path, monkeypatch):
        """Test THOTH_VAULT_PATH legacy support."""
        vault = tmp_path / "legacy_vault"
        vault.mkdir()

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.setenv("THOTH_VAULT_PATH", str(vault))

        result = get_vault_root()
        assert result == vault.resolve()

    def test_thoth_vault_path_nonexistent(self, monkeypatch, caplog):
        """Test THOTH_VAULT_PATH with nonexistent path falls through."""
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.setenv("THOTH_VAULT_PATH", "/nonexistent/legacy")

        with pytest.raises(ValueError, match="Could not detect vault"):
            get_vault_root()

        assert "doesn't exist" in caplog.text

    def test_obsidian_takes_precedence_over_thoth(self, tmp_path: Path, monkeypatch):
        """Test OBSIDIAN_VAULT_PATH takes precedence over THOTH_VAULT_PATH."""
        obsidian_vault = tmp_path / "obsidian"
        thoth_vault = tmp_path / "thoth"
        obsidian_vault.mkdir()
        thoth_vault.mkdir()

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(obsidian_vault))
        monkeypatch.setenv("THOTH_VAULT_PATH", str(thoth_vault))

        result = get_vault_root()
        assert result == obsidian_vault.resolve()


class TestVaultAutoDetection:
    """Test automatic vault detection by walking up directories."""

    def test_auto_detect_in_current_directory(self, tmp_path: Path, monkeypatch):
        """Test auto-detection when _thoth/ is in current directory."""
        vault = tmp_path / "auto_vault"
        vault.mkdir()
        thoth_dir = vault / "_thoth"
        thoth_dir.mkdir()

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(vault)

        result = get_vault_root()
        assert result == vault.resolve()

    def test_auto_detect_one_level_up(self, tmp_path: Path, monkeypatch):
        """Test auto-detection by walking up one directory level."""
        vault = tmp_path / "parent_vault"
        vault.mkdir()
        thoth_dir = vault / "_thoth"
        thoth_dir.mkdir()

        subdir = vault / "nested" / "deep"
        subdir.mkdir(parents=True)

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(subdir)

        result = get_vault_root()
        assert result == vault.resolve()

    def test_auto_detect_multiple_levels_up(self, tmp_path: Path, monkeypatch):
        """Test auto-detection by walking up multiple directory levels."""
        vault = tmp_path / "deep_vault"
        vault.mkdir()
        thoth_dir = vault / "_thoth"
        thoth_dir.mkdir()

        deep_dir = vault / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(deep_dir)

        result = get_vault_root()
        assert result == vault.resolve()

    def test_auto_detect_stops_at_max_depth(self, tmp_path: Path, monkeypatch):
        """Test auto-detection stops after checking 5 parent levels."""
        # Create vault 7 levels up (beyond the limit)
        vault = tmp_path / "far_vault"
        vault.mkdir()
        thoth_dir = vault / "_thoth"
        thoth_dir.mkdir()

        # Create directory 7 levels deep
        deep_dir = vault / "1" / "2" / "3" / "4" / "5" / "6" / "7"
        deep_dir.mkdir(parents=True)

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(deep_dir)

        # Should not find vault due to depth limit
        with pytest.raises(ValueError, match="Could not detect vault"):
            get_vault_root()

    def test_auto_detect_stops_at_filesystem_root(self, tmp_path: Path, monkeypatch):
        """Test auto-detection stops at filesystem root."""
        # Start from a directory with no _thoth anywhere above
        test_dir = tmp_path / "no_vault"
        test_dir.mkdir()

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(test_dir)

        # Should not find vault and eventually raise
        with pytest.raises(ValueError, match="Could not detect vault"):
            get_vault_root()


class TestKnownLocationFallback:
    """Test fallback to known location ~/Documents/thoth."""

    def test_known_location_exists(self, monkeypatch, tmp_path: Path):
        """Test fallback to known location when it exists."""
        # Create known location
        known_vault = Path.home() / "Documents" / "thoth"
        known_vault.mkdir(parents=True, exist_ok=True)
        thoth_dir = known_vault / "_thoth"
        thoth_dir.mkdir(exist_ok=True)

        try:
            monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
            monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
            monkeypatch.chdir(tmp_path)  # Change to dir without _thoth

            result = get_vault_root()
            assert result == known_vault.resolve()
        finally:
            # Cleanup
            if thoth_dir.exists():
                thoth_dir.rmdir()
            if known_vault.exists():
                known_vault.rmdir()

    def test_known_location_not_exists(self, monkeypatch, tmp_path: Path):
        """Test error when known location doesn't exist."""
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(tmp_path)  # Change to dir without _thoth

        # Ensure known location doesn't exist
        known_vault = Path.home() / "Documents" / "thoth"
        if known_vault.exists():
            pytest.skip("Known vault location exists, can't test failure case")

        with pytest.raises(ValueError, match="Could not detect vault"):
            get_vault_root()


class TestVaultDetectionErrorHandling:
    """Test error handling for vault detection."""

    def test_no_vault_found_error_message(self, monkeypatch, tmp_path: Path):
        """Test error message when no vault can be found."""
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ValueError) as exc_info:
            get_vault_root()

        error_msg = str(exc_info.value)
        assert "Could not detect vault" in error_msg
        assert "OBSIDIAN_VAULT_PATH" in error_msg
        assert "run from within vault directory" in error_msg

    def test_empty_environment_variable(self, monkeypatch):
        """Test empty environment variable is ignored."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)

        with pytest.raises(ValueError, match="Could not detect vault"):
            get_vault_root()


class TestVaultDetectionPathResolution:
    """Test path resolution during vault detection."""

    def test_relative_path_resolution(self, tmp_path: Path, monkeypatch):
        """Test relative path in OBSIDIAN_VAULT_PATH is resolved."""
        vault = tmp_path / "vault"
        vault.mkdir()

        # Set relative path
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "./vault")

        result = get_vault_root()
        assert result.is_absolute()
        assert result == vault.resolve()

    def test_path_with_double_dots(self, tmp_path: Path, monkeypatch):
        """Test path with .. is resolved correctly."""
        vault = tmp_path / "vault"
        vault.mkdir()

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        monkeypatch.chdir(subdir)
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "../vault")

        result = get_vault_root()
        assert result.is_absolute()
        assert result == vault.resolve()

    def test_symlink_resolution(self, tmp_path: Path, monkeypatch):
        """Test symlinks are resolved to real paths."""
        real_vault = tmp_path / "real_vault"
        real_vault.mkdir()

        symlink_vault = tmp_path / "symlink_vault"
        symlink_vault.symlink_to(real_vault)

        try:
            monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(symlink_vault))

            result = get_vault_root()
            # Should resolve to real path
            assert result == real_vault.resolve()
        finally:
            # Cleanup
            if symlink_vault.is_symlink():
                symlink_vault.unlink()


class TestVaultDetectionLogging:
    """Test logging behavior during vault detection."""

    def test_logs_success_from_obsidian_vault_path(self, tmp_path: Path, monkeypatch, caplog):
        """Test success logging when using OBSIDIAN_VAULT_PATH."""
        vault = tmp_path / "vault"
        vault.mkdir()

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

        result = get_vault_root()

        assert "Vault detected from OBSIDIAN_VAULT_PATH" in caplog.text
        assert str(vault.resolve()) in caplog.text

    def test_logs_success_from_thoth_vault_path(self, tmp_path: Path, monkeypatch, caplog):
        """Test success logging when using THOTH_VAULT_PATH."""
        vault = tmp_path / "vault"
        vault.mkdir()

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.setenv("THOTH_VAULT_PATH", str(vault))

        result = get_vault_root()

        assert "Vault detected from THOTH_VAULT_PATH" in caplog.text

    def test_logs_success_from_auto_detect(self, tmp_path: Path, monkeypatch, caplog):
        """Test success logging when auto-detecting vault."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "_thoth").mkdir()

        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)
        monkeypatch.chdir(vault)

        result = get_vault_root()

        assert "Vault auto-detected" in caplog.text

    def test_logs_warning_for_invalid_path(self, monkeypatch, caplog):
        """Test warning logged for invalid environment variable path."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/nonexistent/path")

        with pytest.raises(ValueError):
            get_vault_root()

        assert "OBSIDIAN_VAULT_PATH set" in caplog.text
        assert "doesn't exist" in caplog.text
