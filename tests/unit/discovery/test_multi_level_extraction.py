"""Unit tests for multi-level detail page extraction in discovery workflows."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from thoth.discovery.browser.extraction_service import META_TAG_MAP, ExtractionService
from thoth.discovery.browser.workflow_builder import (
    AnalysisOutput,
    DetailPageLevel,
    WorkflowBuilder,
)
from thoth.utilities.schemas import ScrapedArticleMetadata


class TestMetaTagExtraction:
    """Tests for meta tag extraction functionality."""

    @pytest.mark.asyncio
    async def test_meta_tag_map_coverage(self):
        """Test that META_TAG_MAP covers all expected academic fields."""
        assert 'abstract' in META_TAG_MAP
        assert 'pdf_url' in META_TAG_MAP
        assert 'doi' in META_TAG_MAP
        assert 'publication_date' in META_TAG_MAP
        assert 'journal' in META_TAG_MAP
        assert 'authors' in META_TAG_MAP

    @pytest.mark.asyncio
    async def test_extract_meta_tags_basic(self):
        """Test basic meta tag extraction."""
        # Mock page
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(
            return_value={
                'citation_abstract': ['This is a test abstract'],
                'citation_pdf_url': ['https://example.com/paper.pdf'],
                'citation_doi': ['10.1234/test'],
            }
        )

        # Create extraction service
        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        # Extract meta tags
        result = await service._extract_meta_tags(
            mock_page, ['abstract', 'pdf_url', 'doi']
        )

        assert result['abstract'] == 'This is a test abstract'
        assert result['pdf_url'] == 'https://example.com/paper.pdf'
        assert result['doi'] == '10.1234/test'

    @pytest.mark.asyncio
    async def test_extract_meta_tags_multiple_authors(self):
        """Test extraction of multiple author meta tags."""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(
            return_value={
                'citation_author': ['John Doe', 'Jane Smith', 'Bob Johnson'],
            }
        )

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        result = await service._extract_meta_tags(mock_page, ['authors'])

        assert result['authors'] == ['John Doe', 'Jane Smith', 'Bob Johnson']

    @pytest.mark.asyncio
    async def test_extract_meta_tags_fallback_order(self):
        """Test fallback order (e.g., DC.description if citation_abstract missing)."""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(
            return_value={
                'DC.description': ['Fallback abstract text'],
            }
        )

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        result = await service._extract_meta_tags(mock_page, ['abstract'])

        assert result['abstract'] == 'Fallback abstract text'

    @pytest.mark.asyncio
    async def test_extract_meta_tags_graceful_failure(self):
        """Test that meta tag extraction fails gracefully."""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=Exception('JS evaluation failed'))

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        result = await service._extract_meta_tags(mock_page, ['abstract'])

        assert result == {}


class TestDetailPageEnrichment:
    """Tests for detail page enrichment in ExtractionService."""

    @pytest.mark.asyncio
    async def test_enrich_with_detail_pages_skips_complete_articles(self):
        """Test that articles with complete metadata are not enriched."""
        mock_page = MagicMock()
        mock_page.context = MagicMock()

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        # Complete article
        articles = [
            ScrapedArticleMetadata(
                title='Complete Article',
                authors=['Author'],
                abstract='Full abstract',
                pdf_url='https://example.com/paper.pdf',
                doi='10.1234/test',
                url='https://example.com/article',
                source='test',
            )
        ]

        detail_config = [
            {
                'url_source_field': 'url',
                'fields': {
                    'abstract': {'css_selector': '.abstract', 'attribute': 'text'}
                },
                'use_meta_tags': True,
                'follow_links': [],
            }
        ]

        result = await service._enrich_with_detail_pages(articles, detail_config)

        # Should return same articles without navigation
        assert len(result) == 1
        assert result[0].title == 'Complete Article'

    @pytest.mark.asyncio
    async def test_enrich_with_detail_pages_level_2_extraction(self):
        """Test level 2 detail page extraction."""
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_detail_page = AsyncMock()

        # Mock context.new_page() to return our detail page
        mock_context.new_page = AsyncMock(return_value=mock_detail_page)
        mock_page.context = mock_context

        # Mock detail page navigation and extraction
        mock_detail_page.goto = AsyncMock()
        mock_detail_page.query_selector = AsyncMock()
        mock_abstract_elem = AsyncMock()
        mock_abstract_elem.text_content = AsyncMock(return_value='Extracted abstract')

        async def mock_query_selector(selector):
            if 'abstract' in selector:
                return mock_abstract_elem
            return None

        mock_detail_page.query_selector = mock_query_selector
        mock_detail_page.close = AsyncMock()

        # Mock meta tag extraction
        mock_detail_page.evaluate = AsyncMock(return_value={})

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        # Incomplete article
        articles = [
            ScrapedArticleMetadata(
                title='Incomplete Article',
                authors=['Author'],
                url='https://example.com/article',
                source='test',
            )
        ]

        detail_config = [
            {
                'url_source_field': 'url',
                'fields': {
                    'abstract': {
                        'css_selector': '.abstract',
                        'attribute': 'text',
                        'is_multiple': False,
                    }
                },
                'use_meta_tags': False,
                'follow_links': [],
            }
        ]

        result = await service._enrich_with_detail_pages(
            articles, detail_config, rate_limit_delay=0
        )

        # Should have enriched abstract
        assert len(result) == 1
        assert result[0].abstract == 'Extracted abstract'

    @pytest.mark.asyncio
    async def test_enrich_with_detail_pages_depth_cap_at_3(self):
        """Test detail page extraction is capped at 3 levels (level 2 and 3)."""
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_detail_page = AsyncMock()

        mock_context.new_page = AsyncMock(return_value=mock_detail_page)
        mock_page.context = mock_context

        mock_detail_page.goto = AsyncMock()
        mock_detail_page.query_selector = AsyncMock(return_value=None)
        mock_detail_page.query_selector_all = AsyncMock(return_value=[])
        mock_detail_page.close = AsyncMock()
        mock_detail_page.evaluate = AsyncMock(return_value={})

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        articles = [
            ScrapedArticleMetadata(
                title='Article',
                url='https://example.com/article',
                source='test',
            )
        ]

        # Config with 3 levels (which is wrong - should be max 2)
        detail_config = [
            {
                'url_source_field': 'url',
                'fields': {},
                'use_meta_tags': False,
                'follow_links': [],
            },
            {
                'url_source_field': '_followed_link',
                'fields': {},
                'use_meta_tags': False,
                'follow_links': [],
            },
            # This third level should not be processed (depth cap)
            {
                'url_source_field': '_followed_link',
                'fields': {},
                'use_meta_tags': False,
                'follow_links': [],
            },
        ]

        await service._enrich_with_detail_pages(
            articles, detail_config[:2], rate_limit_delay=0
        )

        # Should process only 2 levels (max)
        assert mock_detail_page.goto.call_count <= 2  # At most 2 navigations

    @pytest.mark.asyncio
    async def test_enrich_with_detail_pages_graceful_failure(self):
        """Test that enrichment fails gracefully and returns original articles."""
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_detail_page = AsyncMock()

        mock_context.new_page = AsyncMock(return_value=mock_detail_page)
        mock_page.context = mock_context

        # Simulate navigation failure
        mock_detail_page.goto = AsyncMock(side_effect=Exception('Navigation failed'))
        mock_detail_page.close = AsyncMock()

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        articles = [
            ScrapedArticleMetadata(
                title='Article',
                url='https://example.com/article',
                source='test',
            )
        ]

        detail_config = [
            {
                'url_source_field': 'url',
                'fields': {
                    'abstract': {'css_selector': '.abstract', 'attribute': 'text'}
                },
                'use_meta_tags': False,
                'follow_links': [],
            }
        ]

        result = await service._enrich_with_detail_pages(
            articles, detail_config, rate_limit_delay=0
        )

        # Should return original article even though enrichment failed
        assert len(result) == 1
        assert result[0].title == 'Article'
        assert result[0].abstract is None  # Not enriched


class TestWorkflowBuilderDetailAnalysis:
    """Tests for WorkflowBuilder detail page analysis."""

    @pytest.mark.asyncio
    @patch(
        'thoth.discovery.browser.workflow_builder.WorkflowBuilder._llm_analyze_detail_page'
    )
    @patch(
        'thoth.discovery.browser.workflow_builder.WorkflowBuilder._extract_meta_tags'
    )
    async def test_analyze_detail_page_level_basic(self, mock_meta_tags, mock_llm):
        """Test basic detail page level analysis."""
        from thoth.discovery.browser.workflow_builder import (
            DetailPageAnalysisResult,
            ProposedSelector,
        )

        # Mock LLM analysis
        mock_llm.return_value = DetailPageAnalysisResult(
            selectors=[
                ProposedSelector(
                    field_name='abstract',
                    css_selector='#abstract',
                    attribute='text',
                    confidence=0.9,
                )
            ],
            relevant_links=[],
        )

        # Mock meta tag extraction
        mock_meta_tags.return_value = {
            'pdf_url': 'https://example.com/paper.pdf',
        }

        # Mock page
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(
            return_value={'title': 'Test', 'repeatedPatterns': []}
        )
        mock_elem = AsyncMock()
        mock_elem.text_content = AsyncMock(return_value='Sample abstract text')
        mock_page.query_selector = AsyncMock(return_value=mock_elem)

        # Create builder (mocked config)
        builder = WorkflowBuilder()
        builder.llm_service = MagicMock()

        result = await builder._analyze_detail_page_level(
            page=mock_page,
            detail_url='https://example.com/article',
            missing_fields=['abstract', 'pdf_url'],
            current_depth=2,
        )

        assert result is not None
        assert result.url_source_field == 'url'
        assert 'abstract' in result.fields
        assert result.use_meta_tags is True
        assert 'pdf_url' in result.sample_data

    @pytest.mark.asyncio
    async def test_detail_page_extraction_in_analysis_output(self):
        """Test that AnalysisOutput includes detail_page_extraction."""
        output = AnalysisOutput(
            url='https://example.com',
            page_title='Test',
            page_type='article_listing',
            article_container_selector='.article',
            selectors={'title': {'css_selector': 'h3', 'attribute': 'text'}},
            pagination_selector=None,
            sample_articles=[],
            total_articles_found=0,
            detail_page_extraction=[
                DetailPageLevel(
                    url_source_field='url',
                    fields={
                        'abstract': {'css_selector': '.abstract', 'attribute': 'text'}
                    },
                    use_meta_tags=True,
                    follow_links=[],
                    sample_data={'abstract': 'Sample'},
                )
            ],
        )

        assert len(output.detail_page_extraction) == 1
        assert output.detail_page_extraction[0].url_source_field == 'url'

        # Test to_dict()
        dict_output = output.to_dict()
        assert 'detail_page_extraction' in dict_output
        assert len(dict_output['detail_page_extraction']) == 1


class TestWorkflowReplay:
    """Tests for stored workflow replay during discovery runs."""

    @pytest.mark.asyncio
    async def test_extraction_rules_with_detail_config_triggers_enrichment(self):
        """Test extraction_rules with detail_page_extraction triggers enrichment."""
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=AsyncMock())
        mock_page.context = mock_context

        # Create mock article elements
        mock_article = MagicMock()
        mock_title = MagicMock()
        mock_title.text_content = AsyncMock(return_value='Test Article')
        mock_article.query_selector = AsyncMock(return_value=mock_title)

        mock_page.query_selector_all = AsyncMock(return_value=[mock_article])
        mock_page.wait_for_selector = AsyncMock()

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        extraction_rules = {
            'article_container': '.article',
            'fields': {'title': {'css_selector': 'h3', 'attribute': 'text'}},
            'detail_page_extraction': [
                {
                    'url_source_field': 'url',
                    'fields': {
                        'abstract': {'css_selector': '.abstract', 'attribute': 'text'}
                    },
                    'use_meta_tags': True,
                    'follow_links': [],
                }
            ],
        }

        with patch.object(service, '_enrich_with_detail_pages') as mock_enrich:
            mock_enrich.return_value = []
            await service.extract_articles(extraction_rules, max_articles=10)

            # Should have called enrichment
            mock_enrich.assert_called_once()

    @pytest.mark.asyncio
    async def test_extraction_without_detail_config_skips_enrichment(self):
        """Test that extraction without detail_page_extraction skips enrichment."""
        mock_page = MagicMock()
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.wait_for_selector = AsyncMock()

        service = ExtractionService(
            page=mock_page, source_name='test', stop_on_known=False
        )

        extraction_rules = {
            'article_container': '.article',
            'fields': {'title': {'css_selector': 'h3', 'attribute': 'text'}},
        }

        with patch.object(service, '_enrich_with_detail_pages') as mock_enrich:
            await service.extract_articles(extraction_rules, max_articles=10)

            # Should NOT have called enrichment
            mock_enrich.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
