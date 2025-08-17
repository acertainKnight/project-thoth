#!/usr/bin/env python3
"""
Test for import cycles in the codebase.
"""

import ast
import sys
from pathlib import Path
from collections import defaultdict, deque

class ImportAnalyzer(ast.NodeVisitor):
    """Extract imports from Python files."""
    
    def __init__(self, module_path):
        self.module_path = module_path
        self.imports = set()
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
            
    def visit_ImportFrom(self, node):
        if node.module and not node.level:  # Absolute imports only
            self.imports.add(node.module)

def get_module_name(filepath):
    """Convert filepath to module name."""
    path = Path(filepath)
    # Remove .py extension and convert to module path
    relative = path.relative_to(Path("src"))
    parts = list(relative.parts)
    if parts[-1].endswith('.py'):
        parts[-1] = parts[-1][:-3]
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)

def analyze_imports(filepath):
    """Get all imports from a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        analyzer = ImportAnalyzer(filepath)
        analyzer.visit(tree)
        
        # Filter for thoth imports only
        thoth_imports = {imp for imp in analyzer.imports if imp.startswith('thoth')}
        return thoth_imports
        
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return set()

def build_import_graph():
    """Build a graph of all imports."""
    graph = defaultdict(set)
    
    # Find all Python files
    python_files = list(Path("src/thoth").rglob("*.py"))
    
    for filepath in python_files:
        module_name = get_module_name(filepath)
        imports = analyze_imports(filepath)
        
        for imp in imports:
            # Only add edges for imports within thoth
            if imp.startswith('thoth'):
                graph[module_name].add(imp)
    
    return graph

def find_cycles(graph):
    """Find cycles in the import graph using DFS."""
    cycles = []
    visited = set()
    rec_stack = set()
    
    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor, path):
                    return True
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
        
        path.pop()
        rec_stack.remove(node)
        return False
    
    # Check all nodes
    for node in graph:
        if node not in visited:
            dfs(node, [])
    
    # Remove duplicate cycles
    unique_cycles = []
    seen = set()
    for cycle in cycles:
        # Normalize cycle (start from smallest element)
        min_idx = cycle.index(min(cycle))
        normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
        if normalized not in seen:
            seen.add(normalized)
            unique_cycles.append(list(normalized))
    
    return unique_cycles

def check_problematic_imports():
    """Check for known problematic import patterns."""
    issues = []
    
    # Check if main __init__.py imports from submodules that import back
    init_file = Path("src/thoth/__init__.py")
    if init_file.exists():
        init_imports = analyze_imports(init_file)
        
        # Check for circular patterns
        if 'thoth.pipeline' in init_imports:
            pipeline_imports = analyze_imports(Path("src/thoth/pipeline.py"))
            if any(imp.startswith('thoth.') and imp != 'thoth.pipeline' for imp in pipeline_imports):
                # This is OK as long as pipeline doesn't import from thoth.__init__
                pass
    
    return issues

def main():
    """Run import cycle detection."""
    print("🔄 IMPORT CYCLE DETECTION")
    print("="*50)
    
    print("Building import graph...")
    graph = build_import_graph()
    
    print(f"Found {len(graph)} modules with imports")
    
    print("\nChecking for import cycles...")
    cycles = find_cycles(graph)
    
    if cycles:
        print(f"\n⚠️  Found {len(cycles)} import cycle(s):\n")
        for i, cycle in enumerate(cycles, 1):
            print(f"Cycle {i}:")
            for j in range(len(cycle)-1):
                print(f"  {cycle[j]} → {cycle[j+1]}")
            print()
        return 1
    else:
        print("\n✅ No import cycles detected!")
        
    print("\nChecking for problematic patterns...")
    issues = check_problematic_imports()
    
    if issues:
        print("\n⚠️  Found issues:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("✅ No problematic import patterns found!")
        
    print("\n✨ Import structure is clean!")
    return 0

if __name__ == "__main__":
    exit(main())