"""
Health check and utility endpoints.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from loguru import logger

from thoth.monitoring.health import HealthMonitor
from thoth.utilities.download import download_pdf

router = APIRouter(tags=["health", "utility"])


@router.get('/health')
def health_check(service_manager=None):
    """Health check endpoint returning service statuses."""
    if service_manager is None:
        return JSONResponse({'status': 'uninitialized'})

    monitor = HealthMonitor(service_manager)
    return JSONResponse(monitor.overall_status())


@router.get('/download-pdf')
def download_pdf_endpoint(
    url: str = Query(..., description='PDF URL to download'),
    pdf_dir: Path | None = None
):
    """
    Download a PDF from a URL and save it to the configured PDF directory.

    Args:
        url: The URL of the PDF to download.
        pdf_dir: Directory to save PDFs (injected as dependency).

    Returns:
        JSON response with download status and file path.
    """
    if pdf_dir is None:
        raise HTTPException(status_code=500, detail='PDF directory not configured')

    try:
        file_path = download_pdf(url, pdf_dir)
        return JSONResponse(
            {
                'status': 'success',
                'message': f'PDF downloaded successfully to {file_path}',
                'file_path': str(file_path),
            }
        )
    except Exception as e:
        logger.error(f'Failed to download PDF from {url}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to download PDF: {e!s}'
        ) from e


@router.get('/view-markdown')
def view_markdown(
    path: str = Query(..., description='Path to markdown file'),
    notes_dir: Path | None = None
):
    """
    View the contents of a markdown file.

    Args:
        path: Path to the markdown file relative to the notes directory.
        notes_dir: Notes directory (injected as dependency).

    Returns:
        JSON response with file contents.
    """
    if notes_dir is None:
        raise HTTPException(status_code=500, detail='Notes directory not configured')

    try:
        file_path = notes_dir / path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail='File not found')

        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        return JSONResponse(
            {'status': 'success', 'content': content, 'file_path': str(file_path)}
        )
    except Exception as e:
        logger.error(f'Failed to read markdown file {path}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to read file: {e!s}'
        ) from e