"""
Note generator module for Thoth.

This module handles the generation of Obsidian notes from processed content.
"""

import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

import requests  # Added for URL accessibility check
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from thoth.utilities.models import AnalysisResponse, Citation


class NoteGenerator:
    """
    Generates Obsidian notes from processed content using templates.

    This class handles the creation of structured Obsidian notes from
    processed content using Jinja2 templates.
    """

    def __init__(
        self, templates_dir: Path, notes_dir: Path, api_base_url: str | None = None
    ):
        """
        Initialize the note generator.

        Args:
            templates_dir (Path): Directory containing note templates.
            notes_dir (Path): Directory where generated notes will be saved.
            api_base_url (Optional[str]): Base URL for the FastAPI endpoint.
                                         If None, will be loaded from config.
        """
        self.templates_dir = templates_dir
        self.notes_dir = notes_dir

        # Set API base URL from parameter, environment variable, or default
        if api_base_url:
            self.api_base_url = api_base_url
        else:
            # Try to get from environment variable
            self.api_base_url = os.environ.get(
                'THOTH_API_BASE_URL', 'http://localhost:8000'
            )

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=False,  # No HTML escaping for Markdown
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Default citation format is "api", can be changed to "uri"
        self.citation_format = os.environ.get('THOTH_CITATION_FORMAT', 'api')

        logger.info(
            f'NoteGenerator initialized with templates_dir={templates_dir}, notes_dir={notes_dir}'
        )

    def create_note(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis: AnalysisResponse,
        citations: list[Citation],
    ) -> tuple[str, Path, Path]:
        """
        Create a note from the provided data and rename associated files.

        Args:
            pdf_path: Path to the PDF file.
            markdown_path: Path to the Markdown file.
            analysis: Analysis response containing paper details and content analysis.
            citations: List of citations extracted from the paper.

        Returns:
            tuple[str, Path, Path]: The path to the created note,
                                   the new path to the PDF file,
                                   and the new path to the markdown file.
        """
        logger.info('Creating note from analysis')

        # Find the main article's citation for metadata
        main_citation = next(
            (c for c in citations if getattr(c, 'is_document_citation', False)), None
        )
        if not main_citation and citations:
            main_citation = citations[0]

        title_for_filename = 'Unknown Title'
        if main_citation and main_citation.title:
            title_for_filename = main_citation.title
        elif analysis and analysis.title:
            title_for_filename = analysis.title

        metadata_data = {}  # populated later

        # Ensure metadata_data is populated before this point if it's used for title
        if main_citation:
            metadata_data = {
                'title': main_citation.title,
                'authors': main_citation.authors or [],
                'year': main_citation.year,
                'doi': main_citation.doi,
                'journal': main_citation.journal,
            }
            if main_citation.affiliations:
                metadata_data['affiliations'] = main_citation.affiliations
        else:  # Fallback if no main_citation
            metadata_data = {
                'title': analysis.title
                if analysis
                else 'Unknown Title',  # Use analysis title as fallback
                'authors': analysis.authors.split(', ')
                if analysis and analysis.authors
                else [],
                'year': analysis.year,
                'doi': analysis.doi,
                'journal': analysis.journal,
            }

        title_for_filename = metadata_data.get('title') or 'Unknown Title'

        analysis_dict_data = {}
        if analysis:  # Ensure analysis object exists
            for field_name, field_value in analysis.model_dump().items():
                if field_value is not None and field_name not in [
                    'title',
                    'authors',
                    'affiliations',
                    'year',
                    'doi',
                    'journal',
                ]:
                    analysis_dict_data[field_name] = field_value

            if isinstance(analysis_dict_data.get('key_points'), str):
                analysis_dict_data['key_points'] = analysis_dict_data[
                    'key_points'
                ].splitlines()

        try:
            jinja_template = self.env.get_template('paper_note.md')
            logger.debug(
                'Loaded template from templates/paper_note.md using Jinja2 environment'
            )
        except Exception as e:
            logger.warning(
                f'Template not found or error loading from templates/paper_note.md: {e}, using default template string.'
            )
            default_template_content = self._get_default_template()
            jinja_template = self.env.from_string(default_template_content)

        logger.info(f'Creating note for: {title_for_filename}')

        # Generate the base filename for the note (without extension)
        new_base_filename = self._sanitize_filename(title_for_filename)
        logger.debug(f'Sanitized base filename: {new_base_filename}')
        new_pdf_path = pdf_path
        new_markdown_path = markdown_path
        target_pdf_path = pdf_path.parent / (new_base_filename + pdf_path.suffix)
        target_markdown_path = markdown_path.parent / (
            new_base_filename + markdown_path.suffix
        )
        source_files_data = {
            'pdf': str(target_pdf_path),
            'markdown': str(target_markdown_path),
        }

        data_for_template = {
            'metadata': metadata_data,
            'analysis': analysis_dict_data,
            'citations': citations,
            'source_files': source_files_data,
        }

        note_content = self._format_template(jinja_template, data_for_template)
        note_output_path = self.notes_dir / f'{new_base_filename}.md'
        logger.debug(f'Note output path: {note_output_path}')

        with open(note_output_path, 'w', encoding='utf-8') as f:
            f.write(note_content)
        logger.info(f'Note created successfully at {note_output_path}')

        # --- Rename PDF and Markdown files ---
        if pdf_path and pdf_path.exists():
            try:
                if pdf_path != target_pdf_path:  # Avoid renaming if paths are identical
                    pdf_path.rename(target_pdf_path)
                    new_pdf_path = target_pdf_path
                    logger.info(f'Renamed PDF file to: {new_pdf_path}')
                else:
                    logger.debug(
                        f'PDF path {pdf_path} already matches target. No rename needed.'
                    )
            except OSError as e:
                logger.error(
                    f'Error renaming PDF file {pdf_path} to {target_pdf_path}: {e}'
                )
                # new_pdf_path remains original if rename fails

        if markdown_path and markdown_path.exists():
            try:
                target_markdown_path = markdown_path.parent / (
                    new_base_filename + markdown_path.suffix
                )
                if (
                    markdown_path != target_markdown_path
                ):  # Avoid renaming if paths are identical
                    markdown_path.rename(target_markdown_path)
                    new_markdown_path = target_markdown_path
                    logger.info(f'Renamed Markdown file to: {new_markdown_path}')
                else:
                    logger.debug(
                        f'Markdown path {markdown_path} already matches target. No rename needed.'
                    )
            except OSError as e:
                logger.error(
                    f'Error renaming Markdown file {markdown_path} to {target_markdown_path}: {e}'
                )
                # new_markdown_path remains original if rename fails

        return str(note_output_path), new_pdf_path, new_markdown_path

    def _sanitize_filename(self, title: str) -> str:
        """
        Sanitize a title to be used as a filename.

        Args:
            title: The title to sanitize.

        Returns:
            str: The sanitized filename.
        """
        # Replace spaces with hyphens and remove invalid characters
        filename = re.sub(r'[^\w\s-]', '', title.lower())
        filename = re.sub(r'[\s]+', '-', filename)

        # Limit length
        if len(filename) > 100:
            filename = filename[:100]

        # Remove date prefix for uniqueness
        # date_str = datetime.now().strftime('%Y%m%d') # Removed
        # return f'{date_str}-{filename}' # Removed
        return filename  # Return filename directly

    def _format_template(self, jinja_template: Any, data: dict[str, Any]) -> str:
        """
        Format the template with the provided data using Jinja2.

        Args:
            jinja_template: The loaded Jinja2 template object.
            data: A dictionary containing the data to be included in the note.

        Returns:
            str: The formatted note content.
        """
        logger.debug('Formatting template with data using Jinja2')

        metadata = data.get('metadata', {})
        analysis_content = data.get('analysis', {})
        raw_citations_list = data.get('citations', [])
        raw_source_files_paths = data.get('source_files', {})

        # Prepare citations with generated markdown links
        citations_for_template = []
        if raw_citations_list:
            for cit_obj in raw_citations_list:
                cit_data_dict = cit_obj.model_dump()  # Get dict from Citation model
                logger.debug(f'Citation data dictionary: {cit_data_dict}')
                link_text = cit_obj.formatted or (cit_obj.title or 'N/A')
                markdown_link_for_citation = link_text  # Default to text if no link

                try:
                    # First, try to find the note using the expected path based on title
                    expected_note_path = self._get_expected_citation_note_path(cit_obj)
                    if expected_note_path and expected_note_path.exists():
                        logger.debug(
                            f'Found existing note at expected path: {expected_note_path}'
                        )
                        markdown_link_for_citation = self._create_file_link(
                            str(expected_note_path), link_text
                        )
                    else:
                        # Fallback to the original citation ID-based search
                        citation_id = cit_obj.doi or (
                            cit_obj.backup_id or self._sanitize_filename(cit_obj.text)
                        )
                        obsidian_note_stem = self._find_citation_note(citation_id)
                        if obsidian_note_stem:
                            full_note_path = self.notes_dir / f'{obsidian_note_stem}.md'
                            # Use _create_file_link to generate [[wikilink|text]] or [text](file://...)
                            markdown_link_for_citation = self._create_file_link(
                                str(full_note_path), link_text
                            )
                        elif (
                            cit_obj.url
                            and isinstance(cit_obj.url, str)
                            and cit_obj.url.strip()
                            and (
                                cit_obj.url.startswith('http://')
                                or cit_obj.url.startswith('https://')
                            )
                            and self._is_url_accessible(cit_obj.url)
                        ):  # Prioritize the citation's direct URL
                            uri_target = cit_obj.url
                            markdown_link_for_citation = f'[{link_text}]({uri_target})'
                        elif citation_id:  # Fallback to current API/thoth URI linking
                            uri_target = ''
                            if self.citation_format == 'uri':
                                uri_target = f'thoth://process_citation/{citation_id}'
                            else:
                                # Ensure citation_id is URL-safe if it contains special characters  # noqa: W505
                                safe_citation_id = urllib.parse.quote(str(citation_id))
                                uri_target = f'{self.api_base_url}/process_citation/{safe_citation_id}'
                            markdown_link_for_citation = f'[{link_text}]({uri_target})'
                except Exception as e:
                    logger.error(f'Error processing citation: {e}')

                cit_data_dict['generated_markdown_link'] = markdown_link_for_citation
                citations_for_template.append(cit_data_dict)

        # Prepare context for Jinja2 rendering
        context = {
            'title': metadata.get('title', 'Unknown Title'),
            'authors': metadata.get('authors', []),
            'year': metadata.get('year'),
            'doi': metadata.get('doi'),
            'journal': metadata.get('journal'),
            # Spread analysis content (summary, key_points, abstract, etc.)
            **analysis_content,
            'analysis': analysis_content,
            'citations': citations_for_template,
            'source_files': {
                'pdf_link': self._create_file_link(
                    raw_source_files_paths.get('pdf', ''), 'PDF'
                ),
                'markdown_link': self._create_file_link(
                    raw_source_files_paths.get('markdown', ''), 'Markdown'
                ),
            },
        }

        # Add any other top-level metadata if expected by template
        for key, value in metadata.items():
            if (
                key not in context
            ):  # Avoid overwriting already set items like title, authors
                if key not in [
                    'title',
                    'authors',
                    'year',
                    'doi',
                    'journal',
                    'affiliations',
                ]:  # affiliations might be complex
                    context[key] = value
        if 'affiliations' in metadata:  # Handle affiliations specifically if needed
            context['affiliations'] = metadata['affiliations']

        logger.debug(f'Context for Jinja2: {list(context.keys())}')

        # Render the template with the context
        try:
            note_content = jinja_template.render(context)
        except Exception as e:
            logger.error(f'Error rendering Jinja2 template: {e}')
            logger.error(f'Context keys available during error: {list(context.keys())}')
            # Fallback or re-raise
            return f'Error rendering template: {e}'

        return note_content

    def _create_file_link(self, file_path: str, file_type: str) -> str:
        """
        Create an Obsidian-compatible link to a file.

        Args:
            file_path (str): Path to the file.
            file_type (str): Type of file (PDF, Markdown, etc.).

        Returns:
            str: Formatted link to the file.
        """
        if not file_path:
            logger.warning(f'No {file_type} file path provided')
            return f'No {file_type} file available'

        # Convert to Path object for manipulation
        path = Path(file_path)

        # Check if the file exists
        if not path.exists():
            logger.warning(f'File not found: {path}')

        # Get the filename
        filename = path.name

        # Create a relative path from the notes directory to the file
        try:
            # Try to create a relative path from notes_dir to the file
            rel_path = path.relative_to(self.notes_dir)
            # Use Obsidian's file link format
            logger.debug(f'Created relative link for {file_type} file: {rel_path}')
            return f'[[{rel_path}|{filename}]]'
        except ValueError:
            # If the file is not relative to notes_dir, use an absolute path
            # This is less ideal but will work if the file is outside the vault
            logger.debug(
                f'Created absolute link for {file_type} file: {path.absolute()}'
            )
            return f'[{filename}](file://{path.absolute()})'

    def _find_citation_note(self, note_stem: str) -> str | None:
        """
        Find an existing note for a citation by searching for the citation ID in note filenames.

        Args:
            citation_id (str): The citation ID to search for.

        Returns:
            Optional[str]: The path to the note if found, None otherwise.
        """  # noqa: W505
        logger.debug(f'Searching for note with citation ID: {note_stem}')

        # This is a simple implementation that looks for the citation ID in filenames
        # A more sophisticated approach might search within note content
        for note_file in self.notes_dir.glob('*.md'):
            logger.debug(f'Checking note file: {note_file}')
            logger.debug(f'Note file stem: {note_file.stem}')
            logger.debug(f'Citation ID: {note_stem}')
            if note_stem in note_file.stem:
                # Return the relative path from the notes directory
                logger.debug(
                    f'Found note for citation ID {note_stem}: {note_file.stem}'
                )
                return note_file.stem

        logger.debug(f'No note found for citation ID: {note_stem}')
        return None

    def _get_default_template(self) -> str:
        """
        Get a default template if none is found.

        Returns:
            str: The default template content.
        """
        logger.debug('Using default template')
        return """${frontmatter}
# ${title}

## Summary
${summary}

## Key Points
${key_points}

## Methodology
${methodology}

## Results
${results}

## Limitations
${limitations}

## Citations
${citations}

## Source
${source_files}
"""

    def create_basic_note(
        self, metadata: dict[str, Any], pdf_path: Path, markdown_path: Path
    ) -> str:
        """
        Create a basic note with just metadata when LLM processing fails.

        Args:
            metadata (Dict[str, Any]): Paper metadata.
            pdf_path (Path): Path to the PDF file.
            markdown_path (Path): Path to the Markdown file.

        Returns:
            str: Path to the generated note file.
        """
        logger.info('Creating basic note with metadata only')

        # Create a minimal AnalysisResponse
        title = metadata.get('title', 'Unknown Title')
        authors = ', '.join(metadata.get('authors', []))
        abstract = metadata.get('abstract', '')

        analysis = AnalysisResponse(
            title=title,
            authors=authors,
            abstract=abstract,
            summary='Note: LLM processing failed. Basic note created.',
        )

        # Create an empty citations list
        citations = []

        # Use the main create_note method
        return self.create_note(pdf_path, markdown_path, analysis, citations)

    def _validate_content(self, content: dict[str, Any]) -> None:
        """
        Validate that the content contains required fields.

        Args:
            content (Dict[str, Any]): Content to validate.

        Raises:
            ValueError: If required fields are missing.
        """
        logger.debug('Validating content')

        required_fields = ['title', 'authors']
        missing_fields = [field for field in required_fields if field not in content]

        if missing_fields:
            error_msg = f'Missing required fields: {", ".join(missing_fields)}'
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Ensure source_files is present
        if 'source_files' not in content:
            error_msg = 'Missing source_files in content'
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Ensure source_files contains pdf and markdown
        source_files = content['source_files']
        if not isinstance(source_files, dict):
            error_msg = 'source_files must be a dictionary'
            logger.error(error_msg)
            raise ValueError(error_msg)

        missing_source_files = [
            field for field in ['pdf', 'markdown'] if field not in source_files
        ]

        if missing_source_files:
            error_msg = (
                f'Missing required source files: {", ".join(missing_source_files)}'
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug('Content validation successful')

    def _get_note_filename(self, content: dict[str, Any]) -> str:
        """
        Generate a filename for the note based on content metadata.

        Args:
            content (Dict[str, Any]): Content with metadata.

        Returns:
            str: Generated filename.
        """
        # Use title for filename, with fallback
        title = content.get('title', 'Unknown Title')

        # Add year if available
        year = content.get('year')
        if year:
            filename = f'{year} - {title}.md'
        else:
            filename = f'{title}.md'

        # Clean filename
        filename = self._clean_filename(filename)

        logger.debug(f'Generated filename: {filename}')
        return filename

    def _clean_filename(self, filename: str) -> str:
        """
        Clean a filename to ensure it's valid.

        Args:
            filename (str): Original filename.

        Returns:
            str: Cleaned filename.
        """
        # Replace invalid characters
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Limit length
        if len(filename) > 255:
            base, ext = filename.rsplit('.', 1)
            filename = f'{base[:250]}.{ext}'

        return filename

    def _get_expected_citation_note_path(self, citation: Citation) -> Path | None:
        """
        Get the expected note path for a citation based on its title.

        This method predicts what the note filename would be for a citation
        if it were processed as a main document, using the same naming
        convention as the main note generation.

        Args:
            citation: Citation object to get expected path for.

        Returns:
            Path | None: Expected full path to the citation's note if it has a title,
                        None otherwise.
        """
        if not citation.title:
            logger.debug(f'Citation has no title, cannot predict note path: {citation}')
            return None

        # Use the same sanitization logic as the main note generation
        sanitized_title = self._sanitize_filename(citation.title)
        expected_note_path = self.notes_dir / f'{sanitized_title}.md'

        logger.debug(
            f'Predicted note path for citation "{citation.title}": {expected_note_path}'
        )
        return expected_note_path

    def _is_url_accessible(self, url: str, timeout: float = 3.0) -> bool:
        """
        Check if a URL is accessible by sending a HEAD request.

        Args:
            url (str): The URL to check.
            timeout (float): Timeout in seconds for the request (default is 3.0).

        Returns:
            bool: True if the URL is reachable (status code 200-399 or 429), False
                otherwise.

        Notes:
            HTTP 429 (rate limit) is considered accessible, as are all 2xx/3xx
            responses. Only 4xx/5xx errors except 429 are considered inaccessible.

        Example:
            >>> self._is_url_accessible('https://example.com')
            True
        """
        try:
            response = requests.head(url, allow_redirects=True, timeout=timeout)
            # Accept 2xx, 3xx, and 429 (rate limit) as accessible
            if 200 <= response.status_code < 400 or response.status_code == 429:
                return True
            return False
        except requests.RequestException as exc:
            logger.warning(f'URL not accessible: {url} ({exc})')
            return False
