"""
Utility to convert article URLs to direct PDF URLs for known sources.

Supports: ArXiv, bioRxiv, medRxiv, and other common preprint servers.
"""

from loguru import logger


def convert_to_pdf_url(url: str) -> str | None:
    """
    Convert an article URL to a direct PDF URL for known sources.

    Args:
        url: Article URL (abstract page, DOI, etc.)

    Returns:
        str | None: Direct PDF URL if conversion is possible, None otherwise

    Examples:
        >>> convert_to_pdf_url('https://arxiv.org/abs/2512.10398v2')
        'https://arxiv.org/pdf/2512.10398v2.pdf'

        >>> convert_to_pdf_url('https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1')
        'https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1.full.pdf'
    """
    if not url:
        return None

    url = url.strip()

    # ArXiv: /abs/ -> /pdf/ + .pdf
    if 'arxiv.org/abs/' in url:
        pdf_url = url.replace('/abs/', '/pdf/')
        if not pdf_url.endswith('.pdf'):
            pdf_url += '.pdf'
        logger.debug(f'Converted ArXiv URL: {url} -> {pdf_url}')
        return pdf_url

    # bioRxiv and medRxiv: add .full.pdf
    if 'biorxiv.org/content/' in url or 'medrxiv.org/content/' in url:
        # Remove any existing version suffix fragments
        base_url = url.split('#')[0].split('?')[0]
        if not base_url.endswith('.pdf'):
            pdf_url = base_url.rstrip('/') + '.full.pdf'
            logger.debug(f'Converted bioRxiv/medRxiv URL: {url} -> {pdf_url}')
            return pdf_url

    # PsyArXiv, SocArXiv (OSF): add /download
    if 'psyarxiv.com' in url or 'socarxiv.org' in url or 'osf.io/preprints' in url:
        base_url = url.split('?')[0].rstrip('/')
        if not base_url.endswith('/download'):
            pdf_url = base_url + '/download'
            logger.debug(f'Converted OSF preprint URL: {url} -> {pdf_url}')
            return pdf_url

    # Already a PDF URL
    if url.endswith('.pdf'):
        return url

    # Unknown source - cannot convert
    logger.debug(f'Cannot convert URL to PDF: {url}')
    return None


def should_convert_url(url: str) -> bool:
    """
    Check if a URL can be converted to a PDF URL.

    Args:
        url: Article URL to check

    Returns:
        bool: True if conversion is supported
    """
    if not url:
        return False

    known_sources = [
        'arxiv.org/abs/',
        'biorxiv.org/content/',
        'medrxiv.org/content/',
        'psyarxiv.com',
        'socarxiv.org',
        'osf.io/preprints',
    ]

    return any(source in url for source in known_sources)
