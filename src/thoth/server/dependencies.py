"""
FastAPI dependency injection functions for Thoth server.

This module provides dependency injection for services and components,
replacing module-level globals with thread-safe request-scoped dependencies.
"""

from typing import Optional

from fastapi import HTTPException, Request

from thoth.services.service_manager import ServiceManager


def get_service_manager(request: Request) -> ServiceManager:
    """
    Get ServiceManager from application state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        ServiceManager instance
        
    Raises:
        HTTPException: If ServiceManager not initialized
    """
    service_manager = getattr(request.app.state, 'service_manager', None)
    if service_manager is None:
        raise HTTPException(
            status_code=503,
            detail="ServiceManager not initialized. Server may still be starting up."
        )
    return service_manager


def get_research_agent(request: Request):
    """
    Get research agent from application state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Research agent instance or None
        
    Note:
        Returns None if research agent not initialized (not an error)
    """
    return getattr(request.app.state, 'research_agent', None)


def get_chat_manager(request: Request):
    """
    Get chat manager from application state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Chat manager instance or None
        
    Note:
        Returns None if chat manager not initialized (not an error)
    """
    return getattr(request.app.state, 'chat_manager', None)


def get_workflow_execution_service(request: Request):
    """
    Get workflow execution service from application state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        WorkflowExecutionService instance or None
        
    Note:
        Returns None if workflow service not initialized (not an error)
    """
    return getattr(request.app.state, 'workflow_execution_service', None)


def get_postgres_service(request: Request):
    """
    Get PostgreSQL service from ServiceManager.
    
    Args:
        request: FastAPI request object
        
    Returns:
        PostgreSQL service instance or None
        
    Raises:
        HTTPException: If ServiceManager not initialized
    """
    service_manager = get_service_manager(request)
    return service_manager.postgres if hasattr(service_manager, 'postgres') else None
