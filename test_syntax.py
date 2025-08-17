#!/usr/bin/env python3
"""
Syntax validation for all Python files in the project.
"""

import ast
import py_compile
import tempfile
from pathlib import Path

errors = []
files_checked = 0
files_with_errors = 0

def check_file_syntax(filepath):
    """Check if a Python file has valid syntax."""
    global files_checked, files_with_errors
    
    files_checked += 1
    
    try:
        # First try to parse with ast
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        ast.parse(content)
        
        # Then try to compile
        with tempfile.NamedTemporaryFile(suffix='.pyc', delete=True) as tmp:
            py_compile.compile(str(filepath), cfile=tmp.name, doraise=True)
        
        return True
        
    except SyntaxError as e:
        files_with_errors += 1
        errors.append(f"{filepath}:{e.lineno}: SyntaxError: {e.msg}")
        return False
    except Exception as e:
        files_with_errors += 1
        errors.append(f"{filepath}: {type(e).__name__}: {str(e)}")
        return False

def find_python_files(root_dir):
    """Find all Python files in the project."""
    root = Path(root_dir)
    return list(root.rglob("*.py"))

def main():
    """Check syntax of all Python files."""
    print("🐍 PYTHON SYNTAX VALIDATION")
    print("="*50)
    
    # Find all Python files
    python_files = find_python_files("src/thoth")
    print(f"Found {len(python_files)} Python files to check\n")
    
    # Check each file
    for filepath in sorted(python_files):
        try:
            relative_path = filepath.relative_to(Path.cwd())
        except ValueError:
            relative_path = filepath
        if check_file_syntax(filepath):
            print(f"✅ {relative_path}")
        else:
            print(f"❌ {relative_path}")
    
    # Summary
    print("\n" + "="*50)
    print("SYNTAX VALIDATION SUMMARY")
    print("="*50)
    print(f"Files checked: {files_checked}")
    print(f"Files with errors: {files_with_errors}")
    
    if errors:
        print("\nERRORS FOUND:")
        for error in errors:
            print(f"  {error}")
        return 1
    else:
        print("\n✨ All Python files have valid syntax!")
        return 0

if __name__ == "__main__":
    exit(main())