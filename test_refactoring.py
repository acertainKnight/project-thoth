#!/usr/bin/env python3
"""
Comprehensive test script for Thoth refactoring.

This script tests all major components to ensure the refactoring hasn't broken anything.
"""

import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Test results tracking
tests_passed = 0
tests_failed = 0
failures = []

def test_module(test_name, test_func):
    """Run a test and track results."""
    global tests_passed, tests_failed, failures
    
    print(f"\n{'='*60}")
    print(f"Testing: {test_name}")
    print('='*60)
    
    try:
        test_func()
        tests_passed += 1
        print(f"✅ PASSED: {test_name}")
    except Exception as e:
        tests_failed += 1
        error_msg = f"❌ FAILED: {test_name}\n{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        failures.append(error_msg)
        print(error_msg)


def test_basic_imports():
    """Test that all major modules can be imported."""
    print("Testing basic imports...")
    
    # Core imports
    from thoth import __version__
    print(f"  - Thoth version: {__version__}")
    
    from thoth.pipeline import ThothPipeline
    print("  - ThothPipeline imported")
    
    from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
    print("  - OptimizedDocumentPipeline imported")
    
    # Services
    from thoth.services.service_manager import ServiceManager
    print("  - ServiceManager imported")
    
    # Knowledge graph
    from thoth.knowledge.graph import CitationGraph
    print("  - CitationGraph imported")
    
    # Knowledge components
    from thoth.knowledge.components import (
        CitationStorage,
        CitationSearch,
        GraphAnalyzer,
        CitationFileManager
    )
    print("  - Knowledge components imported")
    
    # Memory components
    from thoth.memory.pipeline import (
        MemoryFilter,
        MemoryEnricher,
        SalienceScorer,
        MemoryWritePipeline,
        MemoryReadPipeline
    )
    print("  - Memory pipeline components imported")
    
    # MCP tools
    from thoth.mcp.tools import TOOL_REGISTRY
    print(f"  - MCP tools registry loaded with {len(TOOL_REGISTRY)} tools")


def test_discovery_tools():
    """Test discovery tool imports and structure."""
    print("Testing discovery tools...")
    
    # Import all discovery tools
    from thoth.mcp.tools.discovery import (
        ListDiscoverySourcesMCPTool,
        CreateArxivSourceMCPTool,
        CreatePubmedSourceMCPTool,
        CreateCrossrefSourceMCPTool,
        CreateOpenalexSourceMCPTool,
        CreateBiorxivSourceMCPTool,
        GetDiscoverySourceMCPTool,
        RunDiscoveryMCPTool,
        DeleteDiscoverySourceMCPTool,
    )
    
    # Check tool attributes
    tools = [
        ListDiscoverySourcesMCPTool,
        CreateArxivSourceMCPTool,
        CreatePubmedSourceMCPTool,
        GetDiscoverySourceMCPTool,
        RunDiscoveryMCPTool,
        DeleteDiscoverySourceMCPTool,
    ]
    
    for tool in tools:
        assert hasattr(tool, 'name'), f"{tool.__name__} missing 'name'"
        assert hasattr(tool, 'description'), f"{tool.__name__} missing 'description'"
        print(f"  - {tool.name}: OK")


def test_data_management_tools():
    """Test data management tool imports."""
    print("Testing data management tools...")
    
    from thoth.mcp.tools.data import (
        BackupCollectionMCPTool,
        ExportArticleDataMCPTool,
        GenerateReadingListMCPTool,
        SyncWithObsidianMCPTool,
    )
    
    tools = [
        BackupCollectionMCPTool,
        ExportArticleDataMCPTool,
        GenerateReadingListMCPTool,
        SyncWithObsidianMCPTool,
    ]
    
    for tool in tools:
        assert hasattr(tool, 'name'), f"{tool.__name__} missing 'name'"
        assert hasattr(tool, 'description'), f"{tool.__name__} missing 'description'"
        print(f"  - {tool.name}: OK")


def test_memory_pipeline():
    """Test memory pipeline functionality."""
    print("Testing memory pipeline...")
    
    from thoth.memory.pipeline import (
        MemoryFilter,
        MemoryEnricher,
        SalienceScorer,
        MemoryWritePipeline,
    )
    
    # Test filter
    filter_obj = MemoryFilter()
    should_store, reason = filter_obj.should_store("Test content", "user")
    print(f"  - MemoryFilter test: {should_store} ({reason})")
    
    # Test enricher
    enricher = MemoryEnricher()
    enriched = enricher.enrich("Test content with https://example.com", "user")
    assert 'urls' in enriched
    print(f"  - MemoryEnricher found URLs: {enriched.get('urls', [])}")
    
    # Test scorer
    scorer = SalienceScorer()
    score = scorer.calculate_salience("Important research findings about neural networks", "user")
    print(f"  - SalienceScorer score: {score:.3f}")
    
    # Test pipeline
    pipeline = MemoryWritePipeline()
    print("  - MemoryWritePipeline created successfully")


def test_knowledge_graph():
    """Test knowledge graph components."""
    print("Testing knowledge graph...")
    
    from thoth.knowledge.graph import CitationGraph, CitationReference
    from thoth.utilities.schemas import Citation
    
    # Test CitationReference
    ref = CitationReference("test-id")
    print(f"  - CitationReference: {ref}")
    
    # Test Citation object
    citation = Citation(
        title="Test Paper",
        authors=["Test Author"],
        year=2024,
        doi="10.1234/test"
    )
    print(f"  - Citation object created: {citation.title}")
    
    # Test CitationGraph initialization
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        graph = CitationGraph(tmpdir)
        print(f"  - CitationGraph initialized with {graph.graph.number_of_nodes()} nodes")
        
        # Test article ID generation
        article_id = graph._generate_article_id(citation)
        print(f"  - Generated article ID: {article_id}")


def test_server_routers():
    """Test server router imports."""
    print("Testing server routers...")
    
    from thoth.server.routers import routers
    print(f"  - Found {len(routers)} routers")
    
    # Import individual routers
    from thoth.server.routers import (
        agent_router,
        chat_router,
        config_router,
        health_router,
        operations_router,
        research_router,
        tools_router,
        websocket_router,
    )
    
    router_names = [
        'agent', 'chat', 'config', 'health',
        'operations', 'research', 'tools', 'websocket'
    ]
    
    for name in router_names:
        print(f"  - {name}_router: OK")


def test_api_sources():
    """Test API source imports."""
    print("Testing API sources...")
    
    from thoth.discovery.sources import (
        BaseAPISource,
        ArxivClient,
        PubMedAPISource,
        CrossRefAPISource,
        OpenAlexAPISource,
        BioRxivAPISource,
    )
    
    # Check base class
    assert hasattr(BaseAPISource, 'search'), "BaseAPISource missing 'search' method"
    print("  - BaseAPISource: OK")
    
    # Check each source
    sources = [
        PubMedAPISource,
        CrossRefAPISource,
        OpenAlexAPISource,
        BioRxivAPISource,
    ]
    
    for source in sources:
        assert issubclass(source, BaseAPISource), f"{source.__name__} not subclass of BaseAPISource"
        print(f"  - {source.__name__}: OK")
    
    # Check ArxivClient
    print("  - ArxivClient: OK")


def test_pipeline_integration():
    """Test pipeline integration with OptimizedDocumentPipeline."""
    print("Testing pipeline integration...")
    
    from thoth.pipeline import ThothPipeline
    from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
    
    # Check that ThothPipeline uses OptimizedDocumentPipeline
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = ThothPipeline(
            output_dir=tmpdir,
            notes_dir=tmpdir,
            markdown_dir=tmpdir
        )
        
        # Check document pipeline type
        assert hasattr(pipeline, 'document_pipeline'), "ThothPipeline missing document_pipeline"
        assert isinstance(pipeline.document_pipeline, OptimizedDocumentPipeline), \
            "ThothPipeline not using OptimizedDocumentPipeline"
        print("  - ThothPipeline correctly uses OptimizedDocumentPipeline")


def test_cli_commands():
    """Test CLI command imports."""
    print("Testing CLI commands...")
    
    # Main CLI
    from thoth.cli.main import main
    print("  - CLI main entry point: OK")
    
    # CLI modules
    from thoth.cli import (
        agent,
        auto_discovery,
        chat,
        config as cli_config,
        discovery,
        mcp,
        memory,
        monitor,
        notes,
        pdf,
        performance,
        queries,
        rag,
        server,
        stats,
        system,
        tags,
        web,
    )
    
    cli_modules = [
        'agent', 'auto_discovery', 'chat', 'config',
        'discovery', 'mcp', 'memory', 'monitor',
        'notes', 'pdf', 'performance', 'queries',
        'rag', 'server', 'stats', 'system', 'tags', 'web'
    ]
    
    for module in cli_modules:
        print(f"  - CLI {module}: OK")


def test_configuration():
    """Test configuration system."""
    print("Testing configuration...")
    
    from thoth.utilities.config import get_config, ThothConfig
    
    # Test get_config
    config = get_config()
    assert isinstance(config, ThothConfig), "get_config() didn't return ThothConfig"
    print("  - get_config(): OK")
    
    # Check config has expected attributes
    expected_attrs = [
        'obsidian_vault_path',
        'obsidian_daily_notes_folder',
        'pdf_dir',
        'markdown_dir',
        'notes_dir',
    ]
    
    for attr in expected_attrs:
        assert hasattr(config, attr), f"ThothConfig missing '{attr}'"
    print("  - ThothConfig attributes: OK")


def test_mcp_tool_registry():
    """Test MCP tool registry completeness."""
    print("Testing MCP tool registry...")
    
    from thoth.mcp.tools import TOOL_REGISTRY
    
    # Expected tools
    expected_tools = [
        # Article tools
        'list_articles', 'search_articles', 'get_article_details',
        'get_related_articles', 'cite_article', 'update_article_metadata',
        # Discovery tools
        'list_discovery_sources', 'create_arxiv_source', 'create_pubmed_source',
        'get_discovery_source', 'run_discovery', 'delete_discovery_source',
        # Data tools
        'backup_collection', 'export_article_data', 'generate_reading_list',
        'sync_with_obsidian',
        # Processing tools
        'process_pdf', 'process_article', 'summarize_article',
        'generate_notes', 'regenerate_notes', 'auto_tag_articles',
        # Citation tools
        'format_citations', 'export_bibliography', 'extract_citations',
        # Tag tools
        'list_tags', 'add_tags', 'remove_tags', 'rename_tag',
        'merge_tags', 'get_popular_tags', 'search_by_tags',
        # Web tools
        'web_search',
    ]
    
    missing_tools = []
    for tool_name in expected_tools:
        if tool_name not in TOOL_REGISTRY:
            missing_tools.append(tool_name)
    
    if missing_tools:
        raise AssertionError(f"Missing tools in registry: {missing_tools}")
    
    print(f"  - All {len(expected_tools)} expected tools present in registry")
    print(f"  - Total tools in registry: {len(TOOL_REGISTRY)}")


def test_backwards_compatibility():
    """Test backwards compatibility of imports."""
    print("Testing backwards compatibility...")
    
    # Test that DocumentPipeline is aliased to OptimizedDocumentPipeline
    from thoth import DocumentPipeline
    from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
    assert DocumentPipeline is OptimizedDocumentPipeline, \
        "DocumentPipeline not properly aliased to OptimizedDocumentPipeline"
    print("  - DocumentPipeline alias: OK")
    
    # Test __main__ entry point
    from thoth.__main__ import main
    from thoth.cli.main import main as cli_main
    assert main is cli_main, "__main__ not pointing to cli.main"
    print("  - __main__ entry point: OK")


def main():
    """Run all tests."""
    print("🧪 THOTH REFACTORING TEST SUITE")
    print("================================\n")
    
    # Run all tests
    test_module("Basic Imports", test_basic_imports)
    test_module("Discovery Tools", test_discovery_tools)
    test_module("Data Management Tools", test_data_management_tools)
    test_module("Memory Pipeline", test_memory_pipeline)
    test_module("Knowledge Graph", test_knowledge_graph)
    test_module("Server Routers", test_server_routers)
    test_module("API Sources", test_api_sources)
    test_module("Pipeline Integration", test_pipeline_integration)
    test_module("CLI Commands", test_cli_commands)
    test_module("Configuration System", test_configuration)
    test_module("MCP Tool Registry", test_mcp_tool_registry)
    test_module("Backwards Compatibility", test_backwards_compatibility)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Tests Passed: {tests_passed}")
    print(f"❌ Tests Failed: {tests_failed}")
    
    if tests_failed > 0:
        print("\nFAILED TESTS:")
        for failure in failures:
            print(failure)
        sys.exit(1)
    else:
        print("\n🎉 ALL TESTS PASSED! The refactoring is successful.")
        sys.exit(0)


if __name__ == "__main__":
    main()