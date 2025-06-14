"""
PDF-related tools for the research assistant.

This module provides tools for locating and managing PDFs for academic articles
using the PDF Locator Service.
"""

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool
from thoth.ingestion.agent_v2.tools.decorators import tool


class LocatePdfInput(BaseModel):
    """Input schema for locating a PDF."""

    doi: str | None = Field(default=None, description='DOI identifier for the article')
    arxiv_id: str | None = Field(
        default=None, description='arXiv identifier for the article'
    )
    title: str | None = Field(
        default=None,
        description='Article title to search for (used to find DOI/arXiv ID if not provided)',
    )


@tool
class LocatePdfTool(BaseThothTool):
    """Locate open-access PDFs for academic articles."""

    name: str = 'locate_pdf'
    description: str = (
        'Locate open-access PDF URLs for academic articles using DOI or arXiv ID. '
        'Searches multiple sources including Crossref, Unpaywall, arXiv, '
        'Semantic Scholar, and DOI content negotiation.'
    )
    args_schema: type[BaseModel] = LocatePdfInput

    def _run(
        self,
        doi: str | None = None,
        arxiv_id: str | None = None,
        title: str | None = None,
    ) -> str:
        """Locate PDF for an article."""
        try:
            # If title is provided but no DOI/arXiv ID, try to find the article first
            if title and not doi and not arxiv_id:
                # Search for the article in the knowledge base
                results = self.service_manager.rag.search(query=title, k=1)
                if results:
                    # Try to extract DOI or arXiv ID from the search results
                    # This is a simplified approach - in reality, we'd need to
                    # parse the metadata
                    result_content = results[0].get('content', '')

                    # Simple pattern matching for DOI
                    import re

                    doi_pattern = r'10\.\d{4,9}/[-._;()/:\w]+'
                    doi_match = re.search(doi_pattern, result_content)
                    if doi_match:
                        doi = doi_match.group()

                    # Simple pattern matching for arXiv ID
                    arxiv_pattern = r'(?:arXiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)'
                    arxiv_match = re.search(arxiv_pattern, result_content)
                    if arxiv_match:
                        arxiv_id = arxiv_match.group(1)

                if not doi and not arxiv_id:
                    return (
                        f"❌ Could not find DOI or arXiv ID for article: '{title}'. "
                        'Please provide a DOI or arXiv ID directly.'
                    )

            if not doi and not arxiv_id:
                return '❌ Please provide either a DOI, arXiv ID, or article title.'

            # Get PDF locator service
            pdf_locator = self.service_manager.pdf_locator

            # Locate the PDF
            location = pdf_locator.locate(doi=doi, arxiv_id=arxiv_id)

            if location:
                output = '✅ **PDF Found!**\n\n'
                output += f'🔗 **URL:** {location.url}\n'
                output += f'📚 **Source:** {location.source}\n'
                if location.licence:
                    output += f'📜 **License:** {location.licence}\n'
                output += f'🔓 **Open Access:** {"Yes" if location.is_oa else "No"}\n'

                if doi:
                    output += f'\n📖 **DOI:** {doi}'
                if arxiv_id:
                    output += f'\n📄 **arXiv ID:** {arxiv_id}'

                return output
            else:
                output = '❌ **No PDF Found**\n\n'
                if doi:
                    output += f'Searched for DOI: {doi}\n'
                if arxiv_id:
                    output += f'Searched for arXiv ID: {arxiv_id}\n'
                output += '\nThe article may not be open access, or the PDF may not be available through our sources.'
                return output

        except Exception as e:
            return self.handle_error(e, 'locating PDF')


class TestPdfSourceInput(BaseModel):
    """Input schema for testing PDF sources."""

    source: str = Field(
        description='Source to test (crossref, unpaywall, arxiv, s2, all)'
    )
    doi: str | None = Field(
        default=None, description='Optional DOI to test with a specific source'
    )


@tool
class ValidatePdfSourceTool(BaseThothTool):
    """Test PDF location sources."""

    name: str = 'validate_pdf_source'
    description: str = (
        'Test PDF location sources to verify they are working correctly. '
        'Can test individual sources or all sources at once.'
    )
    args_schema: type[BaseModel] = TestPdfSourceInput

    def _run(self, source: str, doi: str | None = None) -> str:
        """Test PDF location sources."""
        try:
            pdf_locator = self.service_manager.pdf_locator

            # Default test DOIs for different sources
            test_dois = {
                'crossref': '10.1038/nature12373',  # Nature article
                'unpaywall': '10.1371/journal.pone.0213692',  # PLOS ONE
                'arxiv': '10.48550/arXiv.1706.03762',  # Attention is All You Need
                's2': '10.18653/v1/D15-1166',  # ACL paper
            }

            if doi:
                test_dois = {source: doi}
            elif source != 'all':
                test_dois = {source: test_dois.get(source, test_dois['crossref'])}

            output = f'🧪 **Testing PDF Location Source(s): {source}**\n\n'

            for test_source, test_doi in test_dois.items():
                if source != 'all' and test_source != source:
                    continue

                output += f'**Testing {test_source}...**\n'

                # Test specific source method
                result = None
                if test_source == 'crossref':
                    result = pdf_locator._from_crossref(test_doi)
                elif test_source == 'unpaywall':
                    if not pdf_locator.email:
                        output += '  ⚠️ Unpaywall email not configured\n\n'
                        continue
                    result = pdf_locator._from_unpaywall(test_doi)
                elif test_source == 'arxiv':
                    result = pdf_locator._from_arxiv(test_doi, None)
                elif test_source == 's2':
                    result = pdf_locator._from_semanticscholar(test_doi)

                if result:
                    output += f'  ✅ Success - {result.url}\n'
                    if result.licence:
                        output += f'  📜 License: {result.licence}\n'
                else:
                    output += '  ❌ Not found\n'
                output += '\n'

            return output.strip()

        except Exception as e:
            return self.handle_error(e, f'testing PDF source {source}')


class LocatePdfsForQueryInput(BaseModel):
    """Input schema for locating PDFs for articles matching a query."""

    query_name: str = Field(description='Name of the research query to find PDFs for')
    limit: int = Field(default=10, description='Maximum number of articles to process')


@tool
class LocatePdfsForQueryTool(BaseThothTool):
    """Locate PDFs for articles matching a research query."""

    name: str = 'locate_pdfs_for_query'
    description: str = (
        'Find and locate PDFs for articles in your knowledge base that match '
        'a specific research query. Useful for building a collection of papers '
        'on a specific topic.'
    )
    args_schema: type[BaseModel] = LocatePdfsForQueryInput

    def _run(self, query_name: str, limit: int = 10) -> str:
        """Locate PDFs for articles matching a query."""
        try:
            # Get the query
            query = self.service_manager.query.get_query(query_name)
            if not query:
                return f"❌ Query '{query_name}' not found. Use 'list_queries' to see available queries."

            # Search for articles matching the query
            search_query = f'{query.research_question} {" ".join(query.keywords)}'
            results = self.service_manager.rag.search(query=search_query, k=limit)

            if not results:
                return f"No articles found matching query '{query_name}'"

            output = f'📚 **Locating PDFs for Query: {query_name}**\n\n'
            output += f'Found {len(results)} articles. Searching for PDFs...\n\n'

            pdf_locator = self.service_manager.pdf_locator
            located_count = 0

            for i, result in enumerate(results, 1):
                title = result.get('title', 'Untitled')
                content = result.get('content', '')

                # Try to extract DOI or arXiv ID from content
                import re

                doi = None
                arxiv_id = None

                doi_pattern = r'10\.\d{4,9}/[-._;()/:\w]+'
                doi_match = re.search(doi_pattern, content)
                if doi_match:
                    doi = doi_match.group()

                arxiv_pattern = r'(?:arXiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)'
                arxiv_match = re.search(arxiv_pattern, content)
                if arxiv_match:
                    arxiv_id = arxiv_match.group(1)

                if doi or arxiv_id:
                    location = pdf_locator.locate(doi=doi, arxiv_id=arxiv_id)
                    if location:
                        located_count += 1
                        output += f'✅ {i}. {title[:60]}...\n'
                        output += f'   📄 PDF: {location.source}\n'
                    else:
                        output += f'❌ {i}. {title[:60]}...\n'
                        output += '   📄 PDF: Not found\n'
                else:
                    output += f'⚠️ {i}. {title[:60]}...\n'
                    output += '   📄 No DOI/arXiv ID found\n'

            output += f'\n📊 **Summary:** Located PDFs for {located_count}/{len(results)} articles'

            return output

        except Exception as e:
            return self.handle_error(e, f"locating PDFs for query '{query_name}'")
