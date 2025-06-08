"""
Note service for managing note generation and formatting.

This module consolidates all note-related operations including
note creation, formatting, and linking.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from thoth.services.base import BaseService, ServiceError
from thoth.utilities.schemas import AnalysisResponse, Citation


class NoteService(BaseService):
    """
    Service for managing note generation and formatting.

    This service consolidates:
    - Note template rendering
    - Note file creation
    - Citation linking
    - Note formatting and structure
    """

    def __init__(
        self,
        config=None,
        templates_dir: Path | None = None,
        notes_dir: Path | None = None,
        api_base_url: str | None = None,
    ):
        """
        Initialize the NoteService.

        Args:
            config: Optional configuration object
            templates_dir: Directory containing templates
            notes_dir: Directory for saving notes
            api_base_url: Base URL for API links
        """
        super().__init__(config)
        self.templates_dir = Path(templates_dir or self.config.templates_dir)
        self.notes_dir = Path(notes_dir or self.config.notes_dir)
        self.api_base_url = api_base_url or self.config.api_server_config.base_url

        # Ensure directories exist
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._notes_cache: dict[str, Path] = {}

    def initialize(self) -> None:
        """Initialize the note service."""
        self.logger.info('Note service initialized')

    def create_note(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis: AnalysisResponse,
        citations: list[Citation],
        template_name: str = 'obsidian_note.md',
    ) -> tuple[Path, Path, Path]:
        """
        Create a formatted note from analysis and citations.

        Args:
            pdf_path: Path to the PDF file
            markdown_path: Path to the markdown file
            analysis: Analysis results
            citations: Extracted citations
            template_name: Template to use for rendering

        Returns:
            tuple[Path, Path, Path]: Paths to (note, pdf, markdown)

        Raises:
            ServiceError: If note creation fails
        """
        try:
            self.validate_input(
                pdf_path=pdf_path,
                markdown_path=markdown_path,
                analysis=analysis,
            )

            # Prepare content for template
            content = self._prepare_content(analysis, citations)

            # Generate note filename
            note_filename = self._generate_note_filename(content)
            note_path = self.notes_dir / note_filename

            # Move files to notes directory
            final_pdf_path = self._move_file_to_notes(pdf_path, content['title'])
            final_markdown_path = self._move_file_to_notes(
                markdown_path, content['title'], suffix='_markdown'
            )

            # Update content with final paths
            content['pdf_link'] = self._create_file_link(final_pdf_path, 'PDF')
            content['markdown_link'] = self._create_file_link(
                final_markdown_path, 'Markdown'
            )

            # Render template
            template = self.jinja_env.get_template(template_name)
            note_content = template.render(**content)

            # Write note
            note_path.write_text(note_content, encoding='utf-8')

            self.log_operation(
                'note_created',
                note=str(note_path),
                pdf=str(final_pdf_path),
                markdown=str(final_markdown_path),
            )

            return note_path, final_pdf_path, final_markdown_path

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'creating note')) from e

    def create_basic_note(
        self,
        metadata: dict[str, Any],
        pdf_path: Path,
        markdown_path: Path,
    ) -> Path:
        """
        Create a basic note with minimal metadata.

        Args:
            metadata: Basic metadata for the note
            pdf_path: Path to PDF file
            markdown_path: Path to markdown file

        Returns:
            Path: Path to the created note

        Raises:
            ServiceError: If note creation fails
        """
        try:
            # Prepare basic content
            content = {
                'title': metadata.get('title', 'Untitled'),
                'abstract': metadata.get('abstract', 'No abstract available'),
                'tags': metadata.get('tags', []),
                'pdf_link': self._create_file_link(pdf_path, 'PDF'),
                'markdown_link': self._create_file_link(markdown_path, 'Markdown'),
            }

            # Generate filename
            note_filename = self._generate_note_filename(content)
            note_path = self.notes_dir / note_filename

            # Create basic note content
            note_content = f"""# {content['title']}

## Abstract
{content['abstract']}

## Links
- {content['pdf_link']}
- {content['markdown_link']}

## Tags
{', '.join(f'#{tag}' for tag in content['tags'])}
"""

            # Write note
            note_path.write_text(note_content, encoding='utf-8')

            self.log_operation('basic_note_created', note=str(note_path))

            return note_path

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'creating basic note')) from e

    def _prepare_content(
        self,
        analysis: AnalysisResponse,
        citations: list[Citation],
    ) -> dict[str, Any]:
        """Prepare content dictionary for template rendering."""
        # Extract document citation
        document_citation = next((c for c in citations if c.is_document_citation), None)

        # Format authors
        if document_citation and document_citation.authors:
            authors = ', '.join(document_citation.authors)
        else:
            authors = 'Unknown'

        # Clean title
        title = self._clean_title(
            document_citation.title if document_citation else 'Untitled'
        )

        # Format citations
        reference_citations = [c for c in citations if not c.is_document_citation]
        formatted_citations = self._format_citations_for_note(reference_citations)

        # Build content
        content = {
            'title': title,
            'authors': authors,
            'year': document_citation.year if document_citation else 'Unknown',
            'doi': document_citation.doi if document_citation else None,
            'abstract': analysis.abstract or 'No abstract available',
            'summary': analysis.summary or 'No summary available',
            'key_points': self._format_key_points(analysis.key_points),
            'objectives': analysis.objectives,
            'methodology': analysis.methodology,
            'data': analysis.data,
            'experimental_setup': analysis.experimental_setup,
            'evaluation_metrics': analysis.evaluation_metrics,
            'results': analysis.results,
            'discussion': analysis.discussion,
            'strengths': analysis.strengths,
            'limitations': analysis.limitations,
            'future_work': analysis.future_work,
            'related_work': analysis.related_work,
            'tags': [f'#{tag}' for tag in (analysis.tags or [])],
            'citations': formatted_citations,
            'citation_count': len(reference_citations),
        }

        return content

    def _format_citations_for_note(
        self, citations: list[Citation]
    ) -> list[dict[str, Any]]:
        """Format citations for display in the note."""
        formatted = []

        for i, citation in enumerate(citations, 1):
            # Find existing note if available
            obsidian_link = self._find_citation_note(citation)

            formatted_citation = {
                'number': i,
                'text': citation.text or 'No citation text',
                'title': citation.title or 'Untitled',
                'authors': ', '.join(citation.authors)
                if citation.authors
                else 'Unknown',
                'year': citation.year or 'Unknown',
                'doi': citation.doi,
                'url': citation.url,
                'obsidian_link': obsidian_link,
            }
            formatted.append(formatted_citation)

        return formatted

    def _find_citation_note(self, citation: Citation) -> str | None:
        """Find if a note exists for a citation."""
        if not citation.title:
            return None

        # Clean title for matching
        clean_title = self._clean_filename(citation.title)

        # Search for matching notes
        for note_file in self.notes_dir.glob('*.md'):
            if clean_title.lower() in note_file.stem.lower():
                return f'[[{note_file.stem}]]'

        return None

    def _create_file_link(self, file_path: Path, link_text: str) -> str:
        """Create a link to a file."""
        if self.api_base_url:
            # Create API link
            if 'PDF' in link_text:
                endpoint = 'download-pdf'
            else:
                endpoint = 'view-markdown'

            return f'[{link_text}]({self.api_base_url}/{endpoint}?path={file_path})'
        else:
            # Create local file link
            return f'[{link_text}](file://{file_path})'

    def _move_file_to_notes(
        self, source_path: Path, title: str, suffix: str = ''
    ) -> Path:
        """Move a file to the notes directory with a clean name."""
        clean_title = self._clean_filename(title)
        extension = source_path.suffix

        # Generate target filename
        target_filename = f'{clean_title}{suffix}{extension}'
        target_path = self.notes_dir / target_filename

        # Ensure unique filename
        counter = 1
        while target_path.exists():
            target_filename = f'{clean_title}{suffix}_{counter}{extension}'
            target_path = self.notes_dir / target_filename
            counter += 1

        # Move file
        import shutil

        shutil.move(str(source_path), str(target_path))

        return target_path

    def _generate_note_filename(self, content: dict[str, Any]) -> str:
        """Generate a filename for the note."""
        title = content.get('title', 'Untitled')
        clean_title = self._clean_filename(title)
        return f'{clean_title}.md'

    def _clean_title(self, title: str) -> str:
        """Clean a title for use in notes."""
        if not title:
            return 'Untitled'

        # Remove special characters but keep some punctuation
        import re

        cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
        cleaned = cleaned.strip()

        return cleaned if cleaned else 'Untitled'

    def _clean_filename(self, filename: str) -> str:
        """Clean a filename to be filesystem-safe."""
        import re

        # Remove all non-alphanumeric characters except spaces and dashes
        cleaned = re.sub(r'[^a-zA-Z0-9\s\-]', '', filename)
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', cleaned)
        # Replace spaces with underscores
        cleaned = cleaned.replace(' ', '_')
        # Limit length
        cleaned = cleaned[:100]

        return cleaned.strip('_') or 'untitled'

    def _format_key_points(self, key_points: str | None) -> list[str]:
        """Format key points as a list."""
        if not key_points:
            return []

        # Split by newlines and clean
        points = [p.strip() for p in key_points.split('\n') if p.strip()]

        # Remove bullet point markers if present
        cleaned_points = []
        for point in points:
            # Remove common bullet markers
            point = point.lstrip('•·-*▪▸►◆◇○●')
            point = point.strip()
            if point:
                cleaned_points.append(point)

        return cleaned_points

    def get_note_statistics(self) -> dict[str, Any]:
        """
        Get statistics about notes.

        Returns:
            dict[str, Any]: Note statistics
        """
        try:
            note_files = list(self.notes_dir.glob('*.md'))

            stats = {
                'total_notes': len(note_files),
                'notes_directory': str(self.notes_dir),
                'templates_directory': str(self.templates_dir),
                'api_base_url': self.api_base_url,
                'recent_notes': [],
            }

            # Get recent notes
            note_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            for note_file in note_files[:5]:
                stats['recent_notes'].append(
                    {
                        'name': note_file.name,
                        'size': note_file.stat().st_size,
                        'modified': note_file.stat().st_mtime,
                    }
                )

            return stats

        except Exception as e:
            self.logger.error(self.handle_error(e, 'getting note statistics'))
            return {}
