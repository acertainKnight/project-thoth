"""Health check and file operation endpoints."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from loguru import logger

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context
from thoth.ingestion.pdf_downloader import download_pdf
from thoth.monitoring import HealthMonitor
from thoth.server.dependencies import get_service_manager
from thoth.services.service_manager import ServiceManager

router = APIRouter()

# Module-level variables that will be set by the main app
pdf_dir: Path = None
notes_dir: Path = None
base_url: str = None


def set_directories(pdf_directory: Path, notes_directory: Path, base_url_val: str):
    """Set the directories for this router."""
    global pdf_dir, notes_dir, base_url
    pdf_dir = pdf_directory
    notes_dir = notes_directory
    base_url = base_url_val


@router.get('/health')
def health_check(service_manager: ServiceManager = Depends(get_service_manager)):  # noqa: B008
    """
    Health check endpoint.

    Returns:
        JSONResponse: Health status information with appropriate HTTP status code
    """
    try:
        if service_manager is None:
            logger.warning('Service manager not initialized')
            return JSONResponse(
                status_code=503,
                content={
                    'status': 'unhealthy',
                    'healthy': False,
                    'error': 'Service manager not initialized',
                    'services': {},
                    'timestamp': datetime.utcnow().isoformat(),
                },
            )

        health_monitor = HealthMonitor(service_manager)
        status = health_monitor.overall_status()

        is_healthy = status.get('healthy', False)
        response_data = {
            'status': 'healthy' if is_healthy else 'unhealthy',
            'healthy': is_healthy,
            'services': status.get('services', {}),
            'timestamp': datetime.now().isoformat(),
        }

        # Return appropriate HTTP status code
        http_status = 200 if is_healthy else 503
        return JSONResponse(status_code=http_status, content=response_data)

    except Exception as e:
        logger.error(f'Health check failed with error: {e}')
        return JSONResponse(
            status_code=500,
            content={
                'status': 'unhealthy',
                'healthy': False,
                'error': f'Health check failed: {e!s}',
                'services': {},
                'timestamp': datetime.now().isoformat(),
            },
        )


@router.get('/download-pdf')
def download_pdf_endpoint(
    url: str = Query(..., description='PDF URL to download'),
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """
    Download a PDF from the given URL.

    Args:
        url: The URL of the PDF to download

    Returns:
        JSONResponse: Download result with file information
    """
    try:
        from thoth.mcp.auth import get_current_user_paths

        user_paths = get_current_user_paths()
        target_dir = user_paths.pdf_dir if user_paths else pdf_dir
        pdf_path = download_pdf(url, target_dir)

        logger.info(f'Downloaded PDF: {pdf_path}')

        return JSONResponse(
            content={
                'status': 'success',
                'message': f'PDF downloaded successfully to {pdf_path}',
                'file_path': str(pdf_path),
                'filename': pdf_path.name,
                'base_url': base_url,
            }
        )
    except Exception as e:
        logger.error(f'Error downloading PDF: {e}')
        return JSONResponse(
            content={
                'status': 'error',
                'message': f'Error downloading PDF: {e}',
            },
            status_code=500,
        )


@router.get('/view-markdown')
def view_markdown(
    path: str = Query(..., description='Path to markdown file'),
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """
    View the contents of a markdown file.

    Args:
        path: Path to the markdown file

    Returns:
        JSONResponse: File contents or error message
    """
    try:
        from thoth.mcp.auth import get_current_user_paths

        user_paths = get_current_user_paths()
        user_notes_dir = user_paths.notes_dir if user_paths else notes_dir
        if Path(path).is_absolute():
            full_path = Path(path)
            if user_context.vault_path and not str(full_path).startswith(
                str(user_context.vault_path)
            ):
                return JSONResponse(
                    content={'status': 'error', 'message': 'Access denied'},
                    status_code=403,
                )
        else:
            full_path = user_notes_dir / path

        if not full_path.exists():
            return JSONResponse(
                content={
                    'status': 'error',
                    'message': f'File not found: {full_path}',
                },
                status_code=404,
            )

        # Read the markdown content
        content = full_path.read_text(encoding='utf-8')

        return JSONResponse(
            content={
                'status': 'success',
                'content': content,
                'path': str(full_path),
                'size': len(content),
            }
        )
    except Exception as e:
        logger.error(f'Error reading markdown file: {e}')
        return JSONResponse(
            content={
                'status': 'error',
                'message': f'Error reading file: {e}',
            },
            status_code=500,
        )
