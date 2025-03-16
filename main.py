#!/usr/bin/env python3
"""
Thoth AI Research Agent - Main entry point
"""
import logging
import sys
from pathlib import Path

from thoth.config import load_config
from thoth.core.llm_processor import LLMProcessor
from thoth.core.markdown_processor import MarkdownProcessor
from thoth.core.note_generator import NoteGenerator
from thoth.core.ocr_manager import OCRManager
from thoth.core.pdf_monitor import PDFMonitor
from thoth.linking.manager import LinkManager
from thoth.uri.handler import URIHandler
from thoth.utils.logging import setup_logging


def process_pdf(pdf_path: Path, components):
    """
    Process a PDF file through the Thoth pipeline.

    Args:
        pdf_path: Path to the PDF file to process.
        components: Dictionary of initialized components.

    Returns:
        bool: True if processing was successful, False otherwise.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Processing PDF: {pdf_path}")

    try:
        # Extract components
        ocr_manager = components["ocr_manager"]
        markdown_processor = components["markdown_processor"]
        llm_processor = components["llm_processor"]
        note_generator = components["note_generator"]
        link_manager = components["link_manager"]

        # Convert PDF to Markdown
        markdown_path = ocr_manager.convert_pdf_to_markdown(pdf_path)
        logger.info(f"Converted PDF to Markdown: {markdown_path}")

        # Process Markdown
        content = markdown_processor.process_markdown(markdown_path)
        logger.info(f"Processed Markdown for {pdf_path.name}")

        # Analyze content with LLM
        analysis = llm_processor.analyze_content(content["text"])
        logger.info(f"Analyzed content for {pdf_path.name}")

        # Extract citations
        citations = llm_processor.extract_citations(content["text"])
        logger.info(f"Extracted {len(citations)} citations from {pdf_path.name}")

        # Create note
        note_path = note_generator.create_note(
            {
                "metadata": content["metadata"],
                "analysis": analysis,
                "citations": citations,
                "source_files": {"pdf": pdf_path, "markdown": markdown_path},
            }
        )
        logger.info(f"Created note: {note_path}")

        # Update citation links
        link_manager.update_citation_links(
            {"path": note_path, "metadata": content["metadata"], "citations": citations}
        )
        logger.info(f"Updated citation links for {pdf_path.name}")

        return True

    except Exception as e:
        logger.error(f"Failed to process {pdf_path.name}: {e!s}")
        return False


def main():
    """Main entry point for Thoth."""
    try:
        # Load configuration
        config = load_config()

        # Set up logging
        setup_logging(config.log_level, config.log_file)
        logger = logging.getLogger(__name__)

        # Check for URI handling
        if len(sys.argv) > 1 and sys.argv[1].startswith("thoth://"):
            # Process URI
            uri = sys.argv[1]
            logger.info(f"Processing URI: {uri}")

            uri_handler = URIHandler(config)
            success = uri_handler.process_uri(uri)

            # Exit with appropriate status code
            sys.exit(0 if success else 1)

        logger.info(f"Thoth started. Monitoring {config.pdf_dir} for new PDFs.")

        # Initialize components
        ocr_manager = OCRManager(config.api_keys.mistral)
        markdown_processor = MarkdownProcessor()
        llm_processor = LLMProcessor(config.api_keys.openrouter)
        note_generator = NoteGenerator(config.templates_dir, config.notes_dir)
        link_manager = LinkManager(config.notes_dir)
        pdf_monitor = PDFMonitor(config.pdf_dir)

        # Store components in a dictionary for easy access
        components = {
            "ocr_manager": ocr_manager,
            "markdown_processor": markdown_processor,
            "llm_processor": llm_processor,
            "note_generator": note_generator,
            "link_manager": link_manager,
            "pdf_monitor": pdf_monitor,
        }

        # Register callback for new PDFs
        pdf_monitor.on_new_pdf(lambda pdf_path: process_pdf(pdf_path, components))

        # Process existing PDFs
        logger.info("Processing existing PDFs...")
        pdf_monitor.process_existing_pdfs()
        logger.info("Finished processing existing PDFs.")

        try:
            # Start monitoring
            pdf_monitor.start()
            logger.info(f"Now monitoring {config.pdf_dir} for new PDFs.")

            # Keep the main thread running
            while True:
                import time

                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping Thoth...")
            pdf_monitor.stop()
            logger.info("Thoth stopped.")
    except Exception as e:
        print(f"Error initializing Thoth: {e!s}")
        sys.exit(1)


if __name__ == "__main__":
    main()
