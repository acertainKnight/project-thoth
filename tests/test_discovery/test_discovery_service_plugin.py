from unittest.mock import MagicMock, patch

from thoth.services.discovery_service import DiscoveryService
from thoth.utilities.config import ThothConfig
from thoth.utilities.schemas import (
    DiscoverySource,
    ScheduleConfig,
    ScrapedArticleMetadata,
)


def test_discovery_service_arxiv_plugin(thoth_config: ThothConfig, tmp_path):
    schedule = ScheduleConfig()
    source = DiscoverySource(
        name='arxiv_test',
        source_type='api',
        description='test',
        is_active=True,
        schedule_config=schedule,
        api_config={'source': 'arxiv', 'keywords': ['ml']},
    )

    dummy_article = ScrapedArticleMetadata(
        title='t',
        authors=[],
        journal='j',
        source='arxiv',
        pdf_url='http://x',
    )

    thoth_config.core.discovery_sources_dir = tmp_path
    service = DiscoveryService(config=thoth_config)
    with patch.object(
        service.plugin_registry,
        'create',
        return_value=MagicMock(discover=MagicMock(return_value=[dummy_article])),
    ) as mock_create:
        service.create_source(source)
        result = service.run_discovery(source_name='arxiv_test')

        assert result.articles_found == 1
        mock_create.assert_called_once()
