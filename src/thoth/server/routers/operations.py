"""Operations and streaming endpoints."""

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from thoth.server.routers.websocket import (
    create_background_task,
    get_operation_status,
    update_operation_progress,
)

router = APIRouter()

# Module-level variables that will be set by the main app
service_manager = None


def set_service_manager(sm):
    """Set the service manager for this router."""
    global service_manager
    service_manager = sm


# Request Models
class StreamingOperationRequest(BaseModel):
    operation_type: str  # 'pdf_process', 'discovery_run', 'batch_process'
    parameters: dict[str, Any]
    operation_id: str | None = None


class BatchProcessRequest(BaseModel):
    items: list[dict[str, Any]]
    operation_type: str = 'batch_process'
    batch_size: int = 5


class CommandExecutionRequest(BaseModel):
    command: str
    args: list[str] = []
    kwargs: dict[str, Any] = {}
    streaming: bool = False


@router.get('/{operation_id}/status')
def get_operation_status_endpoint(operation_id: str):
    """Get the status of a long-running operation."""
    status = get_operation_status(operation_id)
    if status is None:
        raise HTTPException(status_code=404, detail='Operation not found')
    return JSONResponse(status)


@router.post('/stream/operation')
async def start_streaming_operation(request: StreamingOperationRequest):
    """Start a streaming operation and return operation ID for tracking."""
    operation_id = request.operation_id or str(uuid.uuid4())

    # Start the operation in background
    create_background_task(execute_streaming_operation(operation_id, request))

    return JSONResponse(
        {
            'operation_id': operation_id,
            'status': 'started',
            'message': f'Operation {request.operation_type} started',
        }
    )


async def execute_streaming_operation(
    operation_id: str, request: StreamingOperationRequest
):
    """Execute a streaming operation with progress updates."""
    try:
        update_operation_progress(
            operation_id, 'running', 0.0, f'Starting {request.operation_type}'
        )

        if request.operation_type == 'pdf_process':
            await stream_pdf_processing(operation_id, request.parameters)
        elif request.operation_type == 'discovery_run':
            await stream_discovery_run(operation_id, request.parameters)
        elif request.operation_type == 'batch_process':
            await stream_batch_process(operation_id, request.parameters)
        else:
            raise ValueError(f'Unknown operation type: {request.operation_type}')

        update_operation_progress(
            operation_id, 'completed', 100.0, 'Operation completed successfully'
        )

    except Exception as e:
        logger.error(f'Streaming operation {operation_id} failed: {e}')
        update_operation_progress(
            operation_id, 'failed', 0.0, f'Operation failed: {e!s}'
        )


async def stream_pdf_processing(operation_id: str, parameters: dict[str, Any]):
    """Stream PDF processing with progress updates."""
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialized')

    pdf_paths = parameters.get('pdf_paths', [])
    if not pdf_paths:
        raise ValueError('No PDF paths provided')

    total_pdfs = len(pdf_paths)

    for i, pdf_path in enumerate(pdf_paths):
        update_operation_progress(
            operation_id,
            'running',
            (i / total_pdfs) * 100,
            f'Processing PDF {i + 1}/{total_pdfs}: {Path(pdf_path).name}',
        )

        try:
            # Use the optimized document pipeline to process PDF
            from thoth.pipelines import DocumentPipeline

            pipeline = DocumentPipeline(service_manager)

            result = await asyncio.to_thread(pipeline.process_pdf, Path(pdf_path))

            # Store result for this PDF
            update_operation_progress(
                operation_id,
                'running',
                ((i + 1) / total_pdfs) * 100,
                f'Completed PDF {i + 1}/{total_pdfs}',
                {'processed_pdfs': i + 1, 'latest_result': result},
            )

        except Exception as e:
            logger.error(f'Failed to process PDF {pdf_path}: {e}')
            update_operation_progress(
                operation_id,
                'running',
                ((i + 1) / total_pdfs) * 100,
                f'Failed to process PDF {i + 1}/{total_pdfs}: {e!s}',
            )


async def stream_discovery_run(operation_id: str, parameters: dict[str, Any]):
    """Stream discovery run with progress updates."""
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialized')

    source_name = parameters.get('source_name')
    max_articles = parameters.get('max_articles', 50)

    update_operation_progress(
        operation_id, 'running', 10.0, f'Starting discovery for source: {source_name}'
    )

    try:
        discovery_service = service_manager.discovery_service
        if not discovery_service:
            raise ValueError('Discovery service not available')

        # Run discovery with progress callbacks
        def progress_callback(current: int, total: int, message: str = ''):
            progress = 10.0 + (current / total) * 80.0  # 10-90% for discovery
            update_operation_progress(operation_id, 'running', progress, message)

        # Execute discovery run
        results = await asyncio.to_thread(
            discovery_service.run_discovery_for_source,
            source_name,
            max_articles,
            progress_callback,
        )

        update_operation_progress(
            operation_id, 'running', 90.0, 'Discovery completed, processing results'
        )

        # Process and return results
        update_operation_progress(
            operation_id,
            'completed',
            100.0,
            f'Discovery completed: {len(results)} articles found',
            {'articles_found': len(results), 'results': results},
        )

    except Exception as e:
        logger.error(f'Discovery run failed: {e}')
        raise


async def stream_batch_process(operation_id: str, parameters: dict[str, Any]):
    """Stream batch processing with progress updates."""
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialized')

    items = parameters.get('items', [])
    batch_size = parameters.get('batch_size', 5)
    process_type = parameters.get('process_type', 'pdf')

    if not items:
        raise ValueError('No items to process')

    total_items = len(items)
    processed_items = []

    update_operation_progress(
        operation_id, 'running', 0.0, f'Starting batch process: {total_items} items'
    )

    # Process items in batches
    for batch_start in range(0, total_items, batch_size):
        batch_end = min(batch_start + batch_size, total_items)
        batch_items = items[batch_start:batch_end]

        # Process batch concurrently
        batch_tasks = []
        for item in batch_items:
            if process_type == 'pdf':
                task = process_single_pdf(item)
            elif process_type == 'discovery':
                task = process_discovery_query(item)
            else:
                raise ValueError(f'Unknown process type: {process_type}')
            batch_tasks.append(task)

        # Execute batch
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        processed_items.extend(batch_results)

        # Update progress
        progress = (batch_end / total_items) * 100
        update_operation_progress(
            operation_id,
            'running',
            progress,
            f'Processed {batch_end}/{total_items} items',
            {'processed_items': len(processed_items)},
        )

    # Final update
    update_operation_progress(
        operation_id,
        'completed',
        100.0,
        f'Batch processing completed: {len(processed_items)} items processed',
        {'results': processed_items, 'total_processed': len(processed_items)},
    )


async def process_single_pdf(item: dict[str, Any]) -> dict[str, Any]:
    """Process a single PDF item."""
    try:
        pdf_path = Path(item.get('path', ''))
        if not pdf_path.exists():
            raise FileNotFoundError(f'PDF not found: {pdf_path}')

        # Use document pipeline to process
        from thoth.pipelines import DocumentPipeline

        pipeline = DocumentPipeline(service_manager)
        result = await asyncio.to_thread(pipeline.process_pdf, pdf_path)

        return {'status': 'success', 'path': str(pdf_path), 'result': result}
    except Exception as e:
        return {'status': 'error', 'path': item.get('path', ''), 'error': str(e)}


async def process_discovery_query(item: dict[str, Any]) -> dict[str, Any]:
    """Process a single discovery query."""
    try:
        query = item.get('query', '')
        max_results = item.get('max_results', 10)

        # Use discovery service
        discovery_service = service_manager.discovery_service
        results = await asyncio.to_thread(
            discovery_service.search_papers, query, max_results
        )

        return {'status': 'success', 'query': query, 'results': results}
    except Exception as e:
        return {'status': 'error', 'query': item.get('query', ''), 'error': str(e)}


@router.post('/batch/process')
async def batch_process(request: BatchProcessRequest):
    """Start a batch processing operation."""
    operation_id = str(uuid.uuid4())

    # Convert to streaming operation request
    StreamingOperationRequest(
        operation_type='batch_process',
        parameters={
            'items': request.items,
            'batch_size': request.batch_size,
            'process_type': request.operation_type,
        },
        operation_id=operation_id,
    )

    # Start the operation in background
    create_background_task(execute_batch_process(operation_id, request))

    return JSONResponse(
        {
            'operation_id': operation_id,
            'status': 'started',
            'message': f'Batch processing started: {len(request.items)} items',
            'batch_size': request.batch_size,
        }
    )


async def execute_batch_process(operation_id: str, request: BatchProcessRequest):
    """Execute batch processing operation."""
    parameters = {
        'items': request.items,
        'batch_size': request.batch_size,
        'process_type': request.operation_type,
    }
    await stream_batch_process(operation_id, parameters)
