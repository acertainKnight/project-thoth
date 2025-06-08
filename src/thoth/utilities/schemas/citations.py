from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Schema for a single citation."""

    text: str | None = Field(default=None)
    authors: list[str] | None = Field(default=None)
    affiliations: list[str] | None = Field(default=None)
    title: str | None = Field(default=None)
    abstract: str | None = Field(default=None)
    year: int | None = Field(default=None)
    journal: str | None = Field(default=None)
    venue: str | None = Field(default=None)
    citation_count: int | None = Field(default=None)
    doi: str | None = Field(default=None)
    backup_id: str | None = Field(default=None)
    url: str | None = Field(default=None)
    volume: str | None = Field(default=None)
    issue: str | None = Field(default=None)
    pages: str | None = Field(default=None)
    obsidian_uri: str | None = Field(default=None)
    is_document_citation: bool = Field(default=False)
    formatted: str | None = Field(default=None)
    fields_of_study: list[str] | None = Field(default=None)
    reference_count: int | None = Field(default=None)
    influential_citation_count: int | None = Field(default=None)
    is_open_access: bool | None = Field(default=None)
    s2_fields_of_study: list[str] | None = Field(default=None)

    def update_from_opencitation(self, open_citation: 'OpenCitation') -> None:
        """Update this Citation with values from an OpenCitation model."""
        field_mapping = {
            'title': 'title',
            'author': 'authors',
            'pub_date': 'year',
            'venue': 'venue',
            'volume': 'volume',
            'issue': 'issue',
            'page': 'pages',
            'abstract': 'abstract',
            'citation_count': 'citation_count',
        }
        for open_field, citation_field in field_mapping.items():
            open_value = getattr(open_citation, open_field)
            if open_value is None or open_value == '':
                continue
            if open_field == 'author' and open_value:
                if self.authors is None:
                    self.authors = [open_value]
            elif open_field == 'pub_date' and open_value:
                try:
                    self.year = int(open_value.split('-')[0])
                except (ValueError, IndexError):
                    pass
            else:
                if getattr(self, citation_field) is None:
                    setattr(self, citation_field, open_value)
        if not self.doi and open_citation.id and ':' in open_citation.id:
            id_type, _ = open_citation.id.split(':', 1)
            if id_type != 'doi' and not self.backup_id:
                self.backup_id = open_citation.id

    def update_from_arxiv(self, arxiv_paper: 'ArxivPaper') -> None:
        """Update this Citation with values from an ArxivPaper model."""
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
        for arxiv_field, citation_field in field_mapping.items():
            arxiv_value = getattr(arxiv_paper, arxiv_field)
            if arxiv_value is not None:
                setattr(self, citation_field, arxiv_value)

    @classmethod
    def from_citation_extraction(
        cls, citation_extraction: 'CitationExtraction'
    ) -> 'Citation':
        """Create a new Citation instance from a CitationExtraction model."""
        citation_data = {
            'text': citation_extraction.text,
            'authors': citation_extraction.authors.split(';')
            if citation_extraction.authors
            else None,
            'affiliations': citation_extraction.affiliations.split(';')
            if citation_extraction.affiliations
            else None,
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
        return cls(**{k: v for k, v in citation_data.items() if v is not None})


class CitationExtraction(BaseModel):
    """Schema for a single citation extraction."""

    text: str | None = Field(default=None)
    authors: str | None = Field(default=None)
    affiliations: str | None = Field(default=None)
    title: str | None = Field(default=None)
    year: int | None = Field(default=None)
    journal: str | None = Field(default=None)
    doi: str | None = Field(default=None)
    backup_id: str | None = Field(default=None)
    url: str | None = Field(default=None)
    volume: str | None = Field(default=None)
    issue: str | None = Field(default=None)
    pages: str | None = Field(default=None)


class ReferencesSection(BaseModel):
    """Schema for the references section identification response."""

    heading: str | None = Field(default=None)


class CitationExtractionResponse(BaseModel):
    """Schema for the citation extraction response."""

    citations: list[CitationExtraction]


class OpenCitation(BaseModel):
    """Schema for a single citation from OpenCitations API."""

    id: str
    title: str
    author: str | None = ''
    pub_date: str | None = ''
    issue: str | None = ''
    volume: str | None = ''
    venue: str | None = ''
    type: str | None = ''
    page: str | None = ''
    publisher: str | None = ''
    editor: str | None = ''


class OpenCitationsResponse(BaseModel):
    """Schema for the OpenCitations API response."""

    citations: list[OpenCitation]


class ArxivPaper(BaseModel):
    """Schema for an arXiv paper."""

    id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    pdf_url: str | None = None
    published: str | None = None
    updated: str | None = None
    comment: str | None = None
    journal_ref: str | None = None
    doi: str | None = None
    citation_count: int | None = None
