"""
Citation analysis and extraction.

This module provides tools for extracting, analyzing, and tracking academic citations.
It integrates with tools like OpenCitations for metadata lookup and Scholarly for
searching Google Scholar without requiring API keys.
"""

# Import these last to avoid circular imports
from thoth.analyze.citations.citations import CitationProcessor
from thoth.analyze.citations.scholarly import ScholarlyAPI
from thoth.utilities.schemas import Citation

__all__ = ['Citation', 'CitationProcessor', 'ScholarlyAPI']
