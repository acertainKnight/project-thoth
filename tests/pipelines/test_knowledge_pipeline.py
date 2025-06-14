from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.pipelines.knowledge_pipeline import KnowledgePipeline


class TestKnowledgePipeline:
    @pytest.fixture
    def knowledge_pipeline(self, temp_workspace):
        pipeline = KnowledgePipeline(
            services=MagicMock(),
            citation_tracker=MagicMock(),
            pdf_tracker=MagicMock(),
            output_dir=temp_workspace / "output",
            notes_dir=temp_workspace / "notes",
            markdown_dir=temp_workspace / "markdown",
        )
        return pipeline

    def test_index_to_rag(self, knowledge_pipeline, temp_workspace):
        md_file = temp_workspace / "markdown" / "file.md"
        md_file.write_text("data")
        knowledge_pipeline._index_to_rag(md_file)
        knowledge_pipeline.services.rag.index_file.assert_called_once_with(md_file)

    def test_index_knowledge_base(self, knowledge_pipeline):
        with patch.object(
            knowledge_pipeline.services.rag, "index_knowledge_base"
        ) as mock_index:
            mock_index.return_value = {
                "total_files": 2,
                "markdown_files": 1,
                "note_files": 1,
                "total_chunks": 2,
                "errors": [],
            }
            stats = knowledge_pipeline.index_knowledge_base()
            assert stats["total_files"] == 2
            assert stats["markdown_files"] == 1
            mock_index.assert_called_once()

    def test_search_knowledge_base(self, knowledge_pipeline):
        with patch.object(knowledge_pipeline.services.rag, "search") as mock_search:
            mock_search.return_value = [
                {
                    "content": "Test content",
                    "title": "Doc",
                    "document_type": "note",
                    "score": 0.8,
                }
            ]
            results = knowledge_pipeline.search_knowledge_base("query", k=3)
            assert len(results) == 1
            assert results[0]["title"] == "Doc"
            mock_search.assert_called_once()

    def test_ask_knowledge_base(self, knowledge_pipeline):
        with patch.object(
            knowledge_pipeline.services.rag, "ask_question"
        ) as mock_ask:
            mock_ask.return_value = {
                "question": "Q",
                "answer": "A",
                "sources": [
                    {"page_content": "c", "metadata": {"title": "Doc"}}
                ],
            }
            resp = knowledge_pipeline.ask_knowledge_base("Q")
            assert resp["question"] == "Q"
            assert "A" in resp["answer"]
            mock_ask.assert_called_once()

    def test_clear_rag_index(self, knowledge_pipeline):
        with patch.object(
            knowledge_pipeline.services.rag, "clear_index"
        ) as mock_clear:
            knowledge_pipeline.clear_rag_index()
            mock_clear.assert_called_once()

    def test_get_rag_stats(self, knowledge_pipeline):
        with patch.object(
            knowledge_pipeline.services.rag, "get_stats"
        ) as mock_stats:
            mock_stats.return_value = {"document_count": 1}
            stats = knowledge_pipeline.get_rag_stats()
            assert stats["document_count"] == 1
            mock_stats.assert_called_once()
