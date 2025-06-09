"""
Tests for NoteService.

Tests the note generation and file management functionality.
"""

import pytest

from thoth.services.note_service import NoteService
from thoth.utilities.config import ThothConfig
from thoth.utilities.schemas import AnalysisResponse, Citation


@pytest.fixture
def note_service(thoth_config: ThothConfig, temp_workspace):
    """Create a NoteService instance for testing."""
    # Ensure the directories exist for the test
    (temp_workspace / 'notes').mkdir(exist_ok=True)
    (temp_workspace / 'pdfs').mkdir(exist_ok=True)
    (temp_workspace / 'markdown').mkdir(exist_ok=True)

    return NoteService(
        config=thoth_config,
        notes_dir=temp_workspace / 'notes',
        pdf_dir=temp_workspace / 'pdfs',
        markdown_dir=temp_workspace / 'markdown',
    )


def test_create_note_moves_files(note_service, temp_workspace):
    """Test that create_note moves and renames files to the correct directories."""
    # Create dummy source files
    pdf_dir = temp_workspace / 'source_pdfs'
    pdf_dir.mkdir()
    source_pdf = pdf_dir / 'original_paper.pdf'
    source_pdf.touch()

    md_dir = temp_workspace / 'source_markdown'
    md_dir.mkdir()
    source_md = md_dir / 'original_paper.md'
    source_md.touch()

    # Mock analysis and citation data
    analysis = AnalysisResponse(
        title='A Test Paper', summary='A summary.', key_points='A key point.'
    )
    doc_citation = Citation(title='A Test Paper', year=2023, is_document_citation=True)

    # Call the create_note method
    note_path, final_pdf_path, final_markdown_path = note_service.create_note(
        pdf_path=source_pdf,
        markdown_path=source_md,
        analysis=analysis,
        citations=[doc_citation],
    )

    # Assert that the final files are in the correct directories
    assert note_path.parent.name == 'notes'
    assert final_pdf_path.parent.name == 'pdfs'
    assert final_markdown_path.parent.name == 'markdown'

    # Assert that the files have been renamed
    assert 'A-Test-Paper' in note_path.stem
    assert 'A-Test-Paper' in final_pdf_path.stem
    assert 'A-Test-Paper' in final_markdown_path.stem
    assert final_markdown_path.stem.endswith('_markdown')

    # Assert that the original files are gone
    assert not source_pdf.exists()
    assert not source_md.exists()
