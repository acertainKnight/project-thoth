from unittest.mock import patch

from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.utilities.models import (
    BrowserRecording,
    DiscoverySource,
    ScheduleConfig,
    ScrapeConfiguration,
)


def test_discovery_manager_emulator(tmp_path):
    schedule = ScheduleConfig()
    source = DiscoverySource(
        name='demo',
        source_type='emulator',
        description='demo',
        schedule_config=schedule,
        scraper_config=ScrapeConfiguration(
            base_url='http://example.com',
            extraction_rules={},
        ),
        browser_recording=BrowserRecording(
            start_url='http://example.com',
            end_url='http://example.com',
            cookies=[],
        ),
    )

    manager = DiscoveryManager(filter=None, sources_config_dir=tmp_path)
    with patch.object(
        manager.emulator_scraper, 'scrape', return_value=[]
    ) as mock_scrape:
        manager.create_source(source)
        result = manager.run_discovery(source_name='demo')
        assert result.articles_found == 0
        mock_scrape.assert_called_once()
