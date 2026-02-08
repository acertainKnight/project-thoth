"""Discovery API sources and scraper configurations."""

from .arxiv import ArxivAPISource, ArxivClient
from .base import APISourceError, BaseAPISource
from .biorxiv import BioRxivAPISource

# Import conference scraper configurations
from .conference_scrapers import (
    PMLR_VOLUME_MAP,
    aaai_scrape_config,
    get_pmlr_volume,
    icml_pmlr_scrape_config,
    ijcai_scrape_config,
    jmlr_scrape_config,
    neurips_scrape_config,
    springer_ml_journal_scrape_config,
)
from .crossref import CrossRefAPISource
from .openalex import OpenAlexAPISource
from .pubmed import PubMedAPISource

__all__ = [
    # API Sources
    'APISourceError',
    'ArxivAPISource',
    'ArxivClient',
    'BaseAPISource',
    'BioRxivAPISource',
    'CrossRefAPISource',
    'OpenAlexAPISource',
    'PubMedAPISource',
    # Conference Scraper Configs
    'neurips_scrape_config',
    'icml_pmlr_scrape_config',
    'jmlr_scrape_config',
    'aaai_scrape_config',
    'ijcai_scrape_config',
    'springer_ml_journal_scrape_config',
    'PMLR_VOLUME_MAP',
    'get_pmlr_volume',
]
