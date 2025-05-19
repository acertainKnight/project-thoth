from pathlib import Path
from typing import Literal, TypedDict

from langchain.schema import Document
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Schema for a single citation.

    Attributes:
        text: The full text of the citation as it appears.
        authors: List of authors (last name, first initial format).
        affiliations: List of affiliations of the authors in the format 'Affiliation of Author1, Affiliation of Author2, ...'.
        title: Title of the paper or book.
        abstract: Abstract of the paper or book.
        year: Publication year.
        journal: Journal or conference name.
        venue: Publication venue (e.g., conference, workshop).
        citation_count: Number of citations for this work.
        doi: Digital Object Identifier.
        backup_id: Alternative identifier (e.g., arXiv ID, ISBN) when DOI is unavailable.
        url: URL if present.
        volume: Journal volume.
        issue: Issue number.
        pages: Page numbers or range.
        obsidian_uri: Obsidian URI.
        is_document_citation: Flag indicating if this is the citation for the document itself.
        formatted: Formatted citation string.
        fields_of_study: List of fields of study for the work
        reference_count: Number of references in the work
        influential_citation_count: Number of influential citations
        is_open_access: Whether the work is open access
        s2_fields_of_study: Semantic Scholar's fields of study classification
    """  # noqa: W505

    text: str | None = Field(
        description='The full text of the citation as it appears', default=None
    )
    authors: list[str] | None = Field(
        description='List of authors (last name, first initial format)', default=None
    )
    affiliations: list[str] | None = Field(
        description='List of affiliations of the authors in the format'
        "'Affiliation of Author1, Affiliation of Author2, ...'",
        default=None,
    )
    title: str | None = Field(description='Title of the paper or book', default=None)
    abstract: str | None = Field(
        description='Abstract of the paper or book', default=None
    )
    year: int | None = Field(description='Publication year', default=None)
    journal: str | None = Field(description='Journal or conference name', default=None)
    venue: str | None = Field(
        description='Publication venue (e.g., conference, workshop)', default=None
    )
    citation_count: int | None = Field(
        description='Number of citations for this work', default=None
    )
    doi: str | None = Field(description='Digital Object Identifier', default=None)
    backup_id: str | None = Field(
        description='Alternative identifier (e.g., arXiv ID, ISBN) when DOI is unavailable',
        default=None,
    )
    url: str | None = Field(description='URL if present', default=None)
    volume: str | None = Field(description='Journal volume', default=None)
    issue: str | None = Field(description='Issue number', default=None)
    pages: str | None = Field(description='Page numbers or range', default=None)
    obsidian_uri: str | None = Field(description='Obsidian URI', default=None)
    is_document_citation: bool = Field(
        description='Flag indicating if this is the citation for the document itself',
        default=False,
    )
    formatted: str | None = Field(description='Formatted citation string', default=None)
    fields_of_study: list[str] | None = Field(
        description='List of fields of study for the work', default=None
    )
    reference_count: int | None = Field(
        description='Number of references in the work', default=None
    )
    influential_citation_count: int | None = Field(
        description='Number of influential citations', default=None
    )
    is_open_access: bool | None = Field(
        description='Whether the work is open access', default=None
    )
    s2_fields_of_study: list[str] | None = Field(
        description="Semantic Scholar's fields of study classification", default=None
    )

    def update_from_opencitation(self, open_citation: 'OpenCitation') -> None:
        """
        Update this Citation with values from an OpenCitation model.

        This method maps fields from the OpenCitation model to this Citation model,
        only updating fields that are None in the current Citation.

        Args:
            open_citation: The OpenCitation model to get values from

        Example:
            >>> citation = Citation(
            ...     text='Example', authors=['Smith, J'], title='Title', year=None
            ... )
            >>> open_citation = OpenCitation(
            ...     id='doi:10.1234/xyz',
            ...     title='Updated Title',
            ...     author='Smith, J.',
            ...     pub_date='2023',
            ... )
            >>> citation.update_from_opencitation(open_citation)
            >>> citation.year
            2023
        """
        # Map fields from OpenCitation to Citation
        field_mapping = {
            'title': 'title',
            'author': 'authors',  # Note: OpenCitation has a single author string, Citation has a list
            'pub_date': 'year',  # Note: OpenCitation has pub_date as string, Citation has year as int
            'venue': 'venue',
            'volume': 'volume',
            'issue': 'issue',
            'page': 'pages',
            'abstract': 'abstract',
            'citation_count': 'citation_count',
        }

        # Update each field if it's None in the current Citation
        for open_field, citation_field in field_mapping.items():
            open_value = getattr(open_citation, open_field)

            # Skip if the OpenCitation field is None or empty
            if open_value is None or open_value == '':
                continue

            # Special handling for different field types
            if open_field == 'author' and open_value:
                # Convert single author string to list format
                if self.authors is None:
                    self.authors = [open_value]
            elif open_field == 'pub_date' and open_value:
                # Try to extract year from pub_date string
                try:
                    # Simple extraction - assumes format like "2023" or "2023-01-01"
                    year_str = open_value.split('-')[0]
                    self.year = int(year_str)
                except (ValueError, IndexError):
                    # If conversion fails, leave year as None
                    pass
            else:
                # For all other fields, only update if current value is None
                current_value = getattr(self, citation_field)
                if current_value is None:
                    setattr(self, citation_field, open_value)

        # Extract alternative ID if DOI is not present in the citation
        if not self.doi and open_citation.id and ':' in open_citation.id:
            id_type, id_value = open_citation.id.split(':', 1)
            if (
                id_type != 'doi' and not self.backup_id
            ):  # Only set backup_id if it's not already set
                self.backup_id = open_citation.id

    def update_from_arxiv(self, arxiv_paper: 'ArxivPaper') -> None:
        """
        Update this Citation with values from an ArxivPaper model.

        This method maps fields from the ArxivPaper model to this Citation model,
        only updating fields that are None in the current Citation.
        """
        field_mapping = {
            'title': 'title',
            'authors': 'authors',
            'published': 'year',
            'journal_ref': 'journal',
            'id': 'backup_id',
            'pdf_url': 'url',
            'doi': 'doi',
            'abstract': 'abstract',
            'venue': 'venue',
            'citation_count': 'citation_count',
        }

        # Update each field if it's None in the current Citation
        for arxiv_field, citation_field in field_mapping.items():
            arxiv_value = getattr(arxiv_paper, arxiv_field)
            if arxiv_value is not None:
                setattr(self, citation_field, arxiv_value)

    @classmethod
    def from_citation_extraction(
        cls, citation_extraction: 'CitationExtraction'
    ) -> 'Citation':
        """
        Create a new Citation instance from a CitationExtraction model.

        This method maps fields from the CitationExtraction model to create a new
        Citation object.

        Args:
            citation_extraction: The CitationExtraction model containing the data.

        Returns:
            Citation: A new Citation instance populated with data from citation_extraction.

        Example:
            >>> citation_extraction = CitationExtraction(
            ...     text='Example citation text.',
            ...     authors=['Smith, J.'],
            ...     title='Example Title',
            ...     year=2023,
            ...     doi='10.1234/example',
            ... )
            >>> citation = Citation.from_citation_extraction(citation_extraction)
            >>> print(citation.title)
            Example Title
            >>> print(citation.year)
            2023
        """  # noqa: W505
        # Map fields directly, Pydantic handles None values correctly during initialization  # noqa: W505
        citation_data = {
            'text': citation_extraction.text,
            'authors': (
                citation_extraction.authors.split(';')
                if citation_extraction.authors
                else None
            ),
            'affiliations': (
                citation_extraction.affiliations.split(';')
                if citation_extraction.affiliations
                else None
            ),
            'title': citation_extraction.title,
            'year': citation_extraction.year,
            'journal': citation_extraction.journal,
            'doi': citation_extraction.doi,
            'backup_id': citation_extraction.backup_id,
            'url': citation_extraction.url,
            'volume': citation_extraction.volume,
            'issue': citation_extraction.issue,
            'pages': citation_extraction.pages,
        }

        filtered_data = {k: v for k, v in citation_data.items() if v is not None}

        return cls(**filtered_data)


class CitationExtraction(BaseModel):
    """Schema for a single citation extraction.

    Args:
        text: The full text of the citation as it appears
        authors: List of authors (last name, first initial format)
        title: Title of the paper or book
        year: Publication year
        journal: Journal or conference name
        doi: Digital Object Identifier
        backup_id: Alternative identifier (e.g., arXiv ID, ISBN) when DOI is unavailable
        url: URL if present
        volume: Journal volume
        issue: Issue number
        pages: Page numbers or range
    """

    text: str | None = Field(
        description='The full text of the citation as it appears', default=None
    )
    authors: str | None = Field(
        description='List of authors separated by a semicolon (last name, first name)',
        default=None,
    )
    affiliations: str | None = Field(
        description='List of affiliations of the authors separated by a semicolon (Affiliation of Author1; Affiliation of Author2; ...)',
        default=None,
    )
    title: str | None = Field(description='Title of the paper or book', default=None)
    year: int | None = Field(description='Publication year', default=None)
    journal: str | None = Field(description='Journal or conference name', default=None)
    doi: str | None = Field(description='Digital Object Identifier', default=None)
    backup_id: str | None = Field(
        description='Alternative identifier (e.g., arXiv ID, ISBN) when DOI is unavailable',
        default=None,
    )
    url: str | None = Field(description='URL if present', default=None)
    volume: str | None = Field(description='Journal volume', default=None)
    issue: str | None = Field(description='Issue number', default=None)
    pages: str | None = Field(description='Page numbers or range', default=None)


class ReferencesSection(BaseModel):
    """Schema for the references section identification response.

    Args:
        heading: The heading of the references section if found

    Example:
        >>> references_section = ReferencesSection(heading='References')
        >>> print(references_section.heading)
        References
    """

    heading: str | None = Field(
        description='The heading of the references section if found', default=None
    )


class CitationExtractionResponse(BaseModel):
    """Schema for the citation extraction response.

    Args:
        citations: List of extracted citations from the references section in the format of CitationExtraction
    """  # noqa: W505

    citations: list[CitationExtraction] = Field(
        description='List of extracted citations from the references section'
    )


class OpenCitation(BaseModel):
    """Schema for a single citation from OpenCitations API."""

    id: str = Field(
        description='Identifier string containing DOI, ISBN, OpenAlex ID, etc.'
    )
    title: str = Field(description='Title of the publication')
    author: str | None = Field(description='Author information', default='')
    pub_date: str | None = Field(description='Publication date', default='')
    issue: str | None = Field(description='Issue number', default='')
    volume: str | None = Field(description='Volume number', default='')
    venue: str | None = Field(description='Publication venue', default='')
    type: str | None = Field(
        description='Publication type (e.g., book, article)', default=''
    )
    page: str | None = Field(description='Page information', default='')
    publisher: str | None = Field(description='Publisher information', default='')
    editor: str | None = Field(description='Editor information', default='')


class OpenCitationsResponse(BaseModel):
    """Schema for the OpenCitations API response."""

    citations: list[OpenCitation] = Field(description='List of OpenCitation citations')


class SearchResult(BaseModel):
    """Schema for a single search result from Google Search API."""

    title: str = Field(description='Title of the search result')
    link: str = Field(description='URL of the search result')
    snippet: str = Field(description='Text snippet from the search result')
    position: int = Field(description='Position in search results')


class SearchResponse(BaseModel):
    """Schema for the Google Search API response."""

    results: list[SearchResult] = Field(description='List of search results')


class AnalysisResponse(BaseModel):
    """Extracts information from the Research Paper and formats it in a clean parsed
    format. No other information is needed.

    Args:
        title: Title of the document if available
        authors: List of authors of the content
        affiliations: List of affiliations of the authors in the format
                      'Affiliation of Author1, Affiliation of Author2, ...'
        abstract: A concise abstract of the content
        key_points: Key points extracted from the content
        summary: A concise summary of the content
        methodology: The methodology used to collect the data
        results: The results of the analysis
        limitations: Limitations of the study
        related_work: Related work to the content
    """

    title: str | None = Field(
        description='Title of the document if available', default=None
    )
    authors: str | None = Field(
        description='List of authors of the content', default=None
    )
    affiliations: str | None = Field(
        description='List of affiliations of the authors in the format'
        "'Affiliation of Author1, Affiliation of Author2, ...'",
        default=None,
    )
    abstract: str | None = Field(
        description='A concise abstract of the content', default=None
    )
    key_points: str | None = Field(
        description='Key points extracted from the content', default=None
    )
    summary: str | None = Field(
        description='A concise summary of the content', default=None
    )
    objectives: str | None = Field(
        description='Primary objectives or research questions addressed', default=None
    )
    methodology: str | None = Field(
        description='Detailed description of the methods and study design', default=None
    )
    data: str | None = Field(
        description='Datasets or data sources used, including size and key characteristics',
        default=None,
    )
    experimental_setup: str | None = Field(
        description='Experimental or analytical setup, including controls and variables',
        default=None,
    )
    evaluation_metrics: str | None = Field(
        description='Metrics used to evaluate performance or results', default=None
    )
    results: str | None = Field(
        description='Key quantitative or qualitative results', default=None
    )
    discussion: str | None = Field(
        description='Interpretation of the results and their implications', default=None
    )
    novelty: str | None = Field(
        description='What is novel about this work compared with prior art',
        default=None,
    )
    significance: str | None = Field(
        description='Why the findings matter for the field', default=None
    )
    strengths: str | None = Field(
        description='Strengths and positive aspects of the study', default=None
    )
    weaknesses: str | None = Field(
        description='Weaknesses, shortcomings, or areas of concern', default=None
    )
    limitations: str | None = Field(
        description='Explicitly stated or inferred limitations of the study',
        default=None,
    )
    ethical_considerations: str | None = Field(
        description='Ethical or societal considerations discussed or implied',
        default=None,
    )
    future_work: str | None = Field(
        description='Suggested future work or open questions', default=None
    )
    related_work: str | None = Field(
        description='Key related works and how this paper differs', default=None
    )
    references_count: int | None = Field(
        description='Number of references cited', default=None
    )


# Define the state for the LangGraph
class AnalysisState(TypedDict):
    """Represents the state of the analysis process."""

    markdown_path: Path | None  # Added: Path to the markdown file
    original_content: str | None  # Changed: Content loaded from the file
    content_chunks: list[Document] | None
    strategy: Literal['direct', 'map_reduce', 'refine'] | None  # Allow None initially
    chunk_analyses: list[AnalysisResponse] | None  # For map_reduce
    current_analysis: AnalysisResponse | None  # For refine
    final_analysis: AnalysisResponse | None


class ArxivPaper(BaseModel):
    """Schema for an arXiv paper."""

    id: str = Field(description='arXiv ID')
    title: str = Field(description='Title of the paper')
    authors: list[str] = Field(description='List of authors')
    abstract: str = Field(description='Abstract of the paper')
    categories: list[str] = Field(description='arXiv categories')
    pdf_url: str | None = Field(description='URL to the PDF', default=None)
    published: str | None = Field(description='Publication date', default=None)
    updated: str | None = Field(description='Last update date', default=None)
    comment: str | None = Field(description='Author comment', default=None)
    journal_ref: str | None = Field(description='Journal reference', default=None)
    doi: str | None = Field(description='Digital Object Identifier', default=None)
    citation_count: int | None = Field(description='Number of citations', default=None)
