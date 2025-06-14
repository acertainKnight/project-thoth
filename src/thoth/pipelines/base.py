from __future__ import annotations

from pathlib import Path

from loguru import logger

from thoth.knowledge.graph import CitationGraph
from thoth.server.pdf_monitor import PDFTracker
from thoth.services.service_manager import ServiceManager


class BasePipeline:
    """Base class for Thoth pipelines providing common attributes."""

    def __init__(
        self,
        services: ServiceManager,
        citation_tracker: CitationGraph,
        pdf_tracker: PDFTracker,
        output_dir: Path,
        notes_dir: Path,
        markdown_dir: Path,
    ) -> None:
        self.services = services
        self.citation_tracker = citation_tracker
        self.pdf_tracker = pdf_tracker
        self.output_dir = Path(output_dir)
        self.notes_dir = Path(notes_dir)
        self.markdown_dir = Path(markdown_dir)
        self.logger = logger.bind(pipeline=self.__class__.__name__)
