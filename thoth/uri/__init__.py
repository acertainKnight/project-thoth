"""
URI module for Thoth.

This module handles custom URIs for citations in Obsidian.
"""

from thoth.uri.generator import URIGenerator, generate_markdown_link, generate_uri
from thoth.uri.handler import URIHandler, process_uri

__all__ = [
    "URIGenerator",
    "URIHandler",
    "generate_markdown_link",
    "generate_uri",
    "process_uri",
]
