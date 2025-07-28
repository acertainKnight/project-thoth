from thoth.discovery.plugins.base import (
    BaseDiscoveryPlugin,
    DiscoveryPluginRegistry,
)
from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata


class MockPlugin(BaseDiscoveryPlugin):
    def discover(
        self, _query: ResearchQuery, _max_results: int
    ) -> list[ScrapedArticleMetadata]:
        return [
            ScrapedArticleMetadata(
                title='Test Article',
                authors=['A'],
                abstract='desc',
                journal='J',
                source=self.get_name(),
                pdf_url='http://example.com/test.pdf',
            )
        ]


def test_plugin_registration_and_retrieval():
    registry = DiscoveryPluginRegistry()
    registry.register('mock', MockPlugin)

    plugin_cls = registry.get('mock')
    assert plugin_cls is MockPlugin

    plugin = registry.create('mock')
    assert isinstance(plugin, MockPlugin)
    assert 'mock' in registry.list_plugins()


def test_base_plugin_functionality():
    plugin = MockPlugin()
    query = ResearchQuery(
        name='q',
        description='d',
        research_question='rq',
        keywords=['k'],
    )

    results = plugin.discover(query, _max_results=1)
    assert len(results) == 1
    assert results[0].source == 'MockPlugin'
