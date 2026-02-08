"""
Note service for managing note generation and formatting.

This module consolidates all note-related operations including
note creation, formatting, and linking.
"""

import os
import re
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
        pdf_dir: Path | None = None,
        markdown_dir: Path | None = None,
        api_base_url: str | None = None,
    ):
        """
        Initialize the NoteService.

        Args:
            config: Optional configuration object
            templates_dir: Directory containing templates
            notes_dir: Directory for saving notes
            pdf_dir: Directory for storing PDFs
            markdown_dir: Directory for storing markdown files
            api_base_url: Base URL for API links
        """
        super().__init__(config)
        self.templates_dir = Path(templates_dir or self.config.templates_dir)
        self.notes_dir = Path(notes_dir or self.config.notes_dir)
        self.pdf_dir = Path(pdf_dir or self.config.pdf_dir)
        self.markdown_dir = Path(markdown_dir or self.config.markdown_dir)
        self.api_base_url = (
            api_base_url
            or f'http://{self.config.servers_config.api.host}:{self.config.servers_config.api.port}'
        )

        # Ensure directories exist
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Use LRUCache with bounded size to prevent unbounded memory growth
        # Limits cache to 500 most recently used notes
        from cachetools import LRUCache

        self._notes_cache: LRUCache = LRUCache(maxsize=500)

    def _get_markdown_content(self, title: str, markdown_path: Path) -> str:  # noqa: ARG002
        """Get markdown content from PostgreSQL."""
        import asyncpg  # noqa: I001
        import asyncio

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def fetch():
            conn = await asyncpg.connect(db_url)
            try:
                result = await conn.fetchval(
                    'SELECT markdown_content FROM papers WHERE title = $1', title
                )
                return result or ''
            finally:
                await conn.close()

        # Use asyncio.run() to handle event loop creation in background threads
        try:
            content = asyncio.run(fetch())
        except RuntimeError as e:
            # Fallback only if there's already a running loop in this thread
            # (this happens when called from async context)
            if 'asyncio.run() cannot be called from a running event loop' in str(e):
                # We're in an async context - run in a separate thread to avoid blocking
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, fetch())
                    content = future.result()
            else:
                raise

        self.logger.debug(f'Loaded markdown from PostgreSQL for: {title}')
        return content

    def _save_markdown_to_postgres(
        self,
        title: str,
        markdown_content: str,
        pdf_path: str,
        note_path: str,
        markdown_path: str = None,
    ) -> None:
        """Update markdown content and file paths in PostgreSQL.

        Updates processed_papers table (via paper_metadata lookup),
        since 'papers' is a VIEW and cannot be directly updated.
        """
        import asyncpg  # noqa: I001
        import asyncio

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def save():
            conn = await asyncpg.connect(db_url)
            try:
                # First get the paper_id from paper_metadata
                # Try exact match first, then normalized match (hyphens -> spaces)
                paper_id = await conn.fetchval(
                    'SELECT id FROM paper_metadata WHERE LOWER(title) = LOWER($1)',
                    title,
                )

                # If not found, try with normalized title (replace hyphens with spaces)
                if paper_id is None:
                    normalized_title = title.replace('-', ' ').replace(',', '')
                    paper_id = await conn.fetchval(
                        "SELECT id FROM paper_metadata WHERE LOWER(REPLACE(title, '-', ' ')) = LOWER($1)",
                        normalized_title,
                    )

                # Also try matching against title_normalized column
                if paper_id is None:
                    paper_id = await conn.fetchval(
                        'SELECT id FROM paper_metadata WHERE title_normalized = LOWER($1)',
                        title.replace('-', ' ').replace(',', '').lower(),
                    )

                if paper_id:
                    # Update or insert processed_papers
                    result = await conn.execute(
                        """
                        INSERT INTO processed_papers
                            (paper_id, markdown_content, pdf_path, note_path, markdown_path, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                        ON CONFLICT (paper_id) DO UPDATE SET
                            markdown_content = EXCLUDED.markdown_content,
                            pdf_path = EXCLUDED.pdf_path,
                            note_path = EXCLUDED.note_path,
                            markdown_path = EXCLUDED.markdown_path,
                            updated_at = NOW()
                        """,
                        paper_id,
                        markdown_content,
                        pdf_path,
                        note_path,
                        markdown_path,
                    )
                    rows_affected = int(result.split()[-1]) if result else 0
                    if rows_affected > 0:
                        self.logger.info(f'Updated paths in PostgreSQL for: {title}')
                    else:
                        self.logger.warning(f'No rows affected for: {title}')
                else:
                    self.logger.warning(f'Paper not found in database: {title}')
            finally:
                await conn.close()

        # Use asyncio.run() to handle event loop creation in background threads
        try:
            asyncio.run(save())
        except RuntimeError as e:
            # Fallback only if there's already a running loop in this thread
            # (this happens when called from async context)
            if 'asyncio.run() cannot be called from a running event loop' in str(e):
                # We're in an async context - run in a separate thread to avoid blocking
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, save())
                    future.result()
            else:
                raise

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
            # Handle dict analysis (from some callers that serialize it)
            if isinstance(analysis, dict):
                from thoth.utilities.schemas import AnalysisResponse

                analysis = AnalysisResponse(**analysis)

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
            note_stem = note_path.stem

            # Rename PDF and Markdown files to match note title (keep in same directory)
            import shutil

            # Keep PDF in its original directory, just rename it
            final_pdf_path = pdf_path.parent / f'{note_stem}{pdf_path.suffix}'
            if pdf_path.exists() and pdf_path != final_pdf_path:
                shutil.move(str(pdf_path), str(final_pdf_path))

            # Try to read markdown content from PostgreSQL first, then file
            markdown_content = self._get_markdown_content(
                content.get('title'), markdown_path
            )

            # Keep markdown in its original directory, just rename it
            final_markdown_path = (
                markdown_path.parent / f'{note_stem}_markdown{markdown_path.suffix}'
            )
            if markdown_path.exists() and markdown_path != final_markdown_path:
                shutil.move(str(markdown_path), str(final_markdown_path))

            # Update content with final paths and correct link formats
            content['source_files'] = {
                'pdf_link': self._create_file_link(final_pdf_path, final_pdf_path.name),
                'markdown_link': self._create_file_link(
                    final_markdown_path, final_markdown_path.name
                ),
            }

            # Render template
            template = self.jinja_env.get_template(template_name)
            note_content = template.render(**content)

            # Remove redundant title header from note content
            note_content = re.sub(r'^# .*\n\n?', '', note_content, count=1)

            # Write note
            note_path.write_text(note_content, encoding='utf-8')

            # Save markdown content to PostgreSQL
            self._save_markdown_to_postgres(
                content.get('title'),
                markdown_content,
                str(final_pdf_path),
                str(note_path),
                str(final_markdown_path),
            )

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
                'title': self._clean_title(metadata.get('title', 'Untitled')),
                'abstract': metadata.get('abstract', 'No abstract available'),
                'tags': metadata.get('tags', []),
                'pdf_link': self._create_file_link(pdf_path, pdf_path.name),
                'markdown_link': self._create_file_link(
                    markdown_path, markdown_path.name
                ),
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

        # Prioritize document_citation for metadata, fallback to analysis object
        title = self._clean_title(
            (
                document_citation.title
                if document_citation and document_citation.title
                else None
            )
            or (analysis.title if analysis and analysis.title else None)
            or 'Untitled'
        )

        authors_list = (
            (
                document_citation.authors
                if document_citation and document_citation.authors
                else None
            )
            or (analysis.authors if analysis and analysis.authors else None)
            or []
        )
        authors = ', '.join(authors_list) if authors_list else 'Unknown'

        year = (
            (
                document_citation.year
                if document_citation and document_citation.year
                else None
            )
            or (analysis.year if analysis and analysis.year else None)
            or 'Unknown'
        )
        doi = (
            document_citation.doi
            if document_citation and document_citation.doi
            else None
        ) or (analysis.doi if analysis and analysis.doi else None)
        journal = (
            document_citation.journal
            if document_citation and document_citation.journal
            else None
        ) or (analysis.journal if analysis and analysis.journal else None)

        # Format citations
        reference_citations = [c for c in citations if not c.is_document_citation]
        formatted_citations = self._format_citations_for_note(reference_citations)

        # Build content
        content = {
            'title': title,
            'authors': authors,
            'year': year,
            'doi': doi,
            'journal': journal,
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
            'tags': [f'{tag}' for tag in (analysis.tags or [])],
            'citations': formatted_citations,
            'citation_count': len(reference_citations),
            'analysis': analysis.model_dump()
            if hasattr(analysis, 'model_dump')
            else analysis.__dict__,
        }

        return content

    def _format_citations_for_note(
        self, citations: list[Citation]
    ) -> list[dict[str, Any]]:
        """
        Format citations for display in the note.

        This method prepares the full citation data for the template,
        including finding links to existing Obsidian notes.
        """
        formatted = []

        for i, citation in enumerate(citations, 1):
            # Convert citation to dict to pass all data to template
            citation_data = (
                citation.model_dump()
                if hasattr(citation, 'model_dump')
                else citation.__dict__
            )

            # Find existing note if available and add it to the data
            obsidian_link = self._find_citation_note(citation)
            citation_data['obsidian_link'] = obsidian_link
            citation_data['number'] = i

            formatted.append(citation_data)

        return formatted

    def _find_citation_note(self, citation: Citation) -> str | None:
        """Find if a note exists for a citation."""
        if not citation.title:
            return None

        # Clean title for matching
        clean_title = self._clean_filename(citation.title)

        # Search for matching notes
        for note_file in self.notes_dir.glob('*.md'):
            if clean_title.lower() == note_file.stem.lower():
                return f'[[{note_file.stem}]]'

        return None

    def _create_file_link(self, file_path: Path, link_text: str) -> str:
        """Create a relative Obsidian wikilink."""
        if not file_path or not file_path.exists():
            return f'{link_text} file not found.'

        try:
            # Create a relative path from the notes directory to the file.
            rel_path = os.path.relpath(file_path, self.notes_dir)
            # Obsidian uses forward slashes for paths.
            rel_path = rel_path.replace(os.path.sep, '/')
            return f'[[{rel_path}|{link_text}]]'
        except ValueError:
            # Fallback for when a relative path cannot be created
            # (e.g. different drives)
            return f'[{link_text}](file:///{file_path.resolve()})'

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
        cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
        cleaned = cleaned.strip()
        cleaned = cleaned.title()

        return cleaned if cleaned else 'Untitled'

    def _clean_filename(self, filename: str) -> str:
        """Clean a filename to be filesystem-safe."""
        import re

        # Remove all non-alphanumeric characters except spaces and dashes
        cleaned = re.sub(r'[^a-zA-Z0-9\s\-]', '', filename)
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', cleaned)
        # Replace spaces with hyphens for better readability in URLs/filenames
        cleaned = cleaned.replace(' ', '-')
        # Limit length
        cleaned = cleaned[:100]

        return cleaned.strip('-') or 'untitled'

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

    def health_check(self) -> dict[str, str]:
        """Basic health status for the NoteService."""
        return super().health_check()
