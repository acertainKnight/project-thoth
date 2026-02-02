"""
PDF downloader module for Thoth.

This module provides functionality to download PDFs from URLs and save them to the configured directory.
"""  # noqa: W505

import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from loguru import logger
from tqdm import tqdm


def download_pdf(url: str, pdf_dir: Path, filename: str | None = None) -> Path:
    """
    Download a PDF from a URL and save it to the configured PDF directory.

    Args:
        url (str): The URL of the PDF to download.
        pdf_dir (Path): The directory to save the PDF to.
        filename (Optional[str]): Optional custom filename. If not provided, will use the last part of the URL.

    Returns:
        Path: Path to the downloaded PDF file.

    Raises:
        ValueError: If the URL is invalid or doesn't point to a PDF.
        httpx.HTTPError: If the download fails.
        IOError: If there are issues saving the file.

    Example:
        >>> pdf_path = download_pdf(
        ...     'https://example.com/paper.pdf', pdf_dir=Path('data/pdf')
        ... )
        >>> print(f'Downloaded to: {pdf_path}')
    """  # noqa: W505
    # Validate URL
    if not url.lower().endswith('.pdf'):
        raise ValueError('URL must point to a PDF file')

    # Get configuration
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Determine filename
    if filename is None:
        filename = os.path.basename(urlparse(url).path)
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'

    # Full path for the PDF
    pdf_path = pdf_dir / filename

    # Download with progress bar
    try:
        # Use httpx.stream() context manager for streaming downloads
        with httpx.stream('GET', url, follow_redirects=True) as response:
            response.raise_for_status()

            # Get total file size
            total_size = int(response.headers.get('content-length', 0))

            # Download with progress bar
            with (
                open(pdf_path, 'wb') as file,
                tqdm(
                    desc=filename,
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as progress_bar,
            ):
                for data in response.iter_bytes(chunk_size=1024):
                    size = file.write(data)
                    progress_bar.update(size)

        logger.info(f'Successfully downloaded PDF to {pdf_path}')
        return pdf_path

    except httpx.HTTPError as e:
        logger.error(f'Failed to download PDF from {url}: {e!s}')
        raise
    except OSError as e:
        logger.error(f'Failed to save PDF to {pdf_path}: {e!s}')
        raise
