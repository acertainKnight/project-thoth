"""
Tests for the LLM Processor module.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from thoth.core.llm_processor import LLMError, LLMProcessor, OpenRouterClient


class TestOpenRouterClient:
    """Tests for the OpenRouterClient class."""

    @pytest.fixture
    def client(self):
        """Create an OpenRouterClient instance for testing."""
        return OpenRouterClient("test_api_key")

    @pytest.fixture
    def lite_client(self):
        """Create an OpenRouterClient instance with lite mode for testing."""
        return OpenRouterClient("test_api_key", lite_mode=True)

    def test_init(self, client):
        """Test initialization of OpenRouterClient."""
        assert client.api_key == "test_api_key"
        assert client.base_url == "https://openrouter.ai/api/v1"
        assert "Authorization" in client.headers
        assert "Content-Type" in client.headers
        assert "HTTP-Referer" in client.headers
        assert "OpenRouter-Lite" not in client.headers

    def test_init_lite_mode(self, lite_client):
        """Test initialization of OpenRouterClient with lite mode."""
        assert lite_client.api_key == "test_api_key"
        assert "OpenRouter-Lite" in lite_client.headers
        assert lite_client.headers["OpenRouter-Lite"] == "true"

    @patch("thoth.core.llm_processor.requests.post")
    def test_call_api_success(self, mock_post, client):
        """Test successful API call."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_post.return_value = mock_response

        # Call the API
        messages = [{"role": "user", "content": "Test message"}]
        response = client.call_api(messages)

        # Check the response
        assert response == mock_response.json.return_value
        mock_post.assert_called_once()

    @patch("thoth.core.llm_processor.requests.post")
    def test_call_api_with_json_format(self, mock_post, client):
        """Test API call with JSON response format."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}]
        }
        mock_post.return_value = mock_response

        # Call the API with response_format
        messages = [{"role": "user", "content": "Test message"}]
        response = client.call_api(
            messages=messages, response_format={"type": "json_object"}
        )

        # Check the response
        assert response == mock_response.json.return_value
        # Verify response_format was included in the request
        called_args = mock_post.call_args[1]["json"]
        assert "response_format" in called_args
        assert called_args["response_format"] == {"type": "json_object"}

    @patch("thoth.core.llm_processor.requests.post")
    def test_call_api_with_tools(self, mock_post, client):
        """Test API call with tools."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "test_function",
                                    "arguments": '{"arg1": "value1"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Define a test tool
        test_tool = {
            "type": "function",
            "function": {
                "name": "test_function",
                "description": "A test function",
                "parameters": {
                    "type": "object",
                    "properties": {"arg1": {"type": "string"}},
                },
            },
        }

        # Call the API with tools
        messages = [{"role": "user", "content": "Test message"}]
        response = client.call_api(
            messages=messages, tools=[test_tool], tool_choice="auto"
        )

        # Check the response
        assert response == mock_response.json.return_value
        # Verify tools were included in the request
        called_args = mock_post.call_args[1]["json"]
        assert "tools" in called_args
        assert called_args["tools"] == [test_tool]
        assert called_args["tool_choice"] == "auto"

    @patch("thoth.core.llm_processor.requests.post")
    def test_call_api_streaming(self, mock_post, client):
        """Test API call with streaming."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call the API with streaming
        messages = [{"role": "user", "content": "Test message"}]
        response = client.call_api(messages=messages, stream=True)

        # Check the response is the raw response object
        assert response == mock_response
        # Verify stream was included in the request
        called_args = mock_post.call_args[1]["json"]
        assert "stream" in called_args
        assert called_args["stream"] is True

    @patch("thoth.core.llm_processor.requests.post")
    def test_call_api_error(self, mock_post, client):
        """Test API call with error response."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        # Call the API and check for exception
        messages = [{"role": "user", "content": "Test message"}]
        with pytest.raises(LLMError):
            client.call_api(messages)

    @patch("thoth.core.llm_processor.requests.get")
    def test_get_generation_stats(self, mock_get, client):
        """Test getting generation stats."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "id": "gen-123",
                "model": "test-model",
                "tokens_prompt": 10,
                "tokens_completion": 20,
                "total_cost": 0.001,
            }
        }
        mock_get.return_value = mock_response

        # Get generation stats
        stats = client.get_generation_stats("gen-123")

        # Check the response
        assert stats == mock_response.json.return_value
        mock_get.assert_called_once_with(
            "https://openrouter.ai/api/v1/generation?id=gen-123",
            headers=client.headers,
            timeout=30,
        )

    @patch("thoth.core.llm_processor.requests.post")
    def test_analyze_content(self, mock_post, client):
        """Test analyzing content."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "gen-123",
            "choices": [
                {
                    "message": {
                        "content": """
Summary: This is a test summary.

Key points:
- Point 1
- Point 2
- Point 3

Limitations:
- Limitation 1

Research question: What is the test question?
"""
                    }
                }
            ],
        }
        mock_post.return_value = mock_response

        # Analyze content
        result = client.analyze_content("Test content")

        # Check the result
        assert "summary" in result
        assert "key_points" in result
        assert "limitations" in result
        assert "research_question" in result
        assert result["summary"] == "This is a test summary."
        assert len(result["key_points"]) == 3
        assert len(result["limitations"]) == 1
        assert result["research_question"] == "What is the test question?"

    @patch("thoth.core.llm_processor.requests.post")
    def test_analyze_content_with_json_format(self, mock_post, client):
        """Test analyzing content with JSON format."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "gen-123",
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"summary": "JSON summary", '
                            '"key_points": ["Point 1", "Point 2"], '
                            '"limitations": ["Limitation 1"], '
                            '"research_question": "JSON question"}'
                        )
                    }
                }
            ],
        }
        mock_post.return_value = mock_response

        # Analyze content with JSON format
        result = client.analyze_content("Test content", use_json_format=True)

        # Check the result
        assert "summary" in result
        assert "key_points" in result
        assert "limitations" in result
        assert "research_question" in result
        assert result["summary"] == "JSON summary"
        assert len(result["key_points"]) == 2
        assert len(result["limitations"]) == 1
        assert result["research_question"] == "JSON question"

        # Verify response_format was included in the request
        called_args = mock_post.call_args[1]["json"]
        assert "response_format" in called_args
        assert called_args["response_format"] == {"type": "json_object"}

    @patch("thoth.core.llm_processor.requests.post")
    def test_analyze_content_json_response(self, mock_post, client):
        """Test analyzing content with JSON response."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": """
Here's the analysis:

```json
{
  "summary": "This is a JSON summary.",
  "key_points": ["JSON Point 1", "JSON Point 2"],
  "limitations": ["JSON Limitation"],
  "research_question": "JSON question?"
}
```
"""
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Analyze content
        result = client.analyze_content("Test content")

        # Check the result
        assert "summary" in result
        assert "key_points" in result
        assert "limitations" in result
        assert "research_question" in result
        assert result["summary"] == "This is a JSON summary."
        assert len(result["key_points"]) == 2
        assert len(result["limitations"]) == 1
        assert result["research_question"] == "JSON question?"

    @patch("thoth.core.llm_processor.requests.post")
    def test_extract_citations(self, mock_post, client):
        """Test extracting citations."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": """
[
  {
    "text": "[1] Smith, J. (2022). Test paper. Journal of Tests, 10(1), 1-10.",
    "authors": ["J. Smith"],
    "title": "Test paper",
    "year": 2022,
    "journal": "Journal of Tests",
    "context": "This is the context."
  },
  {
    "text": "[2] Doe, J. (2021). Another paper. Conference on Testing.",
    "authors": ["J. Doe"],
    "title": "Another paper",
    "year": 2021,
    "journal": "Conference on Testing",
    "context": "This is another context."
  }
]
"""
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Mock the _extract_references_section method
        with patch.object(
            client, "_extract_references_section", return_value="Test references"
        ):
            # Extract citations
            result = client.extract_citations("Test content with ## References section")

            # Check the result
            assert len(result) == 2
            assert (
                result[0]["text"]
                == "[1] Smith, J. (2022). Test paper. Journal of Tests, 10(1), 1-10."
            )
            assert result[0]["authors"] == ["J. Smith"]
            assert result[0]["title"] == "Test paper"
            assert result[0]["year"] == 2022
            assert result[0]["journal"] == "Journal of Tests"
            assert result[0]["context"] == "This is the context."

    @patch("thoth.core.llm_processor.requests.post")
    def test_extract_citations_with_json_format(self, mock_post, client):
        """Test extracting citations with JSON format."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"citations": [{'
                            '"text": "[1] Smith, J. (2022). Test paper.", '
                            '"authors": ["J. Smith"], '
                            '"title": "Test paper", '
                            '"year": 2022}]}'
                        )
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Mock the _extract_references_section method
        with patch.object(
            client, "_extract_references_section", return_value="Test references"
        ):
            # Extract citations with JSON format
            result = client.extract_citations("Test content", use_json_format=True)

            # Check the result
            assert len(result) == 1
            assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
            assert result[0]["authors"] == ["J. Smith"]
            assert result[0]["title"] == "Test paper"
            assert result[0]["year"] == 2022

            # Verify response_format was included in the request
            called_args = mock_post.call_args[1]["json"]
            assert "response_format" in called_args
            assert called_args["response_format"] == {"type": "json_object"}

    @patch("thoth.core.llm_processor.requests.post")
    def test_extract_citations_with_tools(self, mock_post, client):
        """Test extracting citations with tool calling."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "extract_citation",
                                    "arguments": (
                                        '{"text": "[1] Smith, J. (2022). Test paper.", '
                                        '"authors": ["J. Smith"], '
                                        '"title": "Test paper", '
                                        '"year": 2022}'
                                    ),
                                },
                            },
                            {
                                "id": "call_456",
                                "type": "function",
                                "function": {
                                    "name": "extract_citation",
                                    "arguments": (
                                        '{"text": "[2] Doe, J. (2021). Another paper.",'
                                        ' "authors": ["J. Doe"], '
                                        '"title": "Another paper", '
                                        '"year": 2021}'
                                    ),
                                },
                            },
                        ],
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Mock the _extract_references_section method
        with patch.object(
            client, "_extract_references_section", return_value="Test references"
        ):
            # Extract citations with tools
            result = client.extract_citations("Test content", use_tools=True)

            # Check the result
            assert len(result) == 2
            assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
            assert result[0]["authors"] == ["J. Smith"]
            assert result[0]["title"] == "Test paper"
            assert result[0]["year"] == 2022
            assert result[1]["text"] == "[2] Doe, J. (2021). Another paper."
            assert result[1]["authors"] == ["J. Doe"]
            assert result[1]["title"] == "Another paper"
            assert result[1]["year"] == 2021

            # Verify tools were included in the request
            called_args = mock_post.call_args[1]["json"]
            assert "tools" in called_args
            assert called_args["tool_choice"] == "auto"

    def test_extract_references_section(self, client):
        """Test extracting references section."""
        # Test with References header
        content = (
            "# Title\n\n## Introduction\n\nText\n\n"
            "## References\n\nRef1\nRef2\n\n## Conclusion"
        )
        result = client._extract_references_section(content)
        assert result == "Ref1\nRef2"

        # Test with Bibliography header
        content = (
            "# Title\n\n## Introduction\n\nText\n\n"
            "## Bibliography\n\nRef1\nRef2\n\n## Conclusion"
        )
        result = client._extract_references_section(content)
        assert result == "Ref1\nRef2"

        # Test with no references section
        content = "# Title\n\n## Introduction\n\nText\n\n## Conclusion"
        result = client._extract_references_section(content)
        assert result is None

    def test_extract_content_from_response(self, client):
        """Test extracting content from different response structures."""
        # Test standard response
        response = {"choices": [{"message": {"content": "Test content"}}]}
        result = client._extract_content_from_response(response)
        assert result == "Test content"

        # Test tool call response
        response = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [{"function": {"arguments": '{"key": "value"}'}}],
                    }
                }
            ]
        }
        result = client._extract_content_from_response(response)
        assert result == '{"key": "value"}'

        # Test unexpected response structure
        response = {"unexpected": "structure"}
        result = client._extract_content_from_response(response)
        assert json.loads(result) == response

    def test_parse_analysis(self, client):
        """Test parsing analysis content."""
        # Test with text format
        content = """
Summary: This is a summary.

Key points:
- Point 1
- Point 2

Limitations:
- Limitation 1

Research question: What is the question?
"""
        result = client._parse_analysis(content)
        assert result["summary"] == "This is a summary."
        assert len(result["key_points"]) == 2
        assert len(result["limitations"]) == 1
        assert result["research_question"] == "What is the question?"

        # Test with JSON format
        content = """
Some text before JSON.

{
  "summary": "JSON summary",
  "key_points": ["JSON point 1", "JSON point 2"],
  "limitations": ["JSON limitation"],
  "research_question": "JSON question?"
}

Some text after JSON.
"""
        result = client._parse_analysis(content)
        assert result["summary"] == "JSON summary"
        assert len(result["key_points"]) == 2
        assert len(result["limitations"]) == 1
        assert result["research_question"] == "JSON question?"

        # Test with direct JSON string
        content = (
            '{"summary": "Direct JSON", '
            '"key_points": ["Point 1"], '
            '"limitations": [], '
            '"research_question": "Question?"}'
        )
        result = client._parse_analysis(content)
        assert result["summary"] == "Direct JSON"
        assert len(result["key_points"]) == 1
        assert len(result["limitations"]) == 0
        assert result["research_question"] == "Question?"

    def test_parse_citations(self, client):
        """Test parsing citations content."""
        # Test with JSON format
        content = """
Some text before JSON.

[
  {
    "text": "[1] Smith, J. (2022). Test paper.",
    "authors": ["J. Smith"],
    "title": "Test paper",
    "year": 2022
  },
  {
    "text": "[2] Doe, J. (2021). Another paper.",
    "authors": ["J. Doe"],
    "title": "Another paper",
    "year": 2021
  }
]

Some text after JSON.
"""
        result = client._parse_citations(content)
        assert len(result) == 2
        assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
        assert result[0]["authors"] == ["J. Smith"]
        assert result[0]["title"] == "Test paper"
        assert result[0]["year"] == 2022

        # Test with direct JSON string
        content = (
            '[{"text": "[1] Smith, J. (2022). Test paper.", '
            '"authors": ["J. Smith"], '
            '"title": "Test paper", '
            '"year": 2022}]'
        )
        result = client._parse_citations(content)
        assert len(result) == 1
        assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
        assert result[0]["authors"] == ["J. Smith"]
        assert result[0]["title"] == "Test paper"
        assert result[0]["year"] == 2022

        # Test with JSON object containing citations array
        content = (
            '{"citations": [{'
            '"text": "[1] Smith, J. (2022). Test paper.", '
            '"authors": ["J. Smith"], '
            '"title": "Test paper", '
            '"year": 2022}]}'
        )
        result = client._parse_citations(content)
        assert len(result) == 1
        assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
        assert result[0]["authors"] == ["J. Smith"]
        assert result[0]["title"] == "Test paper"
        assert result[0]["year"] == 2022

        # Test with text format (fallback)
        content = """
[1] Smith, J. (2022). Test paper.
[2] Doe, J. (2021). Another paper.
"""
        result = client._parse_citations(content)
        assert len(result) == 2
        assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
        assert result[1]["text"] == "[2] Doe, J. (2021). Another paper."


class TestLLMProcessor:
    """Tests for the LLMProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create a LLMProcessor instance for testing."""
        with patch("thoth.core.llm_processor.OpenRouterClient"):
            processor = LLMProcessor("test_api_key")
            yield processor

    @pytest.fixture
    def advanced_processor(self):
        """Create a LLMProcessor instance with advanced options for testing."""
        with patch("thoth.core.llm_processor.OpenRouterClient"):
            processor = LLMProcessor(
                api_key="test_api_key",
                lite_mode=True,
                use_json_format=True,
                use_tools=True,
            )
            yield processor

    def test_init(self, processor):
        """Test initialization of LLMProcessor."""
        assert isinstance(processor, LLMProcessor)
        assert processor.client is not None
        assert processor.use_json_format is False
        assert processor.use_tools is False

    def test_init_advanced(self, advanced_processor):
        """Test initialization of LLMProcessor with advanced options."""
        assert isinstance(advanced_processor, LLMProcessor)
        assert advanced_processor.client is not None
        assert advanced_processor.use_json_format is True
        assert advanced_processor.use_tools is True

    def test_analyze_content(self, processor):
        """Test analyzing content."""
        # Mock the client's analyze_content method
        processor.client.analyze_content.return_value = {
            "summary": "Test summary",
            "key_points": ["Point 1", "Point 2"],
            "limitations": ["Limitation 1"],
            "research_question": "Test question",
        }

        # Analyze content
        result = processor.analyze_content("Test content")

        # Check the result
        assert result["summary"] == "Test summary"
        assert len(result["key_points"]) == 2
        assert len(result["limitations"]) == 1
        assert result["research_question"] == "Test question"
        processor.client.analyze_content.assert_called_once_with(
            content="Test content", use_json_format=False
        )

    def test_analyze_content_advanced(self, advanced_processor):
        """Test analyzing content with advanced options."""
        # Mock the client's analyze_content method
        advanced_processor.client.analyze_content.return_value = {
            "summary": "Test summary",
            "key_points": ["Point 1", "Point 2"],
            "limitations": ["Limitation 1"],
            "research_question": "Test question",
        }

        # Analyze content
        result = advanced_processor.analyze_content("Test content")

        # Check the result
        assert result["summary"] == "Test summary"
        assert len(result["key_points"]) == 2
        assert len(result["limitations"]) == 1
        assert result["research_question"] == "Test question"
        advanced_processor.client.analyze_content.assert_called_once_with(
            content="Test content", use_json_format=True
        )

    def test_extract_citations(self, processor):
        """Test extracting citations."""
        # Mock the client's extract_citations method
        processor.client.extract_citations.return_value = [
            {
                "text": "[1] Smith, J. (2022). Test paper.",
                "authors": ["J. Smith"],
                "title": "Test paper",
                "year": 2022,
                "journal": "Journal of Tests",
                "context": "This is the context.",
            }
        ]

        # Extract citations
        result = processor.extract_citations("Test content")

        # Check the result
        assert len(result) == 1
        assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
        assert result[0]["authors"] == ["J. Smith"]
        assert result[0]["title"] == "Test paper"
        assert result[0]["year"] == 2022
        assert result[0]["journal"] == "Journal of Tests"
        assert result[0]["context"] == "This is the context."
        processor.client.extract_citations.assert_called_once_with(
            content="Test content", use_json_format=False, use_tools=False
        )

    def test_extract_citations_advanced(self, advanced_processor):
        """Test extracting citations with advanced options."""
        # Mock the client's extract_citations method
        advanced_processor.client.extract_citations.return_value = [
            {
                "text": "[1] Smith, J. (2022). Test paper.",
                "authors": ["J. Smith"],
                "title": "Test paper",
                "year": 2022,
                "journal": "Journal of Tests",
                "context": "This is the context.",
            }
        ]

        # Extract citations
        result = advanced_processor.extract_citations("Test content")

        # Check the result
        assert len(result) == 1
        assert result[0]["text"] == "[1] Smith, J. (2022). Test paper."
        assert result[0]["authors"] == ["J. Smith"]
        assert result[0]["title"] == "Test paper"
        assert result[0]["year"] == 2022
        assert result[0]["journal"] == "Journal of Tests"
        assert result[0]["context"] == "This is the context."
        advanced_processor.client.extract_citations.assert_called_once_with(
            content="Test content", use_json_format=True, use_tools=True
        )

    def test_get_generation_stats(self, processor):
        """Test getting generation stats."""
        # Mock the client's get_generation_stats method
        processor.client.get_generation_stats.return_value = {
            "data": {
                "id": "gen-123",
                "model": "test-model",
                "tokens_prompt": 10,
                "tokens_completion": 20,
                "total_cost": 0.001,
            }
        }

        # Get generation stats
        result = processor.get_generation_stats("gen-123")

        # Check the result
        assert result["data"]["id"] == "gen-123"
        assert result["data"]["model"] == "test-model"
        assert result["data"]["tokens_prompt"] == 10
        assert result["data"]["tokens_completion"] == 20
        assert result["data"]["total_cost"] == 0.001
        processor.client.get_generation_stats.assert_called_once_with("gen-123")
