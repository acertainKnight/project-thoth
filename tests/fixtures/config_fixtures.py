"""Test fixtures for configuration tests.

Provides sample JSON configurations, factory functions, and reusable fixtures
for testing the configuration system.
"""

import json  # noqa: I001
from pathlib import Path
from typing import Any, Dict  # noqa: UP035

import pytest


# ============================================================================
# Sample JSON Configurations
# ============================================================================


def get_minimal_settings_json() -> Dict[str, Any]:  # noqa: UP006
    """Minimal valid settings.json with defaults."""
    return {
        '$schema': './settings.schema.json',
        'version': '1.0.0',
        'lastModified': '2025-12-31T00:00:00Z',
        '_comment': 'Minimal test configuration',
        'apiKeys': {},
        'llm': {},
        'rag': {},
        'memory': {},
        'paths': {},
        'servers': {},
        'discovery': {},
        'citation': {},
        'performance': {},
        'logging': {},
        'apiGateway': {},
        'environment': {},
        'postgres': {},
        'featureFlags': {},
    }


def get_full_settings_json() -> Dict[str, Any]:  # noqa: UP006
    """Complete settings.json with all fields populated."""
    return {
        '$schema': './settings.schema.json',
        'version': '1.0.0',
        'lastModified': '2025-12-31T00:00:00Z',
        '_comment': 'Full test configuration',
        'apiKeys': {
            'mistralKey': 'test-mistral-key',
            'openrouterKey': 'test-openrouter-key',
            'openaiKey': 'test-openai-key',
            'anthropicKey': 'test-anthropic-key',
            'opencitationsKey': 'test-opencitations-key',
            'googleApiKey': 'test-google-key',
            'googleSearchEngineId': 'test-search-engine-id',
            'semanticScholarKey': 'test-semantic-scholar-key',
            'webSearchKey': 'test-web-search-key',
            'webSearchProviders': ['google', 'brave'],
            'lettaApiKey': 'test-letta-key',
            'unpaywallEmail': 'test@example.com',
        },
        'llm': {
            'default': {
                'model': 'google/gemini-2.5-flash',
                'temperature': 0.9,
                'maxTokens': 500000,
                'topP': 1.0,
                'frequencyPenalty': 0.0,
                'presencePenalty': 0.0,
                'streaming': False,
                'useRateLimiter': True,
                'docProcessing': 'auto',
                'maxOutputTokens': 500000,
                'maxContextLength': 8000,
                'chunkSize': 4000,
                'chunkOverlap': 200,
                'refineThresholdMultiplier': 1.2,
                'mapReduceThresholdMultiplier': 3.0,
            },
            'citation': {
                'model': 'openai/gpt-4o-mini',
                'temperature': 0.9,
                'maxTokens': 10000,
                'maxOutputTokens': 10000,
                'maxContextLength': 4000,
                'models': {
                    'documentCitation': 'openai/gpt-4o-mini',
                    'referenceCleaning': 'openai/gpt-4o-mini',
                    'structuredExtraction': 'openai/gpt-4o-mini',
                    'batchStructuredExtraction': 'openai/gpt-4o-mini',
                },
            },
            'tagConsolidator': {
                'consolidateModel': 'google/gemini-2.5-flash',
                'suggestModel': 'google/gemini-2.5-flash',
                'mapModel': 'google/gemini-2.5-flash',
                'temperature': 0.9,
                'maxTokens': 10000,
                'maxOutputTokens': 10000,
                'maxContextLength': 8000,
            },
            'researchAgent': {
                'model': 'google/gemini-3-pro-preview',
                'temperature': 0.9,
                'maxTokens': 50000,
                'maxOutputTokens': 50000,
                'maxContextLength': 100000,
                'useAutoModelSelection': False,
                'autoModelRequireToolCalling': False,
                'autoModelRequireStructuredOutput': False,
            },
            'scrapeFilter': {
                'model': 'google/gemini-2.5-flash',
                'temperature': 0.9,
                'maxTokens': 10000,
                'maxOutputTokens': 10000,
                'maxContextLength': 50000,
            },
            'queryBasedRouting': {
                'enabled': False,
                'routingModel': 'google/gemini-2.5-flash',
                'useDynamicPrompt': False,
            },
        },
        'rag': {
            'embeddingModel': 'openai/text-embedding-3-small',
            'embeddingBatchSize': 100,
            'skipFilesWithImages': True,
            'vectorDbPath': 'knowledge/vector_db',
            'collectionName': 'thoth_knowledge',
            'chunkSize': 1000,
            'chunkOverlap': 200,
            'chunkEncoding': 'cl100k_base',
            'qa': {
                'model': 'google/gemini-2.5-flash',
                'temperature': 0.2,
                'maxTokens': 2000,
                'retrievalK': 4,
            },
        },
        'memory': {
            'letta': {
                'serverUrl': 'http://localhost:8283',
                'agentName': 'thoth_research_agent',
                'coreMemoryLimit': 10000,
                'archivalMemoryEnabled': True,
                'recallMemoryEnabled': True,
                'enableSmartTruncation': True,
                'consolidationIntervalHours': 24,
                'fallbackEnabled': True,
            },
            'thoth': {
                'vectorBackend': 'chromadb',
                'namespace': 'thoth',
                'pipeline': {
                    'enabled': True,
                    'minSalience': 0.1,
                    'enableEnrichment': True,
                    'enableFiltering': True,
                },
                'retrieval': {
                    'enabled': True,
                    'relevanceWeight': 0.4,
                    'salienceWeight': 0.3,
                    'recencyWeight': 0.2,
                    'diversityWeight': 0.1,
                },
            },
            'scheduler': {
                'jobs': {
                    'episodicSummarization': {
                        'enabled': True,
                        'intervalHours': 24,
                        'timeOfDay': '02:00',
                        'daysOfWeek': ['monday', 'wednesday', 'friday'],
                        'parameters': {
                            'analysisWindowHours': 168,
                            'minMemoriesThreshold': 10,
                            'cleanupAfterSummary': False,
                        },
                    }
                }
            },
        },
        'paths': {
            'workspace': '/workspace',
            'pdf': 'data/pdf',
            'markdown': 'data/markdown',
            'notes': '/thoth/notes',
            'prompts': 'data/prompts',
            'templates': 'data/templates',
            'output': 'data/output',
            'knowledgeBase': 'data/knowledge',
            'graphStorage': 'data/graph/citations.graphml',
            'queries': 'data/queries',
            'agentStorage': 'data/agent',
            'discovery': {
                'sources': 'data/discovery/sources',
                'results': 'data/discovery/results',
                'chromeConfigs': 'data/discovery/chrome_configs',
            },
            'logs': 'logs',
        },
        'servers': {
            'api': {
                'host': '0.0.0.0',
                'port': 8000,
                'baseUrl': 'http://localhost:8000',
                'autoStart': False,
            },
            'mcp': {
                'host': 'localhost',
                'port': 8001,
                'autoStart': True,
                'enabled': True,
            },
            'monitor': {
                'autoStart': True,
                'watchInterval': 10,
                'bulkProcessSize': 10,
                'watchDirectories': ['data/pdf', 'data/markdown'],
                'recursive': True,
                'optimized': True,
            },
        },
        'discovery': {
            'autoStartScheduler': False,
            'defaultMaxArticles': 50,
            'defaultIntervalMinutes': 60,
            'rateLimitDelay': 1.0,
            'chromeExtension': {'enabled': True, 'host': 'localhost', 'port': 8765},
            'webSearch': {'providers': ['google', 'brave']},
        },
        'citation': {
            'linkFormat': 'uri',
            'style': 'IEEE',
            'apis': {
                'useOpencitations': True,
                'useScholarly': True,
                'useSemanticScholar': False,
                'useArxiv': False,
            },
            'processing': {'mode': 'single', 'batchSize': 5},
            'useResolutionChain': True,
        },
        'performance': {
            'autoScaleWorkers': True,
            'workers': {
                'tagMapping': 'auto',
                'articleProcessing': 'auto',
                'contentAnalysis': 'auto',
                'citationEnhancement': 'auto',
                'citationPdf': 'auto',
                'citationExtraction': 'auto',
            },
            'ocr': {'maxConcurrent': 3, 'enableCaching': True, 'cacheTtlHours': 24},
            'async': {'enabled': True, 'timeoutSeconds': 300},
            'memory': {
                'optimizationEnabled': True,
                'chunkProcessingEnabled': True,
                'maxDocumentSizeMb': 50,
            },
            'semanticScholar': {
                'maxRetries': 3,
                'maxBackoffSeconds': 30.0,
                'backoffMultiplier': 1.5,
            },
        },
        'logging': {
            'level': 'WARNING',
            'format': '{time} | {level} | {file}:{line} | {function} | {message}',
            'dateFormat': 'YYYY-MM-DD HH:mm:ss',
            'rotation': {'enabled': True, 'maxBytes': 10485760, 'backupCount': 3},
            'file': {
                'enabled': True,
                'path': '/workspace/logs/thoth.log',
                'mode': 'a',
                'level': 'WARNING',
                'rotation': '10 MB',
                'retention': '7 days',
                'compression': 'zip',
            },
            'console': {'enabled': True, 'level': 'WARNING'},
        },
        'apiGateway': {
            'rateLimit': 5.0,
            'cacheExpiry': 3600,
            'defaultTimeout': 15,
            'endpoints': {},
        },
        'environment': {
            'type': 'docker',
            'pythonUnbuffered': True,
            'development': False,
            'security': {'sessionTimeout': 3600, 'apiRateLimit': 100},
        },
        'postgres': {
            'enabled': True,
            'poolMinSize': 5,
            'poolMaxSize': 20,
            'connectionTimeout': 60.0,
            'commandTimeout': 60.0,
            'retryAttempts': 3,
        },
        'featureFlags': {
            'usePostgresForCitations': False,
            'usePostgresForTags': False,
            'usePostgresForRagMetadata': False,
            'enableCacheLayer': True,
            'cacheTtlSeconds': 300,
        },
    }


def get_invalid_settings_json() -> Dict[str, Any]:  # noqa: UP006
    """Invalid settings.json for testing validation."""
    return {
        'llm': {
            'default': {
                'temperature': 'not-a-number',  # Invalid type
                'maxTokens': -1000,  # Invalid value
            }
        }
    }


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture
def temp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault structure with minimal settings.json.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary vault root
    """
    vault_root = tmp_path / 'test_vault'
    vault_root.mkdir()

    # Create _thoth directory
    thoth_dir = vault_root / '_thoth'
    thoth_dir.mkdir()

    # Create minimal settings.json so Config() can be instantiated
    settings_file = thoth_dir / 'settings.json'
    settings_file.write_text(json.dumps(get_minimal_settings_json(), indent=2))

    return vault_root


@pytest.fixture
def minimal_settings_file(temp_vault: Path) -> Path:
    """Create minimal settings.json file.

    Args:
        temp_vault: Path to temporary vault

    Returns:
        Path to settings.json file
    """
    settings_file = temp_vault / '_thoth' / 'settings.json'
    settings_file.write_text(json.dumps(get_minimal_settings_json(), indent=2))
    return settings_file


@pytest.fixture
def full_settings_file(temp_vault: Path) -> Path:
    """Create complete settings.json file.

    Args:
        temp_vault: Path to temporary vault

    Returns:
        Path to settings.json file
    """
    settings_file = temp_vault / '_thoth' / 'settings.json'
    settings_file.write_text(json.dumps(get_full_settings_json(), indent=2))
    return settings_file


@pytest.fixture
def invalid_settings_file(temp_vault: Path) -> Path:
    """Create invalid settings.json file.

    Args:
        temp_vault: Path to temporary vault

    Returns:
        Path to invalid settings.json file
    """
    settings_file = temp_vault / '_thoth' / 'settings.json'
    settings_file.write_text(json.dumps(get_invalid_settings_json(), indent=2))
    return settings_file


@pytest.fixture
def partial_settings_file(temp_vault: Path) -> Path:
    """Create partial settings.json (only some fields).

    Args:
        temp_vault: Path to temporary vault

    Returns:
        Path to partial settings.json file
    """
    partial_settings = {
        'apiKeys': {'openaiKey': 'test-key'},
        'llm': {'default': {'model': 'test-model'}},
    }
    settings_file = temp_vault / '_thoth' / 'settings.json'
    settings_file.write_text(json.dumps(partial_settings, indent=2))
    return settings_file


@pytest.fixture
def malformed_json_file(temp_vault: Path) -> Path:
    """Create malformed JSON file.

    Args:
        temp_vault: Path to temporary vault

    Returns:
        Path to malformed JSON file
    """
    settings_file = temp_vault / '_thoth' / 'settings.json'
    settings_file.write_text('{ invalid json content')
    return settings_file


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    """Create .env file with secrets.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to .env file
    """
    env_file = tmp_path / '.env'
    env_content = """
OPENAI_API_KEY=env-openai-key
ANTHROPIC_API_KEY=env-anthropic-key
OPENROUTER_API_KEY=env-openrouter-key
GOOGLE_API_KEY=env-google-key
MISTRAL_API_KEY=env-mistral-key
DATABASE_URL=postgresql://user:pass@localhost/db
LETTA_API_KEY=env-letta-key
LETTA_SERVER_URL=http://localhost:8283
SERPER_API_KEY=env-serper-key
BRAVE_API_KEY=env-brave-key
"""
    env_file.write_text(env_content.strip())
    return env_file


@pytest.fixture
def sample_api_keys_dict() -> Dict[str, Any]:  # noqa: UP006
    """Sample API keys dictionary."""
    return {
        'mistralKey': 'test-mistral',
        'openrouterKey': 'test-openrouter',
        'openaiKey': 'test-openai',
        'anthropicKey': 'test-anthropic',
        'opencitationsKey': 'test-opencitations',
        'googleApiKey': 'test-google',
        'googleSearchEngineId': 'test-search-id',
        'semanticScholarKey': 'test-semantic',
        'webSearchKey': 'test-websearch',
        'webSearchProviders': ['google'],
        'lettaApiKey': 'test-letta',
        'unpaywallEmail': 'test@example.com',
    }


@pytest.fixture
def sample_llm_default_dict() -> Dict[str, Any]:  # noqa: UP006
    """Sample LLM default configuration dictionary."""
    return {
        'model': 'test-model',
        'temperature': 0.7,
        'maxTokens': 2000,
        'topP': 0.9,
        'frequencyPenalty': 0.5,
        'presencePenalty': 0.5,
        'streaming': True,
        'useRateLimiter': False,
        'docProcessing': 'map_reduce',
        'maxOutputTokens': 2000,
        'maxContextLength': 4000,
        'chunkSize': 2000,
        'chunkOverlap': 100,
        'refineThresholdMultiplier': 1.5,
        'mapReduceThresholdMultiplier': 2.5,
    }


@pytest.fixture
def sample_citation_config_dict() -> Dict[str, Any]:  # noqa: UP006
    """Sample citation configuration dictionary."""
    return {
        'model': 'test-citation-model',
        'temperature': 0.3,
        'maxTokens': 5000,
        'maxOutputTokens': 5000,
        'maxContextLength': 3000,
        'models': {
            'documentCitation': 'doc-model',
            'referenceCleaning': 'ref-model',
            'structuredExtraction': 'extract-model',
            'batchStructuredExtraction': 'batch-model',
        },
    }


@pytest.fixture
def sample_rag_config_dict() -> Dict[str, Any]:  # noqa: UP006
    """Sample RAG configuration dictionary."""
    return {
        'embeddingModel': 'test-embedding-model',
        'embeddingBatchSize': 50,
        'skipFilesWithImages': False,
        'vectorDbPath': 'test/vector_db',
        'collectionName': 'test_collection',
        'chunkSize': 500,
        'chunkOverlap': 100,
        'chunkEncoding': 'cl100k_base',
        'qa': {
            'model': 'test-qa-model',
            'temperature': 0.1,
            'maxTokens': 1000,
            'retrievalK': 3,
        },
    }


@pytest.fixture
def sample_memory_config_dict() -> Dict[str, Any]:  # noqa: UP006
    """Sample memory configuration dictionary."""
    return {
        'letta': {
            'serverUrl': 'http://test:8283',
            'agentName': 'test_agent',
            'coreMemoryLimit': 5000,
            'archivalMemoryEnabled': False,
            'recallMemoryEnabled': False,
            'enableSmartTruncation': False,
            'consolidationIntervalHours': 12,
            'fallbackEnabled': False,
        },
        'thoth': {
            'vectorBackend': 'qdrant',
            'namespace': 'test',
            'pipeline': {
                'enabled': False,
                'minSalience': 0.2,
                'enableEnrichment': False,
                'enableFiltering': False,
            },
            'retrieval': {
                'enabled': False,
                'relevanceWeight': 0.5,
                'salienceWeight': 0.3,
                'recencyWeight': 0.1,
                'diversityWeight': 0.1,
            },
        },
        'scheduler': {'jobs': {}},
    }


@pytest.fixture
def sample_paths_config_dict() -> Dict[str, Any]:  # noqa: UP006
    """Sample paths configuration dictionary."""
    return {
        'workspace': '/test/workspace',
        'pdf': 'test/pdf',
        'markdown': 'test/markdown',
        'notes': '/test/notes',
        'prompts': 'test/prompts',
        'templates': 'test/templates',
        'output': 'test/output',
        'knowledgeBase': 'test/knowledge',
        'graphStorage': 'test/graph.graphml',
        'queries': 'test/queries',
        'agentStorage': 'test/agent',
        'discovery': {
            'sources': 'test/discovery/sources',
            'results': 'test/discovery/results',
            'chromeConfigs': 'test/discovery/configs',
        },
        'logs': 'test/logs',
    }


@pytest.fixture
def sample_logging_config_dict() -> Dict[str, Any]:  # noqa: UP006
    """Sample logging configuration dictionary."""
    return {
        'level': 'DEBUG',
        'format': 'test format',
        'dateFormat': 'YYYY-MM-DD',
        'rotation': {'enabled': False, 'maxBytes': 5000000, 'backupCount': 5},
        'file': {
            'enabled': False,
            'path': '/test/logs/test.log',
            'mode': 'w',
            'level': 'INFO',
            'rotation': '5 MB',
            'retention': '3 days',
            'compression': 'gz',
        },
        'console': {'enabled': False, 'level': 'DEBUG'},
    }
