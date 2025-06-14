from unittest.mock import patch

from thoth.services.discovery_service import DiscoveryService
from thoth.utilities.schemas import (
    BrowserRecording,
    DiscoverySource,
    ScheduleConfig,
    ScrapeConfiguration,
)


def test_discovery_service_emulator(tmp_path):
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

    service = DiscoveryService(sources_dir=tmp_path)
    with patch.object(
        service.emulator_scraper, 'scrape', return_value=[]
    ) as mock_scrape:
        service.create_source(source)
        result = service.run_discovery(source_name='demo')
        assert result.articles_found == 0
        mock_scrape.assert_called_once()
