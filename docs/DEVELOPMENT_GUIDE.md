# Thoth Development Guide

This guide provides comprehensive information for developers who want to contribute to, extend, or customize the Thoth Research Assistant system.

## 🎯 **Quick Development Setup**

### **Prerequisites**
- **Python 3.10+** (3.11 or 3.12 recommended)
- **uv package manager** (latest version)
- **Git** (for version control)
- **Docker** (optional, for containerized development)

### **5-Minute Developer Setup**

```bash
# 1. Clone and enter repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# 2. Install development dependencies
uv sync --dev

# 3. Set up pre-commit hooks
uv run pre-commit install

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Run comprehensive health check
uv run python health_check.py

# 6. Run tests to verify setup
uv run pytest

# 7. Start development API server
uv run python -m thoth api --reload
```

## 🏗️ **Architecture Overview**

### **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Presentation   │    │   Service       │    │   Data          │
│  Layer          │    │   Layer         │    │   Layer         │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • CLI Commands  │    │ • Processing    │    │ • Citation      │
│ • FastAPI       │    │ • Discovery     │    │   Graph         │
│ • Obsidian      │    │ • RAG           │    │ • Vector Store  │
│   Plugin        │    │ • Citation      │    │ • File System  │
│ • Agent Chat    │    │ • Note Gen      │    │ • Config Store  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │    Modern Agent         │
                    │    (LangGraph)          │
                    └─────────────────────────┘
```

### **Core Components**

#### **Service Layer** (`src/thoth/services/`)
- **Service Manager**: Centralized service orchestration
- **Processing Service**: PDF to note conversion pipeline
- **Discovery Service**: Article discovery and scheduling
- **RAG Service**: Vector search and question answering
- **Citation Service**: Citation extraction and graph management
- **Note Service**: Obsidian note generation
- **Tag Service**: Tag consolidation and suggestion

#### **Modern Agent** (`src/thoth/ingestion/agent_v2/`)
- **Core Agent**: LangGraph-based conversational AI
- **Tool Registry**: Modular tool system
- **State Management**: Conversation and session handling
- **Memory System**: Persistent conversation history

#### **Discovery System** (`src/thoth/discovery/`)
- **API Sources**: ArXiv, PubMed integration
- **Web Scrapers**: CSS selector-based scraping
- **Emulator**: Browser automation for complex sites
- **Scheduler**: Automated discovery execution

#### **Analysis Pipeline** (`src/thoth/analyze/`)
- **LLM Processor**: Content analysis and extraction
- **Citation Tracker**: Citation graph management
- **Tag Consolidator**: Tag management and suggestion

## 🛠️ **Development Environment**

### **Environment Setup**

#### **Using UV (Recommended)**
```bash
# Create development environment
uv venv --python 3.11 thoth-dev
source thoth-dev/bin/activate  # Linux/macOS
# thoth-dev\Scripts\activate  # Windows

# Install all dependencies
uv sync --dev

# Install additional development tools
uv add --dev pytest-cov pytest-mock pytest-asyncio
uv add --dev black isort ruff mypy
uv add --dev pre-commit
```

#### **Using Docker**
```bash
# Start development container
docker-compose -f docker-compose.dev.yml up -d

# Access development shell
docker-compose -f docker-compose.dev.yml exec thoth-dev bash

# Run commands in container
docker-compose -f docker-compose.dev.yml exec thoth-dev uv run pytest
```

### **Development Configuration**

Create `.env.dev` for development:
```bash
# Development API keys (use test/development keys)
API_OPENROUTER_KEY="your-dev-key"

# Development models (cost-effective)
LLM_MODEL="openai/gpt-4o-mini"
CITATION_LLM_MODEL="openai/gpt-4o-mini"
RAG_QA_MODEL="openai/gpt-4o-mini"

# Development paths
WORKSPACE_DIR="."
PDF_DIR="dev-data/pdf"
NOTES_DIR="dev-data/notes"

# Debug settings
LOG_LEVEL="DEBUG"
ENDPOINT_HOST="127.0.0.1"
ENDPOINT_PORT="8000"

# Fast processing for development
CITATION_CITATION_BATCH_SIZE="20"
RAG_RETRIEVAL_K="3"
```

### **Development Tools**

#### **Code Quality Tools**
```bash
# Format code
uv run black src/ tests/
uv run isort src/ tests/

# Lint code
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# Run all quality checks
uv run pre-commit run --all-files
```

#### **Testing Tools**
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/thoth --cov-report=html

# Run specific test file
uv run pytest tests/test_services/test_discovery_service.py

# Run tests with debugging
uv run pytest -v -s --pdb

# Run tests in parallel
uv run pytest -n auto
```

#### **Development Server**
```bash
# Start with auto-reload
uv run python -m thoth api --reload --host 127.0.0.1 --port 8000

# Start with debug logging
LOG_LEVEL=DEBUG uv run python -m thoth api --reload

# Start with specific configuration
ENV_FILE=.env.dev uv run python -m thoth api --reload
```

## 🧩 **Extending Thoth**

### **Adding New Agent Tools**

Tools are the primary way to extend agent functionality. Here's how to create a new tool:

#### **1. Create Tool Class**

```python
# src/thoth/ingestion/agent_v2/tools/my_tools.py

from typing import Type, Optional
from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool


class MyToolInput(BaseModel):
    """Input schema for my custom tool."""
    query: str = Field(description="The query to process")
    limit: Optional[int] = Field(default=10, description="Maximum results to return")
    include_metadata: bool = Field(default=True, description="Include metadata in results")


class MyCustomTool(BaseThothTool):
    """
    Custom tool for specific research functionality.

    This tool demonstrates how to create custom functionality
    that can be used by the research agent.
    """

    name: str = "my_custom_tool"
    description: str = "Perform custom research analysis with specific parameters"
    args_schema: Type[BaseModel] = MyToolInput

    def _run(self, query: str, limit: int = 10, include_metadata: bool = True) -> str:
        """Execute the custom tool logic."""
        try:
            # Access service layer through the adapter
            pipeline = self.tool_registry.adapter.pipeline

            # Implement your custom logic here
            results = self._perform_custom_analysis(query, limit, include_metadata)

            # Format results for the agent
            return self._format_results(results)

        except Exception as e:
            return self.handle_error(e)

    def _perform_custom_analysis(self, query: str, limit: int, include_metadata: bool):
        """Implement your custom analysis logic."""
        # Example: Search knowledge base and perform additional processing
        results = []

        # Use existing services
        rag_service = self.tool_registry.adapter.pipeline.services.rag
        search_results = rag_service.search(query, k=limit)

        for result in search_results:
            processed_result = {
                'content': result['content'],
                'score': result['score'],
                'source': result['source']
            }

            if include_metadata:
                processed_result['metadata'] = result.get('metadata', {})

            results.append(processed_result)

        return results

    def _format_results(self, results):
        """Format results for agent consumption."""
        if not results:
            return "No results found for the specified query."

        formatted = f"Found {len(results)} results:\n\n"

        for i, result in enumerate(results, 1):
            formatted += f"{i}. **Score: {result['score']:.3f}**\n"
            formatted += f"   Source: {result['source']}\n"
            formatted += f"   Content: {result['content'][:200]}...\n\n"

        return formatted
```

#### **2. Register Tool**

```python
# src/thoth/ingestion/agent_v2/core/agent.py

def _register_tools(self) -> None:
    """Register all available tools."""
    # ... existing tool registrations ...

    # Register your custom tool
    from thoth.ingestion.agent_v2.tools.my_tools import MyCustomTool
    self.tool_registry.register("my_custom_tool", MyCustomTool)
```

#### **3. Test Tool**

```python
# tests/test_agent_v2/test_tools/test_my_tools.py

import pytest
from unittest.mock import Mock, patch

from thoth.ingestion.agent_v2.tools.my_tools import MyCustomTool


class TestMyCustomTool:
    """Test suite for MyCustomTool."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter for testing."""
        adapter = Mock()
        adapter.pipeline.services.rag.search.return_value = [
            {
                'content': 'Test content',
                'score': 0.95,
                'source': 'test_source.md',
                'metadata': {'title': 'Test Paper'}
            }
        ]
        return adapter

    @pytest.fixture
    def tool(self, mock_adapter):
        """Create tool instance for testing."""
        tool = MyCustomTool()
        tool.tool_registry = Mock()
        tool.tool_registry.adapter = mock_adapter
        return tool

    def test_run_with_valid_input(self, tool):
        """Test tool with valid input parameters."""
        result = tool._run(
            query="test query",
            limit=5,
            include_metadata=True
        )

        assert "Found 1 results" in result
        assert "Score: 0.950" in result
        assert "test_source.md" in result

    def test_run_without_metadata(self, tool):
        """Test tool without metadata."""
        result = tool._run(
            query="test query",
            limit=5,
            include_metadata=False
        )

        assert "Found 1 results" in result
        # Verify metadata is not included in processing

    def test_error_handling(self, tool):
        """Test tool error handling."""
        tool.tool_registry.adapter.pipeline.services.rag.search.side_effect = Exception("Test error")

        result = tool._run(query="test query")

        assert "error" in result.lower()
```

### **Adding New Discovery Sources**

#### **1. Create API Source**

```python
# src/thoth/discovery/custom_api_source.py

from typing import Dict, List, Any
from datetime import datetime

from thoth.discovery.api_sources import BaseAPISource
from thoth.utilities.schemas import ScrapedArticleMetadata


class CustomAPISource(BaseAPISource):
    """
    Custom API source for a specific research database.

    This example shows how to integrate with a custom API
    that provides research paper metadata.
    """

    def search(self, config: Dict[str, Any], max_results: int = 50) -> List[ScrapedArticleMetadata]:
        """
        Search the custom API for articles.

        Args:
            config: API configuration containing search parameters
            max_results: Maximum number of articles to return

        Returns:
            List of article metadata objects
        """
        try:
            # Extract configuration
            api_config = config.get('api_config', {})
            search_terms = api_config.get('search_terms', [])
            api_key = api_config.get('api_key')
            base_url = api_config.get('base_url', 'https://api.example.com')

            # Build search query
            query_params = {
                'q': ' OR '.join(search_terms),
                'max_results': max_results,
                'format': 'json'
            }

            # Make API request
            headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
            response = self._make_request(f"{base_url}/search", params=query_params, headers=headers)

            # Parse response
            articles = []
            for item in response.get('results', []):
                article = self._parse_article_data(item)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            self.logger.error(f"Error searching custom API: {e}")
            return []

    def _parse_article_data(self, item: Dict[str, Any]) -> ScrapedArticleMetadata:
        """Parse article data from API response."""
        try:
            return ScrapedArticleMetadata(
                title=item.get('title', ''),
                authors=item.get('authors', []),
                abstract=item.get('abstract', ''),
                doi=item.get('doi'),
                pdf_url=item.get('pdf_url'),
                journal=item.get('journal'),
                publication_date=item.get('publication_date'),
                source='custom_api',
                scrape_timestamp=datetime.now().isoformat(),
                url=item.get('url'),
                keywords=item.get('keywords', [])
            )
        except Exception as e:
            self.logger.error(f"Error parsing article data: {e}")
            return None

    def _make_request(self, url: str, params: Dict = None, headers: Dict = None):
        """Make HTTP request with error handling and rate limiting."""
        import requests
        import time

        # Implement rate limiting
        time.sleep(self.rate_limit_delay)

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        return response.json()
```

#### **2. Register Source Type**

```python
# src/thoth/discovery/discovery_manager.py

def _get_source_instance(self, source: DiscoverySource):
    """Get appropriate source instance based on type."""
    if source.source_type == 'api':
        if source.api_config and source.api_config.get('source') == 'arxiv':
            return ArxivAPISource()
        elif source.api_config and source.api_config.get('source') == 'pubmed':
            return PubmedAPISource()
        elif source.api_config and source.api_config.get('source') == 'custom':
            from thoth.discovery.custom_api_source import CustomAPISource
            return CustomAPISource()
    # ... handle other source types
```

#### **3. Create Configuration Schema**

```json
{
  "name": "custom_research_db",
  "source_type": "api",
  "description": "Custom research database integration",
  "is_active": true,
  "api_config": {
    "source": "custom",
    "base_url": "https://api.customresearch.com",
    "api_key": "your-api-key",
    "search_terms": ["machine learning", "artificial intelligence"],
    "date_range": {
      "start": "2023-01-01",
      "end": "2024-12-31"
    }
  },
  "schedule_config": {
    "interval_minutes": 720,
    "max_articles_per_run": 25,
    "enabled": true,
    "time_of_day": "06:00",
    "days_of_week": [1, 2, 3, 4, 5]
  },
  "query_filters": ["machine_learning", "ai_research"]
}
```

### **Adding New Services**

#### **1. Create Service Class**

```python
# src/thoth/services/custom_service.py

from typing import Dict, List, Any, Optional
from pathlib import Path

from thoth.services.base import BaseService
from thoth.utilities.config import get_config


class CustomService(BaseService):
    """
    Custom service for specialized functionality.

    This service demonstrates how to add new business logic
    to the Thoth system while following established patterns.
    """

    def __init__(self):
        """Initialize the custom service."""
        super().__init__()
        self.config = get_config()
        self.cache = {}

    def process_custom_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a custom request with business logic.

        Args:
            data: Request data containing parameters

        Returns:
            Dictionary containing processing results
        """
        try:
            # Validate input
            self._validate_input(data)

            # Check cache for existing results
            cache_key = self._generate_cache_key(data)
            if cache_key in self.cache:
                self.logger.info(f"Returning cached result for {cache_key}")
                return self.cache[cache_key]

            # Perform custom processing
            result = self._perform_processing(data)

            # Cache result
            self.cache[cache_key] = result

            return result

        except Exception as e:
            self.logger.error(f"Error in custom processing: {e}")
            raise

    def _validate_input(self, data: Dict[str, Any]) -> None:
        """Validate input data."""
        required_fields = ['type', 'parameters']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

    def _generate_cache_key(self, data: Dict[str, Any]) -> str:
        """Generate cache key from input data."""
        import hashlib
        import json

        # Create stable hash from data
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    def _perform_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual custom processing."""
        processing_type = data['type']
        parameters = data['parameters']

        if processing_type == 'analysis':
            return self._perform_analysis(parameters)
        elif processing_type == 'transformation':
            return self._perform_transformation(parameters)
        else:
            raise ValueError(f"Unknown processing type: {processing_type}")

    def _perform_analysis(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Perform custom analysis."""
        # Implement your analysis logic here
        return {
            'status': 'success',
            'analysis_type': 'custom',
            'results': parameters,  # Placeholder
            'timestamp': self._get_timestamp()
        }

    def _perform_transformation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Perform custom data transformation."""
        # Implement your transformation logic here
        return {
            'status': 'success',
            'transformation_type': 'custom',
            'results': parameters,  # Placeholder
            'timestamp': self._get_timestamp()
        }

    def get_service_stats(self) -> Dict[str, Any]:
        """Get statistics about the service."""
        return {
            'cache_size': len(self.cache),
            'service_name': 'CustomService',
            'version': '1.0.0'
        }
```

#### **2. Register Service**

```python
# src/thoth/services/service_manager.py

@property
def custom(self) -> 'CustomService':
    """Get the custom service instance."""
    if self._custom_service is None:
        from thoth.services.custom_service import CustomService
        self._custom_service = CustomService()
    return self._custom_service

def __init__(self):
    """Initialize the service manager."""
    # ... existing initialization ...
    self._custom_service = None
```

#### **3. Add Service to Pipeline**

```python
# src/thoth/pipeline.py

def custom_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Perform custom processing using the custom service."""
    return self.services.custom.process_custom_request(data)
```

## 🧪 **Testing Guidelines**

### **Test Structure**

```
tests/
├── conftest.py                    # Shared fixtures
├── test_services/                 # Service layer tests
│   ├── test_discovery_service.py
│   ├── test_rag_service.py
│   └── test_custom_service.py
├── test_agent_v2/               # Agent system tests
│   ├── test_core/
│   ├── test_tools/
│   └── test_integration/
├── test_discovery/              # Discovery system tests
├── test_ingestion/              # Processing pipeline tests
├── test_utilities/              # Utility function tests
└── integration/                 # End-to-end tests
```

### **Writing Tests**

#### **Unit Tests**
```python
# tests/test_services/test_custom_service.py

import pytest
from unittest.mock import Mock, patch, MagicMock

from thoth.services.custom_service import CustomService


class TestCustomService:
    """Test suite for CustomService."""

    @pytest.fixture
    def service(self):
        """Create a CustomService instance for testing."""
        return CustomService()

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing."""
        return {
            'type': 'analysis',
            'parameters': {
                'query': 'test query',
                'limit': 10
            }
        }

    def test_process_custom_request_success(self, service, sample_data):
        """Test successful custom request processing."""
        result = service.process_custom_request(sample_data)

        assert result['status'] == 'success'
        assert result['analysis_type'] == 'custom'
        assert 'timestamp' in result

    def test_process_custom_request_missing_field(self, service):
        """Test processing with missing required field."""
        invalid_data = {'type': 'analysis'}  # Missing 'parameters'

        with pytest.raises(ValueError, match="Missing required field: parameters"):
            service.process_custom_request(invalid_data)

    def test_process_custom_request_unknown_type(self, service):
        """Test processing with unknown type."""
        invalid_data = {
            'type': 'unknown_type',
            'parameters': {}
        }

        with pytest.raises(ValueError, match="Unknown processing type"):
            service.process_custom_request(invalid_data)

    def test_caching_behavior(self, service, sample_data):
        """Test that results are properly cached."""
        # First call should perform processing
        result1 = service.process_custom_request(sample_data)

        # Second call should return cached result
        result2 = service.process_custom_request(sample_data)

        assert result1 == result2
        assert len(service.cache) == 1

    @patch('thoth.services.custom_service.get_config')
    def test_initialization_with_config(self, mock_get_config, service):
        """Test service initialization with configuration."""
        mock_config = Mock()
        mock_get_config.return_value = mock_config

        new_service = CustomService()

        assert new_service.config == mock_config
        mock_get_config.assert_called_once()
```

#### **Integration Tests**
```python
# tests/integration/test_custom_workflow.py

import pytest
from pathlib import Path

from thoth.pipeline import ThothPipeline


class TestCustomWorkflow:
    """Integration tests for custom workflows."""

    @pytest.fixture
    def pipeline(self):
        """Create a pipeline instance for testing."""
        return ThothPipeline()

    def test_end_to_end_custom_processing(self, pipeline, tmp_path):
        """Test complete custom processing workflow."""
        # Setup test data
        test_data = {
            'type': 'analysis',
            'parameters': {
                'query': 'machine learning',
                'source': 'test'
            }
        }

        # Execute custom processing
        result = pipeline.custom_processing(test_data)

        # Verify results
        assert result['status'] == 'success'
        assert 'results' in result
        assert 'timestamp' in result

    def test_custom_service_integration(self, pipeline):
        """Test custom service integration with pipeline."""
        # Verify service is accessible
        assert hasattr(pipeline.services, 'custom')

        # Test service functionality
        stats = pipeline.services.custom.get_service_stats()
        assert 'service_name' in stats
        assert stats['service_name'] == 'CustomService'
```

### **Test Configuration**

```python
# tests/conftest.py

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from thoth.utilities.config import ThothConfig


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create required directories
        (workspace / "data" / "pdf").mkdir(parents=True)
        (workspace / "data" / "notes").mkdir(parents=True)
        (workspace / "knowledge").mkdir(parents=True)
        (workspace / "logs").mkdir(parents=True)

        yield workspace


@pytest.fixture
def mock_config(temp_workspace):
    """Create a mock configuration for testing."""
    config = Mock(spec=ThothConfig)
    config.workspace_dir = temp_workspace
    config.pdf_dir = temp_workspace / "data" / "pdf"
    config.notes_dir = temp_workspace / "data" / "notes"
    config.knowledge_base_dir = temp_workspace / "knowledge"

    # Mock API keys
    config.api_keys.openrouter_key = "test-openrouter-key"
    config.api_keys.mistral_key = "test-mistral-key"

    return config


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    llm = Mock()
    llm.invoke.return_value.content = "Test LLM response"
    return llm
```

## 📋 **Code Standards**

### **Python Style Guide**

#### **Formatting**
- **Black**: Automatic code formatting
- **isort**: Import sorting
- **Ruff**: Fast linting and formatting

```bash
# Format code
uv run black src/ tests/
uv run isort src/ tests/
uv run ruff format src/ tests/

# Check formatting
uv run black --check src/ tests/
uv run ruff check src/ tests/
```

#### **Type Hints**
All functions must include type hints:

```python
from typing import Dict, List, Optional, Union
from pathlib import Path

def process_article(
    article_path: Path,
    output_dir: Path,
    include_citations: bool = True
) -> Optional[Dict[str, str]]:
    """
    Process an article with proper type annotations.

    Args:
        article_path: Path to the article file
        output_dir: Directory for output files
        include_citations: Whether to include citations

    Returns:
        Dictionary with processing results or None if failed
    """
    pass
```

#### **Docstrings**
Use Google-style docstrings:

```python
def analyze_research_trends(
    papers: List[Dict[str, Any]],
    time_window: int = 365
) -> Dict[str, Any]:
    """
    Analyze research trends in a collection of papers.

    This function performs temporal analysis of research topics,
    identifying trending themes and their evolution over time.

    Args:
        papers: List of paper metadata dictionaries containing
            title, abstract, publication_date, and keywords
        time_window: Analysis window in days (default: 365)

    Returns:
        Dictionary containing:
            - trends: List of trending topics with scores
            - timeline: Temporal distribution of topics
            - insights: Key findings and patterns

    Raises:
        ValueError: If papers list is empty or invalid

    Example:
        >>> papers = [
        ...     {
        ...         'title': 'AI Research',
        ...         'abstract': 'Study of AI trends...',
        ...         'publication_date': '2024-01-15',
        ...         'keywords': ['AI', 'machine learning']
        ...     }
        ... ]
        >>> trends = analyze_research_trends(papers, time_window=180)
        >>> print(trends['insights'])
        ['AI research increased 25% in last 6 months']
    """
    pass
```

### **Error Handling**

#### **Exception Hierarchy**
```python
# src/thoth/utilities/exceptions.py

class ThothException(Exception):
    """Base exception for Thoth-related errors."""
    pass

class ConfigurationError(ThothException):
    """Raised when configuration is invalid."""
    pass

class ProcessingError(ThothException):
    """Raised when processing fails."""
    pass

class DiscoveryError(ThothException):
    """Raised when discovery fails."""
    pass

class APIError(ThothException):
    """Raised when API calls fail."""
    pass
```

#### **Error Handling Patterns**
```python
from thoth.utilities.exceptions import ProcessingError, APIError

def process_with_proper_error_handling(data: Dict[str, Any]) -> Dict[str, Any]:
    """Example of proper error handling."""
    try:
        # Attempt processing
        result = perform_processing(data)
        return result

    except APIError as e:
        logger.error(f"API error during processing: {e}")
        raise ProcessingError(f"Processing failed due to API error: {e}") from e

    except ValueError as e:
        logger.error(f"Invalid data format: {e}")
        raise ProcessingError(f"Invalid input data: {e}") from e

    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")
        raise ProcessingError(f"Unexpected processing error: {e}") from e
```

### **Logging Standards**

```python
from loguru import logger

def example_function_with_logging():
    """Example of proper logging practices."""
    logger.info("Starting processing operation")

    try:
        # Processing logic
        result = complex_operation()
        logger.debug(f"Operation completed with result: {result}")

        # Log important metrics
        logger.info(f"Processed {len(result)} items successfully")

        return result

    except Exception as e:
        logger.error(f"Operation failed: {e}")
        logger.debug(f"Full error details: {e}", exc_info=True)
        raise
```

## 🚀 **Deployment and CI/CD**

### **GitHub Actions Workflow**

```yaml
# .github/workflows/ci.yml

name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.10, 3.11, 3.12]

    steps:
    - uses: actions/checkout@v4

    - name: Install uv
      uses: astral-sh/setup-uv@v1
      with:
        version: "latest"

    - name: Set up Python
      run: uv python install ${{ matrix.python-version }}

    - name: Install dependencies
      run: uv sync --dev

    - name: Run code quality checks
      run: |
        uv run ruff check src/ tests/
        uv run black --check src/ tests/
        uv run isort --check-only src/ tests/
        uv run mypy src/

    - name: Run tests with coverage
      run: |
        uv run pytest --cov=src/thoth --cov-report=xml --cov-report=html

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

  docker:
    runs-on: ubuntu-latest
    needs: test

    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2

    - name: Build Docker image
      run: |
        docker build -t thoth-research:latest .
        docker run --rm thoth-research:latest python -m thoth --help
```

### **Pre-commit Configuration**

```yaml
# .pre-commit-config.yaml

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-toml

  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.3
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.6.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-PyYAML]
```

## 📖 **Documentation Standards**

### **Code Documentation**

- **Docstrings**: All public functions and classes must have docstrings
- **Type hints**: Required for all function signatures
- **Comments**: Explain complex logic and business decisions
- **Examples**: Include usage examples in docstrings

### **API Documentation**

The FastAPI server automatically generates documentation:
- **Swagger UI**: Available at `/docs`
- **ReDoc**: Available at `/redoc`
- **OpenAPI Schema**: Available at `/openapi.json`

### **Contributing Documentation**

When adding new features:

1. **Update docstrings** for all new functions/classes
2. **Add examples** to the `examples/` directory
3. **Update README** if interface changes
4. **Add integration tests** for new functionality
5. **Update API documentation** if endpoints change

## 🤝 **Contributing Process**

### **Development Workflow**

1. **Fork Repository**: Create your own fork
2. **Create Branch**: `git checkout -b feature/my-new-feature`
3. **Install Dependencies**: `uv sync --dev`
4. **Setup Pre-commit**: `uv run pre-commit install`
5. **Make Changes**: Implement your feature
6. **Write Tests**: Add comprehensive tests
7. **Run Tests**: `uv run pytest`
8. **Check Quality**: `uv run pre-commit run --all-files`
9. **Commit Changes**: Use conventional commit messages
10. **Push Branch**: `git push origin feature/my-new-feature`
11. **Create PR**: Submit pull request with description

### **Commit Message Convention**

```
type(scope): description

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions/modifications
- `chore`: Build process or auxiliary tool changes

Examples:
```
feat(agent): add custom tool registry system

Implement modular tool registration system that allows
dynamic addition of new agent capabilities.

Closes #123
```

### **Pull Request Guidelines**

- **Clear Title**: Describe what the PR does
- **Detailed Description**: Explain changes and motivation
- **Link Issues**: Reference related issues
- **Add Tests**: Include tests for new functionality
- **Update Docs**: Update relevant documentation
- **Check CI**: Ensure all checks pass

## 🐛 **Debugging Tips**

### **Common Issues**

#### **Agent Tool Not Working**
```bash
# Check tool registration
uv run python -c "
from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.pipeline import ThothPipeline

pipeline = ThothPipeline()
agent = create_research_assistant(adapter=pipeline.services)
tools = agent.get_available_tools()
print([tool['name'] for tool in tools])
"
```

#### **Service Not Accessible**
```bash
# Check service initialization
uv run python -c "
from thoth.services import ServiceManager

manager = ServiceManager()
print(f'Discovery service: {manager.discovery}')
print(f'RAG service: {manager.rag}')
"
```

#### **Configuration Issues**
```bash
# Validate configuration
uv run python -c "
from thoth.utilities.config import get_config
config = get_config()
print(f'API keys configured: {bool(config.api_keys.openrouter_key)}')
print(f'Workspace dir: {config.workspace_dir}')
"
```

---

This development guide provides comprehensive information for contributing to Thoth. For specific implementation questions, refer to the existing codebase examples and test cases.
