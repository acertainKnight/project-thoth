"""Scrape pages using a recorded browser session."""

from __future__ import annotations

from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from thoth.discovery.web_scraper import WebScraper
from thoth.utilities.models import (
    BrowserRecording,
    ScrapeConfiguration,
    ScrapedArticleMetadata,
)


class EmulatorScraper:
    """Replay a :class:`BrowserRecording` and scrape the resulting page."""

    def __init__(self, driver_path: str | None = None) -> None:
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless')
        self.driver_path = driver_path
        self.options = options
        self.web_scraper = WebScraper()

    def scrape(
        self,
        recording: BrowserRecording,
        config: ScrapeConfiguration,
        max_articles: int = 50,
    ) -> list[ScrapedArticleMetadata]:
        """Replay the recording and scrape the final page."""
        driver = webdriver.Chrome(self.driver_path, options=self.options)
        try:
            driver.get(recording.start_url)
            for cookie in recording.cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    logger.debug(f'Failed to add cookie: {cookie}')
            driver.get(recording.end_url or config.base_url)
            html = driver.page_source
        finally:
            driver.quit()

        articles = self.web_scraper.parse_html(
            html, recording.end_url or config.base_url, config
        )
        return articles[:max_articles]
