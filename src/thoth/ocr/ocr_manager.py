"""
OCR Manager for Thoth.

This module handles the conversion of PDF files to Markdown using OCR.
"""

from pathlib import Path
from typing import Any

from mistralai import DocumentURLChunk, Mistral
from mistralai.models import OCRResponse, UploadFileOut


class OCRError(Exception):
    """Exception raised for errors in the OCR process."""

    pass


class MistralOCR:
    """
    Manages OCR conversion of PDF files to Markdown.

    This class handles the conversion of PDF files to Markdown using the
    Mistral OCR API.
    """

    def __init__(self, api_key: str):
        """
        Initialize the OCR Manager.

        Args:
            api_key (str): The Mistral API key for OCR.
        """
        self.api_key = api_key
        self.client = Mistral(api_key=self.api_key)

    def convert_pdf_to_markdown(
        self, pdf_path: Path, output_dir: Path | None = None
    ) -> Path:
        """
        Convert a PDF file to Markdown.

        Args:
            pdf_path (Path | str): The path to the PDF file.
            output_dir (Path | None): The directory to save the output Markdown file.

        Returns:
            Path: The path to the output Markdown file.
        """
        uploaded_file = self._upload_file(pdf_path)
        signed_url_obj = self.client.files.get_signed_url(
            file_id=uploaded_file.id, expiry=1
        )
        # Extract the URL string from the signed URL object
        signed_url = signed_url_obj.url
        ocr_response = self._call_ocr_api(signed_url)
        combined_markdown = self._get_combined_markdown(ocr_response)
        output_path = output_dir / f'{pdf_path.stem}.md'
        output_path.write_text(combined_markdown)
        no_images_markdown = self._join_markdown_pages(ocr_response)
        no_images_output_path = output_dir / f'{pdf_path.stem}_no_images.md'
        no_images_output_path.write_text(no_images_markdown)
        return output_path, no_images_output_path

    def _upload_file(self, pdf_path: Path) -> UploadFileOut:
        """
        Upload a PDF file to Mistral.
        """
        uploaded_file = self.client.files.upload(
            file={
                'file_name': pdf_path.stem,
                'content': pdf_path.read_bytes(),
            },
            purpose='ocr',
        )
        return uploaded_file

    def _call_ocr_api(self, signed_url: str) -> dict[str, Any]:
        """
        Call the Mistral OCR API.

        Args:
            signed_url: The signed URL string for the uploaded file

        Returns:
            dict: The OCR response as a dictionary
        """
        response = self.client.ocr.process(
            document=DocumentURLChunk(document_url=signed_url),
            model='mistral-ocr-latest',
            include_image_base64=True,
        )
        # The response is already a dictionary, no need to parse it as JSON
        return response

    def _join_markdown_pages(self, ocr_response: OCRResponse) -> str:
        """
        Join the markdown pages into a single markdown document.
        """
        return '\n\n'.join(page.markdown for page in ocr_response.pages)

    def _get_combined_markdown(self, ocr_response: OCRResponse) -> str:
        """
        Combine OCR text and images into a single markdown document.

        Args:
            ocr_response: Response from OCR processing containing text and images

        Returns:
            Combined markdown string with embedded images
        """
        markdowns: list[str] = []
        # Extract images from page
        for page in ocr_response.pages:
            image_data = {}
            for img in page.images:
                image_data[img.id] = img.image_base64
            # Replace image placeholders with actual images
            markdowns.append(
                self._replace_images_in_markdown(page.markdown, image_data)
            )

        return '\n\n'.join(markdowns)

    def _replace_images_in_markdown(self, markdown_str: str, images_dict: dict) -> str:
        """
        Replace image placeholders in markdown with base64-encoded images.

        Args:
            markdown_str: Markdown text containing image placeholders
            images_dict: Dictionary mapping image IDs to base64 strings

        Returns:
            Markdown text with images replaced by base64 data
        """
        for img_name, base64_str in images_dict.items():
            markdown_str = markdown_str.replace(
                f'![{img_name}]({img_name})', f'![{img_name}]({base64_str})'
            )
        return markdown_str
