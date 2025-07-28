"""
Tests for ThothPipeline.

Tests the main pipeline orchestration functionality.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.pipeline import ThothPipeline


class TestThothPipeline:
    """Test suite for ThothPipeline."""

    @pytest.fixture
    def pipeline(self, mock_config, temp_workspace):  # noqa: ARG002
        """Create a ThothPipeline instance for testing."""
        # Create a minimal pipeline without needing all the config
        # We'll mock the services to avoid initialization issues
        with patch('thoth.pipeline.ServiceManager') as mock_service_manager:
            with patch('thoth.pipeline.CitationGraph') as mock_tracker:
                # Mock the service manager
                mock_services = MagicMock()
                mock_service_manager.return_value = mock_services

                # Create pipeline
                pipeline = ThothPipeline(
                    output_dir=temp_workspace / 'output',
                    notes_dir=temp_workspace / 'notes',
                )

                # Replace with mocked components
                pipeline.services = mock_services
                pipeline.citation_tracker = mock_tracker.return_value

                return pipeline

    def test_process_pdf_success(
        self,
        pipeline,
        sample_pdf_path,
        sample_analysis_response,
        sample_citations,
        temp_workspace,
    ):
        """Test successful PDF processing through pipeline."""
        # Mock service responses
        with patch.object(pipeline.services.processing, 'ocr_convert') as mock_ocr:
            with patch.object(
                pipeline.services.processing, 'analyze_document'
            ) as mock_analyze:
                with patch.object(
                    pipeline.services.citation, 'extract_citations'
                ) as mock_citations:
                    with patch.object(
                        pipeline.services.note, 'create_note'
                    ) as mock_note:
                        with patch.object(
                            pipeline.citation_tracker, 'process_citations'
                        ) as mock_process_citations:
                            with patch.object(
                                pipeline.citation_tracker, 'update_article_file_paths'
                            ) as mock_update_paths:  # noqa: F841
                                # Mock OCR result
                                markdown_path = (
                                    temp_workspace / 'markdown' / 'sample.md'
                                )
                                no_images_path = (
                                    temp_workspace / 'markdown' / 'sample_no_images.md'
                                )
                                mock_ocr.return_value = (markdown_path, no_images_path)

                                # Mock analysis
                                mock_analyze.return_value = sample_analysis_response

                                # Mock citations
                                mock_citations.return_value = sample_citations

                                # Mock note creation
                                note_path = temp_workspace / 'notes' / 'sample_note.md'
                                final_pdf_path = temp_workspace / 'notes' / 'sample.pdf'
                                final_markdown_path = (
                                    temp_workspace / 'notes' / 'sample_markdown.md'
                                )
                                mock_note.return_value = (
                                    note_path,
                                    final_pdf_path,
                                    final_markdown_path,
                                )

                                # Mock citation tracker
                                mock_process_citations.return_value = 'article-123'

                                # Process PDF
                                result_note, result_pdf, result_markdown = (
                                    pipeline.process_pdf(sample_pdf_path)
                                )

                                assert result_note == note_path
                                assert result_pdf == final_pdf_path
                                assert result_markdown == final_markdown_path
                                mock_ocr.assert_called_once()
                                mock_analyze.assert_called_once()
                                mock_citations.assert_called_once()
                                mock_note.assert_called_once()

    def test_process_pdf_failure(self, pipeline, sample_pdf_path):
        """Test PDF processing failure handling."""
        with patch.object(pipeline.services.processing, 'ocr_convert') as mock_ocr:
            # Mock OCR failure
            mock_ocr.side_effect = Exception('OCR failed')

            # Process PDF should raise exception
            with pytest.raises(Exception) as exc_info:
                pipeline.process_pdf(sample_pdf_path)

            assert 'OCR conversion failed' in str(exc_info.value)

    def test_index_knowledge_base(self, pipeline):
        """Test knowledge base indexing."""
        # Create some test files
        (pipeline.markdown_dir).mkdir(parents=True, exist_ok=True)
        (pipeline.notes_dir).mkdir(parents=True, exist_ok=True)
        md_file = pipeline.markdown_dir / 'test.md'
        md_file.write_text('Test markdown content')

        note_file = pipeline.notes_dir / 'test_note.md'
        note_file.write_text('Test note content')

        with patch.object(pipeline.services.rag, 'index_knowledge_base') as mock_index:
            mock_index.return_value = {
                'total_files': 2,
                'markdown_files': 1,
                'note_files': 1,
                'total_chunks': 2,
                'errors': [],
            }

            stats = pipeline.knowledge_pipeline.index_knowledge_base()

            assert stats['total_files'] == 2
            assert stats['markdown_files'] == 1
            assert stats['note_files'] == 1

    def test_search_knowledge_base(self, pipeline):
        """Test knowledge base search."""
        query = 'test query'

        with patch.object(pipeline.services.rag, 'search') as mock_search:
            mock_search.return_value = [
                {
                    'content': 'Test content',
                    'title': 'Test Document',
                    'document_type': 'note',
                    'score': 0.9,
                }
            ]

            results = pipeline.knowledge_pipeline.search_knowledge_base(query, k=5)

            assert len(results) == 1
            assert results[0]['title'] == 'Test Document'
            assert results[0]['score'] == 0.9

    def test_ask_knowledge_base(self, pipeline):
        """Test asking questions to knowledge base."""
        question = 'What is machine learning?'

        with patch.object(pipeline.services.rag, 'ask_question') as mock_ask:
            mock_ask.return_value = {
                'question': question,
                'answer': 'Machine learning is...',
                'sources': [
                    {
                        'page_content': 'ML content',
                        'metadata': {'title': 'ML Paper'},
                    }
                ],
            }

            response = pipeline.knowledge_pipeline.ask_knowledge_base(question)

            assert response['question'] == question
            assert 'Machine learning is' in response['answer']
            assert len(response['sources']) == 1

    def test_regenerate_all_notes(self, pipeline, sample_analysis_response):  # noqa: ARG002
        """Test regenerating all notes."""
        # Set up citation tracker attributes
        pipeline.citation_tracker.note_generator = MagicMock()

        # Mock regenerate_all_notes to return successful files
        pipeline.citation_tracker.regenerate_all_notes.return_value = [
            (Path('/path/to/pdf1.pdf'), Path('/path/to/note1.md'))
        ]

        # Call regenerate_all_notes
        results = pipeline.regenerate_all_notes()

        assert len(results) == 1
        assert results[0][0] == Path('/path/to/pdf1.pdf')
        assert results[0][1] == Path('/path/to/note1.md')

        # Verify method was called
        pipeline.citation_tracker.regenerate_all_notes.assert_called_once()

    def test_consolidate_and_retag_all_articles(self, pipeline):
        """Test tag consolidation and retagging."""
        with patch.object(pipeline.services.tag, 'consolidate_and_retag') as mock_tag:
            mock_tag.return_value = {
                'articles_processed': 10,
                'articles_updated': 8,
                'tags_consolidated': 5,
                'tags_added': 15,
                'original_tag_count': 20,
                'final_tag_count': 30,
                'total_vocabulary_size': 50,
                'consolidation_mappings': {'ml': 'machine-learning'},
                'all_available_tags': ['machine-learning', 'deep-learning'],
            }

            stats = pipeline.consolidate_and_retag_all_articles()

            assert stats['articles_processed'] == 10
            assert stats['articles_updated'] == 8
            assert stats['tags_added'] == 15

    def test_get_services(self, pipeline):
        """Test services property access."""
        assert pipeline.services is not None
        assert hasattr(pipeline.services, 'processing')
        assert hasattr(pipeline.services, 'article')
        assert hasattr(pipeline.services, 'rag')
