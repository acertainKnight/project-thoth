"""
MCP-compliant PDF and content management tools.

This module provides tools for locating PDFs, validating PDF sources,
and extracting metadata from PDF files.
"""

from pathlib import Path
from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult


class LocatePdfMCPTool(MCPTool):
    """MCP tool for locating open-access PDFs for academic articles."""

    @property
    def name(self) -> str:
        return 'locate_pdf'

    @property
    def description(self) -> str:
        return 'Locate open-access PDFs for academic articles using DOI, title, or arXiv ID'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to locate PDF for',
                },
                'search_multiple_sources': {
                    'type': 'boolean',
                    'description': 'Search multiple PDF sources for better coverage',
                    'default': True,
                },
                'auto_download': {
                    'type': 'boolean',
                    'description': 'Automatically call download_pdf tool if PDF is found',
                    'default': False,
                },
            },
            'required': ['article_identifier'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Locate PDF for an article."""
        try:
            article_identifier = arguments['article_identifier']
            download_pdf = arguments.get('download_pdf', False)
            output_directory = arguments.get('output_directory')

            # First, try to find the article in our knowledge base
            search_results = self.service_manager.rag.search(
                query=article_identifier, k=1
            )

            article_info = None
            if search_results:
                article_info = search_results[0]
                title = article_info.get('title', 'Unknown')
                metadata = article_info.get('metadata', {})
                doi = metadata.get('doi', '')
                arxiv_id = metadata.get('arxiv_id', '')
            else:
                title = article_identifier
                doi = ''
                arxiv_id = ''

            response_text = f'🔍 **PDF Location Search for:** {title}\n\n'

            # Try to use PDF locator service
            try:
                # Use the PDF locator service to find PDF
                pdf_results = self.service_manager.pdf_locator.locate_pdf(
                    title=title, doi=doi, arxiv_id=arxiv_id if arxiv_id else None
                )

                if pdf_results and pdf_results.get('success'):
                    pdf_url = pdf_results.get('pdf_url')
                    source = pdf_results.get('source', 'Unknown')

                    response_text += '✅ **PDF Found!**\n'
                    response_text += f'- **Source:** {source}\n'
                    response_text += f'- **URL:** {pdf_url}\n'

                    # Additional metadata if available
                    if pdf_results.get('file_size'):
                        response_text += (
                            f'- **File Size:** {pdf_results["file_size"]}\n'
                        )
                    if pdf_results.get('access_type'):
                        response_text += (
                            f'- **Access Type:** {pdf_results["access_type"]}\n'
                        )

                    response_text += '\n'

                    # Download PDF if requested
                    if download_pdf:
                        try:
                            if output_directory:
                                output_path = Path(output_directory)
                            else:
                                output_path = Path.cwd() / 'downloaded_pdfs'

                            output_path.mkdir(parents=True, exist_ok=True)

                            # Generate filename from title
                            safe_title = ''.join(
                                c for c in title if c.isalnum() or c in (' ', '-', '_')
                            ).rstrip()
                            safe_title = safe_title[:100]  # Limit length
                            filename = f'{safe_title}.pdf'
                            full_path = output_path / filename

                            # Placeholder for actual download
                            response_text += '📥 **Download Status:**\n'
                            response_text += f'- Target path: {full_path}\n'
                            response_text += '- Status: ⚠️ Download functionality not yet implemented\n'
                            response_text += '- Manual download: Copy the URL above to download manually\n\n'

                        except Exception as download_error:
                            response_text += (
                                f'❌ **Download Failed:** {download_error!s}\n\n'
                            )

                    response_text += '💡 **Next Steps:**\n'
                    response_text += '- Use the URL above to access the PDF\n'
                    response_text += (
                        '- Consider processing the PDF with `process_pdf` tool\n'
                    )
                    response_text += '- Save to your preferred reference manager\n'

                else:
                    # PDF not found - provide search suggestions
                    response_text += '❌ **PDF Not Found**\n\n'

                    response_text += '🔍 **Search Attempted:**\n'
                    if doi:
                        response_text += f'- DOI: {doi}\n'
                    if arxiv_id:
                        response_text += f'- arXiv ID: {arxiv_id}\n'
                    response_text += f'- Title: {title}\n\n'

                    response_text += '💡 **Alternative Sources to Try:**\n'
                    response_text += '- Search directly on arXiv.org\n'
                    response_text += "- Check publisher's website\n"
                    response_text += '- Try Google Scholar\n'
                    response_text += '- Look for preprint versions\n'
                    response_text += '- Check institutional repositories\n\n'

                    if doi:
                        response_text += '🌐 **Direct Links:**\n'
                        response_text += f'- DOI URL: https://doi.org/{doi}\n'

                    if arxiv_id:
                        response_text += (
                            f'- arXiv URL: https://arxiv.org/abs/{arxiv_id}\n'
                        )

            except Exception as pdf_error:
                # Fallback if PDF locator service is not available
                response_text += '⚠️ **PDF Locator Service Unavailable**\n\n'
                response_text += f'**Error:** {pdf_error!s}\n\n'

                response_text += '🔍 **Manual Search Suggestions:**\n'
                response_text += f'1. **arXiv:** https://arxiv.org/search/?query={title.replace(" ", "+")}\n'
                response_text += f'2. **Google Scholar:** https://scholar.google.com/scholar?q={title.replace(" ", "+")}\n'

                if doi:
                    response_text += f'3. **DOI Link:** https://doi.org/{doi}\n'

                response_text += (
                    '4. **PubMed Central:** https://www.ncbi.nlm.nih.gov/pmc/\n'
                )
                response_text += (
                    '5. **Directory of Open Access Journals:** https://doaj.org/\n\n'
                )

                response_text += '💡 **Tip:** Many publishers offer free access to older articles or have open access policies.'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class ValidatePdfSourcesMCPTool(MCPTool):
    """MCP tool for testing and validating PDF location sources."""

    @property
    def name(self) -> str:
        return 'validate_pdf_sources'

    @property
    def description(self) -> str:
        return 'Test and validate PDF location sources to ensure they are working correctly'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'source_name': {
                    'type': 'string',
                    'description': 'Specific PDF source to test (optional - tests all if not provided)',
                },
                'test_sample': {
                    'type': 'boolean',
                    'description': 'Test with a sample of known articles',
                    'default': True,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Validate PDF sources."""
        try:
            source_name = arguments.get('source_name')
            test_sample = arguments.get('test_sample', True)

            response_text = '🔧 **PDF Sources Validation**\n\n'

            # Try to get PDF locator service status
            try:
                # This would test the PDF locator service
                response_text += '📊 **Validation Results:**\n\n'

                # Test different PDF sources
                sources_to_test = [
                    {'name': 'arXiv', 'description': 'Open access preprints'},
                    {'name': 'PubMed Central', 'description': 'Biomedical literature'},
                    {
                        'name': 'DOAJ',
                        'description': 'Directory of Open Access Journals',
                    },
                    {
                        'name': 'Unpaywall',
                        'description': 'Open access versions of papers',
                    },
                    {'name': 'CORE', 'description': 'Open access research papers'},
                ]

                if source_name:
                    sources_to_test = [
                        s
                        for s in sources_to_test
                        if s['name'].lower() == source_name.lower()
                    ]
                    if not sources_to_test:
                        return MCPToolCallResult(
                            content=[
                                {
                                    'type': 'text',
                                    'text': f'❌ Unknown PDF source: {source_name}\n\nAvailable sources: arXiv, PubMed Central, DOAJ, Unpaywall, CORE',
                                }
                            ],
                            isError=True,
                        )

                # Test each source
                for source in sources_to_test:
                    response_text += f'**{source["name"]}** - {source["description"]}\n'

                    # Placeholder for actual testing
                    # In a real implementation, this would test API connectivity, etc.
                    response_text += '  - Status: ⚠️ Validation not fully implemented\n'
                    response_text += '  - API Access: Unknown\n'
                    response_text += '  - Rate Limits: Unknown\n'
                    response_text += '  - Last Tested: Never\n\n'

                if test_sample:
                    response_text += '📝 **Sample Testing:**\n'
                    response_text += '- Sample articles test: ⚠️ Not implemented\n'
                    response_text += '- Success rate: Unknown\n'
                    response_text += '- Average response time: Unknown\n\n'

                response_text += '🔧 **Recommendations:**\n'
                response_text += '- Implement comprehensive PDF source testing\n'
                response_text += '- Add monitoring for source availability\n'
                response_text += '- Create fallback mechanisms for failed sources\n'
                response_text += '- Monitor API rate limits and quotas\n\n'

                response_text += '💡 **Current Status:**\n'
                response_text += 'PDF source validation is in development. Basic PDF location functionality is available through the `locate_pdf` tool, but comprehensive validation and monitoring features are planned for future releases.'

            except Exception as validation_error:
                response_text += '❌ **Validation Error:**\n'
                response_text += f'{validation_error!s}\n\n'
                response_text += '🔧 **Troubleshooting:**\n'
                response_text += '- Check PDF locator service configuration\n'
                response_text += '- Verify network connectivity\n'
                response_text += '- Ensure required API keys are configured\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class ExtractPdfMetadataMCPTool(MCPTool):
    """MCP tool for extracting comprehensive metadata from PDF files."""

    @property
    def name(self) -> str:
        return 'extract_pdf_metadata'

    @property
    def description(self) -> str:
        return 'Extract comprehensive metadata from PDF files including title, authors, keywords, and document properties'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'pdf_path': {
                    'type': 'string',
                    'description': 'Path to the PDF file to extract metadata from',
                },
                'extract_text_preview': {
                    'type': 'boolean',
                    'description': 'Extract a preview of the text content',
                    'default': True,
                },
                'analyze_structure': {
                    'type': 'boolean',
                    'description': 'Analyze document structure (sections, figures, tables)',
                    'default': False,
                },
            },
            'required': ['pdf_path'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Extract PDF metadata."""
        try:
            pdf_path = arguments['pdf_path']
            extract_text_preview = arguments.get('extract_text_preview', True)
            analyze_structure = arguments.get('analyze_structure', False)

            # Validate file exists
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'❌ PDF file not found: {pdf_path}'}
                    ],
                    isError=True,
                )

            if not pdf_file.suffix.lower() == '.pdf':
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'❌ File is not a PDF: {pdf_path}'}
                    ],
                    isError=True,
                )

            response_text = '📄 **PDF Metadata Extraction**\n\n'
            response_text += f'**File:** {pdf_file.name}\n'
            response_text += f'**Path:** {pdf_path}\n'
            response_text += (
                f'**Size:** {pdf_file.stat().st_size / (1024 * 1024):.1f} MB\n\n'
            )

            try:
                # Try to extract metadata using PyPDF2 or similar library
                # This is a placeholder implementation
                import PyPDF2

                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)

                    # Basic PDF properties
                    response_text += '📊 **Document Properties:**\n'
                    response_text += f'- Pages: {len(pdf_reader.pages)}\n'

                    # PDF metadata
                    if pdf_reader.metadata:
                        metadata = pdf_reader.metadata
                        response_text += '\n📋 **PDF Metadata:**\n'

                        if metadata.get('/Title'):
                            response_text += f'- **Title:** {metadata["/Title"]}\n'
                        if metadata.get('/Author'):
                            response_text += f'- **Author:** {metadata["/Author"]}\n'
                        if metadata.get('/Subject'):
                            response_text += f'- **Subject:** {metadata["/Subject"]}\n'
                        if metadata.get('/Keywords'):
                            response_text += (
                                f'- **Keywords:** {metadata["/Keywords"]}\n'
                            )
                        if metadata.get('/Creator'):
                            response_text += f'- **Creator:** {metadata["/Creator"]}\n'
                        if metadata.get('/Producer'):
                            response_text += (
                                f'- **Producer:** {metadata["/Producer"]}\n'
                            )
                        if metadata.get('/CreationDate'):
                            response_text += (
                                f'- **Creation Date:** {metadata["/CreationDate"]}\n'
                            )
                        if metadata.get('/ModDate'):
                            response_text += (
                                f'- **Modified Date:** {metadata["/ModDate"]}\n'
                            )

                    # Extract text preview if requested
                    if extract_text_preview and len(pdf_reader.pages) > 0:
                        response_text += '\n📝 **Text Preview (First Page):**\n'
                        try:
                            first_page = pdf_reader.pages[0]
                            text_content = first_page.extract_text()

                            if text_content:
                                # Clean and truncate text
                                preview_text = (
                                    text_content[:500].replace('\n', ' ').strip()
                                )
                                response_text += f'```\n{preview_text}...\n```\n'
                            else:
                                response_text += '⚠️ No text could be extracted from the first page.\n'

                        except Exception as text_error:
                            response_text += (
                                f'❌ Text extraction failed: {text_error!s}\n'
                            )

                    # Document structure analysis
                    if analyze_structure:
                        response_text += '\n🏗️ **Document Structure Analysis:**\n'
                        response_text += f'- Total pages: {len(pdf_reader.pages)}\n'

                        # Analyze page sizes
                        if len(pdf_reader.pages) > 0:
                            first_page = pdf_reader.pages[0]
                            if hasattr(first_page, 'mediabox'):
                                width = float(first_page.mediabox.width)
                                height = float(first_page.mediabox.height)
                                response_text += (
                                    f'- Page size: {width:.0f} x {height:.0f} points\n'
                                )

                        # Check for outline/bookmarks
                        if hasattr(pdf_reader, 'outline') and pdf_reader.outline:
                            response_text += f'- Bookmarks/Outline: Yes ({len(pdf_reader.outline)} items)\n'
                        else:
                            response_text += '- Bookmarks/Outline: None\n'

                        response_text += f'- Estimated reading time: {len(pdf_reader.pages) * 2} minutes\n'

                # Additional analysis suggestions
                response_text += '\n💡 **Analysis Suggestions:**\n'
                response_text += '- Use `process_pdf` to fully process this document\n'
                response_text += '- Check if the PDF is text-based or image-based\n'
                response_text += '- Consider OCR if text extraction is limited\n'
                response_text += '- Look for DOI or arXiv ID in the metadata\n\n'

                response_text += '✅ **Metadata extraction completed successfully!**'

            except ImportError:
                # Fallback if PyPDF2 is not available
                response_text += '⚠️ **PDF Processing Library Not Available**\n\n'
                response_text += '**Basic File Info:**\n'
                response_text += '- File exists: ✅\n'
                response_text += '- File format: PDF\n'
                response_text += (
                    f'- Size: {pdf_file.stat().st_size / (1024 * 1024):.1f} MB\n\n'
                )

                response_text += '🔧 **To enable full metadata extraction:**\n'
                response_text += '- Install PyPDF2: `pip install PyPDF2`\n'
                response_text += '- Or use: `uv add PyPDF2`\n\n'

                response_text += '💡 **Alternative:** Use `process_pdf` tool which includes metadata extraction as part of the full processing pipeline.'

            except Exception as extraction_error:
                response_text += '❌ **Metadata Extraction Failed:**\n'
                response_text += f'{extraction_error!s}\n\n'
                response_text += '🔧 **Possible Issues:**\n'
                response_text += '- PDF file may be corrupted\n'
                response_text += '- PDF may be password protected\n'
                response_text += '- File may not be a valid PDF\n'
                response_text += '- PDF may use unsupported features\n\n'
                response_text += '💡 **Try:** Using a different PDF processing tool or repairing the PDF file.'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)
