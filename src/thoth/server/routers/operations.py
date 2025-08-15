"""
Operations and streaming endpoints.
"""

import asyncio
import json
import threading
import time
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

router = APIRouter(tags=["operations"])

# Operation tracking
operation_progress: dict[str, dict[str, Any]] = {}
operation_lock = threading.Lock()

# Track background tasks
background_tasks: set[asyncio.Task[Any]] = set()


class StreamingOperationRequest(BaseModel):
    """Request model for streaming operations."""
    operation_type: str
    parameters: dict[str, Any]
    stream_progress: bool = True


class BatchProcessRequest(BaseModel):
    """Request model for batch processing."""
    items: list[dict[str, Any]]
    operation: str
    parallel: bool = True
    max_workers: int = 5


def update_operation_progress(
    operation_id: str,
    status: str,
    progress: float,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Update the progress of an operation."""
    with operation_lock:
        operation_progress[operation_id] = {
            'status': status,
            'progress': progress,
            'message': message,
            'details': details or {},
            'updated_at': time.time(),
        }


def get_operation_status(operation_id: str) -> dict[str, Any] | None:
    """Get the status of an operation."""
    with operation_lock:
        return operation_progress.get(operation_id)


def create_background_task(coro) -> None:
    """Create and track a background task."""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(lambda t: background_tasks.discard(t))


async def shutdown_background_tasks(timeout: float = 10.0) -> None:
    """Cancel all background tasks and wait for them to complete."""
    if not background_tasks:
        return

    logger.info(f'Cancelling {len(background_tasks)} background tasks...')
    
    # Cancel all tasks
    for task in background_tasks:
        task.cancel()
    
    # Wait for all tasks to complete
    try:
        await asyncio.wait_for(
            asyncio.gather(*background_tasks, return_exceptions=True),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f'Some background tasks did not complete within {timeout}s')


@router.get('/operations/{operation_id}/status')
def get_operation_status_endpoint(operation_id: str):
    """Get the status of a long-running operation."""
    status = get_operation_status(operation_id)
    if status is None:
        raise HTTPException(status_code=404, detail='Operation not found')
    return JSONResponse(status)


@router.post('/stream/operation')
async def stream_operation(request: StreamingOperationRequest):
    """
    Stream the progress of a long-running operation.
    
    This endpoint supports various operation types with real-time progress updates.
    """
    operation_id = f'{request.operation_type}-{int(time.time() * 1000)}'
    
    async def generate() -> AsyncIterator[str]:
        """Generate streaming response."""
        try:
            # Initialize operation
            update_operation_progress(
                operation_id,
                status='started',
                progress=0.0,
                message=f'Starting {request.operation_type} operation',
            )
            
            yield json.dumps({
                'operation_id': operation_id,
                'status': 'started',
                'progress': 0.0,
                'message': f'Starting {request.operation_type} operation',
            }) + '\n'
            
            # Simulate operation progress (replace with actual operation logic)
            steps = 10
            for i in range(1, steps + 1):
                await asyncio.sleep(0.5)  # Simulate work
                
                progress = i / steps
                message = f'Processing step {i} of {steps}'
                
                update_operation_progress(
                    operation_id,
                    status='processing',
                    progress=progress,
                    message=message,
                    details={'current_step': i, 'total_steps': steps},
                )
                
                if request.stream_progress:
                    yield json.dumps({
                        'operation_id': operation_id,
                        'status': 'processing',
                        'progress': progress,
                        'message': message,
                        'details': {'current_step': i, 'total_steps': steps},
                    }) + '\n'
            
            # Complete operation
            update_operation_progress(
                operation_id,
                status='completed',
                progress=1.0,
                message=f'{request.operation_type} operation completed successfully',
            )
            
            yield json.dumps({
                'operation_id': operation_id,
                'status': 'completed',
                'progress': 1.0,
                'message': f'{request.operation_type} operation completed successfully',
            }) + '\n'
            
        except Exception as e:
            logger.error(f'Error in streaming operation: {e}')
            update_operation_progress(
                operation_id,
                status='failed',
                progress=-1,
                message=f'Operation failed: {e!s}',
            )
            
            yield json.dumps({
                'operation_id': operation_id,
                'status': 'failed',
                'error': str(e),
            }) + '\n'
    
    return StreamingResponse(
        generate(),
        media_type='application/x-ndjson',
        headers={
            'X-Operation-ID': operation_id,
            'Cache-Control': 'no-cache',
        },
    )


@router.post('/batch/process')
async def batch_process(request: BatchProcessRequest):
    """
    Process multiple items in batch with progress tracking.
    
    Supports parallel and sequential processing modes.
    """
    operation_id = f'batch-{int(time.time() * 1000)}'
    total_items = len(request.items)
    
    async def process_batch():
        """Process batch in background."""
        try:
            update_operation_progress(
                operation_id,
                status='started',
                progress=0.0,
                message=f'Starting batch processing of {total_items} items',
            )
            
            if request.parallel:
                # Parallel processing
                semaphore = asyncio.Semaphore(request.max_workers)
                
                async def process_item(idx: int, item: dict[str, Any]):
                    async with semaphore:
                        # Simulate processing
                        await asyncio.sleep(0.1)
                        return {'index': idx, 'result': 'processed', 'item': item}
                
                tasks = [
                    process_item(i, item)
                    for i, item in enumerate(request.items)
                ]
                
                results = []
                for i, task in enumerate(asyncio.as_completed(tasks)):
                    result = await task
                    results.append(result)
                    
                    progress = (i + 1) / total_items
                    update_operation_progress(
                        operation_id,
                        status='processing',
                        progress=progress,
                        message=f'Processed {i + 1} of {total_items} items',
                    )
            else:
                # Sequential processing
                results = []
                for i, item in enumerate(request.items):
                    # Simulate processing
                    await asyncio.sleep(0.1)
                    results.append({
                        'index': i,
                        'result': 'processed',
                        'item': item,
                    })
                    
                    progress = (i + 1) / total_items
                    update_operation_progress(
                        operation_id,
                        status='processing',
                        progress=progress,
                        message=f'Processed {i + 1} of {total_items} items',
                    )
            
            # Complete
            update_operation_progress(
                operation_id,
                status='completed',
                progress=1.0,
                message=f'Successfully processed {total_items} items',
                details={'results': results},
            )
            
        except Exception as e:
            logger.error(f'Batch processing failed: {e}')
            update_operation_progress(
                operation_id,
                status='failed',
                progress=-1,
                message=f'Batch processing failed: {e!s}',
            )
    
    # Start background processing
    create_background_task(process_batch())
    
    return JSONResponse({
        'status': 'accepted',
        'operation_id': operation_id,
        'message': f'Batch processing started for {total_items} items',
        'status_url': f'/operations/{operation_id}/status',
    })


async def notify_progress(message: str | dict[str, Any]) -> None:
    """Send progress notification to connected WebSocket clients."""
    # Import here to avoid circular dependency
    from thoth.server.routers.websocket import progress_ws_manager
    
    if progress_ws_manager and progress_ws_manager.active_connections:
        await progress_ws_manager.broadcast(message)