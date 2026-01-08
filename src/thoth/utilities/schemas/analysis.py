from pathlib import Path
from typing import Literal, TypedDict

from langchain_core.documents import Document
from pydantic import BaseModel, Field, field_validator


class AnalysisResponse(BaseModel):
    """Extract and store structured details from a research paper.

    This model captures all relevant metadata, content summaries, and analytical
    details from a research paper. All fields are optional to allow partial
    extraction and flexible downstream use. The model can be extended as new
    analytical requirements arise; any additional fields will automatically
    propagate to note generation and other consumers.

    Args:
        title: The title of the research paper.
        authors: A list of the authors of the paper.
        year: The publication year of the paper.
        doi: The Digital Object Identifier (DOI) of the paper.
        journal: The journal or venue where the paper was published.
        abstract: The abstract of the content as it appears in the document.
        key_points: 10-15 key points extracted from the content, provided as a
            newline-separated string.
        summary: A multi-paragraph summary of the content.
        objectives: Primary objectives or research questions addressed.
        methodology: Detailed description of the methods and study design,
            including model architecture if applicable.
        data: Datasets or data sources used, including size and key
            characteristics.
        experimental_setup: Experimental or analytical setup, including
            controls and variables.
        evaluation_metrics: Metrics used to evaluate performance or results.
        results: Key quantitative or qualitative results.
        discussion: Interpretation of the results and their implications.
        strengths: Strengths and positive aspects of the study.
        weaknesses: Weaknesses, shortcomings, or areas of concern.
        limitations: Explicitly stated or inferred limitations of the study.
        future_work: Suggested future work or open questions.
        related_work: Key related works and how this paper differs.
        tags: List of tags or keywords associated with the article.

    Returns:
        AnalysisResponse: An instance containing the extracted and structured
            analysis fields for a research paper.

    Example:
        >>> analysis = AnalysisResponse(
        ...     title='Attention Is All You Need',
        ...     authors=['Ashish Vaswani', 'Noam Shazeer'],
        ...     year=2017,
        ...     abstract='This paper explores...',
        ...     key_points='- Point one\n- Point two',
        ...     summary='A comprehensive summary...',
        ...     objectives='To investigate...',
        ...     methodology='We used a randomized control trial...',
        ...     data='Dataset X, 10,000 samples',
        ...     tags=['machine learning', 'NLP'],
        ... )
    """

    title: str | None = Field(
        description='The title of the research paper', default=None
    )
    authors: list[str] | None = Field(
        description='A list of the authors of the paper', default=None
    )
    year: int | None = Field(
        description='The publication year of the paper', default=None
    )
    doi: str | None = Field(
        description='The Digital Object Identifier (DOI) of the paper', default=None
    )
    journal: str | None = Field(
        description='The journal or venue where the paper was published', default=None
    )
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
    weaknesses: str | None = Field(
        description='Weaknesses, shortcomings, or areas of concern',
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
        if tags is None:
            return None
        normalized: list[str] = []
        for tag in tags:
            core = tag[1:] if tag.startswith('#') else tag
            core = core.lower().replace(' ', '_')
            core = ''.join(char for char in core if char.isalnum() or char == '_')
            normalized.append(f'#{core}')
        return normalized


class AnalysisState(TypedDict):
    """Represents the state of the analysis process."""

    markdown_path: Path | None
    original_content: str | None
    content_chunks: list[Document] | None
    strategy: Literal['direct', 'map_reduce', 'refine'] | None
    chunk_analyses: list[AnalysisResponse] | None
    current_analysis: AnalysisResponse | None
    final_analysis: AnalysisResponse | None
