"""
Initialization module for Thoth.

This module provides factory functions for initializing Thoth services and pipelines.
It replaces the ThothPipeline wrapper class with a cleaner functional approach.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from thoth.config import Config, config as global_config
from thoth.knowledge.graph import CitationGraph
from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
from thoth.server.pdf_monitor import PDFTracker
from thoth.services.service_manager import ServiceManager


def initialize_thoth(
    config: Config | None = None,
) -> tuple[ServiceManager, OptimizedDocumentPipeline, CitationGraph]:
    """
    Initialize all Thoth services and pipelines.
    
    This factory function performs the complete initialization sequence:
    1. Loads configuration
    2. Creates and initializes ServiceManager
    3. Runs path migration to ensure synced data works correctly
    4. Creates PDFTracker
    5. Creates CitationGraph
    6. Creates OptimizedDocumentPipeline
    
    Args:
        config: Optional configuration object. If None, uses global config.
    
    Returns:
        tuple: (ServiceManager, OptimizedDocumentPipeline, CitationGraph)
    
    Example:
        >>> services, pipeline, graph = initialize_thoth()
        >>> result = pipeline.process_pdf('paper.pdf')
        >>> papers = graph.get_all_papers()
    """
    # Load configuration
    config = config or global_config
    
    # Ensure required directories exist
    output_dir = Path(config.output_dir)
    notes_dir = Path(config.notes_dir)
    markdown_dir = Path(config.markdown_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize service manager
    services = ServiceManager(config=config)
    services.initialize()
    
    # Run automatic path migration on startup
    # This ensures synced data from other machines works correctly
    from thoth.services.path_migration_service import PathMigrationService
    
    migration_service = PathMigrationService(config)
    migration_results = migration_service.migrate_all()
    if migration_results.get('tracker', {}).get('migrated') or migration_results.get(
        'graph', {}
    ).get('migrated'):
        logger.info('Paths migrated to current machine configuration')
    
    # Initialize PDF tracker
    pdf_tracker = PDFTracker()
    
    # Initialize citation graph
    citation_tracker = CitationGraph(
        knowledge_base_dir=config.knowledge_base_dir,
        graph_storage_path=config.graph_storage_path,
        pdf_dir=config.pdf_dir,
        markdown_dir=config.markdown_dir,
        notes_dir=config.notes_dir,
        service_manager=services,  # Pass ServiceManager for note generation
    )
    
    # Set citation tracker in services that need it
    services.set_citation_tracker(citation_tracker)
    
    # Initialize optimized document pipeline for handling PDF processing
    document_pipeline = OptimizedDocumentPipeline(
        services=services,
        citation_tracker=citation_tracker,
        pdf_tracker=pdf_tracker,
        output_dir=output_dir,
        notes_dir=notes_dir,
        markdown_dir=markdown_dir,
    )
    
    logger.info('Thoth initialized successfully with optimized processing')
    
    return services, document_pipeline, citation_tracker
