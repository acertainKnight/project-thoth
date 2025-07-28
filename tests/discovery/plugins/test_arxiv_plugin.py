from unittest.mock import patch

from thoth.discovery.plugins.arxiv_plugin import ArxivPlugin
from thoth.discovery.plugins.base import DiscoveryPluginRegistry
from thoth.utilities.schemas import ResearchQuery
from thoth.utilities.schemas.citations import ArxivPaper


def sample_query():
    return ResearchQuery(
        name='test',
        description='d',
        research_question='rq',
        keywords=['ml'],
    )


def make_paper():
    return ArxivPaper(
        id='1234.56789',
        title='Test Paper',
        authors=['Alice'],
        abstract='About ML',
        categories=['cs.LG'],
        pdf_url='https://arxiv.org/pdf/1234.56789.pdf',
        published='2024-01-01',
        updated='2024-01-02',
    )


def test_arxiv_plugin_discover():
    query = sample_query()
    paper = make_paper()
    with patch('thoth.discovery.plugins.arxiv_plugin.ArxivClient') as mock_client:
        instance = mock_client.return_value
        instance.search.return_value = [paper]

        plugin = ArxivPlugin(config={'categories': ['cs.LG']})
        results = plugin.discover(query, max_results=5)

        assert len(results) == 1
        result = results[0]
        assert result.title == paper.title
        assert result.arxiv_id == paper.id
        assert result.source == 'arxiv'
        instance.search.assert_called_once()


def test_plugin_registry_registration():
    registry = DiscoveryPluginRegistry()
    registry.register('arxiv', ArxivPlugin)
    assert 'arxiv' in registry.list_plugins()
    plugin = registry.create('arxiv', config={})
    assert isinstance(plugin, ArxivPlugin)
