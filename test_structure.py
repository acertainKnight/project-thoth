#!/usr/bin/env python3
"""
Structural test for Thoth refactoring.

This script verifies the code structure and imports without requiring dependencies.
"""

import ast
import os
from pathlib import Path

# Test results
tests_passed = 0
tests_failed = 0
issues = []

def check_file_exists(filepath):
    """Check if a file exists."""
    path = Path(filepath)
    if not path.exists():
        issues.append(f"Missing file: {filepath}")
        return False
    return True

def check_imports_in_file(filepath, expected_imports):
    """Check if a file contains expected import statements."""
    if not check_file_exists(filepath):
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        issues.append(f"Syntax error in {filepath}: {e}")
        return False
    
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
    
    missing = []
    for expected in expected_imports:
        found = False
        for imp in imports:
            if expected in imp:
                found = True
                break
        if not found:
            missing.append(expected)
    
    if missing:
        issues.append(f"{filepath} missing imports: {missing}")
        return False
    
    return True

def test_module(name, test_func):
    """Run a test."""
    global tests_passed, tests_failed
    
    print(f"\nTesting {name}...")
    if test_func():
        tests_passed += 1
        print(f"✅ {name}: PASSED")
    else:
        tests_failed += 1
        print(f"❌ {name}: FAILED")

def test_project_structure():
    """Test that all expected directories exist."""
    expected_dirs = [
        "src/thoth",
        "src/thoth/server/routers",
        "src/thoth/discovery/sources",
        "src/thoth/memory/scoring",
        "src/thoth/memory/filtering",
        "src/thoth/memory/enrichment",
        "src/thoth/knowledge/components",
        "src/thoth/mcp/tools/discovery",
        "src/thoth/mcp/tools/data",
    ]
    
    for dir_path in expected_dirs:
        if not Path(dir_path).exists():
            issues.append(f"Missing directory: {dir_path}")
            return False
    
    return True

def test_deleted_files():
    """Ensure old files were deleted."""
    deleted_files = [
        "src/thoth/main.py",
        "src/thoth/pipelines/document_pipeline.py",
        "src/thoth/server/api_server.py",
        "src/thoth/discovery/api_sources.py",
        "src/thoth/mcp/tools/discovery_tools.py",
        "src/thoth/mcp/tools/data_management_tools.py",
    ]
    
    for filepath in deleted_files:
        if Path(filepath).exists():
            issues.append(f"File should be deleted: {filepath}")
            return False
    
    return True

def test_new_router_files():
    """Test that router files exist and have proper structure."""
    router_files = [
        "src/thoth/server/routers/__init__.py",
        "src/thoth/server/routers/health.py",
        "src/thoth/server/routers/websocket.py",
        "src/thoth/server/routers/chat.py",
        "src/thoth/server/routers/agent.py",
        "src/thoth/server/routers/research.py",
        "src/thoth/server/routers/config.py",
        "src/thoth/server/routers/operations.py",
        "src/thoth/server/routers/tools.py",
    ]
    
    for filepath in router_files:
        if not check_file_exists(filepath):
            return False
    
    # Check routers __init__.py exports
    return check_imports_in_file(
        "src/thoth/server/routers/__init__.py",
        ["agent", "chat", "config", "health", "operations", "research", "tools", "websocket"]
    )

def test_discovery_source_files():
    """Test discovery source structure."""
    source_files = [
        "src/thoth/discovery/sources/__init__.py",
        "src/thoth/discovery/sources/base.py",
        "src/thoth/discovery/sources/arxiv.py",
        "src/thoth/discovery/sources/pubmed.py",
        "src/thoth/discovery/sources/crossref.py",
        "src/thoth/discovery/sources/openalex.py",
        "src/thoth/discovery/sources/biorxiv.py",
    ]
    
    for filepath in source_files:
        if not check_file_exists(filepath):
            return False
    
    # Check base class exists
    with open("src/thoth/discovery/sources/base.py", 'r') as f:
        if "class BaseAPISource" not in f.read():
            issues.append("BaseAPISource not found in base.py")
            return False
    
    return True

def test_memory_components():
    """Test memory pipeline components."""
    component_files = [
        "src/thoth/memory/scoring/__init__.py",
        "src/thoth/memory/scoring/salience.py",
        "src/thoth/memory/filtering/__init__.py",
        "src/thoth/memory/filtering/memory_filter.py",
        "src/thoth/memory/enrichment/__init__.py",
        "src/thoth/memory/enrichment/memory_enricher.py",
    ]
    
    for filepath in component_files:
        if not check_file_exists(filepath):
            return False
    
    # Check SalienceScorer moved
    with open("src/thoth/memory/scoring/salience.py", 'r') as f:
        if "class SalienceScorer" not in f.read():
            issues.append("SalienceScorer not found in salience.py")
            return False
    
    return True

def test_knowledge_components():
    """Test knowledge graph components."""
    component_files = [
        "src/thoth/knowledge/components/__init__.py",
        "src/thoth/knowledge/components/storage.py",
        "src/thoth/knowledge/components/search.py",
        "src/thoth/knowledge/components/analysis.py",
        "src/thoth/knowledge/components/file_manager.py",
    ]
    
    for filepath in component_files:
        if not check_file_exists(filepath):
            return False
    
    # Check classes exist
    classes = {
        "storage.py": "CitationStorage",
        "search.py": "CitationSearch",
        "analysis.py": "GraphAnalyzer",
        "file_manager.py": "CitationFileManager",
    }
    
    for filename, classname in classes.items():
        with open(f"src/thoth/knowledge/components/{filename}", 'r') as f:
            if f"class {classname}" not in f.read():
                issues.append(f"{classname} not found in {filename}")
                return False
    
    return True

def test_mcp_tool_structure():
    """Test MCP tool modularization."""
    tool_dirs = [
        "src/thoth/mcp/tools/discovery",
        "src/thoth/mcp/tools/data",
    ]
    
    for dir_path in tool_dirs:
        if not Path(dir_path).exists():
            issues.append(f"Missing directory: {dir_path}")
            return False
    
    # Check discovery tools
    discovery_files = [
        "list_sources.py",
        "arxiv_source.py",
        "pubmed_source.py",
        "other_sources.py",
        "management.py",
        "base.py",
        "__init__.py",
    ]
    
    for filename in discovery_files:
        filepath = f"src/thoth/mcp/tools/discovery/{filename}"
        if not check_file_exists(filepath):
            return False
    
    # Check data tools
    data_files = [
        "backup.py",
        "export.py", 
        "reading_list.py",
        "__init__.py",
    ]
    
    for filename in data_files:
        filepath = f"src/thoth/mcp/tools/data/{filename}"
        if not check_file_exists(filepath):
            return False
    
    return True

def test_pipeline_changes():
    """Test pipeline changes."""
    # Check ThothPipeline imports OptimizedDocumentPipeline
    with open("src/thoth/pipeline.py", 'r') as f:
        content = f.read()
        if "from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline" not in content:
            issues.append("ThothPipeline not importing OptimizedDocumentPipeline")
            return False
        if "self.document_pipeline = OptimizedDocumentPipeline(" not in content:
            issues.append("ThothPipeline not using OptimizedDocumentPipeline")
            return False
    
    return True

def test_backwards_compatibility():
    """Test backwards compatibility measures."""
    # Check __init__.py aliases DocumentPipeline
    with open("src/thoth/__init__.py", 'r') as f:
        content = f.read()
        if "from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline as DocumentPipeline" not in content:
            issues.append("DocumentPipeline not aliased in __init__.py")
            return False
    
    # Check __main__.py calls cli.main
    with open("src/thoth/__main__.py", 'r') as f:
        content = f.read()
        if "from thoth.cli.main import main" not in content:
            issues.append("__main__.py not importing cli.main")
            return False
    
    return True

def test_import_updates():
    """Test that imports were updated correctly."""
    # Check CLI imports from new app.py
    files_to_check = [
        ("src/thoth/cli/system.py", "thoth.server.app"),
        ("src/thoth/cli/server.py", "thoth.server.app"),
    ]
    
    for filepath, expected_import in files_to_check:
        with open(filepath, 'r') as f:
            content = f.read()
            if expected_import not in content:
                issues.append(f"{filepath} not importing from {expected_import}")
                return False
    
    # Check discovery manager doesn't import ArxivAPISource
    with open("src/thoth/discovery/discovery_manager.py", 'r') as f:
        content = f.read()
        if "ArxivAPISource" in content and "from thoth.discovery.sources import" in content:
            issues.append("discovery_manager.py still importing ArxivAPISource")
            return False
    
    return True

def test_no_todos():
    """Verify no TODO comments remain."""
    # Files we've cleaned up
    cleaned_files = [
        "src/thoth/mcp/server.py",
        "src/thoth/mcp/client.py",
        "src/thoth/mcp/tools/citation_tools.py",
        "src/thoth/mcp/resources.py",
        "src/thoth/mcp/tools/data_management_tools.py",
        "src/thoth/cli/pdf.py",
        "src/thoth/analyze/citations/async_enhancer.py",
        "src/thoth/pipeline.py",
        "src/thoth/mcp/base_tools.py",
    ]
    
    # Skip data_management_tools.py as it's been deleted
    cleaned_files = [f for f in cleaned_files if "data_management_tools.py" not in f]
    
    for filepath in cleaned_files:
        if Path(filepath).exists():
            with open(filepath, 'r') as f:
                content = f.read()
                if "TODO:" in content:
                    # Count occurrences
                    count = content.count("TODO:")
                    issues.append(f"{filepath} still contains {count} TODO comment(s)")
                    return False
    
    return True

def main():
    """Run all structural tests."""
    print("🔍 THOTH STRUCTURAL VERIFICATION")
    print("="*50)
    
    # Run tests
    test_module("Project Structure", test_project_structure)
    test_module("Deleted Files", test_deleted_files)
    test_module("Router Files", test_new_router_files)
    test_module("Discovery Sources", test_discovery_source_files)
    test_module("Memory Components", test_memory_components)
    test_module("Knowledge Components", test_knowledge_components)
    test_module("MCP Tool Structure", test_mcp_tool_structure)
    test_module("Pipeline Changes", test_pipeline_changes)
    test_module("Backwards Compatibility", test_backwards_compatibility)
    test_module("Import Updates", test_import_updates)
    test_module("No TODOs", test_no_todos)
    
    # Summary
    print("\n" + "="*50)
    print("VERIFICATION SUMMARY")
    print("="*50)
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    
    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
    
    if tests_failed == 0:
        print("\n✨ All structural tests passed!")
        return 0
    else:
        print(f"\n⚠️  {tests_failed} test(s) failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    exit(main())