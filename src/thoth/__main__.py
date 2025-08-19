#!/usr/bin/env python3
"""
Main entry point for Thoth.

This module serves as the package entry point, allowing the application
to be run with 'python -m thoth'.
"""

import sys

from thoth.cli.main import main

if __name__ == '__main__':
    sys.exit(main())
