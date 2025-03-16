#!/usr/bin/env python3
"""
Thoth AI Research Agent - Main entry point
"""
import logging
from pathlib import Path

from thoth.config import load_config
from thoth.utils.logging import setup_logging


def main():
    """Main entry point for Thoth."""
    # Load configuration
    config = load_config()

    # Set up logging
    setup_logging(config.log_level, config.log_file)
    logger = logging.getLogger(__name__)

    logger.info(f"Thoth started. Monitoring {config.pdf_dir} for new PDFs.")

    # TODO: Initialize components and start monitoring


if __name__ == "__main__":
    main()
