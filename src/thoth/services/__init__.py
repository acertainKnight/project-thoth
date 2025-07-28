"""Thoth services package with lazy access to service classes."""

from importlib import import_module

_MODULES = {
    'ArticleService': 'article_service',
    'BaseService': 'base',
    'CitationService': 'citation_service',
    'DiscoveryService': 'discovery_service',
    'ExternalAPIGateway': 'api_gateway',
    'LLMService': 'llm_service',
    'NoteService': 'note_service',
    'PdfLocatorService': 'pdf_locator_service',
    'ProcessingService': 'processing_service',
    'QueryService': 'query_service',
    'RAGService': 'rag_service',
    'ServiceManager': 'service_manager',
    'TagService': 'tag_service',
    'WebSearchService': 'web_search_service',
}

__all__ = list(_MODULES)


def __getattr__(name: str):
    if name in _MODULES:
        module = import_module(f'thoth.services.{_MODULES[name]}')
        return getattr(module, name)
    raise AttributeError(name)
