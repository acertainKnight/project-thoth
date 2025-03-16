"""
Citation Extractor for Thoth.

This module handles the extraction of citations from paper content using LLM.
"""

import logging
import re

from thoth.citation.citation import Citation
from thoth.core.llm_processor import LLMError, LLMProcessor

logger = logging.getLogger(__name__)


class CitationExtractionError(Exception):
    """Exception raised for errors in the citation extraction process."""

    pass


class CitationExtractor:
    """
    Extracts citations from paper content using LLM.

    This class is responsible for identifying and extracting citations from
    academic papers, using a combination of pattern matching and LLM-based
    extraction for more complex cases.
    """

    def __init__(self, llm_processor: LLMProcessor):
        """
        Initialize the CitationExtractor.

        Args:
            llm_processor: LLM processor for content analysis.
        """
        self.llm_processor = llm_processor

    def extract_citations(self, content: str) -> list[Citation]:
        """
        Extract citations from paper content using LLM.

        Args:
            content: The content to extract citations from.

        Returns:
            list[Citation]: A list of Citation objects.

        Raises:
            CitationExtractionError: If the extraction fails.

        Example:
            >>> extractor = CitationExtractor(llm_processor)
            >>> citations = extractor.extract_citations(paper_content)
            >>> len(citations)
            5
        """
        try:
            # First try to extract references section
            references_section = self._extract_references_section(content)
            if not references_section:
                logger.warning("No references section found in content")
                return []

            # Extract citations using LLM
            citation_dicts = self.llm_processor.extract_citations(content)

            # Convert to Citation objects
            citations = []
            for citation_dict in citation_dicts:
                try:
                    citation = Citation.from_dict(citation_dict)
                    citations.append(citation)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to create Citation object: {e}")
                    continue

            logger.info(f"Successfully extracted {len(citations)} citations")
            return citations

        except LLMError as e:
            # Fall back to regex-based extraction if LLM fails
            logger.warning(f"LLM extraction failed, falling back to regex: {e}")
            return self._extract_citations_with_regex(content)
        except Exception as e:
            error_msg = f"Citation extraction failed: {e}"
            logger.error(error_msg)
            raise CitationExtractionError(error_msg) from e

    def _extract_references_section(self, content: str) -> str | None:
        """
        Extract the references section from the content.

        Args:
            content: The content to extract the references section from.

        Returns:
            Optional[str]: The references section, or None if not found.
        """
        # Look for references section
        references_match = re.search(
            r"##\s+References\s*\n\n(.*?)(?=\n\n##|\Z)", content, re.DOTALL
        )
        if not references_match:
            # Try alternative headings
            references_match = re.search(
                r"##\s+(?:Bibliography|Citations|Works Cited)\s*\n\n(.*?)(?=\n\n##|\Z)",
                content,
                re.DOTALL,
            )
            if not references_match:
                return None

        return references_match.group(1)

    def _extract_citations_with_regex(self, content: str) -> list[Citation]:
        """
        Extract citations using regex patterns as a fallback method.

        Args:
            content: The content to extract citations from.

        Returns:
            list[Citation]: A list of Citation objects.
        """
        citations = []
        references_section = self._extract_references_section(content)
        if not references_section:
            return citations

        # Extract individual references
        citation_matches = re.finditer(
            r"\[([\d]+)\]\s+(.+?)(?=\n\[[\d]|\Z)", references_section, re.DOTALL
        )

        for match in citation_matches:
            ref_id = match.group(1)
            citation_text = match.group(2).strip()

            # Basic parsing of citation text
            # This is a simplified approach and won't work for all citation formats
            authors = []
            title = ""
            year = None
            journal = ""

            # Try to extract authors (assuming they come first)
            author_match = re.search(r"^([\w\s.,]+?),", citation_text)
            if author_match:
                author_text = author_match.group(1).strip()
                # Split multiple authors
                authors = [a.strip() for a in author_text.split(",") if a.strip()]

            # Try to extract year
            year_match = re.search(r"\((\d{4})\)", citation_text)
            if year_match:
                try:
                    year = int(year_match.group(1))
                except ValueError:
                    pass

            # Try to extract title (assuming it's in quotes)
            title_match = re.search(r'"([^"]+)"', citation_text)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # If no quoted title, make a best guess
                title = (
                    citation_text[:50] + "..."
                    if len(citation_text) > 50
                    else citation_text
                )

            # Try to extract journal
            journal_match = re.search(
                r'(?:in|,)\s+([\w\s]+Journal|Conference|Proceedings)[\s,]',
                citation_text,
            )
            if journal_match:
                journal = journal_match.group(1).strip()

            # Create Citation object with extracted information
            if title and authors:
                citations.append(
                    Citation(
                        title=title,
                        authors=authors,
                        year=year,
                        journal=journal,
                        context=f"Reference [{ref_id}]",
                    )
                )

        logger.info(f"Extracted {len(citations)} citations with regex")
        return citations

    def find_citation_contexts(
        self, content: str, citations: list[Citation]
    ) -> list[Citation]:
        """
        Find the context in which each citation appears in the content.

        Args:
            content: The content to search for citation contexts.
            citations: The list of citations to find contexts for.

        Returns:
            list[Citation]: The citations with updated context information.

        Example:
            >>> extractor = CitationExtractor(llm_processor)
            >>> citations = extractor.extract_citations(paper_content)
            >>> citations_with_context = extractor.find_citation_contexts(
            ...     paper_content, citations
            ... )
        """
        # Create a copy of the citations to avoid modifying the originals
        citations_with_context = [Citation(**c.to_dict()) for c in citations]

        # Look for citation references in the text
        for i, citation in enumerate(citations_with_context):
            # Try to find the citation by author and year
            if citation.authors and citation.year:
                author_last_name = citation.authors[0].split()[-1]
                pattern = rf"({author_last_name}.*?{citation.year})"
                matches = re.finditer(pattern, content, re.IGNORECASE)

                for match in matches:
                    # Get surrounding context (100 chars before and after)
                    start = max(0, match.start() - 100)
                    end = min(len(content), match.end() + 100)
                    context = content[start:end].strip()

                    # Update citation context
                    citations_with_context[i].context = context
                    break  # Just use the first match for now

        return citations_with_context


def extract_citations(content: str, llm_processor: LLMProcessor) -> list[Citation]:
    """
    Extract citations from paper content using LLM.

    This is a convenience function that creates a CitationExtractor and uses it
    to extract citations from the given content.

    Args:
        content: The content to extract citations from.
        llm_processor: LLM processor for content analysis.

    Returns:
        list[Citation]: A list of Citation objects.

    Raises:
        CitationExtractionError: If the extraction fails.

    Example:
        >>> citations = extract_citations(paper_content, llm_processor)
        >>> len(citations)
        5
    """
    extractor = CitationExtractor(llm_processor)
    return extractor.extract_citations(content)
