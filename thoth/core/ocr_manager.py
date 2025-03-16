"""
OCR Manager for Thoth.

This module handles the conversion of PDF files to Markdown using OCR.
"""

import logging
from pathlib import Path

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Exception raised for errors in the OCR process."""

    pass


class OCRManager:
    """
    Manages OCR conversion of PDF files to Markdown.

    This class handles the conversion of PDF files to Markdown using the
    Mistral OCR API.
    """

    def __init__(
        self, api_key: str, api_url: str = "https://api.mistral.ai/ocr/v1/process"
    ):
        """
        Initialize the OCR Manager.

        Args:
            api_key (str): The Mistral API key for OCR.
            api_url (str): The URL for the Mistral OCR API.
        """
        self.api_key = api_key
        self.api_url = api_url
        logger.debug("OCR Manager initialized")

    def convert_pdf_to_markdown(
        self, pdf_path: Path, output_dir: Path | None = None
    ) -> Path:
        """
        Convert a PDF file to Markdown using OCR.

        Args:
            pdf_path (Path): The path to the PDF file.
            output_dir (Optional[Path]): The directory to save the Markdown file.
                                        If None, uses the same directory as the PDF.

        Returns:
            Path: The path to the generated Markdown file.

        Raises:
            OCRError: If the OCR process fails.
            FileNotFoundError: If the PDF file does not exist.
        """
        # Validate input
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Determine output path
        if output_dir is None:
            markdown_path = pdf_path.with_suffix(".md")
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown_path = output_dir / f"{pdf_path.stem}.md"

        logger.info(f"Converting PDF to Markdown: {pdf_path} -> {markdown_path}")

        try:
            # Call the OCR API
            with open(pdf_path, "rb") as pdf_file:
                response = self._call_ocr_api(pdf_file)

            # Save the Markdown content
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(response)

            logger.info(f"Successfully converted PDF to Markdown: {markdown_path}")
            return markdown_path

        except RequestException as e:
            error_msg = f"OCR API request failed: {e!s}"
            logger.error(error_msg)
            raise OCRError(error_msg) from e
        except Exception as e:
            error_msg = f"OCR conversion failed: {e!s}"
            logger.error(error_msg)
            raise OCRError(error_msg) from e

    def _call_ocr_api(self, pdf_file) -> str:
        """
        Call the Mistral OCR API to convert a PDF file to Markdown.

        Args:
            pdf_file: The PDF file object to convert.

        Returns:
            str: The Markdown content.

        Raises:
            OCRError: If the API call fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/markdown",
        }

        files = {"file": pdf_file}

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                files=files,
                timeout=300,  # 5-minute timeout for large PDFs
            )

            if response.status_code != 200:
                error_msg = (
                    f"OCR API returned error: {response.status_code} - {response.text}"
                )
                logger.error(error_msg)
                raise OCRError(error_msg)

            return response.text

        except RequestException as e:
            error_msg = f"OCR API request failed: {e!s}"
            logger.error(error_msg)
            raise OCRError(error_msg) from e
