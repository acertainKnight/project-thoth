from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.pipeline import ThothPipeline
from thoth.pipelines import DocumentPipeline


class TestDocumentPipeline:
    @pytest.fixture
    def doc_pipeline(self, temp_workspace):
        pipeline = DocumentPipeline(
            services=MagicMock(),
            citation_tracker=MagicMock(),
            pdf_tracker=MagicMock(),
            output_dir=temp_workspace / 'output',
            notes_dir=temp_workspace / 'notes',
            markdown_dir=temp_workspace / 'markdown',
        )
        return pipeline

    @pytest.fixture
    def pipeline(self, mock_config, temp_workspace):  # noqa: ARG002
        with patch('thoth.pipeline.ServiceManager') as mock_service_manager:
            with patch('thoth.pipeline.CitationGraph') as mock_tracker:
                mock_services = MagicMock()
                mock_service_manager.return_value = mock_services
                pipeline = ThothPipeline(
                    output_dir=temp_workspace / 'output',
                    notes_dir=temp_workspace / 'notes',
                )
                pipeline.services = mock_services
                pipeline.citation_tracker = mock_tracker.return_value
                return pipeline

    def test_ocr_convert(self, doc_pipeline, sample_pdf_path, temp_workspace):
        md_path = temp_workspace / 'markdown' / 'out.md'
        no_img = temp_workspace / 'markdown' / 'out_no_img.md'
        doc_pipeline.services.processing.ocr_convert.return_value = (md_path, no_img)

        result = doc_pipeline._ocr_convert(sample_pdf_path)
        assert result == (md_path, no_img)
        doc_pipeline.services.processing.ocr_convert.assert_called_once_with(
            pdf_path=sample_pdf_path, output_dir=doc_pipeline.markdown_dir
        )

    def test_analyze_content(
        self, doc_pipeline, sample_markdown_path, sample_analysis_response
    ):
        doc_pipeline.services.processing.analyze_document.return_value = (
            sample_analysis_response
        )
        result = doc_pipeline._analyze_content(sample_markdown_path)
        assert result == sample_analysis_response
        doc_pipeline.services.processing.analyze_document.assert_called_once_with(
            sample_markdown_path
        )

    def test_extract_citations(
        self, doc_pipeline, sample_markdown_path, sample_citations
    ):
        doc_pipeline.services.citation.extract_citations.return_value = sample_citations
        result = doc_pipeline._extract_citations(sample_markdown_path)
        assert result == sample_citations
        doc_pipeline.services.citation.extract_citations.assert_called_once_with(
            sample_markdown_path
        )

    def test_generate_note(
        self,
        doc_pipeline,
        sample_pdf_path,
        sample_markdown_path,
        sample_analysis_response,
        sample_citations,
        temp_workspace,
    ):
        note_path = temp_workspace / 'notes' / 'note.md'
        new_pdf = temp_workspace / 'pdf' / 'new.pdf'
        new_md = temp_workspace / 'markdown' / 'new.md'
        doc_pipeline.services.note.create_note.return_value = (
            note_path,
            new_pdf,
            new_md,
        )
        doc_pipeline.citation_tracker.process_citations.return_value = 'article-1'

        result = doc_pipeline._generate_note(
            sample_pdf_path,
            sample_markdown_path,
            sample_analysis_response,
            sample_citations,
        )
        assert result == (str(note_path), str(new_pdf), str(new_md))
        doc_pipeline.services.note.create_note.assert_called_once()
        doc_pipeline.citation_tracker.update_article_file_paths.assert_called_once_with(
            article_id='article-1', new_pdf_path=new_pdf, new_markdown_path=new_md
        )

    def test_process_pdf(
        self,
        doc_pipeline,
        sample_pdf_path,
        sample_analysis_response,
        sample_citations,
        temp_workspace,
    ):
        doc_pipeline.pdf_tracker.is_processed.return_value = False
        md_path = temp_workspace / 'markdown' / 'file.md'
        no_img = temp_workspace / 'markdown' / 'file_no_img.md'
        doc_pipeline.services.processing.ocr_convert.return_value = (md_path, no_img)
        doc_pipeline.services.processing.analyze_document.return_value = (
            sample_analysis_response
        )
        doc_pipeline.services.citation.extract_citations.return_value = sample_citations
        note_path = temp_workspace / 'notes' / 'final.md'
        new_pdf = temp_workspace / 'notes' / 'final.pdf'
        new_md = temp_workspace / 'notes' / 'final_markdown.md'
        doc_pipeline.services.note.create_note.return_value = (
            note_path,
            new_pdf,
            new_md,
        )
        doc_pipeline.citation_tracker.process_citations.return_value = 'article-1'

        result = doc_pipeline.process_pdf(sample_pdf_path)
        assert result == (Path(note_path), Path(new_pdf), Path(new_md))
        doc_pipeline.pdf_tracker.mark_processed.assert_called_once()

    def test_thoth_integration(self, pipeline, sample_pdf_path):
        with patch.object(
            pipeline.document_pipeline, 'process_pdf', return_value=('n', 'p', 'm')
        ) as mock_proc:
            result = pipeline.process_pdf(sample_pdf_path)
            assert result == ('n', 'p', 'm')
            mock_proc.assert_called_once_with(sample_pdf_path)
