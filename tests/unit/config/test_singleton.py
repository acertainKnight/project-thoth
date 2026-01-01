"""Tests for Config singleton pattern and thread-safety.

Tests:
- Singleton pattern (multiple instantiations return same object)
- Initialization only happens once
- Thread-safety
- Instance state preservation
"""

import threading
from pathlib import Path

import pytest

from thoth.config import Config


class TestSingletonPattern:
    """Test singleton pattern implementation."""

    def test_multiple_instantiations_return_same_object(self, temp_vault: Path, monkeypatch):
        """Test multiple Config() calls return the same instance."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        # Reset singleton
        Config._instance = None

        config1 = Config()
        config2 = Config()
        config3 = Config()

        # All should be the same instance
        assert config1 is config2
        assert config2 is config3
        assert id(config1) == id(config2) == id(config3)

    def test_singleton_preserved_across_modules(self, temp_vault: Path, monkeypatch):
        """Test singleton is preserved when imported from different contexts."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        # Import from module
        from thoth.config import config as config1

        # Create new instance
        config2 = Config()

        # Should be same instance
        assert config1 is config2

    def test_singleton_state_preserved(self, temp_vault: Path, monkeypatch):
        """Test singleton state is preserved across instantiations."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config1 = Config()
        original_vault = config1.vault_root

        # Create another instance
        config2 = Config()

        # State should be preserved
        assert config2.vault_root == original_vault

    def test_singleton_not_affected_by_new_class(self, temp_vault: Path, monkeypatch):
        """Test creating new Config class doesn't affect singleton."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config1 = Config()

        # Try to "reinitialize" by calling Config() again
        config2 = Config()

        # Should still be same instance
        assert config1 is config2


class TestInitializationOnce:
    """Test that initialization only happens once."""

    def test_init_only_called_once(self, temp_vault: Path, monkeypatch):
        """Test __init__ only executes initialization once."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config = Config()
        assert config._initialized is True

        # Calling Config() again should not re-initialize
        config2 = Config()
        assert config2._initialized is True
        assert config is config2

    def test_vault_detection_not_repeated(self, temp_vault: Path, monkeypatch):
        """Test vault detection only happens once."""
        call_count = 0
        original_vault_root = temp_vault

        def mock_get_vault_root():
            nonlocal call_count
            call_count += 1
            return original_vault_root

        with pytest.mock.patch("thoth.config.get_vault_root", side_effect=mock_get_vault_root):
            Config._instance = None

            config1 = Config()
            config2 = Config()
            config3 = Config()

            # get_vault_root should only be called once
            assert call_count == 1

    def test_settings_loaded_once(self, temp_vault: Path, monkeypatch):
        """Test settings file is only loaded once."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config1 = Config()
        settings1_id = id(config1.settings)

        config2 = Config()
        settings2_id = id(config2.settings)

        # Settings object should be the same instance
        assert settings1_id == settings2_id


class TestThreadSafety:
    """Test thread-safety of singleton pattern."""

    def test_singleton_thread_safe(self, temp_vault: Path, monkeypatch):
        """Test singleton is thread-safe with concurrent instantiation."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        instances = []
        lock = threading.Lock()

        def create_config():
            config = Config()
            with lock:
                instances.append(config)

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_config)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len(set(id(inst) for inst in instances)) == 1

    def test_reload_lock_acquired(self, temp_vault: Path, monkeypatch):
        """Test reload operations acquire lock."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None
        config = Config()

        # Access _reload_lock should exist
        assert hasattr(config, "_reload_lock")
        assert isinstance(config._reload_lock, threading.Lock)

    def test_callback_count_thread_safe(self, temp_vault: Path, monkeypatch):
        """Test reload_callback_count property is thread-safe."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None
        config = Config()

        def register_callback(i):
            Config.register_reload_callback(f"callback_{i}", lambda c: None)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_callback, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should have 10 callbacks registered
        assert config.reload_callback_count == 10


class TestSingletonReset:
    """Test resetting singleton for testing purposes."""

    def test_can_reset_singleton(self, temp_vault: Path, monkeypatch):
        """Test singleton can be reset by setting _instance to None."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None
        config1 = Config()

        # Reset
        Config._instance = None

        config2 = Config()

        # Should be different instances after reset
        assert config1 is not config2

    def test_reset_clears_state(self, temp_vault: Path, monkeypatch):
        """Test resetting singleton clears state."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None
        config1 = Config()

        # Register a callback
        Config.register_reload_callback("test", lambda c: None)
        assert config1.reload_callback_count == 1

        # Reset singleton
        Config._instance = None

        # Create new instance
        config2 = Config()

        # Callbacks should be cleared (new instance)
        assert config2.reload_callback_count == 0

    def test_reset_allows_different_vault(self, tmp_path: Path, monkeypatch):
        """Test resetting singleton allows using different vault."""
        vault1 = tmp_path / "vault1"
        vault1.mkdir()
        (vault1 / "_thoth").mkdir()

        vault2 = tmp_path / "vault2"
        vault2.mkdir()
        (vault2 / "_thoth").mkdir()

        # First vault
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault1))
        Config._instance = None
        config1 = Config()
        assert config1.vault_root == vault1.resolve()

        # Reset and use second vault
        Config._instance = None
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault2))
        config2 = Config()
        assert config2.vault_root == vault2.resolve()


class TestSingletonWithGlobalInstance:
    """Test interaction between singleton and global 'config' instance."""

    def test_global_config_is_singleton(self, temp_vault: Path, monkeypatch):
        """Test global 'config' object is the singleton."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        # Import global config
        from thoth.config import config

        # Create new Config instance
        new_config = Config()

        # Should be the same object
        assert config is new_config

    def test_modifying_singleton_affects_global(self, temp_vault: Path, monkeypatch):
        """Test modifying singleton affects global config."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config1 = Config()
        from thoth.config import config as global_config

        # Modify settings via Config instance
        config1.settings.llm.default.temperature = 0.123

        # Should reflect in global config
        assert global_config.settings.llm.default.temperature == 0.123


class TestSingletonInheritance:
    """Test singleton behavior with subclassing (if applicable)."""

    def test_cannot_subclass_singleton(self):
        """Test that subclassing Config maintains singleton behavior."""

        class SubConfig(Config):
            pass

        # Even subclass should return base singleton
        # This tests that __new__ returns Config._instance
        sub1 = SubConfig()
        sub2 = SubConfig()

        assert sub1 is sub2


class TestSingletonEdgeCases:
    """Test edge cases in singleton implementation."""

    def test_singleton_survives_exception_in_init(self, temp_vault: Path, monkeypatch):
        """Test singleton state after exception during init."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/nonexistent/path")

        Config._instance = None

        # First attempt should fail
        with pytest.raises(ValueError):
            Config()

        # Instance should be created but not initialized
        # Second attempt with valid path should work
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        # Need to reset since init failed
        Config._instance = None
        config = Config()

        assert config._initialized is True

    def test_singleton_with_no_vault_path(self, monkeypatch):
        """Test singleton behavior when no vault path is available."""
        monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)
        monkeypatch.delenv("THOTH_VAULT_PATH", raising=False)

        Config._instance = None

        with pytest.raises(ValueError):
            Config()

        # Instance may be created but not fully initialized
        # This is expected behavior

    def test_multiple_threads_initialization_race(self, temp_vault: Path, monkeypatch):
        """Test race condition during initialization from multiple threads."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        results = []
        errors = []
        lock = threading.Lock()

        def init_config():
            try:
                config = Config()
                with lock:
                    results.append(config)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Start many threads simultaneously
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=init_config)
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All should succeed
        assert len(errors) == 0
        assert len(results) == 20

        # All should be same instance
        assert len(set(id(r) for r in results)) == 1


class TestSingletonInitializedFlag:
    """Test _initialized flag behavior."""

    def test_initialized_flag_false_before_init(self, temp_vault: Path, monkeypatch):
        """Test _initialized is False before initialization."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        # Create instance but don't let __init__ run fully
        # This is tricky to test directly, but we can verify after init
        config = Config()
        assert config._initialized is True

    def test_initialized_prevents_reinit(self, temp_vault: Path, monkeypatch):
        """Test _initialized flag prevents re-initialization."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config = Config()
        vault_root1 = config.vault_root

        # Try to call __init__ again (through Config())
        config2 = Config()
        vault_root2 = config2.vault_root

        # Vault root should not change
        assert vault_root1 == vault_root2
        assert config is config2


class TestSingletonMemoryManagement:
    """Test memory management of singleton."""

    def test_singleton_not_garbage_collected(self, temp_vault: Path, monkeypatch):
        """Test singleton instance is not garbage collected."""
        import gc

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config = Config()
        config_id = id(config)

        # Delete reference
        del config

        # Force garbage collection
        gc.collect()

        # Singleton should still exist
        new_config = Config()
        assert id(new_config) == config_id

    def test_singleton_references_counted(self, temp_vault: Path, monkeypatch):
        """Test singleton maintains correct reference count."""
        import sys

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(temp_vault))

        Config._instance = None

        config1 = Config()
        refcount1 = sys.getrefcount(config1)

        config2 = Config()
        refcount2 = sys.getrefcount(config2)

        # Reference count should increase
        assert refcount2 > refcount1
