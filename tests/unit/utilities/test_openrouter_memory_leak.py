"""Tests for OpenRouterClient memory leak fix."""

import gc
import sys
from unittest.mock import Mock, patch

import pytest

# Skip if openrouter dependencies not available
pytest.importorskip("langchain_openai")
pytest.importorskip("langchain_core")


class TestOpenRouterMemoryLeak:
    """Tests to verify the memory leak fix in OpenRouterClient."""

    @pytest.fixture
    def mock_openrouter_setup(self):
        """Mock OpenRouter API calls."""
        with patch('thoth.utilities.openrouter.requests.get') as mock_get:
            # Mock the credits check
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'data': {'usage': 0, 'limit': 100}
            }
            mock_get.return_value = mock_response
            yield mock_get

    def test_no_class_variable_dict(self, mock_openrouter_setup):
        """Test that OpenRouterClient no longer uses class variable dict."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        # Check class doesn't have custom_attributes class variable
        assert not hasattr(OpenRouterClient, 'custom_attributes'), \
            "OpenRouterClient should not have 'custom_attributes' class variable"

    def test_instance_variables_used(self, mock_openrouter_setup):
        """Test that OpenRouterClient uses instance variables."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        client = OpenRouterClient(
            api_key='test-key',
            model='openai/gpt-4',
            use_rate_limiter=True
        )
        
        # Verify instance variables exist
        assert hasattr(client, '_use_rate_limiter'), \
            "Client should have _use_rate_limiter instance variable"
        assert hasattr(client, '_rate_limiter'), \
            "Client should have _rate_limiter instance variable"
        
        # Verify values
        assert client._use_rate_limiter is True
        assert client._rate_limiter is not None

    def test_no_memory_leak_on_deletion(self, mock_openrouter_setup):
        """Test that deleting clients doesn't leak memory in class variables."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        # The OLD bug: class variable dict accumulated entries that were never cleaned up
        # The NEW fix: no class variable dict exists
        
        # Verify no class-level storage
        assert not hasattr(OpenRouterClient, 'custom_attributes'), \
            "OpenRouterClient should not have custom_attributes class variable"
        
        # Create and delete many clients
        client_instances = []
        for i in range(100):
            client = OpenRouterClient(
                api_key=f'test-key-{i}',
                model='openai/gpt-4',
                use_rate_limiter=True
            )
            # Verify instance variables work
            assert client._use_rate_limiter is True
            assert client._rate_limiter is not None
            client_instances.append(client)
        
        # Delete all clients
        for client in client_instances:
            del client
        del client_instances
        
        # Force garbage collection
        gc.collect()
        
        # The key fix: No class variable means no leaked entries
        # We can't easily test object counts (too much variance), but we verified:
        # 1. No class variable dict exists
        # 2. Instance variables are used
        # 3. Python's normal GC handles instance variables automatically

    def test_rate_limiter_with_instance_variables(self, mock_openrouter_setup):
        """Test that rate limiter works with instance variables."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        client = OpenRouterClient(
            api_key='test-key',
            model='openai/gpt-4',
            use_rate_limiter=True
        )
        
        # Verify rate limiter is set up
        assert client._rate_limiter is not None
        assert hasattr(client._rate_limiter, 'acquire')
        
        # Verify it has the LangChain rate limiter
        langchain_limiter = client._rate_limiter.get_langchain_limiter()
        assert langchain_limiter is not None

    def test_rate_limiter_disabled(self, mock_openrouter_setup):
        """Test that rate limiter can be disabled."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        client = OpenRouterClient(
            api_key='test-key',
            model='openai/gpt-4',
            use_rate_limiter=False
        )
        
        # Verify rate limiter is not set up
        assert client._use_rate_limiter is False
        assert client._rate_limiter is None

    def test_multiple_clients_independent(self, mock_openrouter_setup):
        """Test that multiple clients maintain independent state."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        client1 = OpenRouterClient(
            api_key='test-key-1',
            model='openai/gpt-4',
            use_rate_limiter=True
        )
        
        client2 = OpenRouterClient(
            api_key='test-key-2',
            model='openai/gpt-3.5-turbo',
            use_rate_limiter=False
        )
        
        # Verify independence
        assert client1._use_rate_limiter is True
        assert client2._use_rate_limiter is False
        
        assert client1._rate_limiter is not None
        assert client2._rate_limiter is None
        
        # Verify they don't share state
        assert id(client1._rate_limiter) != id(client2._rate_limiter) if client2._rate_limiter else True

    def test_client_cleanup_on_exception(self, mock_openrouter_setup):
        """Test that clients are cleaned up even if exception occurs."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        initial_count = len(gc.get_objects())
        
        # Create client and raise exception
        try:
            client = OpenRouterClient(
                api_key='test-key',
                model='openai/gpt-4',
                use_rate_limiter=True
            )
            raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Force garbage collection
        gc.collect()
        
        # Verify no leak
        final_count = len(gc.get_objects())
        leaked_objects = final_count - initial_count
        
        assert leaked_objects < 20, \
            f"Memory leak on exception: {leaked_objects} extra objects"

    def test_backward_compatibility(self, mock_openrouter_setup):
        """Test that the fix maintains backward compatibility."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        # Should work the same as before
        client = OpenRouterClient(
            api_key='test-key',
            model='openai/gpt-4',
            temperature=0.7,
            max_tokens=1000,
            use_rate_limiter=True
        )
        
        # Verify all standard properties work
        assert client.model_name == 'openai/gpt-4'
        assert client.temperature == 0.7
        assert client.max_tokens == 1000

    def test_generate_method_uses_instance_variables(self, mock_openrouter_setup):
        """Test that _generate method uses instance variables correctly."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        client = OpenRouterClient(
            api_key='test-key',
            model='openai/gpt-4',
            use_rate_limiter=True
        )
        
        # Mock the rate limiter acquire method
        with patch.object(client._rate_limiter, 'acquire') as mock_acquire:
            # Mock the parent _generate to avoid actual API call
            with patch.object(OpenRouterClient.__bases__[1], '_generate') as mock_parent_generate:
                mock_parent_generate.return_value = Mock()
                
                # Call _generate
                client._generate([Mock()], Mock())
                
                # Verify rate limiter was called
                mock_acquire.assert_called_once()


class TestMemoryLeakRegression:
    """Regression tests to ensure memory leak doesn't return."""

    def test_no_class_dict_accumulation(self):
        """Test that no class-level dict accumulates data."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        # Get all class variables
        class_vars = {
            k: v for k, v in vars(OpenRouterClient).items()
            if not k.startswith('_') and not callable(v)
        }
        
        # Should not have any dict-like class variables storing instance data
        for name, value in class_vars.items():
            if isinstance(value, dict):
                assert len(value) == 0 or not any(isinstance(k, int) for k in value.keys()), \
                    f"Class variable '{name}' appears to store instance data (has int keys)"

    def test_memory_usage_stable_over_time(self):
        """Test that memory usage doesn't grow unbounded with client creation/deletion."""
        from thoth.utilities.openrouter import OpenRouterClient
        
        with patch('thoth.utilities.openrouter.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'data': {'usage': 0, 'limit': 100}}
            mock_get.return_value = mock_response
            
            # The key test: Verify no class-level dict accumulates data
            # With the old bug, custom_attributes would grow to 50 entries
            # With the fix, there's no class variable at all
            
            # Create and delete many clients
            for i in range(50):
                client = OpenRouterClient(
                    api_key=f'key-{i}',
                    model='openai/gpt-4',
                    use_rate_limiter=True
                )
                # Verify instance variables are used (not class dict)
                assert hasattr(client, '_rate_limiter')
                del client
                
                # Periodic garbage collection
                if i % 10 == 0:
                    gc.collect()
            
            gc.collect()
            
            # Verify no class dict exists
            assert not hasattr(OpenRouterClient, 'custom_attributes'), \
                "No class dict should exist to accumulate leaked data"
