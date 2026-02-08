"""
MCP-compliant PDF download tool.

This module provides a dedicated tool for downloading PDF files
from URLs or DOIs with proper error handling and progress tracking.
"""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..base_tools import MCPTool, MCPToolCallResult


class DownloadPdfMCPTool(MCPTool):
    """MCP tool for downloading PDF files from URLs or DOIs."""

    @property
    def name(self) -> str:
        return 'download_pdf'

    @property
    def description(self) -> str:
        return 'Download PDF files from URLs or DOIs with automatic filename generation and progress tracking'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'source': {
                    'type': 'string',
                    'description': 'PDF URL, DOI, or article identifier to download',
                },
                'output_directory': {
                    'type': 'string',
                    'description': 'Directory to save the PDF file (defaults to configured vault PDF directory from settings)',
                },
                'filename': {
                    'type': 'string',
                    'description': 'Custom filename for the PDF (optional, auto-generated if not provided)',
                },
                'overwrite': {
                    'type': 'boolean',
                    'description': 'Overwrite existing file if it exists',
                    'default': False,
                },
                'timeout': {
                    'type': 'integer',
                    'description': 'Download timeout in seconds',
                    'default': 30,
                    'minimum': 5,
                    'maximum': 300,
                },
            },
            'required': ['source'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Download a PDF file."""
        try:
            source = arguments['source']
            output_directory = arguments.get('output_directory')
            custom_filename = arguments.get('filename')
            overwrite = arguments.get('overwrite', False)
            timeout = arguments.get('timeout', 30)

            response_text = '📥 **PDF Download Request**\n\n'
            response_text += f'**Source:** {source}\n'

            # Determine if source is URL, DOI, or article identifier
            download_url = None
            article_title = None

            if source.startswith(('http://', 'https://')):
                # Direct URL
                download_url = source
                response_text += '**Type:** Direct URL\n'

            elif source.startswith('10.') and '/' in source:
                # DOI format
                download_url = f'https://doi.org/{source}'
                response_text += '**Type:** DOI\n'
                response_text += f'**DOI URL:** {download_url}\n'

            else:
                # Try to find the article and get its PDF URL
                response_text += '**Type:** Article identifier\n'

                try:
                    # Search for the article in our knowledge base (use async version)
                    search_results = await self.service_manager.rag.search_async(
                        query=source, k=1
                    )

                    if search_results:
                        article = search_results[0]
                        article_title = article.get('title', 'Unknown')
                        metadata = article.get('metadata', {})

                        response_text += f'**Found Article:** {article_title}\n'

                        # Try to get PDF URL from metadata or use PDF locator
                        pdf_url = metadata.get('pdf_url') or metadata.get('url')

                        if not pdf_url:
                            # Use PDF locator service
                            try:
                                pdf_results = (
                                    self.service_manager.pdf_locator.locate_pdf(
                                        title=article_title,
                                        doi=metadata.get('doi', ''),
                                        arxiv_id=metadata.get('arxiv_id'),
                                    )
                                )

                                if pdf_results and pdf_results.get('success'):
                                    pdf_url = pdf_results.get('pdf_url')
                                    response_text += f'**PDF Located:** {pdf_results.get("source", "Unknown source")}\n'

                            except Exception:
                                pass

                        if pdf_url:
                            download_url = pdf_url
                        else:
                            return MCPToolCallResult(
                                content=[
                                    {
                                        'type': 'text',
                                        'text': f"{response_text}\n**Error:** No PDF URL found for article '{article_title}'.\n\n**Try:** Using `locate_pdf` tool first to find the PDF URL.",
                                    }
                                ],
                                isError=True,
                            )
                    else:
                        return MCPToolCallResult(
                            content=[
                                {
                                    'type': 'text',
                                    'text': f"{response_text}\n**Error:** Article not found: '{source}'.\n\n**Try:** Using a direct PDF URL or DOI instead.",
                                }
                            ],
                            isError=True,
                        )

                except Exception as search_error:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'{response_text}\n**Error:** Failed to search for article: {search_error!s}',
                            }
                        ],
                        isError=True,
                    )

            # Set up output directory
            if output_directory:
                output_path = Path(output_directory)
            else:
                # Use configured vault PDF directory from settings
                from thoth.config import config

                output_path = Path(config.pdf_dir)

            output_path.mkdir(parents=True, exist_ok=True)
            response_text += f'**Output Directory:** {output_path}\n'

            # Generate filename
            if custom_filename:
                if not custom_filename.endswith('.pdf'):
                    custom_filename += '.pdf'
                filename = custom_filename
            else:
                # Auto-generate filename
                if article_title:
                    # Use article title
                    safe_title = ''.join(
                        c for c in article_title if c.isalnum() or c in (' ', '-', '_')
                    ).strip()
                    safe_title = safe_title[:100]  # Limit length
                    filename = f'{safe_title}.pdf'
                else:
                    # Use URL components
                    parsed_url = urlparse(download_url)
                    if parsed_url.path and parsed_url.path.endswith('.pdf'):
                        filename = Path(parsed_url.path).name
                    else:
                        filename = f'downloaded_paper_{hash(download_url) % 10000}.pdf'

            full_path = output_path / filename
            response_text += f'**Filename:** {filename}\n\n'

            # Check if file exists
            if full_path.exists() and not overwrite:
                file_size = full_path.stat().st_size / (1024 * 1024)  # MB
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'{response_text}**File Already Exists**\n\n'
                            f'**Path:** {full_path}\n'
                            f'**Size:** {file_size:.1f} MB\n\n'
                            f'**Options:**\n'
                            f'- Use `overwrite: true` to replace the file\n'
                            f'- Use a different `filename`\n'
                            f'- Use a different `output_directory`',
                        }
                    ]
                )

            # Download the PDF
            response_text += '**Starting Download...**\n'

            try:
                # Set up request headers
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/pdf,application/octet-stream,*/*',
                }

                # Download with streaming using httpx.stream() context manager
                total_size = 0
                downloaded = 0

                with httpx.stream(
                    'GET',
                    download_url,
                    headers=headers,
                    timeout=timeout,
                    follow_redirects=True,
                ) as response:
                    response.raise_for_status()

                    # Check if response is actually a PDF
                    content_type = response.headers.get('content-type', '').lower()
                    total_size = int(response.headers.get('content-length', 0))

                    # Read first chunk to verify PDF content
                    first_chunk = b''
                    with open(full_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if chunk:
                                if not first_chunk:
                                    first_chunk = chunk
                                    # Verify PDF magic bytes if content-type is ambiguous
                                    if (
                                        'pdf' not in content_type
                                        and 'octet-stream' not in content_type
                                        and not first_chunk.startswith(b'%PDF')
                                    ):
                                        f.close()
                                        full_path.unlink()  # Remove partial file
                                        return MCPToolCallResult(
                                            content=[
                                                {
                                                    'type': 'text',
                                                    'text': f'{response_text}**Error:** URL does not appear to serve a PDF file.\n\n'
                                                    f'**Content-Type:** {content_type}\n'
                                                    f'**URL:** {download_url}\n\n'
                                                    f'**Tip:** The URL might redirect to a landing page. Try finding the direct PDF link.',
                                                }
                                            ],
                                            isError=True,
                                        )
                                f.write(chunk)
                                downloaded += len(chunk)

                # Verify download
                final_size = full_path.stat().st_size
                final_size_mb = final_size / (1024 * 1024)

                if final_size == 0:
                    full_path.unlink()  # Remove empty file
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'{response_text}**Download Failed:** File is empty.\n\n'
                                f'**URL:** {download_url}\n'
                                f'**Status Code:** {response.status_code}',
                            }
                        ],
                        isError=True,
                    )

                # Success!
                response_text += '**Download Complete!**\n\n'
                response_text += '**File Details:**\n'
                response_text += f'- **Path:** {full_path}\n'
                response_text += f'- **Size:** {final_size_mb:.1f} MB\n'
                response_text += '- **Status:** Successfully downloaded\n\n'

                # Additional info
                if total_size > 0:
                    response_text += '**Download Stats:**\n'
                    response_text += (
                        f'- **Expected Size:** {total_size / (1024 * 1024):.1f} MB\n'
                    )
                    response_text += f'- **Actual Size:** {final_size_mb:.1f} MB\n'
                    response_text += f'- **Integrity:** {"Complete" if final_size == total_size else "Size mismatch"}\n\n'

                response_text += '**Next Steps:**\n'
                response_text += '- Use `extract_pdf_metadata` to analyze the PDF\n'
                response_text += (
                    '- Use `process_pdf` to add it to your knowledge base\n'
                )
                response_text += '- Open the file to verify it downloaded correctly\n'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text.strip()}]
                )

            except httpx.TimeoutException:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'{response_text}**Download Timeout:** Request timed out after {timeout} seconds.\n\n'
                            f'**Try:** Increasing the timeout value or checking your internet connection.',
                        }
                    ],
                    isError=True,
                )

            except httpx.HTTPError as req_error:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'{response_text}**Download Failed:** {req_error!s}\n\n'
                            f'**URL:** {download_url}\n\n'
                            f'**Common Issues:**\n'
                            f'- URL requires authentication or subscription\n'
                            f'- Server is temporarily unavailable\n'
                            f'- URL has expired or changed\n'
                            f'- Network connectivity issues',
                        }
                    ],
                    isError=True,
                )

            except Exception as download_error:
                # Clean up partial file
                if full_path.exists():
                    try:
                        full_path.unlink()
                    except OSError:
                        pass

                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'{response_text}**Download Error:** {download_error!s}\n\n'
                            f'**Troubleshooting:**\n'
                            f'- Check if the URL is accessible in a browser\n'
                            f'- Verify you have write permissions to the output directory\n'
                            f'- Try a different output directory\n'
                            f'- Check available disk space',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)
