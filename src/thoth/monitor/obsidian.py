"""
Obsidian integration for Thoth.

This module provides FastAPI endpoints for integration with Obsidian.
The main endpoint allows downloading PDFs from URLs via Obsidian's URI capability.
"""

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from thoth.ingestion.pdf_downloader import download_pdf

app = FastAPI(
    title='Thoth Obsidian Integration',
    description='API for integrating Thoth with Obsidian',
    version='0.1.0',
)

# Add CORS middleware to allow requests from Obsidian
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],  # Allow requests from any origin (including Obsidian)
    allow_credentials=True,
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
)

# Module-level variables to store configuration
# These will be set by the start_server function
pdf_dir: Path = None
notes_dir: Path = None
base_url: str = None


@app.get('/download-pdf/')
def download_pdf_endpoint(
    url: str = Query(..., description='URL of the PDF to download'),
):
    """
    Download a PDF from a URL and save it to the configured PDF directory.

    Args:
        url: URL of the PDF to download.

    Returns:
        dict: A JSON response with the path where the PDF was saved.
    """
    if pdf_dir is None:
        raise HTTPException(status_code=500, detail='PDF directory not configured')

    try:
        # Use the pdf_downloader module to download the file
        # Pass None for filename to let the downloader extract it from the URL
        output_path = download_pdf(url, pdf_dir, None)

        # Get the filename from the output path
        filename = output_path.name

        # Calculate relative path from notes directory to PDF file
        # This is needed for correct markdown linking
        relative_path = (
            output_path.relative_to(notes_dir)
            if notes_dir in output_path.parents
            else output_path
        )

        # Construct the response with both markdown link and obsidian URI
        response = {
            'success': True,
            'message': f'PDF downloaded and saved to {output_path}',
            'file_path': str(output_path),
            'markdown_link': f'[{filename}]({relative_path})',
            'obsidian_uri': f'obsidian://open?vault={notes_dir.name}&file={filename}',
            'api_url': f'{base_url}/download-pdf/?url={url}',
        }

        return JSONResponse(content=response)

    except ValueError as e:
        logger.error(f'Invalid URL: {e!s}')
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904
    except Exception as e:
        logger.error(f'Error downloading PDF: {e!s}')
        raise HTTPException(status_code=500, detail=f'Failed to download PDF: {e!s}')  # noqa: B904


def start_server(
    host: str, port: int, pdf_directory: Path, notes_directory: Path, api_base_url: str
):
    """
    Start the FastAPI server.

    Args:
        host (str): Host to bind the server to.
        port (int): Port to bind the server to.
        pdf_directory (Path): Directory where PDFs will be stored.
        notes_directory (Path): Directory where notes are stored (Obsidian vault).
        api_base_url (str): Base URL for the API.
    """
    global pdf_dir, notes_dir, base_url

    # Set module-level configuration
    pdf_dir = pdf_directory
    notes_dir = notes_directory
    base_url = api_base_url

    logger.info(f'Starting Obsidian API server on {host}:{port}')
    logger.info(f'PDF directory: {pdf_dir}')
    logger.info(f'Notes directory: {notes_dir}')
    logger.info(f'API base URL: {base_url}')

    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    # This is for development purposes only
    from pathlib import Path

    start_server(
        '127.0.0.1',
        8000,
        Path('./data/pdf'),
        Path('./data/notes'),
        'http://127.0.0.1:8000',
    )
