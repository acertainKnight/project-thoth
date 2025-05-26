from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain.schema import Document
from pydantic import BaseModel, Field, field_validator


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
    """
    Extracts and stores structured information from a research paper for downstream analysis and note generation.

    This model is designed to capture all relevant metadata, content summaries, and analytical details from a research paper. Fields are optional to allow for partial extraction and flexible downstream use. The model is intended to be updated as new analytical requirements arise; any new fields added will automatically propagate to note generation and other consumers.

    Args:
        abstract (str | None): The abstract of the content as it appears in the document.
        key_points (str | None): 10-15 key points extracted from the content, as a newline-separated string.
        summary (str | None): A multi-paragraph summary of the content.
        objectives (str | None): Primary objectives or research questions addressed.
        methodology (str | None): Detailed description of the methods and study design, including model architecture if applicable.
        data (str | None): Datasets or data sources used, including size and key characteristics.
        experimental_setup (str | None): Experimental or analytical setup, including controls and variables.
        evaluation_metrics (str | None): Metrics used to evaluate performance or results.
        results (str | None): Key quantitative or qualitative results.
        discussion (str | None): Interpretation of the results and their implications.
        strengths (str | None): Strengths and positive aspects of the study.
        weaknesses (str | None): Weaknesses, shortcomings, or areas of concern.
        limitations (str | None): Explicitly stated or inferred limitations of the study.
        future_work (str | None): Suggested future work or open questions.
        related_work (str | None): Key related works and how this paper differs.
        tags (list[str] | None): List of tags or keywords associated with the article.

    Returns:
        AnalysisResponse: An instance containing all extracted and structured analysis fields for a research paper.

    Example:
        >>> analysis = AnalysisResponse(
        ...     abstract='This paper explores...',
        ...     key_points='- Point one\n- Point two',
        ...     summary='A comprehensive summary...',
        ...     objectives='To investigate...',
        ...     methodology='We used a randomized control trial...',
        ...     data='Dataset X, 10,000 samples',
        ...     tags=['machine learning', 'NLP'],
        ... )
    """  # noqa: W505

    abstract: str | None = Field(
        description='The abstract of the content as it appears in the document',
        default=None,
    )
    key_points: str | None = Field(
        description='10 - 15 key points extracted from the content. This should serve as a quick overview of the content. '
        'These should be bullet points that are easy to read and understand, but do not include the punctuation marks for the bullet points.'
        'These should be the most important points of the content.',
        default=None,
    )
    summary: str | None = Field(
        description='A summary of the content. This should be a multi-paragraph summary of the content.'
        'This should be a summary of the content that is easy to read and understand.',
        default=None,
    )
    objectives: str | None = Field(
        description='Primary objectives or research questions addressed', default=None
    )
    methodology: str | None = Field(
        description='Detailed description of the methods and study design. '
        'Include the model design architecture if applicable. '
        'This should be an extremely detailed description of the study design.',
        default=None,
    )
    data: str | None = Field(
        description='Datasets or data sources used, including size and key characteristics',
        default=None,
    )
    experimental_setup: str | None = Field(
        description='Experimental or analytical setup, including controls and variables. '
        'This should be a detailed description of the experimental or analytical setup of the study.',
        default=None,
    )
    evaluation_metrics: str | None = Field(
        description='Metrics used to evaluate performance or results. '
        'This should be a summary of the metrics used to evaluate the performance of the study.',
        default=None,
    )
    results: str | None = Field(
        description='Key quantitative or qualitative results. '
        'This should be a summary of the results of the study.',
        default=None,
    )
    discussion: str | None = Field(
        description='Interpretation of the results and their implications. '
        'What does this article contribute to the field? '
        'What advancements does it bring? '
        'How can this be applied in other domains?',
        default=None,
    )
    strengths: str | None = Field(
        description='Strengths and positive aspects of the study, including the model architecture, data, and methodology',
        default=None,
    )
    limitations: str | None = Field(
        description='Explicitly stated or inferred limitations, weaknesses, shortcomings, or areas of concern',
        default=None,
    )
    future_work: str | None = Field(
        description='Suggested future work or open questions', default=None
    )
    related_work: str | None = Field(
        description='Key related works and how this paper differs', default=None
    )
    tags: list[str] | None = Field(
        description=(
            'List of clear, simple, and consistent tags or keywords for the article. '
            'Tags should use common, identifiable words so that different reviewers '
            'are likely to assign the same tags to related articles, ensuring uniform '
            'organization and easy discovery across a larger collection.'
        ),
        default=None,
    )

    @field_validator('tags')
    def normalize_tags(cls, tags: list[str] | None) -> list[str] | None:  # noqa: N805
        """Normalize tags by lowercasing, removing punctuation, and replacing spaces with underscores.

        Args:
            tags (list[str] | None): List of tags to normalize.

        Returns:
            list[str] | None: Normalized tags with leading '#' or None if input is None.
        """  # noqa: W505
        if tags is None:
            return None
        normalized: list[str] = []
        for tag in tags:
            core = tag[1:] if tag.startswith('#') else tag
            core = core.lower().replace(' ', '_')
            # Remove all characters except alphanumeric and underscore
            core = ''.join(char for char in core if char.isalnum() or char == '_')
            normalized.append(f'#{core}')
        return normalized


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


class TagConsolidationResponse(BaseModel):
    """Schema for tag consolidation response from LLM.

    This model represents the response from the LLM when consolidating similar
    tags across the citation graph to create a unified tagging system.

    Args:
        tag_mappings: Dictionary mapping old tags to their canonical equivalents
        consolidated_tags: List of all unique canonical tags after consolidation
        reasoning: Dictionary explaining the reasoning for each canonical tag choice

    Example:
        >>> response = TagConsolidationResponse(
        ...     tag_mappings={
        ...         '#ml': '#machine_learning',
        ...         '#ai': '#artificial_intelligence',
        ...     },
        ...     consolidated_tags=['#machine_learning', '#artificial_intelligence'],
        ...     reasoning={
        ...         '#machine_learning': 'Chose as canonical over abbreviation #ml'
        ...     },
        ... )
    """

    tag_mappings: dict[str, str] = Field(
        description='Dictionary mapping ALL input tags to their canonical equivalents (including tags that map to themselves)',
        default_factory=dict,
    )
    consolidated_tags: list[str] = Field(
        description='List of all unique canonical tags after consolidation'
    )
    reasoning: str = Field(
        description='Text explaining the reasoning for each canonical tag choice and new tag suggestions',
        default='',
    )


class ConsolidatedTagsResponse(BaseModel):
    """Schema for getting the consolidated list of canonical tags (first step).

    This model represents the response from the LLM when identifying which tags
    should be the canonical tags after consolidation, without worrying about mappings.
    Also includes suggestions for new category-level and aggregate tags.

    Args:
        consolidated_tags: List of all unique canonical tags after consolidation
        suggested_category_tags: List of new broader category tags for organization
        suggested_aggregate_tags: List of new cross-cutting aggregate tags
        reasoning: Dictionary explaining the reasoning for each canonical tag choice and
        new tag suggestions

    Example:
        >>> response = ConsolidatedTagsResponse(
        ...     consolidated_tags=['#machine_learning', '#artificial_intelligence'],
        ...     suggested_category_tags=['#ai_methods', '#computational_intelligence'],
        ...     suggested_aggregate_tags=['#data_science', '#pattern_recognition'],
        ...     reasoning={
        ...         '#machine_learning': 'Chose as canonical for ML-related tags'
        ...     },
        ... )
    """

    consolidated_tags: list[str] = Field(
        description='List of all unique canonical tags after consolidation'
    )
    suggested_category_tags: list[str] = Field(
        description='List of new broader category tags that would help organize the canonical tags',
        default_factory=list,
    )
    suggested_aggregate_tags: list[str] = Field(
        description='List of new cross-cutting aggregate tags that combine related concepts',
        default_factory=list,
    )
    reasoning: str = Field(
        description='Text explaining the reasoning for each canonical tag choice and new tag suggestions',
        default='',
    )


class SingleTagMappingResponse(BaseModel):
    """Schema for mapping a single tag to its canonical form (second step).

    This model represents the response when asking the LLM to map one specific
    tag to its canonical equivalent from a provided list.

    Args:
        canonical_tag: The canonical tag that the original tag should map to

    Example:
        >>> response = SingleTagMappingResponse(canonical_tag='#machine_learning')
    """

    canonical_tag: str = Field(
        description='The canonical tag that the original tag should map to'
    )


class TagSuggestionResponse(BaseModel):
    """Schema for additional tag suggestions response from LLM.

    This model represents the response from the LLM when suggesting additional
    relevant tags for an article based on its abstract and existing tag vocabulary.

    Args:
        suggested_tags: List of additional relevant tags from the existing vocabulary
        reasoning: Text explaining why each suggested tag is relevant to the article

    Example:
        >>> response = TagSuggestionResponse(
        ...     suggested_tags=['#deep_learning', '#computer_vision'],
        ...     reasoning='Article uses neural networks extensively',
        ... )
    """

    suggested_tags: list[str] = Field(
        description='List of additional relevant tags from the existing vocabulary',
        default_factory=list,
    )
    reasoning: str = Field(
        description='Text explaining why each suggested tag is relevant to the article',
        default='',
    )


class ResearchQuery(BaseModel):
    """Schema for a research query that defines what kinds of articles to collect.

    This model represents a structured research query that can be used to evaluate
    whether articles meet specific research interests and criteria.

    Args:
        name: Unique name/identifier for this query
        description: Human-readable description of what this query is looking for
        research_question: The main research question or interest area
        keywords: List of important keywords that should be present
        required_topics: Topics that must be present in relevant articles
        preferred_topics: Topics that are preferred but not required
        excluded_topics: Topics that should exclude an article
        methodology_preferences: Preferred research methodologies
        publication_date_range: Date range for relevant publications
        minimum_relevance_score: Minimum score (0-1) for an article to be
            considered relevant
        created_at: When this query was created
        updated_at: When this query was last modified
        is_active: Whether this query is currently being used for filtering

    Example:
        >>> query = ResearchQuery(
        ...     name='deep_learning_nlp',
        ...     description='Deep learning approaches to natural language processing',
        ...     research_question='How are transformer architectures being applied to
        ...     NLP tasks?',
        ...     keywords=['transformer', 'attention', 'BERT', 'GPT'],
        ...     required_topics=['natural language processing', 'deep learning'],
        ...     preferred_topics=['transformer architecture', 'attention mechanisms'],
        ...     excluded_topics=['computer vision', 'robotics'],
        ...     minimum_relevance_score=0.7,
        ... )
    """

    name: str = Field(description='Unique name/identifier for this query')
    description: str = Field(
        description='Human-readable description of what this query is looking for'
    )
    research_question: str = Field(
        description='The main research question or interest area'
    )
    keywords: list[str] = Field(
        description='List of important keywords that should be present',
        default_factory=list,
    )
    required_topics: list[str] = Field(
        description='Topics that must be present in relevant articles',
        default_factory=list,
    )
    preferred_topics: list[str] = Field(
        description='Topics that are preferred but not required',
        default_factory=list,
    )
    excluded_topics: list[str] = Field(
        description='Topics that should exclude an article', default_factory=list
    )
    methodology_preferences: list[str] = Field(
        description='Preferred research methodologies', default_factory=list
    )
    publication_date_range: dict[str, str] | None = Field(
        description='Date range for relevant publications (start_date, end_date)',
        default=None,
    )
    minimum_relevance_score: float = Field(
        description='Minimum score (0-1) for an article to be considered relevant',
        default=0.7,
        ge=0.0,
        le=1.0,
    )
    created_at: str | None = Field(
        description='When this query was created', default=None
    )
    updated_at: str | None = Field(
        description='When this query was last modified', default=None
    )
    is_active: bool = Field(
        description='Whether this query is currently being used for filtering',
        default=True,
    )

    @field_validator('name')
    def validate_name(cls, name: str) -> str:  # noqa: N805
        """Validate that the name is a valid filename."""
        # Remove or replace invalid filename characters
        import re

        clean_name = re.sub(r'[^\w\-_.]', '_', name.lower())
        return clean_name


class QueryEvaluationResponse(BaseModel):
    """Schema for evaluating how well an article matches a research query.

    This model represents the LLM's evaluation of whether an article meets
    the criteria defined in a research query.

    Args:
        relevance_score: Overall relevance score from 0.0 to 1.0
        meets_criteria: Whether the article meets the minimum criteria
        keyword_matches: List of keywords from the query that were found
        topic_analysis: Analysis of how well the article matches required/preferred
            topics
        methodology_match: How well the article's methodology matches preferences
        reasoning: Detailed explanation of the evaluation
        recommendation: Whether to keep, reject, or review the article
        confidence: Confidence level in the evaluation (0.0 to 1.0)

    Example:
        >>> evaluation = QueryEvaluationResponse(
        ...     relevance_score=0.85,
        ...     meets_criteria=True,
        ...     keyword_matches=['transformer', 'attention'],
        ...     topic_analysis='Strong match for NLP and deep learning topics',
        ...     recommendation='keep',
        ...     confidence=0.9,
        ... )
    """

    relevance_score: float = Field(
        description='Overall relevance score from 0.0 to 1.0', ge=0.0, le=1.0
    )
    meets_criteria: bool = Field(
        description='Whether the article meets the minimum criteria'
    )
    keyword_matches: list[str] = Field(
        description='List of keywords from the query that were found',
        default_factory=list,
    )
    topic_analysis: str = Field(
        description='Analysis of how well the article matches required/preferred topics'
    )
    methodology_match: str | None = Field(
        description="How well the article's methodology matches preferences",
        default=None,
    )
    reasoning: str = Field(description='Detailed explanation of the evaluation')
    recommendation: Literal['keep', 'reject', 'review'] = Field(
        description='Whether to keep, reject, or review the article'
    )
    confidence: float = Field(
        description='Confidence level in the evaluation (0.0 to 1.0)',
        ge=0.0,
        le=1.0,
        default=0.8,
    )


class QueryRefinementSuggestion(BaseModel):
    """Schema for suggestions on how to improve a research query.

    This model represents suggestions from the LLM on how to refine or improve
    a research query based on analysis of articles and user feedback.

    Args:
        suggested_keywords: New keywords to add to the query
        suggested_topics: New topics to consider
        refinement_reasoning: Explanation of why these refinements are suggested
        query_improvements: Specific improvements to the research question
        methodology_suggestions: Suggestions for methodology preferences

    Example:
        >>> suggestion = QueryRefinementSuggestion(
        ...     suggested_keywords=['BERT', 'fine-tuning'],
        ...     suggested_topics=['transfer learning'],
        ...     refinement_reasoning='Based on recent articles, these terms are
        ...     commonly used',
        ... )
    """

    suggested_keywords: list[str] = Field(
        description='New keywords to add to the query', default_factory=list
    )
    suggested_topics: list[str] = Field(
        description='New topics to consider', default_factory=list
    )
    refinement_reasoning: str = Field(
        description='Explanation of why these refinements are suggested'
    )
    query_improvements: str | None = Field(
        description='Specific improvements to the research question', default=None
    )
    methodology_suggestions: list[str] = Field(
        description='Suggestions for methodology preferences', default_factory=list
    )


class ResearchAgentState(TypedDict):
    """Represents the state of the research query agent conversation."""

    # Current conversation context
    user_message: str | None  # Current user input
    agent_response: str | None  # Agent's response
    conversation_history: list[dict[str, str]] | None  # Previous messages

    # Query being worked on
    current_query: ResearchQuery | None  # Query being created/edited
    query_name: str | None  # Name of query being edited
    available_queries: list[str] | None  # List of existing query names

    # Article being evaluated
    current_article: AnalysisResponse | None  # Article being evaluated
    evaluation_result: QueryEvaluationResponse | None  # Evaluation result

    # Agent actions and state
    action: (
        Literal[
            'create_query',
            'edit_query',
            'evaluate_article',
            'refine_query',
            'list_queries',
            'delete_query',
            'chat',
            'end',
        ]
        | None
    )
    needs_user_input: bool | None  # Whether agent is waiting for user input
    error_message: str | None  # Any error that occurred


class ScrapedArticleMetadata(BaseModel):
    """Schema for scraped article metadata before PDF download.

    This model represents the metadata extracted from article scraping
    that will be used for initial filtering before downloading PDFs.

    Args:
        title: Title of the article
        authors: List of authors
        abstract: Abstract or summary of the article
        publication_date: Publication date
        journal: Journal or venue name
        doi: Digital Object Identifier
        arxiv_id: ArXiv identifier if applicable
        url: URL to the article
        pdf_url: Direct URL to PDF if available
        keywords: Keywords associated with the article
        source: Source where the article was scraped from
        scrape_timestamp: When the article was scraped
        additional_metadata: Any additional metadata from scraping

    Example:
        >>> metadata = ScrapedArticleMetadata(
        ...     title='Deep Learning for Natural Language Processing',
        ...     authors=['Smith, J.', 'Doe, A.'],
        ...     abstract='This paper presents a novel approach...',
        ...     journal='Nature Machine Intelligence',
        ...     doi='10.1038/s42256-023-00123-4',
        ...     source='arxiv',
        ... )
    """

    title: str = Field(description='Title of the article')
    authors: list[str] = Field(description='List of authors', default_factory=list)
    abstract: str | None = Field(
        description='Abstract or summary of the article', default=None
    )
    publication_date: str | None = Field(description='Publication date', default=None)
    journal: str | None = Field(description='Journal or venue name', default=None)
    doi: str | None = Field(description='Digital Object Identifier', default=None)
    arxiv_id: str | None = Field(
        description='ArXiv identifier if applicable', default=None
    )
    url: str | None = Field(description='URL to the article', default=None)
    pdf_url: str | None = Field(
        description='Direct URL to PDF if available', default=None
    )
    keywords: list[str] = Field(
        description='Keywords associated with the article', default_factory=list
    )
    source: str = Field(description='Source where the article was scraped from')
    scrape_timestamp: str | None = Field(
        description='When the article was scraped', default=None
    )
    additional_metadata: dict[str, Any] = Field(
        description='Any additional metadata from scraping', default_factory=dict
    )

    def to_analysis_response(self) -> AnalysisResponse:
        """
        Convert scraped metadata to AnalysisResponse format for evaluation.

        Returns:
            AnalysisResponse: Converted analysis response with available fields.

        Example:
            >>> metadata = ScrapedArticleMetadata(title='Test', abstract='Abstract')
            >>> analysis = metadata.to_analysis_response()
            >>> print(analysis.title)
            'Test'
        """
        return AnalysisResponse(
            abstract=self.abstract,
            key_points=None,  # Not available from scraping
            summary=self.abstract,  # Use abstract as summary
            objectives=None,
            methodology=None,
            data=None,
            experimental_setup=None,
            evaluation_metrics=None,
            results=None,
            discussion=None,
            strengths=None,
            limitations=None,
            future_work=None,
            related_work=None,
            tags=self.keywords if self.keywords else None,
        )


class PreDownloadEvaluationResponse(BaseModel):
    """Schema for evaluating scraped article metadata before PDF download.

    This model represents the evaluation of whether an article should be
    downloaded based on its metadata (title, abstract, etc.).

    Args:
        relevance_score: Overall relevance score from 0.0 to 1.0
        should_download: Whether the article should be downloaded
        keyword_matches: List of keywords from the query that were found
        topic_analysis: Analysis of how well the article matches required/preferred
            topics
        reasoning: Detailed explanation of the evaluation
        confidence: Confidence level in the evaluation (0.0 to 1.0)
        matching_queries: List of query names that recommend downloading

    Example:
        >>> evaluation = PreDownloadEvaluationResponse(
        ...     relevance_score=0.85,
        ...     should_download=True,
        ...     keyword_matches=['machine learning', 'healthcare'],
        ...     topic_analysis='Strong match for ML and healthcare topics',
        ...     reasoning='Article clearly focuses on ML applications in healthcare',
        ...     confidence=0.9,
        ... )
    """

    relevance_score: float = Field(
        description='Overall relevance score from 0.0 to 1.0', ge=0.0, le=1.0
    )
    should_download: bool = Field(
        description='Whether the article should be downloaded'
    )
    keyword_matches: list[str] = Field(
        description='List of keywords from the query that were found',
        default_factory=list,
    )
    topic_analysis: str = Field(
        description='Analysis of how well the article matches required/preferred topics'
    )
    reasoning: str = Field(description='Detailed explanation of the evaluation')
    confidence: float = Field(
        description='Confidence level in the evaluation (0.0 to 1.0)',
        ge=0.0,
        le=1.0,
        default=0.8,
    )
    matching_queries: list[str] = Field(
        description='List of query names that recommend downloading',
        default_factory=list,
    )


class FilterLogEntry(BaseModel):
    """Schema for logging article filtering decisions.

    This model represents a log entry that records the filtering decision
    for an article, including metadata and reasoning.

    Args:
        timestamp: When the filtering decision was made
        article_metadata: The scraped article metadata
        evaluation_result: The evaluation result
        decision: Final decision (download/skip)
        queries_evaluated: List of queries that were evaluated
        pdf_downloaded: Whether PDF was successfully downloaded
        pdf_path: Path where PDF was stored (if downloaded)
        error_message: Any error that occurred during processing

    Example:
        >>> log_entry = FilterLogEntry(
        ...     timestamp='2023-12-01T10:30:00',
        ...     article_metadata=metadata,
        ...     evaluation_result=evaluation,
        ...     decision='download',
        ...     queries_evaluated=['ml_healthcare'],
        ... )
    """

    timestamp: str = Field(description='When the filtering decision was made')
    article_metadata: ScrapedArticleMetadata = Field(
        description='The scraped article metadata'
    )
    evaluation_result: PreDownloadEvaluationResponse = Field(
        description='The evaluation result'
    )
    decision: Literal['download', 'skip'] = Field(
        description='Final decision (download/skip)'
    )
    queries_evaluated: list[str] = Field(
        description='List of queries that were evaluated', default_factory=list
    )
    pdf_downloaded: bool = Field(
        description='Whether PDF was successfully downloaded', default=False
    )
    pdf_path: str | None = Field(
        description='Path where PDF was stored (if downloaded)', default=None
    )
    error_message: str | None = Field(
        description='Any error that occurred during processing', default=None
    )
