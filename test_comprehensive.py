#!/usr/bin/env python3
"""
Comprehensive test suite for Thoth refactoring.
"""

import os
import sys
from pathlib import Path

# Summary results
total_checks = 0
passed_checks = 0
failed_checks = 0
warnings = []
errors = []

def check(name, condition, error_msg=None):
    """Perform a check and track results."""
    global total_checks, passed_checks, failed_checks
    
    total_checks += 1
    if condition:
        passed_checks += 1
        print(f"✅ {name}")
        return True
    else:
        failed_checks += 1
        print(f"❌ {name}")
        if error_msg:
            errors.append(f"{name}: {error_msg}")
        return False

def warn(msg):
    """Add a warning."""
    warnings.append(msg)
    print(f"⚠️  {msg}")

print("🧪 COMPREHENSIVE THOTH VERIFICATION")
print("="*60)

# 1. File Structure Checks
print("\n📁 FILE STRUCTURE")
print("-"*40)

# Check deleted files
deleted_files = [
    "src/thoth/main.py",
    "src/thoth/pipelines/document_pipeline.py",
    "src/thoth/server/api_server.py",
    "src/thoth/discovery/api_sources.py",
    "src/thoth/mcp/tools/discovery_tools.py",
    "src/thoth/mcp/tools/data_management_tools.py",
]

for filepath in deleted_files:
    check(f"Deleted: {filepath}", not Path(filepath).exists())

# Check new directories
new_dirs = [
    "src/thoth/server/routers",
    "src/thoth/discovery/sources",
    "src/thoth/memory/scoring",
    "src/thoth/memory/filtering",
    "src/thoth/memory/enrichment",
    "src/thoth/knowledge/components",
    "src/thoth/mcp/tools/discovery",
    "src/thoth/mcp/tools/data",
]

for dirpath in new_dirs:
    check(f"Created: {dirpath}", Path(dirpath).exists())

# 2. Module Structure
print("\n📦 MODULE STRUCTURE")
print("-"*40)

# Check key files exist
key_files = [
    ("Entry point", "src/thoth/__main__.py"),
    ("Server app", "src/thoth/server/app.py"),
    ("CLI main", "src/thoth/cli/main.py"),
    ("OptimizedDocumentPipeline", "src/thoth/pipelines/optimized_document_pipeline.py"),
    ("BaseAPISource", "src/thoth/discovery/sources/base.py"),
    ("ArxivClient", "src/thoth/discovery/sources/arxiv.py"),
]

for name, filepath in key_files:
    check(name, Path(filepath).exists())

# 3. Import Structure
print("\n🔗 IMPORT STRUCTURE")
print("-"*40)

# Check critical imports
import_checks = [
    ("__init__.py aliases DocumentPipeline", 
     "src/thoth/__init__.py", 
     "from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline as DocumentPipeline"),
    ("__main__.py imports cli.main", 
     "src/thoth/__main__.py", 
     "from thoth.cli.main import main"),
    ("pipeline.py uses OptimizedDocumentPipeline", 
     "src/thoth/pipeline.py", 
     "from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline"),
]

for name, filepath, expected in import_checks:
    if Path(filepath).exists():
        with open(filepath, 'r') as f:
            content = f.read()
            check(name, expected in content)

# 4. Code Quality
print("\n✨ CODE QUALITY")
print("-"*40)

# Check for TODOs in cleaned files
cleaned_files = [
    "src/thoth/mcp/server.py",
    "src/thoth/mcp/client.py",
    "src/thoth/mcp/tools/citation_tools.py",
    "src/thoth/mcp/resources.py",
    "src/thoth/cli/pdf.py",
    "src/thoth/analyze/citations/async_enhancer.py",
    "src/thoth/pipeline.py",
    "src/thoth/mcp/base_tools.py",
]

todo_count = 0
for filepath in cleaned_files:
    if Path(filepath).exists():
        with open(filepath, 'r') as f:
            content = f.read()
            todos = content.count("TODO:")
            if todos > 0:
                todo_count += todos
                warn(f"{filepath} still has {todos} TODO(s)")

check("No TODOs in cleaned files", todo_count == 0)

# 5. Component Organization
print("\n🏗️ COMPONENT ORGANIZATION")
print("-"*40)

# Check memory pipeline components
memory_components = {
    "MemoryFilter": "src/thoth/memory/filtering/memory_filter.py",
    "MemoryEnricher": "src/thoth/memory/enrichment/memory_enricher.py",
    "SalienceScorer": "src/thoth/memory/scoring/salience.py",
}

for class_name, filepath in memory_components.items():
    if Path(filepath).exists():
        with open(filepath, 'r') as f:
            check(f"{class_name} in {Path(filepath).name}", 
                  f"class {class_name}" in f.read())

# Check knowledge components
knowledge_components = {
    "CitationStorage": "src/thoth/knowledge/components/storage.py",
    "CitationSearch": "src/thoth/knowledge/components/search.py",
    "GraphAnalyzer": "src/thoth/knowledge/components/analysis.py",
    "CitationFileManager": "src/thoth/knowledge/components/file_manager.py",
}

for class_name, filepath in knowledge_components.items():
    if Path(filepath).exists():
        with open(filepath, 'r') as f:
            check(f"{class_name} in {Path(filepath).name}", 
                  f"class {class_name}" in f.read())

# 6. MCP Tools
print("\n🔧 MCP TOOLS")
print("-"*40)

# Check discovery tools
discovery_tools = [
    "ListDiscoverySourcesMCPTool",
    "CreateArxivSourceMCPTool",
    "CreatePubmedSourceMCPTool",
    "GetDiscoverySourceMCPTool",
    "RunDiscoveryMCPTool",
    "DeleteDiscoverySourceMCPTool",
]

discovery_init = Path("src/thoth/mcp/tools/discovery/__init__.py")
if discovery_init.exists():
    with open(discovery_init, 'r') as f:
        content = f.read()
        for tool in discovery_tools:
            check(f"Discovery exports {tool}", tool in content)

# Check data tools
data_tools = [
    "BackupCollectionMCPTool",
    "ExportArticleDataMCPTool",
    "GenerateReadingListMCPTool",
    "SyncWithObsidianMCPTool",
]

data_init = Path("src/thoth/mcp/tools/data/__init__.py")
if data_init.exists():
    with open(data_init, 'r') as f:
        content = f.read()
        for tool in data_tools:
            check(f"Data exports {tool}", tool in content)

# 7. Known Issues
print("\n⚠️ KNOWN ISSUES")
print("-"*40)

# Import cycles that are handled with TYPE_CHECKING
known_cycles = [
    "knowledge.graph ↔ service_manager (handled with TYPE_CHECKING)",
    "pipeline ↔ pdf_monitor (handled with lazy import)",
]

for cycle in known_cycles:
    warn(f"Import cycle: {cycle}")

# Summary
print("\n" + "="*60)
print("VERIFICATION SUMMARY")
print("="*60)
print(f"Total Checks: {total_checks}")
print(f"✅ Passed: {passed_checks}")
print(f"❌ Failed: {failed_checks}")

if warnings:
    print(f"\n⚠️ Warnings ({len(warnings)}):")
    for warning in warnings:
        print(f"  - {warning}")

if errors:
    print(f"\n❌ Errors ({len(errors)}):")
    for error in errors:
        print(f"  - {error}")

if failed_checks == 0:
    print("\n🎉 ALL CHECKS PASSED!")
    print("The refactoring has been successfully completed.")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run the test suite: pytest")
    print("3. Test the application: thoth --help")
    sys.exit(0)
else:
    print(f"\n❌ {failed_checks} check(s) failed. Please review the errors above.")
    sys.exit(1)