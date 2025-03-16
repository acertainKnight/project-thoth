"""
Main entry point for the Thoth package.

This module allows running Thoth as a module with `python -m thoth`.
"""

import os
import sys

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import main

if __name__ == "__main__":
    main()
