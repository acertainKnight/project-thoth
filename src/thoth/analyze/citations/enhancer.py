from thoth.analyze.citations.opencitation import OpenCitationsAPI
from thoth.analyze.citations.scholarly import ScholarlyAPI
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.discovery.api_sources import ArxivClient
from thoth.utilities.schemas import Citation


class CitationEnhancer:
    """Enhances citation data using external APIs."""

    def __init__(self, config):
        self.use_semanticscholar = config.citation_config.use_semanticscholar
        self.use_opencitations = config.citation_config.use_opencitations
        self.use_scholarly = config.citation_config.use_scholarly
        self.use_arxiv = config.citation_config.use_arxiv

        self.semanticscholar_tool = (
            SemanticScholarAPI(api_key=config.api_keys.semanticscholar_api_key)
            if self.use_semanticscholar
            else None
        )
        self.opencitations_tool = (
            OpenCitationsAPI(access_token=config.api_keys.opencitations_key)
            if self.use_opencitations and config.api_keys.opencitations_key
            else None
        )
        self.scholarly_tool = ScholarlyAPI() if self.use_scholarly else None
        self.arxiv_tool = ArxivClient() if self.use_arxiv else None

    def enhance(self, citations: list[Citation]) -> list[Citation]:
        """
        Enhances a list of citations by fetching additional data from external APIs.
        """
        if not citations:
            return []

        # Process with Semantic Scholar first
        if self.use_semanticscholar and self.semanticscholar_tool:
            citations = self.semanticscholar_tool.semantic_scholar_lookup(citations)

        # Process with other services for remaining gaps
        for citation in citations:
            has_identifier, has_missing_fields = self._check_citation(citation)
            if not has_missing_fields:
                continue

            if self.use_opencitations and self.opencitations_tool and has_identifier:
                citation.update_from_opencitation(
                    self.opencitations_tool.lookup_metadata_sync(
                        [f'doi:{citation.doi}' if citation.doi else citation.backup_id]
                    )[0]
                )

            if (
                self.use_arxiv
                and self.arxiv_tool
                and (not has_identifier or self._check_citation(citation)[1])
            ):
                self._arxiv_lookup([citation])

            if (
                self.use_scholarly
                and self.scholarly_tool
                and (not has_identifier or self._check_citation(citation)[1])
            ):
                self._scholarly_lookup([citation])

        return citations

    def _check_citation(self, citation: Citation) -> tuple[bool, bool]:
        """Checks if a citation has an identifier and if it has missing fields."""
        has_identifier = bool(citation.doi or citation.backup_id)
        has_missing_fields = any(
            getattr(citation, field) is None for field in citation.model_fields
        )
        return has_identifier, has_missing_fields

    def _arxiv_lookup(self, citations: list[Citation]):
        if self.arxiv_tool:
            self.arxiv_tool.arxiv_lookup(citations)

    def _scholarly_lookup(self, citations: list[Citation]):
        if self.scholarly_tool:
            self.scholarly_tool.find_doi_sync(citations[0])
            self.scholarly_tool.find_pdf_url_sync(citations[0])
