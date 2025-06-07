from unittest.mock import MagicMock, patch

from thoth.discovery.emulator_scraper import EmulatorScraper
from thoth.discovery.web_emulator import BrowserRecording, WebEmulatorRecorder
from thoth.utilities.models import ScrapeConfiguration


def test_web_emulator_recording(tmp_path):
    mock_driver = MagicMock()
    mock_driver.current_url = 'http://example.com/page'
    mock_driver.get_cookies.return_value = []
    with patch(
        'thoth.discovery.web_emulator.webdriver.Chrome', return_value=mock_driver
    ):
        recorder = WebEmulatorRecorder()
        recorder.start_recording('http://example.com')
        recording = recorder.stop_recording()
        assert isinstance(recording, BrowserRecording)
        out_file = tmp_path / 'rec.json'
        recorder.save_recording(recording, out_file)
        loaded = recorder.load_recording(out_file)
        assert loaded.start_url == 'http://example.com'
        assert loaded.end_url == 'http://example.com/page'


def test_emulator_scraper_parse_html():
    recording = BrowserRecording(
        start_url='http://example.com', end_url='http://example.com/page', cookies=[]
    )
    config = ScrapeConfiguration(base_url='http://example.com', extraction_rules={})

    mock_driver = MagicMock()
    mock_driver.page_source = '<html></html>'

    with patch(
        'thoth.discovery.emulator_scraper.webdriver.Chrome', return_value=mock_driver
    ):
        scraper = EmulatorScraper()
        with patch.object(
            scraper.web_scraper, 'parse_html', return_value=[]
        ) as mock_parse:
            result = scraper.scrape(recording, config)
            assert result == []
            mock_parse.assert_called_once()
