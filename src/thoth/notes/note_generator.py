"""
Note generator module for Thoth.

This module handles the generation of Obsidian notes from processed content.
"""

import os
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

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
    ) -> str:
        """
        Create a note from the provided data.

        Args:
            pdf_path: Path to the PDF file
            markdown_path: Path to the Markdown file
            analysis: Analysis response containing paper details and content analysis
            citations: List of citations extracted from the paper

        Returns:
            str: The path to the created note.
        """
        logger.info('Creating note from analysis')

        pdf_path_str = str(pdf_path) if pdf_path else ''
        markdown_path_str = str(markdown_path) if markdown_path else ''

        source_files_data = {'pdf': pdf_path_str, 'markdown': markdown_path_str}

        metadata_data = {
            'title': analysis.title,
            'authors': (
                analysis.authors.split(', ')
                if isinstance(analysis.authors, str)
                else (analysis.authors if analysis.authors else [])
            ),  # Ensure authors is a list
            'year': (
                analysis.year if hasattr(analysis, 'year') else None
            ),  # Assuming AnalysisResponse might have these
            'doi': analysis.doi if hasattr(analysis, 'doi') else None,
            'journal': analysis.journal if hasattr(analysis, 'journal') else None,
        }
        if analysis.affiliations:
            metadata_data['affiliations'] = analysis.affiliations

        analysis_dict_data = {}
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

        # Ensure key_points is a list of strings if it's a string with newlines
        if isinstance(analysis_dict_data.get('key_points'), str):
            analysis_dict_data['key_points'] = analysis_dict_data[
                'key_points'
            ].splitlines()

        data_for_template = {
            'metadata': metadata_data,
            'analysis': analysis_dict_data,
            'citations': citations,  # Pass raw citations, linking logic will be in _format_template
            'source_files': source_files_data,
        }

        try:
            jinja_template = self.env.get_template('paper_note.md')
            logger.debug(
                'Loaded template from templates/paper_note.md using Jinja2 environment'
            )
        except Exception as e:  # Catch Jinja's TemplateNotFound or other errors
            logger.warning(
                f'Template not found or error loading from templates/paper_note.md: {e}, using default template string.'
            )
            default_template_content = self._get_default_template()
            jinja_template = self.env.from_string(default_template_content)

        title = analysis.title or 'Unknown Title'
        logger.info(f'Creating note for: {title}')

        filename = self._sanitize_filename(title)
        logger.debug(f'Sanitized filename: {filename}')

        note_content = self._format_template(jinja_template, data_for_template)

        output_path = self.notes_dir / f'{filename}.md'
        logger.debug(f'Output path: {output_path}')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(note_content)

        logger.info(f'Note created successfully at {output_path}')
        return str(output_path)

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

        # Add date prefix for uniqueness
        date_str = datetime.now().strftime('%Y%m%d')
        return f'{date_str}-{filename}'

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
                    elif citation_id:
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
            return f'{file_type} file not found: {path.name}'

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

    def _find_citation_note(self, citation_id: str) -> str | None:
        """
        Find an existing note for a citation by searching for the citation ID in note filenames.

        Args:
            citation_id (str): The citation ID to search for.

        Returns:
            Optional[str]: The path to the note if found, None otherwise.
        """  # noqa: W505
        logger.debug(f'Searching for note with citation ID: {citation_id}')

        # This is a simple implementation that looks for the citation ID in filenames
        # A more sophisticated approach might search within note content
        for note_file in self.notes_dir.glob('*.md'):
            logger.debug(f'Checking note file: {note_file}')
            logger.debug(f'Note file stem: {note_file.stem}')
            logger.debug(f'Citation ID: {citation_id}')
            if citation_id in note_file.stem:
                # Return the relative path from the notes directory
                logger.debug(
                    f'Found note for citation ID {citation_id}: {note_file.stem}'
                )
                return note_file.stem

        logger.debug(f'No note found for citation ID: {citation_id}')
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
