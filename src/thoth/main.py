#!/usr/bin/env python3
"""
Main entry point for Thoth.

This module provides a command-line interface for running the Thoth system
by calling the refactored CLI implementation.
"""

import sys

from thoth.cli.main import main

if __name__ == '__main__':
    sys.exit(main())
